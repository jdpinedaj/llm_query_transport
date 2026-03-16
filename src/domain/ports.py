"""
Domain Ports (Interfaces).
--------------------------
LLM Query Transport - Abstract interfaces for infrastructure dependencies

This module defines the contracts (ports) that the business logic depends on,
allowing different implementations (adapters) to be plugged in.

Key Interfaces:
- SessionManager: Abstract session state management
- ConfigProvider: Abstract configuration source
- UINotifier: Abstract UI update notifications
"""

from abc import ABC, abstractmethod
from typing import Any


class SessionManager(ABC):
    """Abstract interface for session state management.

    This allows the business logic to store and retrieve session data
    without being coupled to any specific framework (Streamlit, Flask, etc.)
    """

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from session state."""

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set a value in session state."""

    @abstractmethod
    def has(self, key: str) -> bool:
        """Check if a key exists in session state."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a key from session state."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all session state."""

    @abstractmethod
    def get_all(self) -> dict[str, Any]:
        """Get all session state as a dictionary."""


class ConfigProvider(ABC):
    """Abstract interface for configuration management.

    This allows the system to retrieve configuration from different sources
    (Streamlit secrets, .env files, etc.)
    """

    @abstractmethod
    def get(self, key: str, default: str | None = None) -> str:
        """Get a configuration value."""

    @abstractmethod
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean configuration value."""

    @abstractmethod
    def get_int(self, key: str, default: int | None = None) -> int:
        """Get an integer configuration value."""

    @abstractmethod
    def has(self, key: str) -> bool:
        """Check if a configuration key exists."""


class UINotifier(ABC):
    """Abstract interface for UI update notifications.

    This allows the business logic to trigger UI updates without
    being coupled to the UI framework.
    """

    @abstractmethod
    def request_rerun(self) -> None:
        """Request a UI refresh/rerun."""

    @abstractmethod
    def show_spinner(self, message: str) -> Any:
        """Show a loading spinner with a message."""
