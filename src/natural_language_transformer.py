#!##########################################
#!############# IMPORTS ####################
#!##########################################

# Standard Libraries
import json
import random
from typing import List, Tuple

# Local Imports
from src.logs import logger
from src.sub_utils import _convert_datetime
from src.load_config import LoadConfig

# External Libraries
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# from langchain_core.runnables import RunnableSequence

APPCFG = LoadConfig()

#!##########################################
#!####### NaturalLanguageTransformer #######
#!##########################################


class NaturalLanguageTransformer:
    """
    A class to transform SQL query results into natural language using a PromptTemplate.
    Attributes:
        llm_model (ChatOpenAI): The LLM model to use for the transformation.
        prompt_template (PromptTemplate): The prompt template used to generate the transformation.
    Methods:
        transform_result(first_request, chat_context, rows, columns, refined_query, initial_date, final_date): Transform the result of an SQL query into natural language.
    """

    def __init__(
        self,
        llm_model: ChatOpenAI,
    ):
        self.llm_model = llm_model
        self.prompt_template = self._create_prompt_template()

    @staticmethod
    def _sample_rows(
        rows: List[Tuple],
        columns: List[str],
        sample_size: int = 50,
    ) -> str:
        """
        Sample rows from the SQL result and convert them into JSON format.

        Args:
            rows (List[Tuple]): The result of the SQL query as a list of rows (each row is a tuple of values).
            columns (List[str]): The columns of the SQL query result as a list of strings.
            sample_size (int): The number of rows to sample (default is 50).

        Returns:
            str: The sampled rows in JSON format.
        """
        if len(rows) > sample_size:
            rows_sample = random.sample(rows, sample_size)
            logger.info(f"Sampled {sample_size} rows from a total of {len(rows)}")
        else:
            rows_sample = rows
            logger.info(f"Using all {len(rows)} rows")

        serialized_rows = [dict(zip(columns, row)) for row in rows_sample]
        return json.dumps(serialized_rows, indent=2, default=_convert_datetime)

    def _create_prompt_template(self) -> PromptTemplate:
        """
        Creates and returns a PromptTemplate for transforming SQL query results into natural language.

        Returns:
            PromptTemplate: The template used to generate the transformation.
        """
        template_string = """
        You are a highly skilled data analyst. Your task is to transform SQL query results into clear and concise natural language summaries.

        ===ORIGINAL REQUEST===
        {first_request}

        ===CHAT CONTEXT===
        {chat_context}

        ===COLUMNS===
        {columns_formatted}

        ===SQL QUERY RESULT (JSON)===
        {result_json}

        ===REFINED SQL QUERY===
        {refined_query}

        ===INSTRUCTIONS===
        Provide a summary of the query outcome. The summary should be concise, directly reference relevant details from the refined SQL query, and answer the original request accurately.

        - If the result is a sample, include the note: {sample_note}.

        {type_specific_instructions}
        """

        prompt_template = PromptTemplate(
            input_variables=[
                "first_request",
                "chat_context",
                "columns_formatted",
                "result_json",
                "refined_query",
                "sample_note",
                "type_specific_instructions",
            ],
            template=template_string,
        )

        logger.info("PromptTemplate created successfully.")
        return prompt_template

    def transform_result(
        self,
        first_request: str,
        chat_context: str,
        rows: List[Tuple],
        columns: List[str],
        refined_query: str,
    ) -> str:
        """
        Transforms the result of an SQL query into natural language using a prompt template.
        Args:
            first_request (str): The original request that generated the SQL query.
            type_query (str): The type of the query ('visitation' or 'venue').
            chat_context (str): The chat context to provide additional information for the transformation.
            rows (List[Tuple]): The result of the SQL query as a list of rows (each row is a tuple of values).
            columns (List[str]): The columns of the SQL query result as a list of strings.
            refined_query (str): The refined SQL query used to generate the result.

        Returns:
            str: The result of the transformation in natural language.
        """

        sample_size = 50
        result_json = self._sample_rows(rows, columns, sample_size)

        prompt_input = {
            "first_request": first_request,
            "chat_context": chat_context,
            "columns_formatted": ", ".join(columns),
            "result_json": result_json,
            "refined_query": refined_query,
            "sample_note": (
                "Note: Mention that the result is a sample of the total data available, and for more information check the CSV file."
                if len(rows) > sample_size
                else ""
            ),
            "type_specific_instructions": (
                (
                    f"Provide a concise summary of the query outcome, directly referencing short, relevant details from the refined SQL query. "
                    f"Aim for brevity and precision, focusing on essential information that answers the original request. Avoid unnecessary explanations "
                    f"and highlight key points directly related to the SQL query."
                )
            ),
        }

        # logger.debug(f"Prompt input prepared: {prompt_input}")

        # Create runnable sequence using PromptTemplate
        chain = self.prompt_template | self.llm_model

        # Generate transformed result
        ai_message = chain.invoke(prompt_input)
        transformed_result = (
            ai_message.content.strip()
        )  # Extract content and then strip

        # * Another option.
        # # Generate transformed result using LLMChain
        # from langchain.chains import LLMChain
        # chain = LLMChain(
        #     llm=self.llm_model,
        #     prompt=self.prompt_template,
        # )
        # transformed_result = chain.run(**prompt_input).strip()

        return transformed_result
