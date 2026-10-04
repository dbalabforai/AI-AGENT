import asyncio
import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from mcp.server.fastmcp import FastMCP

OWNER = "dbalabforai"
REPOSITORY = "AI-AGENT"
API_BASE = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 20

server = FastMCP("github-tools")


class GitHubAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _request_json(endpoint: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-AGENT-GitHub-MCP",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(f"{API_BASE}{endpoint}", headers=headers)
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except HTTPError as error:
        try:
            details = json.load(error)
        except (json.JSONDecodeError, UnicodeDecodeError):
            details = {}
        message = details.get("message", error.reason)
        raise GitHubAPIError(
            f"GitHub API returned HTTP {error.code}: {message}",
            status_code=error.code,
        ) from error
    except URLError as error:
        raise GitHubAPIError(
            f"Could not reach the GitHub API: {error.reason}"
        ) from error


async def _get_json(endpoint: str):
    return await asyncio.to_thread(_request_json, endpoint)


def _repository_endpoint(suffix: str = "") -> str:
    owner = quote(OWNER, safe="")
    repository = quote(REPOSITORY, safe="")
    return f"/repos/{owner}/{repository}{suffix}"


@server.tool()
async def github_repo_info() -> str:
    """Show basic information about the configured GitHub repository."""

    data = await _get_json(_repository_endpoint())
    fields = (
        "full_name",
        "description",
        "private",
        "html_url",
        "default_branch",
        "language",
        "stargazers_count",
        "forks_count",
        "open_issues_count",
        "created_at",
        "updated_at",
    )
    return json.dumps(
        {field: data[field] for field in fields},
        indent=2,
        ensure_ascii=False,
    )


@server.tool()
async def github_readme() -> str:
    """Read the README from the configured GitHub repository."""

    try:
        data = await _get_json(_repository_endpoint("/readme"))
    except GitHubAPIError as error:
        if error.status_code == 404:
            return f"README not found in {OWNER}/{REPOSITORY}."
        raise

    if data.get("encoding") != "base64" or "content" not in data:
        raise GitHubAPIError("GitHub returned README content in an unsupported format.")

    content = base64.b64decode(data["content"]).decode("utf-8")
    return content.rstrip()


@server.tool()
async def github_list_files() -> str:
    """List all files in the configured repository's default-branch tree."""

    repository = await _get_json(_repository_endpoint())
    branch = quote(repository["default_branch"], safe="")
    tree = await _get_json(
        _repository_endpoint(f"/git/trees/{branch}?recursive=1")
    )
    paths = [
        item["path"]
        for item in tree["tree"]
        if item["type"] == "blob"
    ]
    result = "\n".join(paths) if paths else "(repository contains no files)"
    if tree.get("truncated"):
        result += "\nWarning: GitHub truncated this recursive tree response."
    return result


@server.tool()
async def github_latest_commits() -> str:
    """Show the ten latest commits on the configured repository's default branch."""

    commits = await _get_json(
        _repository_endpoint("/commits?per_page=10")
    )
    return "\n".join(
        f"{commit['sha'][:7]} {commit['commit']['author']['date']} "
        f"{commit['commit']['message'].splitlines()[0]}"
        for commit in commits
    )


if __name__ == "__main__":
    server.run(transport="stdio")
