from pathlib import Path

from mcp.server.fastmcp import FastMCP

server = FastMCP("local-files")
ROOT_DIR = Path(__file__).resolve().parent


@server.tool()
def read_file(path: str) -> str:
    """Read a UTF-8 text file inside the AI-AGENT folder."""
    target = (ROOT_DIR / path).resolve()

    try:
        target.relative_to(ROOT_DIR)
    except ValueError:
        return "Error: File must be inside the project folder."

    if not target.is_file():
        return "Error: File not found."

    if target.name.lower() == "memory.json":
        return "Error: Access to agent memory is blocked."

    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return f"Error reading file: {error}"


@server.tool()
def list_files() -> list[str]:
    """List files in the project folder, excluding agent memory."""
    return sorted(
        path.name
        for path in ROOT_DIR.iterdir()
        if path.is_file() and path.name.lower() != "memory.json"
    )


@server.tool()
def search_files(query: str) -> list[str]:
    """Search project text files for a phrase, excluding agent memory."""
    matches = []

    for path in ROOT_DIR.iterdir():
        if (
            not path.is_file()
            or path.name.lower() == "memory.json"
            or path.stat().st_size > 1_000_000
        ):
            continue

        try:
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if query.casefold() in line.casefold():
                    matches.append(f"{path.name}:{line_number}: {line.strip()}")
        except (OSError, UnicodeError):
            continue

    return matches


if __name__ == "__main__":
    server.run(transport="stdio")