# AI Agent

A lightweight local AI assistant that combines an Ollama chat loop with Model Context Protocol (MCP) tools for working with project files, Git repositories, and GitHub metadata.

## Overview

This project provides an interactive command-line agent that can:

- read, write, list, and search project files
- summarize or analyze non-Python files
- inspect repository status and recent Git history
- review working-tree changes and preview staged commits
- query GitHub repository metadata and README content
- retain short-term conversation memory in `memory.json`

The entry point is `agent.py`, which wires together the local file MCP server, the Git MCP server, and the GitHub MCP server.

## Repository structure

- `agent.py` — interactive AI agent CLI
- `mcp_server.py` — local filesystem utilities exposed through MCP
- `git_mcp_server.py` — Git status, diff, staging, and commit support
- `github_mcp_server.py` — GitHub repository metadata and README access
- `test_mcp.py` — local MCP server smoke tests
- `test_git_mcp.py` — Git MCP tests
- `test_github_mcp.py` — GitHub MCP tests
- `memory.json` — saved assistant memory and conversation state
- `notes.txt`, `meeting.txt` — example project files used by the agent

## Requirements

- Python 3.10+
- Ollama installed and running
- An Ollama model available locally, such as `llama3.1`

Install the Python dependencies:

```bash
pip install mcp ollama
```

Pull the model used by the agent:

```bash
ollama pull llama3.1
```

Optional for GitHub access:

```bash
export GITHUB_TOKEN="your_github_token"
```

## Quick start

Run the agent:

```bash
python agent.py
```

Then use commands like:

```text
list files
search notes
read notes.txt
analyze meeting.txt
git status
git log
github repo info
review changes
commit changes
exit
```

## Features

### Local file tools

The MCP server allows the agent to safely work with non-Python project files inside the repository root.

Supported operations include:

- `list files`
- `search <text>`
- `read <file>`
- `write <file>: <content>`
- `analyze <file>`
- `summarize <file>`
- `extract_tasks <file>`

Python files are intentionally excluded from these file-system tools.

### Git workflow

The Git MCP layer exposes commands such as:

- `git status`
- `git log`
- `git branch`
- `git diff`
- `git diff full`
- `review changes`
- `commit changes`

The review flow checks working-tree changes, summarizes them, and prepares a staged commit preview before confirmation.

### GitHub integration

The GitHub MCP server is configured for the repository:

- `dbalabforai/AI-AGENT`

It can read:

- repository metadata
- README content
- file list from the default branch
- latest commit summaries

## Safety and constraints

- File access is restricted to the project directory.
- Access to `memory.json` is blocked from the local file MCP tool.
- Git paths are validated before staging to prevent unsafe repository-relative path manipulation.
- GitHub metadata calls require network access and optionally a personal access token via `GITHUB_TOKEN`.

## Notes

This project is designed as a local, educational, and automation-oriented assistant. It is intentionally compact and does not aim to replace a full production chat platform or agent framework.

## License

This project does not currently declare a license file. If you intend to distribute or reuse it publicly, add an explicit license before publication.
