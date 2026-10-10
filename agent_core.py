import os
import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# --------------------------------------------------
# Git MCP
# --------------------------------------------------

async def _call_git_mcp(tool_name):

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
                {}
            )

            text = "\n".join(
                item.text
                for item in result.content
                if hasattr(item, "text")
            )

            return text


def call_git_mcp(tool_name):

    return asyncio.run(
        _call_git_mcp(tool_name)
    )

# --------------------------------------------------
# Filesystem MCP
# --------------------------------------------------

async def _call_filesystem_mcp(tool_name, arguments):

    server_path = Path(__file__).with_name(
        "mcp_server.py"
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

            return text


def call_filesystem_mcp(
    tool_name,
    arguments=None
):

    if arguments is None:
        arguments = {}

    return asyncio.run(
        _call_filesystem_mcp(
            tool_name,
            arguments
        )
    )

# --------------------------------------------------
# Shared Backend
# --------------------------------------------------

def execute_command(command):

    command = command.strip().lower()

    # ------------------------------------------
    # Health Check
    # ------------------------------------------

    if command == "ping":
        return "Agent backend is working."

    # ------------------------------------------
    # Git MCP
    # ------------------------------------------

    if command == "git branch":
        return call_git_mcp(
            "git_branch"
        )

    if command == "git status":
        return call_git_mcp(
            "git_status"
        )

    # --------------------------------------------------
    # GitHub MCP
    # --------------------------------------------------

    async def _call_github_mcp(tool_name):

        server_path = Path(__file__).with_name(
            "github_mcp_server.py"
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
                    {}
                )

                text = "\n".join(
                    item.text
                    for item in result.content
                    if hasattr(item, "text")
                )

                return text


    def call_github_mcp(tool_name):

        return asyncio.run(
            _call_github_mcp(tool_name)
        )

    # ------------------------------------------
    # Local File Listing
    # (Filesystem MCP comes next)
    # ------------------------------------------

    if command.lower() == "list files":
        return call_filesystem_mcp(
            "list_files"
    )

    if command == "github repo info":
        return call_github_mcp(
            "github_repo_info"
        )
    
    if command.startswith("read "):
        filename = command[5:].strip()
        return call_filesystem_mcp(
            "read_file",
            {
                "path": filename
            }
        )
    
    # ------------------------------------------
    # Unknown Command
    # ------------------------------------------

    return (
        f"Command not implemented: "
        f"{command}"
    )