#! Imports
# Standard libraries
import yaml
from datetime import datetime, timedelta
import os
from typing import Dict, Any
from dotenv import load_dotenv

#  External libraries
import streamlit as st
from pyprojroot import here
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

load_dotenv()


class LoadConfig:
    """
    LoadConfig loads the configuration from `app_config.yml` and stores parameters as class attributes.
    This class is responsible for reading configuration sections related to database, monitoring metrics,
    model parameters, OpenAI, Gemini, business instructions, developer comments, and Langsmith secrets.
    The parameters are organized into attributes accessible throughout the app using `LoadConfig().attribute_name`.

    Attributes:
        General:
            platform (str): Platform to use, either "aws" or "gcp".
            model_to_use (str): Model to use, either "openai" or "gemini".
            analysis_langsmith (bool): Indicates if Langsmith secrets are loaded.

        Database:
            database_config (dict): Configuration parameters for the database.
            initial_date (str): Initial date in "YYYY-MM-DD" format.
            final_date (str): Final date in "YYYY-MM-DD" format.
            recent_week_start_date (str): Start date of the recent week in "YYYY-MM-DD" format.
            locations_brands_categories_directly_from_db (bool): Fetch locations, brands, and categories directly from the database.
            db_name (str): Database name.
            schema_name (str): Schema name.
            gcp_project_id (str): GCP project ID if using GCP.

        Monitoring:
            monitoring_config (dict): Monitoring configuration parameters.
            time_to_refresh_metrics (int): Time interval to refresh metrics in seconds.
            rds_metrics (List[str]): List of AWS RDS metrics to monitor.
            cloudsql_metrics (List[str]): List of GCP Cloud SQL metrics to monitor.
            metrics_to_use (List[str]): Selected metrics based on platform.

        Models:
            model_general_parameters (dict): General model parameters.
            temperature_generation_refinement (float): Temperature setting for generation refinement.
            top_p_generation_refinement (float): Top-p setting for generation refinement.
            temperature_transformation (float): Temperature setting for transformation.
            top_p_transformation (float): Top-p setting for transformation.
            use_examples_vector_database (bool): Whether to use examples vector database.

        OpenAI:
            openai_config (dict): OpenAI-specific configuration parameters.
            openai_model_generation_refinement (str): Model used for generation refinement in OpenAI.
            openai_model_transformation (str): Model used for transformation in OpenAI.
            openai_embedding_model (str): Embedding model used in OpenAI.

        Gemini:
            gemini_config (dict): Gemini-specific configuration parameters.
            gemini_model_generation_refinement (str): Model used for generation refinement in Gemini.
            gemini_model_transformation (str): Model used for transformation in Gemini.
            gemini_embedding_model (str): Embedding model used in Gemini.

        Business Instructions:
            business_instructions (dict): Business-specific instructions.
            default_type_query (str): Default query type.
            default_granularity_geo (str): Default geographic granularity.
            default_granularity_venue (str): Default venue granularity.
            default_top_all (int): Default setting for top-all queries.
            columns_to_take_from_visitation_table (List[str]): Columns to extract from the visitation table.

        Developer Comments:
            dev_comments (dict): Developer-specific settings.
            save_logs (bool): If True, logs are saved.
            include_refinement_process (bool): If True, includes the refinement process.
            show_dates_details_extraction (bool): If True, shows date details extraction.
            show_developer_comments (bool): If True, shows developer comments.
            show_refined_query (bool): If True, shows refined queries.

        Secrets:
            SMC_API_KEY (str): SMC API key.
            BASE_RELAY_URL (str): Base URL for OpenAI relay.
            RELAY_URL (str): Relay URL for OpenAI.
            LANGCHAIN_TRACING_V2 (str): Langsmith tracing environment variable.
            LANGCHAIN_API_KEY (str): Langsmith API key.
            DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME (str): Database connection parameters based on platform.

        LLM Models:
            llm_model_generation_refinement: The LLM model used for generation refinement.
            llm_model_transformation: The LLM model used for transformation.
            embeddings_model: The embeddings model used for language tasks.

    Methods:
        __init__: Initializes the configuration by loading parameters from the configuration file.
        _load_general_config: Loads general configuration parameters.
        _load_database_config: Loads database configuration parameters.
        _load_monitoring_config: Loads monitoring configuration parameters.
        _load_model_parameters: Loads model parameters.
        _load_openai_config: Loads OpenAI configuration parameters.
        _load_gemini_config: Loads Gemini configuration parameters.
        _load_business_instructions: Loads business instructions.
        _load_developer_comments: Loads developer comments.
        _load_secrets: Loads secrets.
        _load_llm_models: Loads LLM models.
    """

    def __init__(self) -> None:
        # Load configuration from YAML file
        with open(here("configs/app_config.yml")) as cfg:
            app_config = yaml.load(cfg, Loader=yaml.FullLoader)

        # Load general configuration
        self._load_general_config(app_config)
        self._load_database_config(app_config)
        self._load_monitoring_config(app_config)
        self._load_model_parameters(app_config)
        self._load_openai_config(app_config)
        self._load_gemini_config(app_config)
        self._load_business_instructions(app_config)
        self._load_developer_comments(app_config)
        self._load_secrets()
        self._load_llm_models()

    def _load_general_config(self, config: Dict[str, Any]) -> None:
        self.platform = config["platform"]
        self.model_to_use = config["model_to_use"]
        self.analysis_langsmith = config["analysis_langsmith"]

    def _load_database_config(self, config: Dict[str, Any]) -> None:
        self.database_config = config["database_config"]
        self.initial_date = self.database_config["initial_date"]
        self.final_date = self.database_config["final_date"]
        self.recent_week_start_date = (
            datetime.strptime(self.final_date, "%Y-%m-%d") - timedelta(days=6)
        ).strftime("%Y-%m-%d")
        self.locations_brands_categories_directly_from_db = self.database_config[
            "locations_brands_categories_directly_from_db"
        ]

        db_config = self.database_config[self.platform]
        self.db_name = db_config["db_name"]
        self.schema_name = db_config["schema_name"]
        self.gcp_project_id = self.database_config.get("gcp", {}).get("gcp_project_id")

    def _load_monitoring_config(self, config: Dict[str, Any]) -> None:
        self.monitoring_config = config["monitoring_config"]
        self.time_to_refresh_metrics = self.monitoring_config["time_to_refresh_metrics"]
        self.rds_metrics = list(self.monitoring_config["rds_metrics"].keys())
        self.cloudsql_metrics = list(self.monitoring_config["cloudsql_metrics"].keys())
        self.metrics_to_use = (
            self.rds_metrics if self.platform == "aws" else self.cloudsql_metrics
        )

    def _load_model_parameters(self, config: Dict[str, Any]) -> None:
        self.model_general_parameters = config["model_general_parameters"]
        self.temperature_generation_refinement = self.model_general_parameters[
            "temperature_generation_refinement"
        ]
        self.top_p_generation_refinement = self.model_general_parameters[
            "top_p_generation_refinement"
        ]
        self.temperature_transformation = self.model_general_parameters[
            "temperature_transformation"
        ]
        self.top_p_transformation = self.model_general_parameters[
            "top_p_transformation"
        ]
        self.use_examples_vector_database = self.model_general_parameters[
            "use_examples_vector_database"
        ]

    def _load_openai_config(self, config: Dict[str, Any]) -> None:
        self.openai_config = config["openai_config"]
        self.openai_model_generation_refinement = self.openai_config[
            "openai_model_generation_refinement"
        ]
        self.openai_model_transformation = self.openai_config[
            "openai_model_transformation"
        ]
        self.openai_embedding_model = self.openai_config["openai_embedding_model"]

    def _load_gemini_config(self, config: Dict[str, Any]) -> None:
        self.gemini_config = config["gemini_config"]
        self.gemini_model_generation_refinement = self.gemini_config[
            "gemini_model_generation_refinement"
        ]
        self.gemini_model_transformation = self.gemini_config[
            "gemini_model_transformation"
        ]
        self.gemini_embedding_model = self.gemini_config["gemini_embedding_model"]

    def _load_business_instructions(self, config: Dict[str, Any]) -> None:
        self.business_instructions = config["business_instructions"]
        self.default_type_query = self.business_instructions["default_type_query"]
        self.default_granularity_geo = self.business_instructions[
            "default_granularity_geo"
        ]
        self.default_granularity_venue = self.business_instructions[
            "default_granularity_venue"
        ]
        self.default_top_all = self.business_instructions["default_top_all"]
        self.columns_to_take_from_visitation_table = self.business_instructions[
            "columns_to_take_from_visitation_table"
        ]

    def _load_developer_comments(self, config: Dict[str, Any]) -> None:
        self.dev_comments = config["dev_comments"]
        self.save_logs = self.dev_comments["save_logs"]
        self.include_refinement_process = self.dev_comments[
            "include_refinement_process"
        ]
        self.show_dates_details_extraction = self.dev_comments[
            "show_dates_details_extraction"
        ]
        self.show_developer_comments = self.dev_comments["show_developer_comments"]
        self.show_refined_query = self.dev_comments["show_refined_query"]

    def _load_secrets(self) -> None:
        self.SMC_API_KEY = st.secrets["SMC_API_KEY"]
        self.BASE_RELAY_URL = st.secrets["BASE_RELAY_URL"]
        self.RELAY_URL = st.secrets["RELAY_URL"]

        if self.analysis_langsmith:
            self.LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2")
            self.LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")

        self.DB_USER = st.secrets["DB_USER_GCP"]
        self.DB_PASS = st.secrets["DB_PASS_GCP"]
        self.DB_HOST = st.secrets["DB_HOST_GCP"]
        self.DB_PORT = st.secrets["DB_PORT_GCP"]
        self.DB_NAME = st.secrets["DB_NAME_GCP"]

    def _load_llm_models(self) -> None:
        self.llm_model_generation_refinement = ChatOpenAI(
            base_url=self.BASE_RELAY_URL,
            model_name=self.openai_model_generation_refinement,
            api_key=self.SMC_API_KEY,
            temperature=self.temperature_generation_refinement,
            top_p=self.top_p_generation_refinement,
        )

        self.embeddings_model = OpenAIEmbeddings(
            api_key=self.SMC_API_KEY,
            base_url=self.BASE_RELAY_URL,
            model=self.openai_embedding_model,
        )

        self.llm_model_transformation = ChatOpenAI(
            base_url=self.BASE_RELAY_URL,
            model_name=self.openai_model_transformation,
            api_key=self.SMC_API_KEY,
            temperature=self.temperature_transformation,
            top_p=self.top_p_transformation,
        )
