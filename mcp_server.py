from pathlib import Path

from mcp.server.fastmcp import FastMCP

server = FastMCP("local-files")
ROOT_DIR = Path(__file__).resolve().parent
MEMORY_FILE = "memory.json"


def get_project_file(path: str) -> Path:
    target = (ROOT_DIR / path).resolve()

    try:
        target.relative_to(ROOT_DIR)
    except ValueError:
        raise ValueError("File must be inside the project folder.")

    if target.name.lower() == MEMORY_FILE:
        raise ValueError("Access to agent memory is blocked.")

    if target.suffix.lower() == ".py":
        raise ValueError("Python files are excluded from MCP file tools.")

    return target


@server.tool()
def read_file(path: str) -> str:
    """Read a non-Python UTF-8 file inside the project folder."""
    try:
        target = get_project_file(path)
        if not target.is_file():
            return "Error: File not found."
        return target.read_text(encoding="utf-8")
    except (ValueError, OSError, UnicodeError) as error:
        return f"Error: {error}"


@server.tool()
def write_file(path: str, content: str) -> str:
    """Write a non-Python UTF-8 file inside the project folder."""
    try:
        target = get_project_file(path)
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote {path}"
    except (ValueError, OSError) as error:
        return f"Error: {error}"


@server.tool()
def list_files() -> list[str]:
    """List non-Python project files, excluding agent memory."""
    return sorted(
        path.name
        for path in ROOT_DIR.iterdir()
        if path.is_file()
        and path.name.lower() != MEMORY_FILE
        and path.suffix.lower() != ".py"
    )


@server.tool()
def search_files(query: str) -> list[str]:
    """Search non-Python project files, excluding agent memory."""
    if not query.strip():
        return []

    matches = []

    for path in ROOT_DIR.iterdir():
        if (
            not path.is_file()
            or path.name.lower() == MEMORY_FILE
            or path.suffix.lower() == ".py"
        ):
            continue

        try:
            if path.stat().st_size > 1_000_000:
                continue

            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if query.casefold() in line.casefold():
                    matches.append(
                        f"{path.name}:{line_number}: {line.strip()}"
                    )
        except (OSError, UnicodeError):
            continue

    return matches


if __name__ == "__main__":
    server.run(transport="stdio")