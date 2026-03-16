"""
Domain Schemas.
---------------
LLM Query Transport - Pydantic models for type-safe data exchange

This module defines the data structures used across the pipeline:
- UserQueryInfo: Structured user query information
- SQLQueryInfo: Input for SQL generation
- NaturalLanguageInput/Output: For result transformation
- ChatHistoryEntry: Complete conversation history
"""

from pydantic import BaseModel, Field


class UserQueryInfo(BaseModel):
    """Structured information extracted from a user query."""

    user_query: str = Field(description="The original natural language query")
    chat_history: str = Field(default="", description="Compiled relevant chat history")


class SQLQueryInfo(BaseModel):
    """Input schema for SQL query generation."""

    table_info: str = Field(description="Database table schema information")
    user_input: str = Field(description="The user's natural language question")
    chat_history: str = Field(default="", description="Relevant chat history context")
    additional_context: str = Field(default="", description="Additional context for SQL generation")


class NaturalLanguageInput(BaseModel):
    """Input schema for natural language transformation."""

    first_request: str = Field(description="The original user request")
    chat_context: str = Field(default="", description="Chat context for transformation")
    columns: list[str] = Field(description="Column names from SQL result")
    result_json: str = Field(description="SQL result data in JSON format")
    refined_query: str = Field(description="The refined SQL query used")
    sample_note: str = Field(default="", description="Note about data sampling")


class NaturalLanguageOutput(BaseModel):
    """Output schema for natural language transformation."""

    transformed_result: str = Field(description="The natural language summary of SQL results")
    is_sampled: bool = Field(default=False, description="Whether the result was sampled")
    total_rows: int = Field(default=0, description="Total number of rows in the original result")


class ChatHistoryEntry(BaseModel):
    """Complete history entry combining data from all pipeline stages."""

    user_query: str = Field(description="Original user query")
    initial_sql_query: str = Field(default="", description="Initially generated SQL query")
    refined_sql_query: str = Field(default="", description="Refined SQL query (if refinement was applied)")
    result_rows: int = Field(default=0, description="Number of result rows")
    result_columns: list[str] = Field(default_factory=list, description="Result column names")
    nl_response: str = Field(default="", description="Natural language response")
    error: str | None = Field(default=None, description="Error message if any stage failed")
