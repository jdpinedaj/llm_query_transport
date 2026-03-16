"""
SQL Query Generator.
--------------------
LLM Query Transport - Generates SQL queries from natural language using LLMs

Uses LangChain with FAISS semantic similarity for few-shot example selection.
Prompts are loaded from YAML files via PromptLoader.
"""

import re

from langchain.chains.sql_database.query import create_sql_query_chain
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI

from src.config.prompts.prompt_loader import prompt_loader
from src.config.settings import LoadConfig, logger


class SQLQueryGenerator:
    """Generates SQL queries based on user questions and chat context."""

    def __init__(
        self,
        llm_model: ChatOpenAI,
        embeddings_model,
        db: SQLDatabase,
    ):
        self.llm_model = llm_model
        self.embeddings_model = embeddings_model
        self.db = db

    @staticmethod
    def extract_sql_query(query_output: str) -> str:
        """Extract SQL query from the model's output text."""
        # Try extracting from a ```sql block
        pattern = r"```sql(.*?)```"
        match = re.search(pattern, query_output, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Fallback to extracting starting with common SQL keywords
        pattern_sql = r"\b(SELECT|WITH)\b.*?;"
        match_sql = re.search(pattern_sql, query_output, re.DOTALL | re.IGNORECASE)
        if match_sql:
            return match_sql.group(0).strip()

        raise ValueError(f"No valid SQL query found in the output: {query_output}")

    def create_sql_query(
        self,
        question: str,
        chat_history_combined: str,
        config: LoadConfig,
        initial_query: str = "",
    ) -> str:
        """Generate or refine an SQL query based on the user's question and chat context."""
        is_refinement = bool(initial_query)

        # Load contexts from YAML
        table_info = prompt_loader.get_raw("contexts", "table_info")
        additional_context = prompt_loader.get_raw("contexts", "additional_context")
        examples = prompt_loader.get_raw("contexts", "examples")

        if config.use_examples_vector_database:
            prompt_template = prompt_loader.get_few_shot_template(
                file_name="sql_generation",
                prompt_name="few_shot_sql_generation",
                examples=examples,
                embeddings_model=self.embeddings_model,
                k=config.few_shot_k,
            )
        else:
            prompt_template = prompt_loader.get_prompt_template(
                file_name="sql_generation",
                prompt_name="simple_sql_generation",
            )

        logger.info(f"Generating SQL query for: {question}")

        try:
            chain = create_sql_query_chain(
                llm=self.llm_model,
                db=self.db,
                prompt=prompt_template,
            )
            sql_query = chain.invoke(
                {
                    "question": question,
                    "top_k": config.top_k,
                    "table_info": table_info,
                    "additional_context": additional_context,
                    "chat_history_combined": chat_history_combined,
                },
            )
            return sql_query.strip(".").replace('"', "'")

        except Exception as e:
            error_message = "refining" if is_refinement else "generating"
            raise ValueError(f"An error occurred while {error_message} the SQL query: {e}") from e
