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
        self.use_examples_vector_database: bool = params["use_examples_vector_database"]

    def _load_openai_config(self, config: dict[str, Any]) -> None:
        openai_cfg = config["openai_config"]
        self.openai_model_generation_refinement: str = openai_cfg["openai_model_generation_refinement"]
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
        db = config.get("database", {})
        self.db_host: str = os.getenv("DB_HOST", db.get("host", "localhost"))
        self.db_port: str = os.getenv("DB_PORT", db.get("port", "5432"))
        self.db_user: str = os.getenv("DB_USER", "")
        self.db_pass: str = os.getenv("DB_PASS", "")
        self.db_name: str = os.getenv("DB_NAME", db.get("name", "bike_1"))

    def _load_query_parameters(self, config: dict[str, Any]) -> None:
        qp = config.get("query_parameters", {})
        self.decimal_places: int = qp.get("decimal_places", 4)
        self.sample_size: int = qp.get("sample_size", 50)
        self.few_shot_k: int = qp.get("few_shot_k", 5)
        self.top_k: int = qp.get("top_k", 1)
        self.memory_window_size: int = qp.get("memory_window_size", 5)

    def _load_ui_config(self, config: dict[str, Any]) -> None:
        ui = config.get("ui", {})
        self.page_title: str = ui.get("page_title", "LLM Query Transport")
        self.page_icon: str = ui.get("page_icon", "🚲")
        self.logo_image: str = ui.get("logo_image", "images/upv-logo.png")
        self.logo_width: int = ui.get("logo_width", 180)
        self.container_height: int = ui.get("container_height", 700)
        self.input_height: int = ui.get("input_height", 150)
        self.max_container_width: str = ui.get("max_container_width", "1800px")
        self.outer_columns: list = ui.get("outer_columns", [0.05, 0.90, 0.05])
        self.content_columns: list = ui.get("content_columns", [0.40, 0.60])
        self.input_columns: list = ui.get("input_columns", [0.15, 0.70, 0.15])
        self.button_columns: list = ui.get("button_columns", [0.15, 0.35, 0.35, 0.15])
        self.default_query: str = ui.get("default_query", "Get the average duration of trips grouped by zip codes")
        self.welcome_message: str = ui.get("welcome_message", "Hello! Ask me any question about the bike-sharing database.")
        self.spinner_text: str = ui.get("spinner_text", "Thinking...")
        self.csv_filename_prefix: str = ui.get("csv_filename_prefix", "query_results")
        self.csv_timestamp_format: str = ui.get("csv_timestamp_format", "%Y%m%d_%H%M%S")

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

    def _load_llm_models(self) -> None:
        self.llm_model_generation_refinement = ChatOpenAI(
            model_name=self.openai_model_generation_refinement,
            api_key=self.OPENAI_API_KEY,
            temperature=self.temperature_generation_refinement,
            top_p=self.top_p_generation_refinement,
        )

        self.embeddings_model = OpenAIEmbeddings(
            api_key=self.OPENAI_API_KEY,
            model=self.openai_embedding_model,
        )

        self.llm_model_transformation = ChatOpenAI(
            model_name=self.openai_model_transformation,
            api_key=self.OPENAI_API_KEY,
            temperature=self.temperature_transformation,
            top_p=self.top_p_transformation,
        )
