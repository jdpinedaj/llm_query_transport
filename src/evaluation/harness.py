"""
Evaluation Harness.
-------------------
Runs test cases through the full text-to-SQL pipeline and collects metrics.
"""

import time

from src.config.settings import LoadConfig
from src.infrastructure.database.postgres_adapter import PostgreSQLAdapter
from src.infrastructure.llm.natural_language_transformer import NaturalLanguageTransformer
from src.infrastructure.llm.sql_query_generator import SQLQueryGenerator


def run_single_evaluation(test_case: dict, config: LoadConfig, db_adapter: PostgreSQLAdapter, db) -> dict:
    """Run a single test case through the pipeline and collect all metrics."""
    result = {
        "id": test_case["id"],
        "question": test_case["question"],
        "difficulty": test_case["difficulty"],
        "gold_sql": test_case["gold_sql"],
        "predicted_sql": None,
        "raw_llm_output": None,
        "sql_generation_time": None,
        "sql_execution_time": None,
        "nl_transform_time": None,
        "total_time": None,
        "gold_result": None,
        "predicted_result": None,
        "execution_error": None,
        "generation_error": None,
        "is_valid_execution": False,
        "nl_response": None,
    }

    total_start = time.perf_counter()

    # Step 1: Generate SQL
    generator = SQLQueryGenerator(
        llm_model=config.llm_model_generation_refinement,
        embeddings_model=config.embeddings_model,
        db=db,
    )

    try:
        gen_start = time.perf_counter()
        raw_output = generator.create_sql_query(
            question=test_case["question"],
            chat_history_combined="",
            config=config,
        )
        result["sql_generation_time"] = time.perf_counter() - gen_start
        result["raw_llm_output"] = raw_output
        result["predicted_sql"] = SQLQueryGenerator.extract_sql_query(raw_output)
    except Exception as e:
        result["generation_error"] = str(e)
        result["total_time"] = time.perf_counter() - total_start
        return result

    # Step 2: Execute predicted SQL
    try:
        exec_start = time.perf_counter()
        pred_rows, pred_cols = db_adapter.execute_query(result["predicted_sql"])
        result["sql_execution_time"] = time.perf_counter() - exec_start
        result["predicted_result"] = (pred_rows, pred_cols)
        result["is_valid_execution"] = True
    except Exception as e:
        result["execution_error"] = str(e)
        result["sql_execution_time"] = time.perf_counter() - exec_start

    # Step 3: Execute gold SQL for comparison
    try:
        gold_rows, gold_cols = db_adapter.execute_query(test_case["gold_sql"])
        result["gold_result"] = (gold_rows, gold_cols)
    except Exception as e:
        print(f"  WARNING: Gold SQL failed for {test_case['id']}: {e}")

    # Step 4: NL transformation (for latency measurement)
    if result["is_valid_execution"]:
        try:
            transformer = NaturalLanguageTransformer(
                llm_model=config.llm_model_transformation,
                sample_size=config.sample_size,
            )
            nl_start = time.perf_counter()
            nl_response = transformer.transform_result(
                first_request=test_case["question"],
                chat_context="",
                rows=pred_rows,
                columns=pred_cols,
                refined_query=result["predicted_sql"],
            )
            result["nl_transform_time"] = time.perf_counter() - nl_start
            result["nl_response"] = nl_response
        except Exception:
            result["nl_transform_time"] = time.perf_counter() - nl_start

    result["total_time"] = time.perf_counter() - total_start
    return result


def run_full_evaluation(
    test_cases: list[dict],
    config: LoadConfig,
    db_adapter: PostgreSQLAdapter,
    db,
    *,
    delay: float = 0.3,
) -> list[dict]:
    """Run all test cases and return list of result dicts."""
    results = []
    for i, tc in enumerate(test_cases):
        print(f"[{i + 1}/{len(test_cases)}] {tc['id']} - {tc['question'][:60]}...")
        result = run_single_evaluation(tc, config, db_adapter, db)
        results.append(result)
        status = "OK" if result["is_valid_execution"] else "FAIL"
        gen_time = f"{result['sql_generation_time']:.2f}s" if result["sql_generation_time"] else "N/A"
        print(f"  -> {status} | gen={gen_time}")
        time.sleep(delay)
    return results
