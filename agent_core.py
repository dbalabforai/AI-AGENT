import os
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ERROR_PREFIX = "Error:"


# --------------------------------------------------
# Git MCP
# --------------------------------------------------

async def _call_git_mcp(tool_name, arguments):

    server_path = Path(__file__).with_name(
        "git_mcp_server.py"
    ).resolve()

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
    )

    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):

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
            return f"{ERROR_PREFIX} {text}"

        return text


def call_git_mcp(tool_name, arguments=None):

    return asyncio.run(
        _call_git_mcp(
            tool_name,
            arguments or {},
        )
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

    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):

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


async def _call_github_mcp(tool_name, arguments):
    server_path = Path(__file__).with_name(
        "github_mcp_server.py"
    ).resolve()
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env={
            "GITHUB_TOKEN": os.environ["GITHUB_TOKEN"]
        } if os.environ.get("GITHUB_TOKEN") else None,
    )

    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        result = await session.call_tool(tool_name, arguments)
        text = "\n".join(
            item.text
            for item in result.content
            if hasattr(item, "text")
        )
        if result.isError:
            return f"{ERROR_PREFIX} {text}"
        return text


def call_github_mcp(tool_name, arguments=None):
    return asyncio.run(
        _call_github_mcp(tool_name, arguments or {})
    )


# --------------------------------------------------
# Shared Backend
# --------------------------------------------------

def _format_changed_files(changes):
    sections = {
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
            sections["Added"].append(path)
        elif "D" in code:
            sections["Deleted"].append(path)
        elif "R" in code or "C" in code:
            sections["Renamed"].append(
                f"{change.get('original_path', '?')} -> {path}"
            )
        elif "M" in code:
            sections["Modified"].append(path)
        else:
            sections["Other"].append(f"{code} {path}")

    return "\n".join(
        f"{name}:\n" + "\n".join(f"- {path}" for path in paths)
        for name, paths in sections.items()
        if paths
    )


def _suggest_commit_message(changes):
    counts = {"added": 0, "modified": 0, "deleted": 0}
    for change in changes:
        code = change["code"]
        if code == "??" or "A" in code:
            counts["added"] += 1
        elif "D" in code:
            counts["deleted"] += 1
        elif "M" in code:
            counts["modified"] += 1

    paths = " ".join(
        path.lower()
        for change in changes
        for path in (change["path"], change.get("original_path"))
        if path
    )
    if "github" in paths and "git" in paths:
        return "Add GitHub support and improve Git tools"
    if "github" in paths:
        return "Update GitHub integration"
    if "git" in paths:
        return "Update Git tools"
    if counts["added"] and not counts["modified"] and not counts["deleted"]:
        return "Add project files"
    if counts["deleted"] and not counts["added"] and not counts["modified"]:
        return "Remove project files"
    return "Update project files"


def review_working_tree():
    raw_changes = call_git_mcp("git_changed_files")
    if raw_changes.startswith(ERROR_PREFIX):
        return {"error": raw_changes}

    try:
        changes = json.loads(raw_changes)
    except ValueError as error:
        return {"error": f"{ERROR_PREFIX} Could not parse changed files: {error}"}

    if not changes:
        return {
            "changes": [],
            "message": "",
            "text": "No changes to review.",
        }

    diff_summary = call_git_mcp("git_diff")
    if diff_summary.startswith(ERROR_PREFIX):
        return {"error": diff_summary}

    message = _suggest_commit_message(changes)
    text = (
        "Changes detected:\n"
        f"{_format_changed_files(changes)}\n\n"
        f"Tracked diff:\n{diff_summary}\n\n"
        f'Suggested commit message:\n"{message}"\n\n'
        "Use 'commit changes' to prepare a commit preview."
    )
    return {
        "changes": changes,
        "message": message,
        "text": text,
    }


def prepare_commit(changes, message):
    if not changes:
        return {"error": "Run 'review changes' first; there are no approved paths to stage."}

    paths = []
    for change in changes:
        for path in (change["path"], change.get("original_path")):
            if path and path not in paths:
                paths.append(path)

    staged_summary = call_git_mcp(
        "git_stage_paths",
        {"paths": paths},
    )
    if staged_summary.startswith(ERROR_PREFIX):
        return {"error": staged_summary}
    if staged_summary == "(no changes were staged)":
        return {"error": "No changes were staged. Run 'review changes' again."}

    fingerprint = call_git_mcp("git_staged_fingerprint")
    if fingerprint.startswith(ERROR_PREFIX):
        rollback = call_git_mcp("git_unstage_paths", {"paths": paths})
        return {"error": f"{fingerprint}\nStaging rollback: {rollback}"}

    return {
        "paths": paths,
        "message": message,
        "fingerprint": fingerprint,
        "preview": (
            "Commit preview:\n"
            f"{_format_changed_files(changes)}\n\n"
            f"{staged_summary}\n\n"
            f'Suggested commit:\n"{message}"\n\n'
            "Confirm below to create this local commit."
        ),
    }


def cancel_commit(paths):
    return call_git_mcp("git_unstage_paths", {"paths": paths})


def commit_reviewed_changes(pending_commit):
    return call_git_mcp(
        "git_commit",
        {
            "message": pending_commit["message"],
            "paths": pending_commit["paths"],
            "expected_diff_hash": pending_commit["fingerprint"],
        },
    )


def _review_github_changes():
    review = review_working_tree()
    if "error" in review:
        return review["error"]

    sync_output = call_git_mcp("git_sync_status")
    if sync_output.startswith(ERROR_PREFIX):
        return sync_output
    try:
        status = json.loads(sync_output)
    except ValueError as error:
        return f"{ERROR_PREFIX} Could not read Git upstream status: {error}"

    upstream = status.get("upstream")
    ahead = status.get("ahead")
    behind = status.get("behind")
    branch = status.get("branch")
    if not isinstance(ahead, int) or not isinstance(behind, int):
        return f"{ERROR_PREFIX} Git upstream status returned invalid commit counts."
    if not upstream:
        guidance = (
            "No upstream branch is configured. Configure one and push manually, "
            f"for example: git push -u origin {branch or '<branch>'}."
        )
    elif behind:
        guidance = f"Your branch is {behind} commit(s) behind {upstream}; fetch and reconcile before pushing."
        if ahead:
            guidance += f" It is also {ahead} commit(s) ahead."
    elif ahead:
        remote, separator, branch_name = upstream.partition("/")
        push_command = f"git push {remote} {branch_name}" if separator else "git push"
        guidance = (
            f"Your branch has {ahead} local commit(s) not on {upstream}. "
            f"When ready, publish them manually with `{push_command}`."
        )
    elif not review["changes"]:
        guidance = f"No uncommitted changes or known local commits to push to {upstream}."
    else:
        guidance = (
            f"No local commits are currently ahead of {upstream}. Commit reviewed "
            "changes, then run 'github review changes' again for push guidance."
        )

    return f"{review['text']}\n\nRemote status:\n{guidance}"


def execute_command(command):

    command = " ".join(command.strip().lower().split())

    # ------------------------------------------
    # Health Check
    # ------------------------------------------

    if command == "ping":
        return "Agent backend is working."

    # ------------------------------------------
    # Git MCP
    # ------------------------------------------

    git_commands = {
        "git branch": ("git_branch", {}),
        "git status": ("git_status", {}),
        "git log": ("git_log", {}),
        "git diff": ("git_diff", {}),
        "git diff full": ("git_diff", {"full": True}),
        "git remote": ("git_remote", {}),
        "git last commit": ("git_last_commit", {}),
    }
    if command in git_commands:
        tool_name, arguments = git_commands[command]
        return call_git_mcp(tool_name, arguments)

    github_commands = {
        "github repo info": "github_repo_info",
        "github readme": "github_readme",
        "github list files": "github_list_files",
        "github latest commits": "github_latest_commits",
    }
    if command in github_commands:
        return call_github_mcp(github_commands[command])

    if command == "github review changes":
        return _review_github_changes()

    if command == "review changes":
        review = review_working_tree()
        return review.get("text") or review.get("error", "Unable to review changes.")

    if command == "commit changes":
        return (
            "Run 'review changes' first, then use the commit preview and "
            "confirmation controls in the Streamlit interface."
        )

    # ------------------------------------------
    # Local File Listing
    # (Filesystem MCP comes next)
    # ------------------------------------------

    if command == "list files":
        return call_filesystem_mcp(
            "list_files"
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