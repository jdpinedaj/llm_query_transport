"""
Chat History Collector.
-----------------------
LLM Query Transport - Aggregates data from all pipeline stages

Collects and structures data from query extraction, SQL generation,
execution, and NL transformation into ChatHistoryEntry records.
"""

from src.config.settings import logger
from src.domain.ports import SessionManager
from src.domain.schemas import ChatHistoryEntry


class ChatHistoryCollector:
    """Aggregates pipeline data into structured chat history entries."""

    def __init__(self, session: SessionManager, memory_window_size: int = 5):
        self.session = session
        self.memory_window_size = memory_window_size

    def collect(
        self,
        user_query: str,
        initial_sql: str = "",
        refined_sql: str = "",
        result_rows: int = 0,
        result_columns: list[str] | None = None,
        nl_response: str = "",
        error: str | None = None,
    ) -> ChatHistoryEntry:
        """Collect data from all pipeline stages into a ChatHistoryEntry."""
        entry = ChatHistoryEntry(
            user_query=user_query,
            initial_sql_query=initial_sql,
            refined_sql_query=refined_sql,
            result_rows=result_rows,
            result_columns=result_columns or [],
            nl_response=nl_response,
            error=error,
        )

        # Append to session history
        history = self.session.get("structured_history", [])
        history.append(entry.model_dump())
        self.session.set("structured_history", history)

        logger.info(
            "Memory stored",
            query=user_query[:80],
            has_sql=bool(initial_sql),
            result_rows=result_rows,
            has_error=bool(error),
            total_entries=len(history),
        )
        return entry

    def compile_relevant_history(self) -> str:
        """Compile the last N relevant interactions from chat history.

        Uses memory_window_size to limit how many interactions are sent
        as context to the LLM, preventing unbounded token growth.
        """
        chat_history = self.session.get("chat_history", [])
        relevant_types = {
            "user_query": "User Request",
            "refined_query_output": "Refined Query Output",
            "transformed_result": "Assistant Response",
            "assistant": "Assistant",
        }

        relevant_messages = []
        for msg in chat_history:
            msg_type = msg.get("type")
            if msg_type in relevant_types:
                subtitle = relevant_types[msg_type]
                relevant_messages.append(f"### {subtitle}\n\n{msg['content']}\n")

        total_relevant = len(relevant_messages)

        # Keep only the last N messages based on memory_window_size
        if self.memory_window_size > 0 and total_relevant > self.memory_window_size:
            relevant_messages = relevant_messages[-self.memory_window_size :]
            logger.info(
                "Memory window applied",
                total_messages=total_relevant,
                window_size=self.memory_window_size,
                discarded=total_relevant - self.memory_window_size,
            )
        else:
            logger.info(
                "Memory retrieved",
                total_messages=total_relevant,
                window_size=self.memory_window_size,
            )

        compiled = "\n".join(relevant_messages)
        logger.debug("Memory context compiled", context_length=len(compiled))
        return compiled
