#!##########################################
#!############# IMPORTS ####################
#!##########################################

# Standard Libraries
import re
from datetime import datetime
from typing import List, Tuple

# Local Imports
from src.load_config import LoadConfig
from src.logs import logger
from src.contexts import (
    _context_introduction,
    _context_for_creation_query,
    _table_info,
    EXAMPLES_QUERIES,
)

# External Libraries
from langchain.chains.sql_database.query import create_sql_query_chain
from langchain.prompts import PromptTemplate, FewShotPromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI


APPCFG = LoadConfig()

#!##########################################
#!############# SQLQueryGenerator ##########
#!##########################################


class SQLQueryGenerator:
    """
    A class to generate SQL queries based on user questions and chat context.
    Attributes:
        llm_model (ChatOpenAI): The model used to generate SQL queries.
        embeddings_model (Embeddings): The model used to generate embeddings for the examples.
        db (SQLDatabase): The database connection.
    Methods:
        create_sql_query(question, type_query, granularity_geographical_order, granularity_venue_order, chat_history_combined, start_date, end_date, use_examples_vector_database, initial_query): Generate or refine an SQL query based on user questions and chat context.
    """

    def __init__(
        self,
        llm_model: ChatOpenAI,
        embeddings_model: str,
        db: SQLDatabase,
    ):
        self.llm_model = llm_model
        self.embeddings_model = embeddings_model
        self.db = db

    @staticmethod
    def _get_date_range_days(
        start_date: str,
        end_date: str,
    ) -> int:
        """
        Get the number of days in the date range.
        Args:
            start_date (str): The start date in the format "YYYY-MM-DD".
            end_date (str): The end date in the format "YYYY-MM-DD".
        Returns:
            int: The number of days in the date range.
        """
        return (
            datetime.strptime(end_date, "%Y-%m-%d")
            - datetime.strptime(start_date, "%Y-%m-%d")
        ).days + 1

    @staticmethod
    def _extract_sql_query(query_output: str) -> str:
        """
        Extracts the SQL query from the model's output text, starting with common SQL keywords and ending at the first semicolon.
        Args:
            query_output (str): The output text from the model.
        Returns:
            str: The extracted SQL query.
        """
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
        else:
            raise ValueError(f"No valid SQL query found in the output: {query_output}")

    def _get_context(
        self,
    ) -> Tuple[str, List[str]]:
        """
        Get the context for the SQL query based on the type of query and the selected criteria.

        Returns:
            Tuple[str, List[str]]: The context for the SQL query and a list of examples.
        """
        context = _context_for_creation_query()
        examples = EXAMPLES_QUERIES

        return context, examples

    def create_sql_query(
        self,
        question: str,
        chat_history_combined: str,
        initial_query: str = "",
    ) -> str:
        """
        Generate or refine the SQL query based on the user's question and chat context.
        Args:
            question (str): The user's question.
            type_query (str): The type of query: "visitation" or "venue".
            chat_history_combined (str): The combined chat history.
            initial_query (str): The initial SQL query to refine.
        Returns:
            str: The generated or refined SQL query.
        """
        is_refinement = bool(initial_query)

        context_introduction = _context_introduction()
        additional_context, examples = self._get_context()

        table_info = _table_info()

        if not APPCFG.use_examples_vector_database:
            custom_template = """
            You are the number {top_k} PostgreSQL expert in the world. 
            {context_introduction}
            TABLE_INFO: Only use the following tables and columns:
            {table_info}

            Use the following format:

            Question: {input}
            SQLQuery: 
            SQLResult: 
            Answer: 

            Additional context:
            {additional_context}

            Chat history:
            {chat_history_combined}
            """

            prompt_template = PromptTemplate(
                input_variables=[
                    "input",
                    "top_k",
                    "table_info",
                    "context_introduction",
                    "additional_context",
                ],
                template=custom_template,
            )

        else:
            custom_template = """
            You are the number {top_k} PostgreSQL expert in the world. 
            {context_introduction}
            TABLE_INFO: Only use the following tables and columns:
            {table_info}

            Additional context:
            {additional_context}

            Chat history:
            {chat_history_combined}

            Examples and corresponding queries:
            Below are some examples of questions and their corresponding SQL queries:
            """
            logger.info(f"custom_template: {custom_template}")

            example_selector = SemanticSimilarityExampleSelector.from_examples(
                examples=examples,
                embeddings=self.embeddings_model,
                vectorstore_cls=FAISS,
                k=5,
                input_keys=["input"],
            )
            logger.info(f"example_selector: {example_selector}")

            example_prompt = PromptTemplate.from_template(
                "User input: {input}\nSQL query: {query}"
            )
            logger.info(f"example_prompt: {example_prompt}")

            prompt_template = FewShotPromptTemplate(
                example_selector=example_selector,
                example_prompt=example_prompt,
                prefix=custom_template,
                suffix="User input: {input}\nSQL query: ",
                input_variables=[
                    "input",
                    "top_k",
                    "table_info",
                    "context_introduction",
                    "additional_context",
                ],
            )
            logger.info(f"prompt_template: {prompt_template}")

        logger.info(
            prompt_template.format(
                input=question,
                top_k=1,
                table_info=table_info,
                context_introduction=context_introduction,
                additional_context=additional_context,
                chat_history_combined=chat_history_combined,
            )
        )

        try:
            chain = create_sql_query_chain(
                llm=self.llm_model,
                db=self.db,
                prompt=prompt_template,
            )
            sql_query = chain.invoke(
                {
                    "question": question,
                    "top_k": 1,
                    "table_info": table_info,
                    "context_introduction": context_introduction,
                    "additional_context": additional_context,
                    "chat_history_combined": chat_history_combined,
                }
            )

            sql_query = sql_query.strip(".").replace('"', "'")
            return sql_query

        except Exception as e:
            error_message = "refining" if is_refinement else "generating"
            raise ValueError(
                f"An error occurred while {error_message} the SQL query: {e}"
            )
