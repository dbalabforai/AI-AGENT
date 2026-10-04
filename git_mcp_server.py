import asyncio
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

server = FastMCP("git-tools")

ROOT_DIR = Path(__file__).resolve().parent


async def run_git_command(args: list[str]) -> str:
    command = ["git", *args]
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=ROOT_DIR,
        env=environment,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return f"Error: git {' '.join(args)} timed out after 30 seconds."

    output = stdout.decode("utf-8", errors="replace").strip()
    if process.returncode != 0:
        error = stderr.decode("utf-8", errors="replace").strip()
        return f"Error: {error or f'git exited with code {process.returncode}'}"

    return output


@server.tool()
async def git_status() -> str:
    """Show git repository status."""

    return await run_git_command(
        ["status"]
    )


@server.tool()
async def git_log(limit: int = 10) -> str:
    """Show recent git commits."""

    if limit < 1:
        return "Error: limit must be at least 1."

    return await run_git_command(
        [
            "log",
            f"-{limit}",
            "--oneline",
        ]
    )


@server.tool()
async def git_branch() -> str:
    """Show current git branch."""

    return await run_git_command(
        [
            "branch",
            "--show-current",
        ]
    )


if __name__ == "__main__":
    server.run(transport="stdio")