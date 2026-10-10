import asyncio
import hashlib
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

server = FastMCP("git-tools")

ROOT_DIR = Path(__file__).resolve().parent
ERROR_PREFIX = "Error:"
STATUS_PORCELAIN_V1 = "--porcelain=v1"


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

    output = stdout.decode("utf-8", errors="replace").rstrip("\r\n")
    if process.returncode != 0:
        error = stderr.decode("utf-8", errors="replace").strip()
        return f"Error: {error or f'git exited with code {process.returncode}'}"

    return output


def _parse_changed_files(status_output: str) -> list[dict[str, str]]:
    records = status_output.split("\0")
    changed_files = []
    index = 0

    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < 4:
            continue

        code = record[:2]
        path = record[3:]
        change = {
            "code": code,
            "path": path,
        }
        if ("R" in code or "C" in code) and index < len(records):
            change["original_path"] = records[index]
            index += 1
        changed_files.append(change)

    return changed_files


def _validate_paths(paths: list[str]) -> str | None:
    if not paths:
        return "Error: no changed file paths were provided."

    for path in paths:
        candidate = Path(path)
        if (
            not path
            or candidate.is_absolute()
            or (len(path) > 1 and path[1] == ":")
            or ".." in Path(path.replace("\\", "/")).parts
        ):
            return f"Error: invalid repository-relative path: {path!r}"
    return None


def _literal_pathspec(path: str) -> str:
    return f":(literal){path.replace(chr(92), '/')}"


async def _staged_paths() -> list[str] | None:
    output = await run_git_command(
        ["diff", "--cached", "--name-only", "--no-renames", "-z"]
    )
    if output.startswith(ERROR_PREFIX):
        return None
    return [path for path in output.split("\0") if path]


@server.tool()
async def git_status() -> str:
    """Show a concise list of changed, added, deleted, and untracked files."""

    output = await run_git_command(
        ["status", STATUS_PORCELAIN_V1, "-z"]
    )
    if output.startswith(ERROR_PREFIX):
        return output

    changes = _parse_changed_files(output)
    if not changes:
        return "No changes."

    sections: dict[str, list[str]] = {
        "Modified": [],
        "Added": [],
        "Deleted": [],
        "Renamed": [],
        "Untracked": [],
        "Other changes": [],
    }
    for change in changes:
        code = change["code"]
        path = change["path"]

        if code == "??":
            sections["Untracked"].append(path)
        elif "R" in code or "C" in code:
            original_path = change.get("original_path")
            label = "Renamed"
            sections[label].append(
                f"{original_path} -> {path}"
                if original_path
                else path
            )
        elif "D" in code:
            sections["Deleted"].append(path)
        elif "A" in code:
            sections["Added"].append(path)
        elif "M" in code:
            sections["Modified"].append(path)
        else:
            sections["Other changes"].append(f"{code} {path}")

    return "\n\n".join(
        f"{section}:\n" + "\n".join(f"- {path}" for path in paths)
        for section, paths in sections.items()
        if paths
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


@server.tool()
async def git_diff(full: bool = False) -> str:
    """Show a compact tracked-change summary, or the full patch when requested."""

    if full:
        args = ["diff", "HEAD", "--"]
    else:
        args = ["diff", "--stat", "HEAD", "--"]

    output = await run_git_command(args)
    if output.startswith(ERROR_PREFIX):
        return output
    return output or "(no tracked changes)"


@server.tool()
async def git_changed_files() -> str:
    """Return changed repository paths and status codes as JSON."""

    output = await run_git_command(
        ["status", STATUS_PORCELAIN_V1, "-z"]
    )
    if output.startswith(ERROR_PREFIX):
        return output
    return json.dumps(_parse_changed_files(output), ensure_ascii=True)


@server.tool()
async def git_stage_paths(paths: list[str]) -> str:
    """Stage only the provided changed paths; refuse to stage over existing index changes."""

    validation_error = _validate_paths(paths)
    if validation_error:
        return validation_error

    status_output = await run_git_command(
        ["status", STATUS_PORCELAIN_V1, "-z"]
    )
    if status_output.startswith(ERROR_PREFIX):
        return status_output

    changed_files = _parse_changed_files(status_output)
    if any(
        change["code"] != "??" and change["code"][0] != " "
        for change in changed_files
    ):
        return (
            "Error: there are already staged changes. Commit or unstage them "
            "before starting the approved-path commit workflow."
        )

    available_paths = {
        path
        for change in changed_files
        for path in (change["path"], change.get("original_path"))
        if path
    }
    if not set(paths).issubset(available_paths):
        return "Error: one or more paths are no longer changed. Run 'review changes' again."

    result = await run_git_command(
        ["add", "-A", "--", *(_literal_pathspec(path) for path in paths)]
    )
    if result.startswith(ERROR_PREFIX):
        return result

    staged = await run_git_command(
        ["diff", "--cached", "--stat"]
    )
    if staged.startswith(ERROR_PREFIX):
        return staged
    return staged or "(no changes were staged)"


@server.tool()
async def git_unstage_paths(paths: list[str]) -> str:
    """Unstage only the approved paths, refusing if other paths are staged."""

    validation_error = _validate_paths(paths)
    if validation_error:
        return validation_error

    staged_paths = await _staged_paths()
    if staged_paths is None:
        return "Error: could not inspect staged paths."
    if not set(staged_paths).issubset(paths):
        return "Error: unrelated paths are staged; refusing to change the index."
    if not staged_paths:
        return "(no staged changes to undo)"

    result = await run_git_command(
        ["restore", "--staged", "--", *(_literal_pathspec(path) for path in paths)]
    )
    if result.startswith(ERROR_PREFIX):
        return result
    return "Approved changes were unstaged; working files were left unchanged."


@server.tool()
async def git_staged_fingerprint() -> str:
    """Return a SHA-256 fingerprint for the current staged patch."""

    staged_diff = await run_git_command(
        [
            "diff",
            "--cached",
            "--binary",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            "--",
        ]
    )
    if staged_diff.startswith(ERROR_PREFIX):
        return staged_diff
    return hashlib.sha256(staged_diff.encode("utf-8")).hexdigest()


@server.tool()
async def git_commit(
    message: str,
    paths: list[str],
    expected_diff_hash: str,
) -> str:
    """Commit staged changes only when every staged path was explicitly approved."""

    validation_error = _validate_paths(paths)
    if validation_error:
        return validation_error
    if not message.strip():
        return "Error: commit message cannot be empty."
    if not expected_diff_hash:
        return "Error: staged patch fingerprint is required."

    staged_paths = await _staged_paths()
    if staged_paths is None:
        return "Error: could not inspect staged paths."
    if not staged_paths:
        return "Error: there are no staged changes to commit."
    if not set(staged_paths).issubset(paths):
        return "Error: staged changes include paths outside the approved review."

    current_diff_hash = await git_staged_fingerprint()
    if current_diff_hash.startswith(ERROR_PREFIX):
        return current_diff_hash
    if current_diff_hash != expected_diff_hash:
        return "Error: staged changes differ from the approved preview; review them again."

    return await run_git_command(
        ["commit", "-m", message.strip()]
    )


@server.tool()
async def git_remote() -> str:
    """Show configured Git remotes and their fetch and push URLs."""

    output = await run_git_command(
        [
            "remote",
            "-v",
        ]
    )
    return output or "(no Git remotes configured)"


@server.tool()
async def git_last_commit() -> str:
    """Show details for the latest commit."""

    return await run_git_command(
        [
            "log",
            "-1",
            "--format=Commit: %H%nAuthor: %an <%ae>%nDate: %aI%nSubject: %s%n%n%b",
        ]
    )


@server.tool()
async def git_sync_status() -> str:
    """Return the current branch's upstream and known ahead/behind counts as JSON."""

    output = await run_git_command(
        ["status", "--porcelain=v2", "--branch"]
    )
    if output.startswith(ERROR_PREFIX):
        return output

    status = {
        "branch": None,
        "upstream": None,
        "ahead": 0,
        "behind": 0,
    }
    for line in output.splitlines():
        if line.startswith("# branch.head "):
            status["branch"] = line.removeprefix("# branch.head ")
        elif line.startswith("# branch.upstream "):
            status["upstream"] = line.removeprefix("# branch.upstream ")
        elif line.startswith("# branch.ab "):
            counts = line.removeprefix("# branch.ab ").split()
            if len(counts) != 2 or not counts[0].startswith("+") or not counts[1].startswith("-"):
                return "Error: could not parse Git upstream status."
            try:
                status["ahead"] = int(counts[0][1:])
                status["behind"] = int(counts[1][1:])
            except ValueError:
                return "Error: could not parse Git upstream commit counts."

    return json.dumps(status, ensure_ascii=True)


if __name__ == "__main__":
    server.run(transport="stdio")