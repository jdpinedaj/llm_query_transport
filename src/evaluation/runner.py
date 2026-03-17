"""
Evaluation Runner.
------------------
Main entry point for text-to-SQL evaluation metrics.

Usage:
    python -m src.evaluation.runner
    make evaluate
"""

import copy
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.config.settings import LoadConfig
from src.evaluation.harness import run_full_evaluation
from src.evaluation.metrics import (
    COMPONENTS_LIST,
    compute_aggregate_component_scores,
    compute_execution_accuracy,
    compute_latency_stats,
    compute_ver,
    make_serializable,
)
from src.evaluation.visualization import generate_all_figures
from src.infrastructure.database.postgres_adapter import PostgreSQLAdapter

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEST_SET_PATH = PROJECT_ROOT / "data" / "evaluation" / "test_set.json"
RESULTS_DIR = PROJECT_ROOT / "results" / "evaluation"


def _print_header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _print_config(config: LoadConfig) -> None:
    """Print model and config summary."""
    _print_header("CONFIGURATION")
    print(f"  Model (SQL gen):      {config.openai_model_generation_refinement}")
    print(f"  Model (NL transform): {config.openai_model_transformation}")
    is_gpt5 = LoadConfig.is_gpt5(config.openai_model_generation_refinement)
    print(f"  GPT-5 detected:       {is_gpt5}")
    if is_gpt5:
        print(f"  Reasoning (gen):      {config.reasoning_effort_generation}")
        print(f"  Reasoning (transform):{config.reasoning_effort_transformation}")
        print(f"  Max tokens:           {config.max_completion_tokens}")
    else:
        print(f"  Temperature (gen):    {config.temperature_generation_refinement}")
        print(f"  Top-p (gen):          {config.top_p_generation_refinement}")
    print(f"  Few-shot enabled:     {config.use_examples_vector_database}")
    print(f"  Few-shot k:           {config.few_shot_k}")


def _print_ex(ex: dict, mode: str) -> None:
    """Print Execution Accuracy results."""
    print(f"\n--- Execution Accuracy (EX) — {mode} ---")
    o = ex["overall"]
    print(f"  Overall: {o['correct']}/{o['total']} = {o['ex']:.1%}")
    for diff, data in ex["by_difficulty"].items():
        print(f"  {diff.capitalize():8s}: {data['correct']}/{data['total']} = {data['ex']:.1%}")


def _print_ver(ver: dict, mode: str) -> None:
    """Print Valid Execution Rate results."""
    print(f"\n--- Valid Execution Rate (VER) — {mode} ---")
    o = ver["overall"]
    print(f"  VER:               {o['valid']}/{o['total']} = {o['ver']:.1%}")
    print(f"  Error Rate:        {o['error_rate']:.1%}")
    print(f"  Generation errors: {o['generation_errors']}")
    print(f"  Execution errors:  {o['execution_errors']}")
    for diff, data in ver["by_difficulty"].items():
        print(f"  {diff.capitalize():8s}: {data['valid']}/{data['total']} = {data['ver']:.1%}")


def _print_latency(stats: dict, mode: str) -> None:
    """Print latency stats table."""
    print(f"\n--- Latency (seconds) — {mode} ---")
    df = pd.DataFrame(stats).T
    df = df[["n", "mean", "median", "p95", "min", "max", "std"]].round(3)
    print(df.to_string())


def _print_components(results: list[dict], mode: str) -> None:
    """Print component matching P/R/F1 table."""
    scores = compute_aggregate_component_scores(results)
    if not scores:
        print(f"\n--- Component Matching — {mode}: no data ---")
        return

    summary = {}
    for comp in COMPONENTS_LIST:
        f1_values = [s[comp]["f1"] for s in scores]
        p_values = [s[comp]["precision"] for s in scores]
        r_values = [s[comp]["recall"] for s in scores]
        summary[comp] = {
            "Precision": np.mean(p_values),
            "Recall": np.mean(r_values),
            "F1": np.mean(f1_values),
        }

    print(f"\n--- Component Matching — Average P/R/F1 ({mode}) ---")
    print(pd.DataFrame(summary).T.round(3).to_string())

    # F1 by difficulty
    print(f"\n--- Component F1 by Difficulty ({mode}) ---")
    f1_by_diff = {}
    for diff in ["easy", "medium", "hard"]:
        subset = [s for s in scores if s["difficulty"] == diff]
        if subset:
            f1_by_diff[diff] = {comp: np.mean([s[comp]["f1"] for s in subset]) for comp in COMPONENTS_LIST}
    print(pd.DataFrame(f1_by_diff).round(3).to_string())


def _print_per_question_detail(results: list[dict]) -> None:
    """Print per-question pass/fail detail."""
    from src.evaluation.metrics import compare_result_sets

    print("\n--- Per-Question Detail ---")
    for r in results:
        match = r["is_valid_execution"] and compare_result_sets(r["gold_result"], r["predicted_result"])
        symbol = "pass" if match else "FAIL"
        error = ""
        if r["generation_error"]:
            error = f" | GenError: {r['generation_error'][:50]}"
        elif r["execution_error"]:
            error = f" | ExecError: {r['execution_error'][:50]}"
        print(f"  [{symbol:4s}] {r['id']} ({r['difficulty']:6s}) - {r['question'][:55]}...{error}")


def _print_comparison(
    ex_fs: dict,
    ex_sp: dict,
    ver_fs: dict,
    ver_sp: dict,
    lat_fs: dict,
    lat_sp: dict,
) -> None:
    """Print side-by-side comparison table."""
    _print_header("BASELINE COMPARISON")
    comparison = {
        "Metric": [
            "Execution Accuracy (EX)",
            "Valid Execution Rate (VER)",
            "Error Rate",
            "Mean Latency — SQL Gen (s)",
            "Mean Latency — Total (s)",
            "Median Latency — SQL Gen (s)",
            "P95 Latency — SQL Gen (s)",
        ],
        "Few-Shot + FAISS": [
            f"{ex_fs['overall']['ex']:.1%}",
            f"{ver_fs['overall']['ver']:.1%}",
            f"{ver_fs['overall']['error_rate']:.1%}",
            f"{lat_fs.get('SQL Generation', {}).get('mean', 0):.2f}",
            f"{lat_fs.get('Total Pipeline', {}).get('mean', 0):.2f}",
            f"{lat_fs.get('SQL Generation', {}).get('median', 0):.2f}",
            f"{lat_fs.get('SQL Generation', {}).get('p95', 0):.2f}",
        ],
        "Simple Prompting": [
            f"{ex_sp['overall']['ex']:.1%}",
            f"{ver_sp['overall']['ver']:.1%}",
            f"{ver_sp['overall']['error_rate']:.1%}",
            f"{lat_sp.get('SQL Generation', {}).get('mean', 0):.2f}",
            f"{lat_sp.get('Total Pipeline', {}).get('mean', 0):.2f}",
            f"{lat_sp.get('SQL Generation', {}).get('median', 0):.2f}",
            f"{lat_sp.get('SQL Generation', {}).get('p95', 0):.2f}",
        ],
    }
    print(pd.DataFrame(comparison).to_string(index=False))

    # EX by difficulty
    print("\n--- Execution Accuracy by Difficulty ---")
    ex_diff = {"Difficulty": [], "Few-Shot + FAISS": [], "Simple Prompting": []}
    for diff in ["easy", "medium", "hard"]:
        ex_diff["Difficulty"].append(diff.capitalize())
        ex_diff["Few-Shot + FAISS"].append(f"{ex_fs['by_difficulty'].get(diff, {}).get('ex', 0):.1%}")
        ex_diff["Simple Prompting"].append(f"{ex_sp['by_difficulty'].get(diff, {}).get('ex', 0):.1%}")
    print(pd.DataFrame(ex_diff).to_string(index=False))


def _export_results(
    config: LoadConfig,
    test_cases: list[dict],
    ex_fs: dict,
    ex_sp: dict,
    ver_fs: dict,
    ver_sp: dict,
    results_fs: list[dict],
    results_sp: list[dict],
) -> None:
    """Export evaluation results to JSON."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    export_data = {
        "metadata": {
            "model_sql_generation": config.openai_model_generation_refinement,
            "model_nl_transformation": config.openai_model_transformation,
            "few_shot_k": config.few_shot_k,
            "top_k": config.top_k,
            "test_cases_count": len(test_cases),
        },
        "summary": {
            "few_shot": {
                "execution_accuracy": ex_fs["overall"]["ex"],
                "valid_execution_rate": ver_fs["overall"]["ver"],
                "error_rate": ver_fs["overall"]["error_rate"],
            },
            "simple": {
                "execution_accuracy": ex_sp["overall"]["ex"],
                "valid_execution_rate": ver_sp["overall"]["ver"],
                "error_rate": ver_sp["overall"]["error_rate"],
            },
        },
        "few_shot_results": make_serializable(results_fs),
        "simple_results": make_serializable(results_sp),
    }

    output_path = RESULTS_DIR / "evaluation_results.json"
    with open(output_path, "w") as f:
        json.dump(export_data, f, indent=2, default=str)

    print(f"\nResults exported to: {output_path}")


def main() -> None:
    """Run the full evaluation pipeline."""
    # Load test set
    _print_header("LOADING TEST SET")
    with open(TEST_SET_PATH) as f:
        test_data = json.load(f)

    test_cases = test_data["test_cases"]
    print(f"  Loaded {len(test_cases)} test cases")
    print(f"    Easy:   {sum(1 for t in test_cases if t['difficulty'] == 'easy')}")
    print(f"    Medium: {sum(1 for t in test_cases if t['difficulty'] == 'medium')}")
    print(f"    Hard:   {sum(1 for t in test_cases if t['difficulty'] == 'hard')}")

    # Init config & DB
    config = LoadConfig()
    _print_config(config)

    db_adapter = PostgreSQLAdapter(config.database_uri, decimal_places=config.decimal_places)
    _engine, db = db_adapter.connect()
    rows, _cols = db_adapter.execute_query("SELECT COUNT(*) FROM station;")
    print(f"\n  Database connected. Station count: {rows[0][0]}")

    # ── Mode 1: Few-Shot + FAISS ──
    _print_header("MODE 1: Few-Shot + FAISS")
    results_fs = run_full_evaluation(test_cases, config, db_adapter, db)

    ex_fs = compute_execution_accuracy(results_fs)
    ver_fs = compute_ver(results_fs)
    lat_fs = compute_latency_stats(results_fs)

    _print_ex(ex_fs, "Few-Shot + FAISS")
    _print_per_question_detail(results_fs)
    _print_ver(ver_fs, "Few-Shot + FAISS")
    _print_latency(lat_fs, "Few-Shot + FAISS")
    _print_components(results_fs, "Few-Shot + FAISS")

    # ── Mode 2: Simple Prompting ──
    _print_header("MODE 2: Simple Prompting")
    config_simple = copy.copy(config)
    config_simple.use_examples_vector_database = False
    results_sp = run_full_evaluation(test_cases, config_simple, db_adapter, db)

    ex_sp = compute_execution_accuracy(results_sp)
    ver_sp = compute_ver(results_sp)
    lat_sp = compute_latency_stats(results_sp)

    _print_ex(ex_sp, "Simple Prompting")
    _print_ver(ver_sp, "Simple Prompting")
    _print_latency(lat_sp, "Simple Prompting")
    _print_components(results_sp, "Simple Prompting")

    # ── Comparison ──
    _print_comparison(ex_fs, ex_sp, ver_fs, ver_sp, lat_fs, lat_sp)

    # ── Figures ──
    generate_all_figures(
        ex_few_shot=ex_fs,
        ex_simple=ex_sp,
        ver_few_shot=ver_fs,
        ver_simple=ver_sp,
        results_few_shot=results_fs,
        results_simple=results_sp,
        output_dir=RESULTS_DIR,
    )

    # ── Export JSON ──
    _export_results(config, test_cases, ex_fs, ex_sp, ver_fs, ver_sp, results_fs, results_sp)

    # ── Summary ──
    _print_header("DONE")
    print(f"  Figures: {RESULTS_DIR}/*.png, *.svg")
    print(f"  JSON:    {RESULTS_DIR}/evaluation_results.json")


if __name__ == "__main__":
    main()
