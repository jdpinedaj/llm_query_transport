"""
Configuration Settings.
-----------------------
LLM Query Transport - Central configuration loader

Loads configuration from app_config.yml, manages secrets,
and initializes LLM models. Provides structured logging with structlog.
"""

import logging
import os
import time
import warnings
from collections.abc import Callable, MutableMapping
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

warnings.filterwarnings("ignore", message="Importing verbose from langchain root module")
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

try:
    import structlog

    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False

load_dotenv()


# ============================================================================
# STRUCTURED LOGGING CONFIGURATION
# ============================================================================


def drop_color_message_key(_, __, event_dict: dict) -> dict:
    """Remove color_message key from event dict if present."""
    event_dict.pop("color_message", None)
    return event_dict


def simple_renderer(logger: Any, name: str, event_dict: MutableMapping[str, Any]) -> str:
    """Simple log renderer for non-local environments."""
    if "logger" in event_dict:
        return f"{event_dict.get('level', '').upper()}: {event_dict.get('event')} [{event_dict.get('logger')}]"
    return f"{event_dict.get('level', '').upper()}: {event_dict.get('event')}"


def init_logging(
    log_level: str = os.getenv("LOG_LEVEL", "INFO"),
    environment: str = os.getenv("ENVIRONMENT", "LOCAL"),
) -> None:
    """Initialize structured logging configuration."""
    if not STRUCTLOG_AVAILABLE:
        _init_basic_logging(log_level)
        return

    LEVEL = log_level.upper()
    IS_LOCAL = environment.upper() == "LOCAL"
    DEBUG_MODE = LEVEL == "DEBUG"

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.stdlib.ExtraAdder(),
        drop_color_message_key,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.MODULE,
            ],
        ),
    ]
    if DEBUG_MODE:
        shared_processors += [structlog.stdlib.add_logger_name]

    if IS_LOCAL:

        def custom_local_renderer(logger: Any, name: str, event_dict: MutableMapping[str, Any]) -> str:
            level = event_dict.get("level", "").upper()
            filename = event_dict.get("filename", "")
            lineno = event_dict.get("lineno", "")
            event = event_dict.get("event", "")

            level_colors = {
                "DEBUG": "\033[36m",  # Cyan
                "INFO": "\033[32m",  # Green
                "WARNING": "\033[33m",  # Yellow
                "ERROR": "\033[31m",  # Red
                "CRITICAL": "\033[35m",  # Magenta
            }

            filename_color = "\033[94m"  # Bright Blue
            lineno_color = "\033[95m"  # Bright Magenta
            reset = "\033[0m"

            level_color = level_colors.get(level, "")
            return f"{level_color}[{level}]{reset} {filename_color}[{filename}]{reset} {lineno_color}[line:{lineno}]{reset} {event}"

        log_renderer: structlog.dev.ConsoleRenderer | Callable[[Any, str, MutableMapping[str, Any]], str] = custom_local_renderer
    else:
        log_renderer = simple_renderer

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,  # type: ignore[arg-type]
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            log_renderer,
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    level_num = logging.DEBUG if DEBUG_MODE else logging.INFO

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level_num)

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],  # type: ignore[arg-type, list-item]
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _init_basic_logging(log_level: str) -> None:
    """Fallback basic logging when structlog is not available."""
    level_mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    log_format = "[%(asctime)s] [%(levelname)s] [%(lineno)s] [%(module)s] %(message)s"
    log_timestamp_format = "%Y-%m-%dT%H:%M:%S%z"

    formatter = logging.Formatter(log_format, log_timestamp_format)
    formatter.converter = time.gmtime

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    level = level_mapping.get(log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def get_logger(name: str | None = None):
    """Get a logger instance (structlog if available, else standard logging)."""
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    return logging.getLogger(name or __name__)


# Initialize logging on module import
init_logging()
logger = get_logger(__name__)


# ============================================================================
# CONFIGURATION LOADER
# ============================================================================


def _get_config_path() -> Path:
    """Resolve the path to app_config.yml."""
    return Path(__file__).parent / "app_config.yml"


class LoadConfig:
    """Loads configuration from app_config.yml and initializes LLM models."""

    def __init__(self) -> None:
        config_path = _get_config_path()
        with open(config_path) as cfg:
            app_config = yaml.safe_load(cfg)

        self._load_general_config(app_config)
        self._load_model_parameters(app_config)
        self._load_openai_config(app_config)
        self._load_developer_comments(app_config)
        self._load_database_config(app_config)
        self._load_query_parameters(app_config)
        self._load_ui_config(app_config)
        self._load_secrets()
        self._load_llm_models()

    def _load_general_config(self, config: dict[str, Any]) -> None:
        self.model_to_use: str = config["model_to_use"]
        self.analysis_langsmith: bool = config["analysis_langsmith"]

    def _load_model_parameters(self, config: dict[str, Any]) -> None:
        params = config["model_general_parameters"]
        self.temperature_generation_refinement: float = params["temperature_generation_refinement"]
        self.top_p_generation_refinement: float = params["top_p_generation_refinement"]
        self.temperature_transformation: float = params["temperature_transformation"]
        self.top_p_transformation: float = params["top_p_transformation"]
        self.reasoning_effort_generation: str = params["reasoning_effort_generation"]
        self.reasoning_effort_transformation: str = params["reasoning_effort_transformation"]
        self.max_completion_tokens: int = params["max_completion_tokens"]
        self.use_examples_vector_database: bool = params["use_examples_vector_database"]

    def _load_openai_config(self, config: dict[str, Any]) -> None:
        openai_cfg = config["openai_config"]
        # OPENAI_MODEL env var overrides the YAML default for generation/refinement
        self.openai_model_generation_refinement: str = os.getenv(
            "OPENAI_MODEL",
            openai_cfg["openai_model_generation_refinement"],
        )
        self.openai_model_transformation: str = openai_cfg["openai_model_transformation"]
        self.openai_embedding_model: str = openai_cfg["openai_embedding_model"]

    def _load_developer_comments(self, config: dict[str, Any]) -> None:
        dev = config["dev_comments"]
        self.save_logs: bool = dev["save_logs"]
        self.include_refinement_process: bool = dev["include_refinement_process"]
        self.show_dates_details_extraction: bool = dev["show_dates_details_extraction"]
        self.show_developer_comments: bool = dev["show_developer_comments"]
        self.show_refined_query: bool = dev["show_refined_query"]

    def _load_database_config(self, config: dict[str, Any]) -> None:
        db = config["database"]
        self.db_host: str = os.getenv("DB_HOST", db["host"])
        self.db_port: str = os.getenv("DB_PORT", db["port"])
        self.db_user: str = os.getenv("DB_USER", "")
        self.db_pass: str = os.getenv("DB_PASS", "")
        self.db_name: str = os.getenv("DB_NAME", db["name"])

    def _load_query_parameters(self, config: dict[str, Any]) -> None:
        qp = config["query_parameters"]
        self.decimal_places: int = qp["decimal_places"]
        self.sample_size: int = qp["sample_size"]
        self.few_shot_k: int = qp["few_shot_k"]
        self.top_k: int = qp["top_k"]
        self.memory_window_size: int = qp["memory_window_size"]

    def _load_ui_config(self, config: dict[str, Any]) -> None:
        ui = config["ui"]
        self.page_title: str = ui["page_title"]
        self.page_icon: str = ui["page_icon"]
        self.logo_image: str = ui["logo_image"]
        self.logo_width: int = ui["logo_width"]
        self.container_height: int = ui["container_height"]
        self.input_height: int = ui["input_height"]
        self.max_container_width: str = ui["max_container_width"]
        self.outer_columns: list = ui["outer_columns"]
        self.content_columns: list = ui["content_columns"]
        self.input_columns: list = ui["input_columns"]
        self.button_columns: list = ui["button_columns"]
        self.default_query: str = ui["default_query"]
        self.welcome_message: str = ui["welcome_message"]
        self.spinner_text: str = ui["spinner_text"]
        self.csv_filename_prefix: str = ui["csv_filename_prefix"]
        self.csv_timestamp_format: str = ui["csv_timestamp_format"]

    @property
    def database_uri(self) -> str:
        return f"postgresql+psycopg2://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"

    def _load_secrets(self) -> None:
        try:
            import streamlit as st

            self.OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        except Exception:
            self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

        if self.analysis_langsmith:
            self.LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2")
            self.LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")

    @staticmethod
    def is_gpt5(model: str) -> bool:
        """Check if the model is a GPT-5 reasoning model."""
        return "gpt-5" in model.lower()

    def _build_llm(self, model: str, temperature: float, top_p: float, reasoning_effort: str) -> ChatOpenAI:
        """Build a ChatOpenAI instance based on model type.

        GPT-5.x reasoning models do not support temperature/top_p/stop;
        they use reasoning_effort instead.
        """
        if self.is_gpt5(model):
            return _GPT5ChatOpenAI(
                model=model,
                api_key=self.OPENAI_API_KEY,
                reasoning_effort=reasoning_effort,
                max_completion_tokens=self.max_completion_tokens,
            )
        return ChatOpenAI(
            model=model,
            api_key=self.OPENAI_API_KEY,
            temperature=temperature,
            top_p=top_p,
        )

    def _load_llm_models(self) -> None:
        self.llm_model_generation_refinement = self._build_llm(
            model=self.openai_model_generation_refinement,
            temperature=self.temperature_generation_refinement,
            top_p=self.top_p_generation_refinement,
            reasoning_effort=self.reasoning_effort_generation,
        )

        self.embeddings_model = OpenAIEmbeddings(
            api_key=self.OPENAI_API_KEY,
            model=self.openai_embedding_model,
        )

        self.llm_model_transformation = self._build_llm(
            model=self.openai_model_transformation,
            temperature=self.temperature_transformation,
            top_p=self.top_p_transformation,
            reasoning_effort=self.reasoning_effort_transformation,
        )


class _GPT5ChatOpenAI(ChatOpenAI):
    """ChatOpenAI subclass that strips unsupported params (like 'stop') for GPT-5.x.

    LangChain's create_sql_query_chain internally calls llm.bind(stop=[...]),
    but GPT-5.x reasoning models do not support the 'stop' parameter.
    """

    def bind(self, **kwargs: Any):
        kwargs.pop("stop", None)
        return super().bind(**kwargs)
