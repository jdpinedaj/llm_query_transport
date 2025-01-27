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
            model_to_use (str): Model to use, either "openai" or "gemini".
            analysis_langsmith (bool): Indicates if Langsmith secrets are loaded.

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
        self._load_model_parameters(app_config)
        self._load_openai_config(app_config)
        self._load_developer_comments(app_config)
        self._load_secrets()
        self._load_llm_models()

    def _load_general_config(self, config: Dict[str, Any]) -> None:
        self.model_to_use = config["model_to_use"]
        self.analysis_langsmith = config["analysis_langsmith"]

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
