"""
Streamlit UI Helpers.
---------------------
LLM Query Transport - Helper functions for the Streamlit frontend

Provides session state management, message display, CSV download,
and chat management utilities.
"""

import base64

import pandas as pd
import streamlit as st


def initialize_session_states() -> None:
    """Initialize the session states for the Streamlit app."""
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
        st.session_state["sql_query_results"] = []
    if "reset_counter" not in st.session_state:
        st.session_state["reset_counter"] = 0
    if "sql_query_results" not in st.session_state:
        st.session_state["sql_query_results"] = []


def manage_messages(
    role: str,
    content: str,
    message_type: str | None = None,
    csv_data: tuple | None = None,
    timestamp: str | None = None,
) -> None:
    """Add a message to the chat history."""
    message_data: dict = {"role": role, "content": content}
    if message_type:
        message_data["type"] = message_type
    if csv_data:
        message_data["csv_data"] = csv_data
    if timestamp:
        message_data["timestamp"] = timestamp
    st.session_state.setdefault("chat_history", []).append(message_data)


def render_chat_message(message: dict) -> None:
    """Render a single chat message with optional CSV download."""
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message.get("csv_data"):
            rows, columns = message["csv_data"]
            if rows and columns and len(rows) > 0 and len(columns) > 0:
                timestamp = message.get("timestamp", "")
                csv_filename = f"{message.get('csv_prefix', 'query_results')}_{timestamp}.csv"
                df = pd.DataFrame(data=rows, columns=columns)
                csv = df.to_csv(index=False)
                b64_csv = base64.b64encode(csv.encode()).decode()
                href = f'<a href="data:file/csv;base64,{b64_csv}" download="{csv_filename}">Download CSV File</a>'
                st.markdown(href, unsafe_allow_html=True)


def download_data_csv() -> None:
    """Create a download button for the latest SQL query result as CSV."""
    results = st.session_state.get("sql_query_results")
    if results and len(results) >= 2 and len(results[0]) > 0 and len(results[1]) > 0:
        rows, columns = results
        df = pd.DataFrame(data=rows, columns=columns)
        csv = df.to_csv(index=False)
        b64_csv = base64.b64encode(csv.encode()).decode()
        href = f'<a href="data:file/csv;base64,{b64_csv}" download="query_results.csv">Download CSV File</a>'
        st.markdown(href, unsafe_allow_html=True)
    else:
        st.write("No data available to download.")


def clear_chat_and_restart() -> None:
    """Clear the chat history and restart the app."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["reset_counter"] = 0
    st.session_state["chat_history"] = []
    st.rerun()
