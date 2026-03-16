"""
Configuration Provider Adapters.
--------------------------------
LLM Query Transport - Concrete implementations of ConfigProvider interface
"""

import os

from src.domain.ports import ConfigProvider


class StreamlitConfigProvider(ConfigProvider):
    """Configuration provider using Streamlit secrets."""

    def __init__(self):
        import streamlit as st

        self._secrets = st.secrets

    def get(self, key: str, default: str | None = None) -> str:
        try:
            return str(self._secrets[key])
        except (KeyError, FileNotFoundError) as e:
            if default is not None:
                return default
            raise KeyError(f"Configuration key '{key}' not found in Streamlit secrets") from e

    def get_bool(self, key: str, default: bool = False) -> bool:
        try:
            value = str(self._secrets[key]).lower()
            return value in ("true", "1", "yes", "on")
        except (KeyError, FileNotFoundError):
            return default

    def get_int(self, key: str, default: int | None = None) -> int:
        try:
            return int(self._secrets[key])
        except (KeyError, FileNotFoundError) as e:
            if default is not None:
                return default
            raise KeyError(f"Configuration key '{key}' not found in Streamlit secrets") from e

    def has(self, key: str) -> bool:
        try:
            _ = self._secrets[key]
        except (KeyError, FileNotFoundError):
            return False
        else:
            return True


class EnvConfigProvider(ConfigProvider):
    """Configuration provider using environment variables."""

    def __init__(self, env_file: str | None = None):
        if env_file:
            from dotenv import load_dotenv

            load_dotenv(env_file)

    def get(self, key: str, default: str | None = None) -> str:
        value = os.getenv(key)
        if value is None:
            if default is not None:
                return default
            raise KeyError(f"Configuration key '{key}' not found in environment")
        return value

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    def get_int(self, key: str, default: int | None = None) -> int:
        value = os.getenv(key)
        if value is None:
            if default is not None:
                return default
            raise KeyError(f"Configuration key '{key}' not found in environment")
        return int(value)

    def has(self, key: str) -> bool:
        return os.getenv(key) is not None


class CompositeConfigProvider(ConfigProvider):
    """Configuration provider that tries multiple sources in priority order."""

    def __init__(self, providers: list[ConfigProvider]):
        self._providers = providers

    def get(self, key: str, default: str | None = None) -> str:
        for provider in self._providers:
            if provider.has(key):
                return provider.get(key)
        if default is not None:
            return default
        raise KeyError(f"Configuration key '{key}' not found in any provider")

    def get_bool(self, key: str, default: bool = False) -> bool:
        for provider in self._providers:
            if provider.has(key):
                return provider.get_bool(key, default)
        return default

    def get_int(self, key: str, default: int | None = None) -> int:
        for provider in self._providers:
            if provider.has(key):
                return provider.get_int(key)
        if default is not None:
            return default
        raise KeyError(f"Configuration key '{key}' not found in any provider")

    def has(self, key: str) -> bool:
        return any(provider.has(key) for provider in self._providers)
