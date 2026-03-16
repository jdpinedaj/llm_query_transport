"""
Chat Orchestrator.
------------------
LLM Query Transport - Main pipeline orchestration service

Coordinates the complete text-to-SQL pipeline:
1. Connect to database
2. Generate SQL query (with optional refinement)
3. Execute query safely
4. Transform results to natural language
5. Manage chat history
"""

from datetime import UTC, datetime

from src.config.settings import LoadConfig, logger
from src.domain.ports import SessionManager, UINotifier
from src.infrastructure.database.postgres_adapter import PostgreSQLAdapter
from src.infrastructure.llm.chat_history_collector import ChatHistoryCollector
from src.infrastructure.llm.natural_language_transformer import NaturalLanguageTransformer
from src.infrastructure.llm.sql_query_generator import SQLQueryGenerator


class ChatOrchestrator:
    """Orchestrates the complete text-to-SQL pipeline."""

    def __init__(
        self,
        session: SessionManager,
        ui_notifier: UINotifier,
        config: LoadConfig,
        database_uri: str,
    ):
        self.session = session
        self.ui = ui_notifier
        self.config = config
        self.db_adapter = PostgreSQLAdapter(database_uri, decimal_places=config.decimal_places)
        self.history_collector = ChatHistoryCollector(session)

    def _manage_messages(
        self,
        role: str,
        content: str,
        message_type: str | None = None,
        csv_data: tuple | None = None,
        timestamp: str | None = None,
        csv_prefix: str | None = None,
    ) -> None:
        """Add a message to the chat history."""
        message_data: dict = {"role": role, "content": content}
        if message_type:
            message_data["type"] = message_type
        if csv_data:
            message_data["csv_data"] = csv_data
        if timestamp:
            message_data["timestamp"] = timestamp
        if csv_prefix:
            message_data["csv_prefix"] = csv_prefix
        chat_history = self.session.get("chat_history", [])
        chat_history.append(message_data)
        self.session.set("chat_history", chat_history)

    def _initialize_session(self) -> None:
        """Initialize session states if they don't exist."""
        if not self.session.has("chat_history"):
            self.session.set("chat_history", [])
            self.session.set("sql_query_results", [])
        if not self.session.has("reset_counter"):
            self.session.set("reset_counter", 0)
        if not self.session.has("sql_query_results"):
            self.session.set("sql_query_results", [])

    def _reset_state_variables(self) -> None:
        """Reset state variables before processing new input."""
        keys_to_keep = {"chat_history", "reset_counter", "user_query", "assistant", "structured_history"}
        all_keys = self.session.get_all()
        for key in all_keys:
            if key not in keys_to_keep:
                self.session.set(key, [])

    def execute_pipeline(self, user_query: str) -> None:
        """Execute the complete text-to-SQL pipeline."""
        logger.info(f"Starting pipeline for query: {user_query}")

        self._initialize_session()
        self._reset_state_variables()
        self._manage_messages("user", user_query, "user_query")

        # Compile chat history for context
        chat_history_combined = self.history_collector.compile_relevant_history()

        try:
            # Step 1: Connect to database
            engine, db = self.db_adapter.connect()
            if not db or not engine:
                self._manage_messages(
                    "assistant",
                    "An error occurred while connecting to the database. Please try again later.",
                    "database_connection_error",
                )
                return
        except Exception as e:
            self._handle_error(e, user_query)
            return

        try:
            # Step 2: Generate initial SQL query
            generator = SQLQueryGenerator(
                llm_model=self.config.llm_model_generation_refinement,
                embeddings_model=self.config.embeddings_model,
                db=db,
            )

            initial_query_output = generator.create_sql_query(
                question=user_query,
                chat_history_combined=chat_history_combined,
                config=self.config,
            )

            initial_sql_query = SQLQueryGenerator.extract_sql_query(initial_query_output)
            logger.info(f"Initial SQL query: {initial_sql_query}")
            self.session.set("initial_query", initial_sql_query)

            if self.config.show_developer_comments:
                self._manage_messages("assistant", f"initial_query: {initial_sql_query}", "initial_query")

            # Step 3: Optional refinement
            if self.config.include_refinement_process:
                refined_query_output = generator.create_sql_query(
                    question=user_query,
                    chat_history_combined=chat_history_combined,
                    config=self.config,
                    initial_query=initial_sql_query,
                )
                refined_sql_query = SQLQueryGenerator.extract_sql_query(refined_query_output)
                logger.info("SQL query refined via refinement process.")
            else:
                refined_query_output = initial_query_output
                refined_sql_query = initial_sql_query
                logger.info("Using initial query (no refinement).")

            logger.info(f"Final SQL query: {refined_sql_query}")
            self.session.set("refined_query", refined_sql_query)

            if self.config.show_refined_query:
                self._manage_messages("assistant", f"refined_query: {refined_sql_query}", "refined_query")

            # Step 4: Execute the SQL query
            rows, columns = self.db_adapter.execute_query(refined_sql_query)
            self.session.set("sql_query_results", (rows, columns))

            # Step 5: Transform results to natural language
            transformer = NaturalLanguageTransformer(
                llm_model=self.config.llm_model_transformation,
                sample_size=self.config.sample_size,
            )

            transformed_result = transformer.transform_result(
                first_request=user_query,
                chat_context=chat_history_combined,
                rows=rows,
                columns=columns,
                refined_query=refined_query_output,
            )

            # Attach CSV data and timestamp to the transformed result message
            timestamp = datetime.now(tz=UTC).strftime(self.config.csv_timestamp_format)
            self._manage_messages(
                "assistant",
                transformed_result,
                "transformed_result",
                csv_data=(rows, columns),
                timestamp=timestamp,
                csv_prefix=self.config.csv_filename_prefix,
            )

            # Collect structured history
            self.history_collector.collect(
                user_query=user_query,
                initial_sql=initial_sql_query,
                refined_sql=refined_sql_query,
                result_rows=len(rows),
                result_columns=list(columns),
                nl_response=transformed_result,
            )

        except Exception as e:
            self._handle_error(e, user_query)

        logger.info("Pipeline execution completed.")
        self.ui.request_rerun()

    def _handle_error(self, e: Exception, user_query: str) -> None:
        """Handle pipeline errors."""
        import traceback

        tb_info = traceback.format_exc()
        error_message = f"An error occurred while processing the query: '{user_query}'\nException: {e!s}\nTraceback details:\n{tb_info}"
        logger.error(error_message)

        self._manage_messages("assistant", error_message, "error")

        self.history_collector.collect(
            user_query=user_query,
            error=str(e),
        )

        if not self.config.show_developer_comments:
            self._manage_messages(
                "assistant",
                "Please try again, refine your request and ask a more specific question.",
            )
