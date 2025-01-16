#!##########################################
#!############# IMPORTS ####################
#!##########################################

# Standard Libraries
import json
import re
import os
import base64
import traceback
import requests
from datetime import datetime, timedelta, date, timezone
from decimal import Decimal
from typing import List, Tuple, Any, Dict
import importlib


# Local Imports
from src.load_config import LoadConfig
from src.logs import logger

# External Libraries
import streamlit as st
import pandas as pd
from pyprojroot import here
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from langchain_community.utilities import SQLDatabase

APPCFG = LoadConfig()

#!##########################################
#!########### SUB-FUNCTIONS ################
#!##########################################


def _connect_to_sqlite_db(db_path: str) -> Tuple[Engine, SQLDatabase]:
    """Connect to a local SQLite database."""
    try:
        # SQLite URI format: sqlite:///path_to_your_database.db
        SQLITE_URI = f"sqlite:///{db_path}"
        engine = create_engine(SQLITE_URI)
        db = SQLDatabase(engine)  # Optional: Only if using LangChain
        return engine, db
    except Exception as e:
        print(f"Error connecting to the SQLite database: {e}")
        return None, None


def test_query(engine: Engine):
    """Test a simple query to check database access."""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT COUNT(*) FROM station;"))
            response = result.fetchall()
            print(f"Station table first rows: {response}")
    except Exception as e:
        print(f"Error executing the test query: {e}")


# def _connect_to_db() -> Tuple[connection, SQLDatabase]:
#     """Connect to the database."""
#     try:
#         import psycopg2
#         from psycopg2.extensions import connection
#     except Exception as e:
#         st.error(f"Error importing psycopg2: {e}")
#         return None, None
#     try:
#         engine = psycopg2.connect(
#             dbname=APPCFG.DB_NAME,
#             user=APPCFG.DB_USER,
#             password=APPCFG.DB_PASS,
#             host=APPCFG.DB_HOST,
#             port=APPCFG.DB_PORT,
#         )
#         db = SQLDatabase(engine)
#         return engine, db
#     except Exception as e:
#         st.error(f"Error connecting to the database: {e}")
#         return None, None


def _initialize_session_states() -> None:
    """Initialize the session states for the Streamlit app."""
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
        st.session_state["sql_query_results"] = []
    if "reset_counter" not in st.session_state:
        st.session_state["reset_counter"] = 0
    if "sql_query_results" not in st.session_state:
        st.session_state["sql_query_results"] = []


def _get_external_ip() -> str:
    """
    Get the external IP address of the user.
    Returns:
        str: The external IP address of the user.
    """
    try:
        response = requests.get("https://api.ipify.org?format=json")
        response.raise_for_status()
        ip_data = response.json()
        return ip_data["ip"]
    except requests.exceptions.RequestException as e:
        st.error(f"Network error: {e}")
    except ValueError:
        st.error("Invalid response received from the IP service")
    except KeyError:
        st.error("Unexpected response structure received from the IP service")
    return None


def _convert_datetime(obj: Any) -> Any:
    """
    Convert datetime objects to ISO format for JSON serialization.
    Args:
        obj (Any): The object to serialize.
    Returns:
        Any: The serialized object.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(
        "Object of type '{}' is not serializable".format(type(obj).__name__)
    )


def _download_data_csv() -> None:
    """Creates a download button in the Streamlit app to download the latest SQL query result as a CSV file."""
    if (
        "sql_query_results" in st.session_state
        and st.session_state["sql_query_results"]
        and len(st.session_state["sql_query_results"][0]) > 0
        and len(st.session_state["sql_query_results"][1]) > 0
    ):
        rows, columns = st.session_state["sql_query_results"]
        df = pd.DataFrame(data=rows, columns=columns)
        csv = df.to_csv(index=False)
        b64_csv = base64.b64encode(csv.encode()).decode()
        href = f'<a href="data:file/csv;base64,{b64_csv}" download="query_results.csv">📊 Download CSV File</a>'
        st.markdown(href, unsafe_allow_html=True)
    else:
        st.write("No data available to download.")


def _clear_chat_and_restart() -> None:
    """Clear the chat history and restart the app."""
    # Clear all session states including chat history
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    # Re-initialize necessary keys after clearing
    st.session_state["reset_counter"] = 0
    st.session_state["chat_history"] = []
    st.rerun()


def _append_to_query(
    query: str,
    prefix: str,
    elements: List[str],
    element_type: str,
) -> str:
    """Append elements to the SQL query based on the selected criteria."""
    if elements:
        elements_str = ", ".join(f"'{element}'" for element in elements)
        if query:
            query += f" {prefix} "
        else:
            query += f"{element_type}: "
        query += f"({elements_str})"
    return query


def _extract_sql_query(query_output: str) -> str:
    """
    Extracts the SQL query from the model's output text, starting with common SQL keywords and ending at the first semicolon.
    Args:
        query_output (str): The text output from the model which may contain an SQL query starting with 'SELECT' or 'WITH'.
    Returns:
        str: The extracted SQL query.
    Raises:
        ValueError: If the SQL query cannot be extracted.
    """
    try:
        # Use regular expression to find SQL queries starting with 'SELECT' or 'WITH' and ending with ';'
        # _manage_messages(
        #     "assistant", f"query_output input in _extract_sql_query: {query_output}"
        # )
        pattern = r"```sql(.*?)```"
        match = re.search(pattern, query_output, re.DOTALL)
        if match:
            # _manage_messages(
            #     "assistant",
            #     f"match.group(1).strip() in _extract_sql_query: {match.group(1).strip()}",
            # )
            return match.group(1).strip()
        else:
            raise ValueError(f"No valid SQL query found in the output: {query_output}")
    except ValueError as e:
        # Raise an error if no query is found
        raise ValueError(
            f"Failed to extract SQL query in the output: {query_output}. Error: {e}"
        )


def _reset_state_variables() -> None:
    """Resets all state variables to their default values, except for some specified keys."""
    keys_to_keep = {
        "chat_history",
        "reset_counter",
        "user_query",
        "assistant",
        "test_response_model",
    }
    keys_to_reset = [key for key in st.session_state if key not in keys_to_keep]

    for key in keys_to_reset:
        st.session_state[key] = []


def _compile_relevant_chat_history() -> str:
    """Compile relevant parts of the chat history based on specified message types."""
    relevant_types = {
        "user_query": "User Request",
        "refined_query_output": "Refined Query Output",
        "transformed_result": "Assistant Response",
        "chat_history_combined": "Chat History Combined",
        "assistant": "Assistant",
        "test_response_model": "Test Response Model",
    }
    chat_history = st.session_state.get("chat_history", [])
    relevant_messages = []

    for msg in chat_history:
        msg_type = msg.get("type")
        if msg_type in relevant_types:
            subtitle = relevant_types[msg_type]
            relevant_messages.append(f"### {subtitle}\n\n{msg['content']}\n")

    return "\n".join(relevant_messages)


def _manage_messages(
    role: str,
    content: str,
    message_type: str = None,
) -> None:
    """
    Manage the messages in the chat history with an additional type attribute for filtering.
    Args:
        role (str): The role of the message sender.
        content (str): The content of the message.
        message_type (str): The type of the message to assist in filtering.
    """
    message_data = {"role": role, "content": content}
    if message_type:
        message_data["type"] = message_type
    st.session_state.setdefault("chat_history", []).append(message_data)


def _manage_errors(e: Exception, user_query: str) -> None:
    """
    Manage errors that occur during the execution of the chatbot.
    This function enhances error reporting by including traceback information,
    allowing for easier identification of where errors are occurring in the code.
    Args:
        e (Exception): The exception that occurred.
        user_query (str): The user's query at the time of the error.
    """
    # Capture the traceback and format it into a readable string
    tb_info = traceback.format_exc()

    # Create a detailed error message including the traceback information
    error_message = (
        f"An error occurred while processing the query: '{user_query}'\n"
        f"Exception: {str(e)}\n"
        f"Traceback details:\n{tb_info}"
    )

    # Append the error message to the chat history
    st.session_state["chat_history"].append(
        {
            "role": "assistant",
            "content": error_message,
        }
    )

    # Display the error in the app's interface
    st.error(f"An error occurred: {str(e)}\nPlease check the logs for more details.")
