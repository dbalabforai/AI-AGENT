import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ollama import chat

# --------------------------------------------------
# Configuration
# --------------------------------------------------

MEMORY_FILE = "memory.json"
MAX_MESSAGES = 100

SYSTEM_PROMPT = {
    "role": "system",
    "content": """
You are a concise AI assistant.

Rules:
- Give short answers.
- Default to under 20 words.
- Remember user facts.
- Do not explain unless asked.
- Do not make assumptions.
- Do not ask unnecessary follow-up questions.
"""
}

# --------------------------------------------------
# Load Memory
# --------------------------------------------------

if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        messages = json.load(f)

    if not messages or messages[0]["role"] != "system":
        messages.insert(0, SYSTEM_PROMPT)
else:
    messages = [SYSTEM_PROMPT]

# --------------------------------------------------
# MCP Client
# --------------------------------------------------

async def _call_mcp_tool(tool_name, arguments):
    server_path = Path(__file__).with_name("mcp_server.py").resolve()

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:

            await session.initialize()

            result = await session.call_tool(
                tool_name,
                arguments
            )

            text = "\n".join(
                item.text
                for item in result.content
                if hasattr(item, "text")
            )

            if result.isError:
                return f"Error: {text}"

            return text


def call_mcp_tool(tool_name, arguments):
    try:
        return asyncio.run(
            _call_mcp_tool(tool_name, arguments)
        )
    except Exception as error:
        return f"Error: MCP server: {error}"

# --------------------------------------------------
# MCP Tool Wrappers
# --------------------------------------------------

def read_file(filename):
    return call_mcp_tool(
        "read_file",
        {"path": filename}
    )


def write_project_file(filename, content):
    return call_mcp_tool(
        "write_file",
        {
            "path": filename,
            "content": content,
        }
    )


def list_project_files():
    return call_mcp_tool(
        "list_files",
        {}
    )


def search_project_files(query):
    return call_mcp_tool(
        "search_files",
        {"query": query}
    )

# --------------------------------------------------
# File Processing
# --------------------------------------------------

def process_file(action, filename):

    content = read_file(filename)

    if not content:
        return "File is empty."

    if content.startswith("Error"):
        return content

    if action == "read":
        return content

    action_prompts = {

        "analyze": """
Analyze the document.

Return:
- Purpose
- Key Facts
- Important Dates
- Open Items

Use ONLY information from the document.
""",

        "summarize": """
Summarize the document in 3-5 concise bullet points.

Use ONLY information from the document.
""",

        "extract_tasks": """
Extract action items only.

Return a bullet list.

Use ONLY information from the document.
"""
    }

    prompt = action_prompts.get(
        action,
        "Process the document."
    )

    response = chat(
        model="llama3.1",
        messages=[
            {
                "role": "system",
                "content": """
You are processing a file.

The complete file contents have already been provided.

Rules:
- Never say the file is missing.
- Never ask for the file.
- Never ask for more information.
- Use ONLY the provided file content.
- Do not invent facts.
- Do not make recommendations.
- Be concise.
"""
            },
            {
                "role": "user",
                "content": f"""
TASK:

{prompt}

FILE CONTENT:

{content}
"""
            }
        ]
    )

    return response["message"]["content"]

# --------------------------------------------------
# Commands
# --------------------------------------------------

TOOLS = {
    "read",
    "analyze",
    "summarize",
    "extract_tasks"
}

print("""
AI Agent Started

Commands:
  list_files
  search <text>

  read <file>
  write <file>: <content>

  analyze <file>
  summarize <file>
  extract_tasks <file>

Type 'exit' to quit.
""")

# --------------------------------------------------
# Main Loop
# --------------------------------------------------

while True:

    user_input = input("You: ").strip()

    if user_input.lower() == "exit":
        break

    normalized_input = " ".join(user_input.lower().split())
    parts = user_input.split(maxsplit=2)

    # --------------------------------------------------
    # list_files
    # --------------------------------------------------

    if normalized_input in {
        "list_files",
        "list files",
        "show files",
        "show file",
        "list file",
    }:
        print("\nAgent:")
        print(list_project_files())
        print()
        continue

    # --------------------------------------------------
    # search
    # --------------------------------------------------

    if len(parts) == 2 and parts[0].lower() == "search":

        print("\nAgent:")
        print(search_project_files(parts[1]))
        print()

        continue

    # --------------------------------------------------
    # write
    # --------------------------------------------------

    if user_input.lower().startswith("write "):

        try:

            command = user_input[6:].strip()

            filename, content = command.split(":", 1)

            result = write_project_file(
                filename.strip(),
                content.strip()
            )

            print("\nAgent:")
            print(result)
            print()

        except ValueError:

            print(
                "\nAgent:\n"
                "Usage:\n"
                "write filename.txt: your content\n"
            )

        continue

    # --------------------------------------------------
    # file tools
    # --------------------------------------------------

    if len(parts) == 2 and parts[0].lower() in TOOLS:

        result = process_file(
            parts[0].lower(),
            parts[1]
        )

        print(f"\nAgent:\n{result}\n")

        continue

    # --------------------------------------------------
    # read <file>, read_files <file>, or read file <file>
    # --------------------------------------------------

    if parts and parts[0].lower() in {"read", "read_file", "read_files"}:
        if (
            parts[0].lower() == "read"
            and len(parts) == 3
            and parts[1].lower() in {"file", "files"}
        ):
            filename = parts[2]
        elif len(parts) >= 2:
            filename = user_input.split(maxsplit=1)[1]
        else:
            filename = ""

        if filename:
            result = process_file("read", filename)
            print(f"\nAgent:\n{result}\n")
        else:
            print("\nAgent:\nUsage: read <file>\n")

        continue

    # --------------------------------------------------
    # Normal Chat
    # --------------------------------------------------

    messages.append({
        "role": "user",
        "content": user_input
    })

    response = chat(
        model="llama3.1",
        messages=messages
    )

    assistant_message = response["message"]["content"]

    print(f"\nAgent: {assistant_message}\n")

    messages.append({
        "role": "assistant",
        "content": assistant_message
    })

    if len(messages) > MAX_MESSAGES:
        messages = [
            messages[0]
        ] + messages[-(MAX_MESSAGES - 1):]

    with open(
        MEMORY_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            messages,
            f,
            indent=2
        )