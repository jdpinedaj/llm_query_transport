"""
Session Management Adapters.
----------------------------
LLM Query Transport - Concrete implementations of SessionManager and UINotifier
"""

from contextlib import contextmanager
from typing import Any

from src.domain.ports import SessionManager, UINotifier


class StreamlitSessionManager(SessionManager):
    """Streamlit-specific session manager using st.session_state."""

    def __init__(self):
        import streamlit as st

        self._st = st

    def get(self, key: str, default: Any = None) -> Any:
        return self._st.session_state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._st.session_state[key] = value

    def has(self, key: str) -> bool:
        return key in self._st.session_state

    def delete(self, key: str) -> None:
        if key in self._st.session_state:
            del self._st.session_state[key]

    def clear(self) -> None:
        self._st.session_state.clear()

    def get_all(self) -> dict[str, Any]:
        return {str(k): v for k, v in self._st.session_state.items()}


class InMemorySessionManager(SessionManager):
    """Simple in-memory session manager for testing and non-web contexts."""

    def __init__(self):
        self._session: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._session.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._session[key] = value

    def has(self, key: str) -> bool:
        return key in self._session

    def delete(self, key: str) -> None:
        self._session.pop(key, None)

    def clear(self) -> None:
        self._session.clear()

    def get_all(self) -> dict[str, Any]:
        return self._session.copy()


class StreamlitUINotifier(UINotifier):
    """Streamlit-specific UI notifier using st.rerun() and st.spinner()."""

    def __init__(self):
        import streamlit as st

        self._st = st

    def request_rerun(self) -> None:
        self._st.rerun()

    @contextmanager
    def show_spinner(self, message: str):
        with self._st.spinner(message):
            yield


class NoOpUINotifier(UINotifier):
    """No-op UI notifier for testing and non-web contexts."""

    def request_rerun(self) -> None:
        pass

    @contextmanager
    def show_spinner(self, message: str):
        yield
