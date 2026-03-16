"""
Evaluation Metrics.
-------------------
Execution Accuracy (EX), Valid Execution Rate (VER), Latency stats,
and Component Matching (Precision / Recall / F1) for text-to-SQL evaluation.
"""

import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from itertools import combinations

import numpy as np

# ============================================================================
# VALUE NORMALIZATION & RESULT COMPARISON
# ============================================================================


def normalize_value(val):
    """Normalize a single value for comparison.

    Applies rounding (2 decimal places), date→ISO, and string lowercasing/stripping
    to ensure fair comparison between gold and predicted result sets.
    """
    if val is None:
        return None
    if isinstance(val, float):
        return round(val, 2)
    if isinstance(val, Decimal):
        return round(float(val), 2)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, str):
        return val.strip().lower()
    return val


def compare_result_sets(gold_result, predicted_result) -> bool:
    """Compare gold and predicted result sets (multiset comparison, order-insensitive).

    Handles three common divergences between gold and predicted SQL:
    1. Column ordering differences (multiset comparison, not list)
    2. Extra informative columns in predicted output (column-subset matching)
    3. Minor rounding and casing differences (via normalize_value)
    """
    if gold_result is None or predicted_result is None:
        return False

    gold_rows, _gold_cols = gold_result
    pred_rows, _pred_cols = predicted_result

    gold_normalized = [tuple(normalize_value(v) for v in row) for row in gold_rows]
    pred_normalized = [tuple(normalize_value(v) for v in row) for row in pred_rows]

    # Direct multiset comparison
    if Counter(gold_normalized) == Counter(pred_normalized):
        return True

    # Different row counts → no match
    if len(gold_normalized) != len(pred_normalized):
        return False

    # Column-subset matching: if predicted SQL returns extra columns,
    # check whether the gold columns exist as a subset within the predicted rows.
    if gold_normalized and pred_normalized:
        gold_ncols = len(gold_normalized[0])
        pred_ncols = len(pred_normalized[0])

        if gold_ncols < pred_ncols:
            gold_counter = Counter(gold_normalized)
            for col_indices in combinations(range(pred_ncols), gold_ncols):
                pred_subset = [tuple(row[i] for i in col_indices) for row in pred_normalized]
                if Counter(pred_subset) == gold_counter:
                    return True

    return False


# ============================================================================
# EXECUTION ACCURACY (EX)
# ============================================================================


def compute_execution_accuracy(results: list[dict]) -> dict:
    """Compute EX = correct / total, overall and by difficulty."""
    total = len(results)
    correct = sum(1 for r in results if r["is_valid_execution"] and compare_result_sets(r["gold_result"], r["predicted_result"]))
    overall_ex = correct / total if total > 0 else 0.0

    by_difficulty = {}
    for diff in ["easy", "medium", "hard"]:
        subset = [r for r in results if r["difficulty"] == diff]
        if subset:
            c = sum(1 for r in subset if r["is_valid_execution"] and compare_result_sets(r["gold_result"], r["predicted_result"]))
            by_difficulty[diff] = {"correct": c, "total": len(subset), "ex": c / len(subset)}

    return {"overall": {"correct": correct, "total": total, "ex": overall_ex}, "by_difficulty": by_difficulty}


# ============================================================================
# VALID EXECUTION RATE (VER)
# ============================================================================


def compute_ver(results: list[dict]) -> dict:
    """VER = valid executions / total. Error rate = 1 - VER."""
    total = len(results)
    valid = sum(1 for r in results if r["is_valid_execution"])
    gen_errors = sum(1 for r in results if r["generation_error"])
    exec_errors = sum(1 for r in results if r["execution_error"])
    ver = valid / total if total > 0 else 0.0

    by_difficulty = {}
    for diff in ["easy", "medium", "hard"]:
        subset = [r for r in results if r["difficulty"] == diff]
        if subset:
            v = sum(1 for r in subset if r["is_valid_execution"])
            by_difficulty[diff] = {"valid": v, "total": len(subset), "ver": v / len(subset)}

    return {
        "overall": {
            "valid": valid,
            "total": total,
            "ver": ver,
            "error_rate": 1 - ver,
            "generation_errors": gen_errors,
            "execution_errors": exec_errors,
        },
        "by_difficulty": by_difficulty,
    }


# ============================================================================
# LATENCY STATISTICS
# ============================================================================


def compute_latency_stats(results: list[dict]) -> dict:
    """Compute latency statistics per pipeline stage."""
    stages = {
        "SQL Generation": "sql_generation_time",
        "SQL Execution": "sql_execution_time",
        "NL Transformation": "nl_transform_time",
        "Total Pipeline": "total_time",
    }
    stats = {}
    for stage_name, key in stages.items():
        times = [r[key] for r in results if r[key] is not None]
        if times:
            stats[stage_name] = {
                "mean": float(np.mean(times)),
                "median": float(np.median(times)),
                "p95": float(np.percentile(times, 95)),
                "min": float(np.min(times)),
                "max": float(np.max(times)),
                "std": float(np.std(times)),
                "n": len(times),
            }
    return stats


# ============================================================================
# COMPONENT MATCHING (PARTIAL MATCH F1)
# ============================================================================

COMPONENTS_LIST = ["SELECT", "WHERE", "GROUP BY", "ORDER BY", "JOIN", "AGGREGATION"]


def _split_respecting_parens(text: str, delimiter: str = ",") -> list[str]:
    """Split text by delimiter, but skip delimiters inside parentheses."""
    parts = []
    depth = 0
    current = []
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == delimiter and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return [p for p in parts if p]


def _normalize_select_item(item: str) -> str:
    """Normalize a SELECT item for fair comparison.

    Strips aliases (AS ...), type casts (::type), table prefixes (t.),
    and DISTINCT keyword to compare the core expression.
    """
    s = item.strip()
    # Remove alias (AS ...)
    s = re.sub(r"\s+AS\s+\S+$", "", s)
    # Remove type casts (::numeric(10,2), ::text, etc.)
    s = re.sub(r"::\w+(\([^)]*\))?", "", s)
    # Remove ROUND/NULLIF wrappers but keep the inner expression
    s = re.sub(r"ROUND\s*\((.*),\s*\d+\)\s*$", r"\1", s)
    # Remove table/alias prefix (e.g., S., T1., ST.)
    s = re.sub(r"\b[A-Z]\w{0,3}\.", "", s)
    # Remove DISTINCT keyword
    s = re.sub(r"^\s*DISTINCT\s+", "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_sql_components(sql: str) -> dict:
    """Extract SQL components for partial match scoring using regex.

    Uses parenthesis-aware splitting to correctly handle type casts,
    function calls, and nested expressions.
    """
    sql_upper = sql.upper().strip().rstrip(";")

    components: dict[str, list[str]] = {
        "SELECT": [],
        "WHERE": [],
        "GROUP BY": [],
        "ORDER BY": [],
        "JOIN": [],
        "AGGREGATION": [],
    }

    select_match = re.search(r"SELECT\s+(.*?)\s+FROM\s", sql_upper, re.DOTALL)
    if select_match:
        raw_items = _split_respecting_parens(select_match.group(1))
        components["SELECT"] = [_normalize_select_item(c) for c in raw_items]

    where_match = re.search(r"WHERE\s+(.*?)(?:\sGROUP\s|\sORDER\s|\sLIMIT\s|\sHAVING\s|$)", sql_upper, re.DOTALL)
    if where_match:
        conditions = [c.strip() for c in re.split(r"\sAND\s|\sOR\s", where_match.group(1))]
        components["WHERE"] = conditions

    group_match = re.search(r"GROUP\s+BY\s+(.*?)(?:\sORDER\s|\sHAVING\s|\sLIMIT\s|$)", sql_upper, re.DOTALL)
    if group_match:
        components["GROUP BY"] = [c.strip() for c in _split_respecting_parens(group_match.group(1))]

    order_match = re.search(r"ORDER\s+BY\s+(.*?)(?:\sLIMIT\s|$)", sql_upper, re.DOTALL)
    if order_match:
        components["ORDER BY"] = [c.strip() for c in _split_respecting_parens(order_match.group(1))]

    join_matches = re.findall(r"JOIN\s+(\S+)", sql_upper)
    components["JOIN"] = join_matches

    agg_matches = re.findall(r"(COUNT|SUM|AVG|MIN|MAX)\s*\(", sql_upper)
    components["AGGREGATION"] = sorted(set(agg_matches))

    return components


def compute_component_f1(gold_components: dict, pred_components: dict) -> dict:
    """Compute precision, recall, F1 for each SQL component."""
    scores = {}
    for component, gold_values in gold_components.items():
        gold_set = set(gold_values)
        pred_set = set(pred_components[component])

        if len(gold_set) == 0 and len(pred_set) == 0:
            scores[component] = {"precision": 1.0, "recall": 1.0, "f1": 1.0}
        elif len(pred_set) == 0:
            scores[component] = {"precision": 1.0, "recall": 0.0, "f1": 0.0}
        elif len(gold_set) == 0:
            scores[component] = {"precision": 0.0, "recall": 1.0, "f1": 0.0}
        else:
            tp = len(gold_set & pred_set)
            precision = tp / len(pred_set)
            recall = tp / len(gold_set)
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            scores[component] = {"precision": precision, "recall": recall, "f1": f1}
    return scores


def compute_aggregate_component_scores(results: list[dict]) -> list[dict]:
    """Compute component F1 for each test case that has both predicted and gold SQL."""
    all_scores = []
    for r in results:
        if r["predicted_sql"] and r["gold_sql"]:
            gold_comp = extract_sql_components(r["gold_sql"])
            pred_comp = extract_sql_components(r["predicted_sql"])
            scores = compute_component_f1(gold_comp, pred_comp)
            scores["id"] = r["id"]
            scores["difficulty"] = r["difficulty"]
            all_scores.append(scores)
    return all_scores


# ============================================================================
# SERIALIZATION
# ============================================================================


def make_serializable(results: list[dict]) -> list[dict]:
    """Convert results to JSON-serializable format (remove non-serializable fields)."""
    clean = []
    for r in results:
        entry = {k: v for k, v in r.items() if k not in ("gold_result", "predicted_result")}
        if r["gold_result"]:
            entry["gold_row_count"] = len(r["gold_result"][0])
            entry["gold_col_count"] = len(r["gold_result"][1])
        if r["predicted_result"]:
            entry["predicted_row_count"] = len(r["predicted_result"][0])
            entry["predicted_col_count"] = len(r["predicted_result"][1])
        entry["execution_match"] = r["is_valid_execution"] and compare_result_sets(r["gold_result"], r["predicted_result"])
        clean.append(entry)
    return clean
