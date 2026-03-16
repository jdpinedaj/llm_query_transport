"""
PostgreSQL Database Adapter.
-----------------------------
LLM Query Transport - Database connection and query execution

Provides safe SQL execution against a PostgreSQL database with
DML/DDL protection.
"""

from decimal import Decimal
from typing import Any

from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.config.settings import logger


class PostgreSQLAdapter:
    """Adapter for connecting to and querying a PostgreSQL database."""

    def __init__(self, database_uri: str, decimal_places: int = 4):
        self.database_uri = database_uri
        self.decimal_places = decimal_places
        self.engine: Engine | None = None
        self.db: SQLDatabase | None = None

    def connect(self) -> tuple[Engine, SQLDatabase]:
        """Connect to the PostgreSQL database."""
        try:
            self.engine = create_engine(self.database_uri)
            self.db = SQLDatabase(self.engine)
            logger.info("Connected to PostgreSQL database")
            return self.engine, self.db
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL database: {e}")
            raise

    def _round_row(self, row: tuple) -> tuple:
        """Round float and Decimal values in a row to configured decimal places."""
        return tuple(
            round(v, self.decimal_places) if isinstance(v, (float, Decimal)) else v
            for v in row
        )

    def execute_query(self, query: str) -> tuple[list[tuple[Any, ...]], list[str]]:
        """Execute a SQL query with safety checks.

        Only allows SELECT and WITH statements. Blocks DML/DDL operations.

        Returns:
            Tuple of (rows, columns)

        """
        if not self.engine:
            raise RuntimeError("Database not connected. Call connect() first.")

        query_trimmed = query.strip()

        # Validate query type
        if not query_trimmed.upper().startswith(("SELECT", "WITH")):
            raise ValueError("Invalid query: Only SELECT or WITH statements are allowed.")

        if not query_trimmed.endswith(";"):
            raise ValueError("The SQL query must end with a semicolon.")

        # Block DML/DDL operations
        dml_ddl_keywords = ["INSERT ", "UPDATE ", "DELETE ", "ALTER ", "DROP ", "CREATE ", "TRUNCATE "]
        if any(keyword in query_trimmed.upper() for keyword in dml_ddl_keywords):
            raise ValueError("Security alert: Modification operations are not permitted.")

        try:
            with self.engine.connect() as connection:
                result = connection.execute(text(query_trimmed))
                rows = [self._round_row(row) for row in result.fetchall()]
                columns = list(result.keys())
                return rows, columns
        except SQLAlchemyError as e:
            logger.error(f"Error executing SQL query: {e}")
            raise
