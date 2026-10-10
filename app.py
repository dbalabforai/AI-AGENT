import streamlit as st

from agent_core import execute_command

st.set_page_config(
    page_title="AI Developer Assistant",
    layout="wide"
)

st.title("🤖 AI Developer Assistant")

# ----------------------------------
# Sidebar
# ----------------------------------

with st.sidebar:

    st.header("Quick Actions")

    st.subheader("Filesystem")

    if st.button("📁 List Files"):
        st.session_state.command = "list files"

    if st.button("📄 Read Notes"):
        st.session_state.command = "read notes.txt"

    st.subheader("Git")

    if st.button("🌿 Git Branch"):
        st.session_state.command = "git branch"

    if st.button("📊 Git Status"):
        st.session_state.command = "git status"

    st.subheader("GitHub")

    if st.button("🐙 Repo Info"):
        st.session_state.command = "github repo info"

# ----------------------------------
# Main Input
# ----------------------------------

if "command" not in st.session_state:
    st.session_state.command = ""

command = st.text_input(
    "Enter command",
    value=st.session_state.command,
    placeholder="git status"
)

if st.button("Run"):

    result = execute_command(command)

    st.markdown("### Command")
    st.code(command)

    st.markdown("### Response")
    st.text_area(
        "Command output",
        result,
        height=300,
        label_visibility="collapsed"
    )