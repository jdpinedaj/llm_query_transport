"""
Natural Language Transformer.
-----------------------------
LLM Query Transport - Transforms SQL query results into natural language

Converts SQL results to human-readable summaries using LLM,
with intelligent row sampling for large result sets.
"""

import json
import random
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from langchain_openai import ChatOpenAI

from src.config.prompts.prompt_loader import prompt_loader
from src.config.settings import logger


def _convert_datetime(obj: Any) -> Any:
    """Convert datetime objects to ISO format for JSON serialization."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type '{type(obj).__name__}' is not serializable")


class NaturalLanguageTransformer:
    """Transforms SQL query results into natural language summaries."""

    def __init__(self, llm_model: ChatOpenAI, sample_size: int = 50):
        self.llm_model = llm_model
        self.sample_size = sample_size
        self.prompt_template = prompt_loader.get_prompt_template(
            "natural_language_transform",
            "result_transformation",
        )

    @staticmethod
    def _sample_rows(
        rows: list[tuple],
        columns: list[str],
        sample_size: int,
    ) -> str:
        """Sample rows from the SQL result and convert to JSON."""
        if len(rows) > sample_size:
            rows_sample = random.sample(rows, sample_size)
            logger.info(f"Sampled {sample_size} rows from a total of {len(rows)}")
        else:
            rows_sample = rows
            logger.info(f"Using all {len(rows)} rows")

        serialized_rows = [dict(zip(columns, row, strict=False)) for row in rows_sample]
        return json.dumps(serialized_rows, indent=2, default=_convert_datetime)

    def transform_result(
        self,
        first_request: str,
        chat_context: str,
        rows: list[tuple],
        columns: list[str],
        refined_query: str,
    ) -> str:
        """Transform SQL query results into natural language."""
        result_json = self._sample_rows(rows, columns, self.sample_size)

        prompt_input = {
            "first_request": first_request,
            "chat_context": chat_context,
            "columns_formatted": ", ".join(columns),
            "result_json": result_json,
            "refined_query": refined_query,
            "sample_note": (
                "Note: The result is a sample of the total data available, for more information check the CSV file."
                if len(rows) > self.sample_size
                else ""
            ),
            "type_specific_instructions": (
                "Provide a concise summary of the query outcome, directly referencing short, relevant details "
                "from the refined SQL query. Aim for brevity and precision, focusing on essential information "
                "that answers the original request."
            ),
        }

        chain = self.prompt_template | self.llm_model
        ai_message = chain.invoke(prompt_input)
        return ai_message.content.strip()
