import asyncio
import json
import os
import sys
import traceback
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ollama import chat

# --------------------------------------------------
# Configuration
# --------------------------------------------------

MEMORY_FILE = "memory.json"
MAX_MESSAGES = 100
reviewed_changes = []
review_summary = ""
pending_commit = None

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

# --------------------------------------------------
# Git MCP Client
# --------------------------------------------------

async def _call_git_mcp_tool(tool_name, arguments):
    server_path = Path(__file__).with_name(
        "git_mcp_server.py"
    ).resolve()

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
    )

    async with stdio_client(params) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

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


def call_git_mcp_tool(tool_name, arguments=None):

    if arguments is None:
        arguments = {}

    try:
        return asyncio.run(
            _call_git_mcp_tool(
                tool_name,
                arguments,
            )
        )
    except Exception as error:
        details = "".join(
            traceback.format_exception(error)
        ).strip()
        return f"Error: Git MCP:\n{details}"


def git_status():
    return call_git_mcp_tool(
        "git_status"
    )


def git_log():
    return call_git_mcp_tool(
        "git_log"
    )


def git_branch():
    return call_git_mcp_tool(
        "git_branch"
    )
    

def summarize_git_changes(changes, diff_summary):
    counts = {
        "added": 0,
        "modified": 0,
        "deleted": 0,
        "renamed": 0,
        "other": 0,
    }
    for change in changes:
        code = change["code"]
        if code == "??" or "A" in code:
            counts["added"] += 1
        elif "D" in code:
            counts["deleted"] += 1
        elif "R" in code or "C" in code:
            counts["renamed"] += 1
        elif "M" in code:
            counts["modified"] += 1
        else:
            counts["other"] += 1

    details = [
        f"{count} {label}"
        for label, count in counts.items()
        if count
    ]
    summary = f"{len(changes)} changed files: {', '.join(details)}."
    if diff_summary and diff_summary != "(no tracked changes)":
        summary += f"\nTracked diff:\n{diff_summary}"

    path_names = " ".join(
        path.lower()
        for change in changes
        for path in (change["path"], change.get("original_path"))
        if path
    )
    if "github" in path_names and "git" in path_names:
        commit_message = "Add GitHub support and improve Git tools"
    elif "github" in path_names:
        commit_message = "Update GitHub integration"
    elif "git" in path_names:
        commit_message = "Update Git tools"
    elif counts["added"] and not counts["modified"] and not counts["deleted"]:
        commit_message = "Add project files"
    elif counts["deleted"] and not counts["added"] and not counts["modified"]:
        commit_message = "Remove project files"
    else:
        commit_message = "Update project files"
    return summary, commit_message


def changed_paths(changes):
    paths = []
    for change in changes:
        for path in (change["path"], change.get("original_path")):
            if path and path not in paths:
                paths.append(path)
    return paths


def format_changed_files(changes):
    groups = {
        "Added": [],
        "Modified": [],
        "Deleted": [],
        "Renamed": [],
        "Other": [],
    }
    for change in changes:
        code = change["code"]
        path = change["path"]
        if code == "??" or "A" in code:
            groups["Added"].append(path)
        elif "D" in code:
            groups["Deleted"].append(path)
        elif "R" in code or "C" in code:
            original = change.get("original_path")
            groups["Renamed"].append(f"{original} -> {path}")
        elif "M" in code:
            groups["Modified"].append(path)
        else:
            groups["Other"].append(f"{code} {path}")

    return "\n".join(
        f"{label}:\n" + "\n".join(f"- {path}" for path in paths)
        for label, paths in groups.items()
        if paths
    )


def review_working_tree():
    global reviewed_changes, review_summary

    result = call_git_mcp_tool("git_changed_files")
    if result.startswith("Error:"):
        return result
    try:
        changes = json.loads(result)
    except json.JSONDecodeError as error:
        return f"Error: Could not read changed paths from Git MCP: {error}"

    if not changes:
        reviewed_changes = []
        review_summary = ""
        return "No changes to review."

    diff = call_git_mcp_tool("git_diff")
    if diff.startswith("Error:"):
        return diff

    summary, commit_message = summarize_git_changes(changes, diff)

    reviewed_changes = changes
    review_summary = summary
    return (
        "Changes detected:\n"
        f"{format_changed_files(changes)}\n\n"
        f"Summary:\n{summary}\n\n"
        f'Suggested commit message:\n"{commit_message}"\n\n'
        "Use 'commit changes' to stage only these reviewed paths and preview them."
    )


def review_github_changes():
    review = review_working_tree()
    if review.startswith("Error:"):
        return review

    sync_status = call_git_mcp_tool("git_sync_status")
    if sync_status.startswith("Error:"):
        return sync_status
    try:
        status = json.loads(sync_status)
    except json.JSONDecodeError as error:
        return f"Error: Could not read Git upstream status: {error}"

    branch = status.get("branch")
    upstream = status.get("upstream")
    ahead = status.get("ahead")
    behind = status.get("behind")
    if not isinstance(ahead, int) or not isinstance(behind, int):
        return "Error: Git upstream status returned invalid commit counts."

    if not upstream:
        remote_guidance = (
            "No upstream branch is configured, so I cannot determine whether "
            "local commits need pushing. After committing, configure an upstream "
            "and push manually, for example: git push -u origin "
            f"{branch or '<branch>'}."
        )
    elif behind:
        remote_guidance = (
            f"Your branch is {behind} commit(s) behind {upstream}. Fetch and "
            "reconcile with the remote before pushing."
        )
        if ahead:
            remote_guidance += f" It is also {ahead} commit(s) ahead."
    elif ahead:
        upstream_parts = upstream.split("/", 1)
        push_command = (
            f"git push {upstream_parts[0]} {upstream_parts[1]}"
            if len(upstream_parts) == 2
            else "git push"
        )
        remote_guidance = (
            f"Your branch has {ahead} local commit(s) not on {upstream}. "
            f"When ready, publish them manually with `{push_command}`."
        )
    elif review == "No changes to review.":
        remote_guidance = (
            f"No uncommitted changes or known local commits to push to "
            f"{upstream} (based on the last fetch)."
        )
    else:
        remote_guidance = (
            f"No local commits are currently ahead of {upstream} (based on the "
            "last fetch). To commit these changes, use `commit changes`; after "
            "the commit, run `github review changes` again for the push command."
        )

    return f"{review}\n\nRemote status:\n{remote_guidance}"


def prepare_commit():
    global pending_commit

    if not reviewed_changes:
        return "Run 'review changes' first; there are no approved paths to stage."

    paths = changed_paths(reviewed_changes)
    staged_summary = call_git_mcp_tool(
        "git_stage_paths",
        {"paths": paths},
    )
    if staged_summary.startswith("Error:"):
        rollback = call_git_mcp_tool(
            "git_unstage_paths",
            {"paths": paths},
        )
        return f"{staged_summary}\nStaging rollback: {rollback}"
    if staged_summary == "(no changes were staged)":
        return "No changes were staged. Run 'review changes' again."

    summary, commit_message = summarize_git_changes(
        reviewed_changes,
        staged_summary,
    )
    staged_fingerprint = call_git_mcp_tool("git_staged_fingerprint")
    if staged_fingerprint.startswith("Error:"):
        rollback = call_git_mcp_tool(
            "git_unstage_paths",
            {"paths": paths},
        )
        return f"{staged_fingerprint}\nStaging rollback: {rollback}"

    pending_commit = {
        "paths": paths,
        "message": commit_message,
        "fingerprint": staged_fingerprint,
    }
    return (
        "Commit preview:\n"
        f"Files staged:\n{format_changed_files(reviewed_changes)}\n\n"
        f"{staged_summary}\n\n"
        f"Summary:\n{summary}\n\n"
        f'Suggested commit:\n"{commit_message}"\n\n'
        "Confirm commit? Reply yes or no."
    )


async def _call_github_mcp_tool(tool_name, arguments):
    server_path = Path(__file__).with_name(
        "github_mcp_server.py"
    ).resolve()
    server_env = {}
    if os.environ.get("GITHUB_TOKEN"):
        server_env["GITHUB_TOKEN"] = os.environ["GITHUB_TOKEN"]

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env=server_env,
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            text = "\n".join(
                item.text
                for item in result.content
                if hasattr(item, "text")
            )
            if result.isError:
                return f"Error: {text}"
            return text


def call_github_mcp_tool(tool_name):
    try:
        return asyncio.run(
            _call_github_mcp_tool(tool_name, {})
        )
    except Exception as error:
        details = "".join(
            traceback.format_exception(error)
        ).strip()
        return f"Error: GitHub MCP:\n{details}"


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

HELP_TEXT = """
AI Agent Started

Help:
  help
  list tools
  show tools

Filesystem:
  list files
  search <text>

  read <file>
  write <file>: <content>

  analyze <file>
  summarize <file>
  extract_tasks <file>

Git:
  git status
  git log
  git branch
  git diff
  git diff full
  git remote
  git last commit
  review changes
  commit changes

GitHub (dbalabforai/AI-AGENT):
  github repo info
  github readme
  github list files
  github latest commits
  github review changes

Change publishing workflow:
  1. Run 'review changes' to see modified, added, and deleted files.
  2. Run 'commit changes' and reply 'yes' to create a local commit.
  3. Run 'github review changes' to check whether local commits need pushing.
  4. Run the displayed 'git push ...' command in a separate terminal.

The agent does not execute raw 'git add', 'git commit', or 'git push'
commands typed as chat. For manual Git commands, use a separate terminal.

Type 'exit' to quit.
"""

print(HELP_TEXT)

# --------------------------------------------------
# Main Loop
# --------------------------------------------------

while True:

    try:
        user_input = input("You: ").strip()
    except EOFError:
        if pending_commit is not None:
            rollback = call_git_mcp_tool(
                "git_unstage_paths",
                {"paths": pending_commit["paths"]},
            )
            print(f"\nAgent:\nInput closed; commit cancelled.\n{rollback}\n")
        break

    if pending_commit is not None:
        if user_input.lower() == "yes":
            result = call_git_mcp_tool(
                "git_commit",
                {
                    "message": pending_commit["message"],
                    "paths": pending_commit["paths"],
                    "expected_diff_hash": pending_commit["fingerprint"],
                },
            )
            print(f"\nAgent:\n{result}\n")
            if not result.startswith("Error:"):
                pending_commit = None
                reviewed_changes = []
        elif user_input.lower() == "no":
            result = call_git_mcp_tool(
                "git_unstage_paths",
                {"paths": pending_commit["paths"]},
            )
            print(f"\nAgent:\nCommit cancelled.\n{result}\n")
            if not result.startswith("Error:"):
                pending_commit = None
                reviewed_changes = []
        elif user_input.lower() == "exit":
            result = call_git_mcp_tool(
                "git_unstage_paths",
                {"paths": pending_commit["paths"]},
            )
            print(f"\nAgent:\nCommit cancelled.\n{result}\n")
            if not result.startswith("Error:"):
                pending_commit = None
                reviewed_changes = []
                break
        else:
            print("\nAgent:\nPlease reply yes or no to the commit preview.\n")
        continue

    if user_input.lower() == "exit":
        break

    normalized_input = " ".join(user_input.lower().split())
    parts = user_input.split(maxsplit=2)

    if normalized_input in {"help", "show tools", "list tools"}:
        print(f"\n{HELP_TEXT}")
        continue

    if normalized_input == "review changes":
        print(f"\nAgent:\n{review_working_tree()}\n")
        continue

    if normalized_input == "commit changes":
        print(f"\nAgent:\n{prepare_commit()}\n")
        continue

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
    # Git Commands
    # --------------------------------------------------

    if user_input.lower() == "git status":

        print("\nAgent:")
        print(git_status())
        print()

        continue

    if user_input.lower() == "git log":

        print("\nAgent:")
        print(git_log())
        print()

        continue

    if user_input.lower() == "git branch":

        print("\nAgent:")
        print(git_branch())
        print()

        continue

    git_commands = {
        "git remote": "git_remote",
        "git last commit": "git_last_commit",
    }
    if normalized_input == "git diff":
        print("\nAgent:")
        print(call_git_mcp_tool("git_diff"))
        print()
        continue

    if normalized_input == "git diff full":
        print("\nAgent:")
        print(call_git_mcp_tool("git_diff", {"full": True}))
        print()
        continue

    git_tool = git_commands.get(normalized_input)
    if git_tool:
        print("\nAgent:")
        print(call_git_mcp_tool(git_tool))
        print()
        continue

    manual_git_commands = ("git add", "git commit", "git push")
    if any(
        normalized_input == command
        or normalized_input.startswith(f"{command} ")
        for command in manual_git_commands
    ):
        print(
            "\nAgent:\n"
            "This raw Git command was not executed. Run it in a separate "
            "terminal, or use the agent workflow: 'review changes' then "
            "'commit changes' and confirm with 'yes'. For push status and "
            "the correct push command, run 'github review changes'.\n"
        )
        continue

    # --------------------------------------------------
    # GitHub Commands
    # --------------------------------------------------

    if normalized_input == "github review changes":
        print("\nAgent:")
        print(review_github_changes())
        print()
        continue

    github_commands = {
        "github repo info": "github_repo_info",
        "github_repo_info": "github_repo_info",
        "github readme": "github_readme",
        "github_readme": "github_readme",
        "github list files": "github_list_files",
        "github_list_files": "github_list_files",
        "github latest commits": "github_latest_commits",
        "github_latest_commits": "github_latest_commits",
    }
    github_tool = github_commands.get(normalized_input)
    if github_tool:
        print("\nAgent:")
        print(call_github_mcp_tool(github_tool))
        print()
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