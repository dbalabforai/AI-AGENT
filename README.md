# AI Agent

A local command-line AI assistant for everyday project work. It combines Ollama chat with MCP tools for working with files, Git, and GitHub.

> **Runs locally:** the chat model runs through Ollama on your machine. There is no hosted web app at this time.

## What you can do

- Ask the assistant questions and keep conversation history locally.
- List, search, read, and write project files.
- Analyze documents, summarize them, or extract action items.
- Inspect Git status, history, branches, and diffs.
- Review changes and prepare a commit preview before confirming a commit.
- Fetch repository details, the README, file list, and recent commits from GitHub.

## Get started

### 1. Install prerequisites

- Python 3.10 or newer
- [Ollama](https://ollama.com/) installed and running
- Git installed and available on `PATH`

### 2. Download dependencies and the model

From the repository directory, install the Python packages:

```powershell
py -m pip install mcp ollama
```

Download the model used by the agent:

```powershell
ollama pull llama3.1
```

Make sure Ollama is running before starting the agent.

### 3. Start the agent

```powershell
py agent.py
```

The command prompt displays the available commands. For example:

```text
help
list tools
list files
search project
read notes.txt
summarize meeting.txt
git status
github repo info
github review changes
review changes
exit
```

Enter `help`, `list tools`, or `show tools` at any time to redisplay the full command menu.

## Agent tools and MCP servers

The agent is a Python CLI client. It launches the MCP servers as local subprocesses and calls their tools when you enter a matching command.

**MCP** (Model Context Protocol) is a standard way for an AI application to call tools provided by separate servers. In this project, each server exposes a focused set of capabilities:

| Server | What it provides |
| --- | --- |
| `mcp_server.py` (`local-files`) | Lists and searches project files, and reads or writes supported files. It excludes Python files and `memory.json`. |
| `git_mcp_server.py` (`git-tools`) | Reports repository state and history, shows diffs, and stages or commits reviewed changes. |
| `github_mcp_server.py` (`github-tools`) | Reads GitHub repository metadata, README content, the default-branch file list, and recent commits. |

The local file and Git servers operate on the repository containing the project. GitHub tools are configured for `dbalabforai/AI-AGENT`.

## Commands

### Files

| Command | Description |
| --- | --- |
| `list files` | List supported files in the project directory. |
| `search <text>` | Find text in supported project files. |
| `read <file>` | Display a file's contents. |
| `write <file>: <content>` | Write text to a project file. |
| `analyze <file>` | Identify purpose, key facts, dates, and open items. |
| `summarize <file>` | Summarize a document in concise bullets. |
| `extract_tasks <file>` | Extract action items from a document. |

### Git

| Command | Description |
| --- | --- |
| `git status`, `git log`, `git branch` | Inspect repository state, recent commits, or the current branch. |
| `git diff`, `git diff full` | View a compact change summary or full patch. |
| `review changes` | Summarize working-tree changes and suggest a commit message. |
| `commit changes` | Stage only the paths from the latest review and show a commit preview. Confirm with `yes` or cancel with `no`. This creates a local commit, not a push. |

### GitHub

| Command | Description |
| --- | --- |
| `github repo info` | Show basic repository metadata. |
| `github readme` | Read the repository README. |
| `github list files` | List files on the default branch. |
| `github latest commits` | Show recent commits on the default branch. |
| `github review changes` | Review local changes, suggest how to commit them, and report whether local commits are ahead of the configured remote. It does not commit, fetch, or push. |

GitHub's public repository data can be read without a token. To authenticate API requests or access data requiring authentication, set `GITHUB_TOKEN` in the environment before launching the agent. Do not put the token in source code or commit it.

The remote status uses the local tracking information from the last `git fetch`; it does not contact GitHub or update remote-tracking branches. If changes need committing, use `review changes`, then `commit changes` and confirm with `yes`. The commit is local only. Run `github review changes` again afterward to see whether the branch is ahead and get the appropriate manual push command (for example, `git push origin main`). Nothing is pushed automatically.

### Add, commit, and push workflow

Use the agent's review and commit commands for the safest path:

1. Run `review changes` to inspect the changed files and suggested commit message.
2. Run `commit changes` to stage only those reviewed files and preview the commit.
3. Reply `yes` to create the local commit, or `no` to cancel.
4. Run `github review changes` to check whether local commits are ahead of the remote.
5. If it displays a push command, run that command in a separate terminal opened in the repository (for example, `git push origin main`).

If you prefer manual Git commands, run them in a separate terminal, not at the agent's chat prompt:

```powershell
git status
git add README.md agent.py
git commit -m "Describe the change"
git push origin main
```

Replace the example file names and commit message with the files and change you intend to publish. Use `git add .` only when you intend to stage every changed and untracked file. The agent does not execute raw `git add`, `git commit`, or `git push` commands entered as chat; it will say so rather than claiming the command succeeded.

## Project files

- `agent.py` — interactive CLI and MCP client
- `mcp_server.py` — local file tools
- `git_mcp_server.py` — Git tools
- `github_mcp_server.py` — GitHub tools
- `test_mcp.py`, `test_git_mcp.py`, `test_github_mcp.py` — MCP server tool-listing smoke checks
- `memory.json` — locally saved chat history; generated or updated when chatting

## Safety notes

- File tools are restricted to the project directory; they cannot access `memory.json` or `.py` files.
- Git staging and commit operations are limited to reviewed, changed paths and require confirmation before committing.
- Conversation history is stored locally in `memory.json`.

## Current scope

This project currently provides a local CLI, not a public website or hosted service. Anyone who wants to use it needs to install the prerequisites and run it on their own machine.
