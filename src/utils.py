#!##########################################
#!############# IMPORTS ####################
#!##########################################

# Standard Libraries
from typing import List, Tuple, Any

# Local Imports
from src.sql_query_generator import SQLQueryGenerator
from src.natural_language_transformer import NaturalLanguageTransformer
from src.logs import logger
from src.load_config import LoadConfig
from src.sub_utils import (
    _connect_to_sqlite_db,
    _initialize_session_states,
    _reset_state_variables,
    _compile_relevant_chat_history,
    _manage_messages,
    _manage_errors,
)


from pyprojroot import here  # TODO: To change passing db_path from parameters...


# External Libraries
import streamlit as st
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI

APPCFG = LoadConfig()


#!##########################################
#!########## MAIN FUNCTIONS ################
#!##########################################


def generate_or_refine_sql_query(
    question: str,
    chat_history_combined: str,
    db: SQLDatabase,
    initial_query: str = "",
) -> str:
    """
    Generates or refines an SQL query based on the user's question using a Language Model.
    Args:
        question (str): The user's natural language query.
        chat_history_combined (str): The combined chat history to provide context for the SQL query generation or refinement.
        db (SQLDatabase): The SQL database object to connect to the database.
        initial_query (str): The initial SQL query to refine (if applicable).
    Returns:
        str: The generated or refined SQL query.
    """

    # Initialize the SQL query generator
    generator = SQLQueryGenerator(
        llm_model=APPCFG.llm_model_generation_refinement,
        embeddings_model=APPCFG.embeddings_model,
        db=db,
    )
    return generator.create_sql_query(
        question=question,
        chat_history_combined=chat_history_combined,
        initial_query=initial_query,
    )


def execute_query(
    engine: Any,
    response_text: str,
) -> Tuple[List[Tuple[Any, ...]], List[str]]:
    """
    This function executes the SQL query found in the response text and returns the result.
    Args:
        engine (Any): The SQLAlchemy engine object to connect to the database.
        response_text (str): The response text containing the SQL query.
    Returns:
        Tuple[List[Tuple[Any, ...]], List[str]]: The result of the SQL query as a list of rows (each row is a tuple of values),
        and the columns of the SQL query result as a list of strings.
    """
    # Trim the response text to remove leading and trailing whitespace
    query_trimmed = response_text.strip()

    # Check if the query starts with "SELECT" or "WITH"
    if not query_trimmed.startswith("SELECT") and not query_trimmed.startswith("WITH"):
        error_msg = "Invalid query: Only SELECT or WITH statements are allowed."
        st.error(error_msg)
        return [], []

    # Ensure the query ends with a semicolon for security
    if not query_trimmed.endswith(";"):
        error_msg = "The SQL query must end with a semicolon."
        st.error(error_msg)
        return [], []

    # Ensure no DML or DDL operations are embedded
    dml_ddl_keywords = [
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "ALTER ",
        "DROP ",
        "CREATE ",
        "TRUNCATE ",
    ]
    if any(keyword in query_trimmed for keyword in dml_ddl_keywords):
        error_msg = "Security alert: Modification operations are not permitted."
        st.error(error_msg)
        return [], []

    try:
        with engine.connect() as connection:
            # Execute the SQL query
            result = connection.execute(text(query_trimmed))
            # Fetch all results
            rows = result.fetchall()
            columns = result.keys()
            return rows, columns

    except SQLAlchemyError as e:
        st.error(f"Error occurred while executing the SQL query: {e}")
        return [], []

    #  Replicating but using psycopg2 instead of sqlalchemy
    # try:
    #     with engine.cursor() as cursor:
    #         # Execute the SQL query
    #         cursor.execute(query_trimmed)
    #         # Fetch all results
    #         rows = cursor.fetchall()
    #         columns = [desc[0] for desc in cursor.description]
    #         return rows, columns

    # except Exception as e:
    #     st.error(f"Error occurred while executing the SQL query: {e}")
    #     return [], []


def transform_sql_result_into_natural_language(
    first_request: str,
    chat_context: str,
    rows: List[Tuple],
    columns: List[str],
    refined_query: str,
) -> str:
    """
    Transforms the result of an SQL query into natural language using the OpenAI model via a relay.
    Args:
        first_request (str): The original request that generated the SQL query.
        type_query (str): The type of the query ('visitation' or 'venue').
        chat_context (str): The chat context to provide additional information for the transformation.
        rows (list): The result of the SQL query as a list of rows (each row is a tuple of values).
        columns (list): The columns of the SQL query result as a list of strings.
        refined_query (str): The refined SQL query used to generate the result.
        start_date (str): The start date extracted from the user's question.
        end_date (str): The end date extracted from the user's question.
    Returns:
        str: The result of the transformation in natural language.
    """
    # Initialize the natural language transformer
    transformer = NaturalLanguageTransformer(
        llm_model=APPCFG.llm_model_transformation,
    )

    return transformer.transform_result(
        first_request=first_request,
        chat_context=chat_context,
        rows=rows,
        columns=columns,
        refined_query=refined_query,
    )


@st.fragment()
def execute_all_in_chat(user_query: str) -> None:
    """
    Handles the entire process of generating an SQL query from a natural language question,
    executing the query, and transforming the result back into natural language, updating the
    chat history accordingly.
    Args:
        user_query (str): The user's natural language query.
    Returns:
        None
    """
    #  Checking the input data
    logger.info(
        f"\n\n===RESULTS FROM _create_default_query WITHIN execute_all_in_chat==="
    )

    logger.info(f"User query: {user_query}")
    # logger.info(
    #     f"Selected location placekeys: {selected_location_placekeys if selected_location_placekeys else 'None'}"
    # )
    # logger.info(
    #     f"Selected brand IDs: {selected_brands_ids if selected_brands_ids else 'None'}"
    # )

    # # STEP 1: print sql_query_results if it exists in st.session_state
    # if "sql_query_results" in st.session_state:
    #     sql_query_results = st.session_state["sql_query_results"]
    #     _manage_messages("assistant", f"STEP 1: SQL Query Results:\n{sql_query_results}")
    # else:
    #     _manage_messages("assistant", "STEP 1: No SQL Query Results Found.")

    # Initialize the session states for the Streamlit app
    _initialize_session_states()

    # Reset the availability of query results and other variables before processing new input
    _reset_state_variables()

    # # STEP 2: print sql_query_results if it exists in st.session_state
    # if "sql_query_results" in st.session_state:
    #     sql_query_results = st.session_state["sql_query_results"]
    #     _manage_messages("assistant", f"STEP 2: SQL Query Results:\n{sql_query_results}")
    # else:
    #     _manage_messages("assistant", "STEP 2: No SQL Query Results Found.")

    _manage_messages(
        "user",
        f"{user_query}",
        "user_query",
    )

    # Extract chat history texts for SQL context
    chat_history_combined = _compile_relevant_chat_history()
    # _manage_messages("assistant", f"Relevant Chat History:\n{chat_history_combined}")

    try:
        # Connecting to the db
        # engine, db = _connect_to_sqlite_db(db_path=APPCFG.DB_PATH)
        db_path = here("data/spider_data/database/bike_1/bike_1.sqlite")

        engine, db = _connect_to_sqlite_db(db_path=db_path)

        # Check if the connection to the database was successful
        if not db or not engine:
            _manage_messages(
                "assistant",
                "An error occurred while connecting to the database. Please try again later.",
                "database_connection_error",
            )
            return

    except Exception as e:
        _manage_errors(e, user_query)

    try:

        #! Generate the initial SQL query
        #  Using the langchain model to get the information
        initial_query_output = generate_or_refine_sql_query(
            question=user_query,
            chat_history_combined=chat_history_combined,
            db=db,
        )

        # Extract SQL query from the initial output
        initial_sql_query = SQLQueryGenerator._extract_sql_query(initial_query_output)
        logger.info(f"\n-------\ninitial_sql_query:\n {initial_sql_query}\n")

        st.session_state["initial_query"] = initial_sql_query

        if APPCFG.show_developer_comments:
            _manage_messages(
                "assistant",
                f"initial_query_output: {initial_query_output}",
                "initial_query_output",
            )
            _manage_messages(
                "assistant",
                f"initial_query: {initial_sql_query}",
                "initial_query",
            )

        #! Refine the SQL query
        if APPCFG.include_refinement_process:
            #  Using the langchain model to get the information
            refined_query_output = generate_or_refine_sql_query(
                question=user_query,
                chat_history_combined=chat_history_combined,
                db=db,
                initial_query=initial_sql_query,
            )

            # Extract refined SQL query
            refined_sql_query = SQLQueryGenerator._extract_sql_query(
                refined_query_output
            )
            logger.info(
                "The refined SQL query was created using the refinement process."
            )

        else:
            refined_query_output = initial_query_output
            refined_sql_query = initial_sql_query
            logger.info("The refined SQL query is the same as the initial query.")

        logger.info(
            f"\n--------------\n\n--------------\n\n--------------\n\n--------------\nrefined_sql_query:\n\n {refined_sql_query}\n--------------\n\n--------------\n\n--------------\n\n--------------\n"
        )
        st.session_state["refined_query"] = refined_sql_query

        if APPCFG.show_developer_comments:
            _manage_messages(
                "assistant",
                f"refined_query_output: {refined_query_output}",
                "refined_query_output",
            )

        if APPCFG.show_refined_query:
            _manage_messages(
                "assistant",
                f"refined_query: {refined_sql_query}",
                "refined_query",
            )

        #! Execute the refined SQL query
        rows, columns = execute_query(engine, refined_sql_query)
        st.session_state["sql_query_results"] = (rows, columns)

        # # STEP 3: print sql_query_results if it exists in st.session_state
        # if "sql_query_results" in st.session_state:
        #     sql_query_results = st.session_state["sql_query_results"]
        #     _manage_messages(
        #         "assistant", f"STEP 3: SQL Query Results:\n{sql_query_results}"
        #     )
        # else:
        #     _manage_messages("assistant", "STEP 3: No SQL Query Results Found.")

        #! Transform SQL query result into natural language
        transformed_result = transform_sql_result_into_natural_language(
            first_request=user_query,
            chat_context=chat_history_combined,
            rows=rows,
            columns=columns,
            refined_query=refined_query_output,
        )

        # Update chat history with the SQL query and its natural language transformation
        _manage_messages(
            "assistant",
            transformed_result,
            "transformed_result",
        )

        # Update chat history combined
        chat_history_combined = _compile_relevant_chat_history()
        # _manage_messages(
        #     "assistant",
        #     f"Relevant Chat History:\n{chat_history_combined}",
        # )

    except Exception as e:
        _manage_errors(e, user_query)

        # Update chat history combined
        chat_history_combined = _compile_relevant_chat_history()

        if APPCFG.show_developer_comments:
            _manage_messages(
                "assistant", f"Relevant Chat History:\n{chat_history_combined}"
            )
        else:
            _manage_messages(
                "assistant",
                f"Please try again, refine your request and ask a more specific question.",
            )
    logger.info("End of execute_all_in_chat function.")

    #! Rerun the app to reflect updates in the UI
    st.rerun()
