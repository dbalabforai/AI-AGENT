import streamlit as st

from agent_core import (
    cancel_commit,
    commit_reviewed_changes,
    execute_command,
    prepare_commit,
    review_working_tree,
)

st.set_page_config(
    page_title="AI Developer Assistant",
    layout="wide"
)

st.title("🤖 AI Developer Assistant")

if "command" not in st.session_state:
    st.session_state.command = ""
if "last_output" not in st.session_state:
    st.session_state.last_output = ""
if "last_command" not in st.session_state:
    st.session_state.last_command = ""
if "reviewed_changes" not in st.session_state:
    st.session_state.reviewed_changes = []
if "suggested_commit_message" not in st.session_state:
    st.session_state.suggested_commit_message = ""
if "pending_commit" not in st.session_state:
    st.session_state.pending_commit = None


def set_command(command):
    st.session_state.command = command


with st.sidebar:
    st.header("Quick Actions")

    st.subheader("Filesystem")
    st.button("📁 List Files", on_click=set_command, args=("list files",))
    st.button("📄 Read README", on_click=set_command, args=("read README.md",))

    st.subheader("Git")
    git_actions = (
        ("Git Status", "git status"),
        ("Git Log", "git log"),
        ("Git Branch", "git branch"),
        ("Git Diff", "git diff"),
        ("Git Diff Full", "git diff full"),
        ("Git Remote", "git remote"),
        ("Git Last Commit", "git last commit"),
        ("Review Changes", "review changes"),
        ("Commit Changes", "commit changes"),
    )
    for label, command_value in git_actions:
        st.button(
            label,
            key=f"action_{command_value.replace(' ', '_')}",
            on_click=set_command,
            args=(command_value,),
        )

    st.subheader("GitHub")
    github_actions = (
        ("Repo Info", "github repo info"),
        ("Read README", "github readme"),
        ("List Repository Files", "github list files"),
        ("Latest Commits", "github latest commits"),
        ("Review GitHub Changes", "github review changes"),
    )
    for label, command_value in github_actions:
        st.button(
            label,
            key=f"action_{command_value.replace(' ', '_')}",
            on_click=set_command,
            args=(command_value,),
        )

command = st.text_input(
    "Enter command",
    key="command",
    placeholder="git status",
)

if st.button("Run"):
    normalized_command = " ".join(command.strip().lower().split())
    st.session_state.last_command = command

    if normalized_command == "review changes":
        review = review_working_tree()
        if "error" in review:
            st.session_state.reviewed_changes = []
            st.session_state.suggested_commit_message = ""
            st.session_state.last_output = review["error"]
        else:
            st.session_state.reviewed_changes = review["changes"]
            st.session_state.suggested_commit_message = review["message"]
            st.session_state.last_output = review["text"]
    elif normalized_command == "commit changes":
        prepared = prepare_commit(
            st.session_state.reviewed_changes,
            st.session_state.suggested_commit_message,
        )
        if "error" in prepared:
            st.session_state.last_output = prepared["error"]
        else:
            st.session_state.pending_commit = prepared
            st.session_state.last_output = prepared["preview"]
    else:
        st.session_state.last_output = execute_command(command)

if st.session_state.pending_commit:
    st.warning("This will create a local Git commit. Confirm only if the preview is correct.")
    st.code(st.session_state.pending_commit["preview"])
    confirm_column, cancel_column = st.columns(2)
    with confirm_column:
        if st.button("Confirm Commit", type="primary"):
            result = commit_reviewed_changes(st.session_state.pending_commit)
            st.session_state.last_output = result
            if not result.startswith("Error:"):
                st.session_state.pending_commit = None
                st.session_state.reviewed_changes = []
                st.session_state.suggested_commit_message = ""
    with cancel_column:
        if st.button("Cancel Commit"):
            result = cancel_commit(st.session_state.pending_commit["paths"])
            st.session_state.last_output = f"Commit cancelled.\n{result}"
            if not result.startswith("Error:"):
                st.session_state.pending_commit = None

if st.session_state.last_output:
    st.markdown("### Command")
    st.code(st.session_state.last_command)
    st.markdown("### Response")
    st.code(st.session_state.last_output)
