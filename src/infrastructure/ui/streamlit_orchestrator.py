"""
Streamlit Orchestrator.
-----------------------
LLM Query Transport - Streamlit-specific wrapper around ChatOrchestrator

Applies @st.fragment() for partial reruns and wires Streamlit-specific
adapters (session, UI notifier) to the ChatOrchestrator.
"""

import streamlit as st

from src.application.services.chat_orchestrator import ChatOrchestrator
from src.config.settings import LoadConfig
from src.infrastructure.session_adapters import StreamlitSessionManager, StreamlitUINotifier


def create_streamlit_orchestrator(config: LoadConfig, database_uri: str) -> ChatOrchestrator:
    """Create a ChatOrchestrator wired with Streamlit-specific adapters."""
    session = StreamlitSessionManager()
    ui_notifier = StreamlitUINotifier()

    return ChatOrchestrator(
        session=session,
        ui_notifier=ui_notifier,
        config=config,
        database_uri=database_uri,
    )


@st.fragment()
def execute_all_in_chat(user_query: str, config: LoadConfig, database_uri: str) -> None:
    """Streamlit fragment that executes the full pipeline.

    Uses @st.fragment() for partial reruns optimization.
    """
    orchestrator = create_streamlit_orchestrator(config, database_uri)
    orchestrator.execute_pipeline(user_query)
