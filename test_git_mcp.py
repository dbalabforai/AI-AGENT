import asyncio
import sys
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).with_name("git_mcp_server.py")


async def call_and_print(session, tool_name, arguments):
    print(f"Calling {tool_name}...", flush=True)

    result = await session.call_tool(tool_name, arguments)

    text = "\n".join(
        item.text
        for item in result.content
        if hasattr(item, "text")
    )

    if result.isError:
        raise RuntimeError(f"{tool_name} failed: {text}")

    print(text or "(no text result)")
    print()


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER.resolve())],
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(
            read_stream,
            write_stream,
            read_timeout_seconds=timedelta(seconds=40),
        ) as session:
            await session.initialize()
            print("\n=== Git MCP Test ===\n", flush=True)

            await call_and_print(session, "git_branch", {})
            await call_and_print(session, "git_status", {})
            await call_and_print(session, "git_log", {"limit": 5})


def run():
    try:
        asyncio.run(main())
    except TimeoutError as error:
        raise SystemExit("Timed out waiting for the Git MCP server.") from error


if __name__ == "__main__":
    run()