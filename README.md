# AI Developer Assistant

A local Streamlit app that provides filesystem, Git, and GitHub tools through
three local MCP (Model Context Protocol) servers. It runs on your computer;
it is not a hosted service.

## Features

- Browse and read project files.
- Check Git status, branches, history, and diffs.
- Review working-tree changes and create a local commit after confirmation.
- Read public GitHub repository information, files, and recent commits.

## Requirements

- Python 3.10 or newer
- Git installed and available as a terminal command
- Internet access for GitHub actions

Ollama is not required. The MCP servers are launched automatically by the app
as local subprocesses.

## Quick start

### 1. Install prerequisites

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/)
and Git from [git-scm.com](https://git-scm.com/downloads).

In **Windows PowerShell**, verify the installations:

1. py --version
2. git --version

### 2A. Clone, install, and run — Windows

In **Windows PowerShell**, run each command in order:

1. git clone https://github.com/dbalabforai/AI-AGENT.git
2. cd AI-AGENT
3. py -3 -m venv .venv
4. .\.venv\Scripts\Activate.ps1
5. python -m pip install --upgrade pip
6. python -m pip install -r requirements.txt
7. streamlit run app.py

### 2B. Clone, install, and run — macOS or Linux

In your **macOS or Linux terminal** (such as Terminal), run each command in
order:

1. git clone https://github.com/dbalabforai/AI-AGENT.git
2. cd AI-AGENT
3. python3 -m venv .venv
4. source .venv/bin/activate
5. python -m pip install --upgrade pip
6. python -m pip install -r requirements.txt
7. streamlit run app.py

Streamlit starts a local server and opens the app in your browser. Keep the
terminal open while using the app; press **Ctrl+C** there to stop it.

### 3. Start the app again later

Open a terminal in the project folder and activate its environment before
starting Streamlit. Do not clone the repository again.

**Windows PowerShell:**

1. .\.venv\Scripts\Activate.ps1
2. streamlit run app.py

**macOS or Linux terminal:**

1. source .venv/bin/activate
2. streamlit run app.py

### If PowerShell blocks environment activation

Use the virtual environment's Python directly from the project folder. These
commands install the dependencies and start the app without activation:

1. .\.venv\Scripts\python.exe -m pip install -r requirements.txt
2. .\.venv\Scripts\python.exe -m streamlit run app.py

### Optional: GitHub authentication

The GitHub tools can read public repository data without a token. For
authenticated requests, set GITHUB_TOKEN before starting the app.

In **Windows PowerShell**, from the project folder:

1. $env:GITHUB_TOKEN = "your-token"
2. streamlit run app.py

Keep your token private. Do not add it to source files or commit it.

## Commands in the app

| Area | Command | What it does |
| --- | --- | --- |
| Files | list files | List supported files in the project folder. |
| Files | read filename | Read a supported file, such as README.md. |
| Git | git status | Show changed, added, and deleted files. |
| Git | git log | Show recent commits. |
| Git | git branch | Show the current branch. |
| Git | git diff | Show a summary of tracked changes. |
| Git | git diff full | Show the full tracked-change diff. |
| Git | git remote | Show configured Git remotes. |
| Git | git last commit | Show the latest commit. |
| Git | review changes | Review changed paths and prepare a suggested commit message. |
| Git | commit changes | Stage reviewed paths and display a commit preview. |
| GitHub | github repo info | Show metadata for dbalabforai/AI-AGENT. |
| GitHub | github readme | Read that repository's README. |
| GitHub | github list files | List files on its default branch. |
| GitHub | github latest commits | Show recent commits on its default branch. |
| GitHub | github review changes | Review local changes and report local push guidance. |

To commit, enter review changes, then commit changes, inspect the preview,
and select **Confirm Commit**. This creates a local commit only; it does not
push to GitHub. Select **Cancel Commit** to cancel.

## MCP servers

MCP lets an application call tools exposed by separate servers. This app
starts the following local servers automatically:

| File | Server | Capabilities |
| --- | --- | --- |
| mcp_server.py | local-files | Lists, searches, reads, and writes supported project files. |
| git_mcp_server.py | git-tools | Inspects Git and stages or commits reviewed changes. |
| github_mcp_server.py | github-tools | Reads repository metadata and content from GitHub. |

The filesystem server is restricted to this project folder and excludes
Python files and memory.json from its file tools. The GitHub server is
currently configured for dbalabforai/AI-AGENT.

## Project files

- app.py — Streamlit user interface.
- agent_core.py — Connects the interface to MCP servers and routes commands.
- mcp_server.py — Local filesystem MCP server.
- git_mcp_server.py — Git MCP server.
- github_mcp_server.py — GitHub MCP server.
- test_mcp.py, test_git_mcp.py, test_github_mcp.py — MCP server smoke checks.
- requirements.txt — Python dependencies.
