"""
Evaluation Visualizations.
--------------------------
Publication-ready figures for text-to-SQL evaluation results.
Generates PNG + SVG for each figure.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.evaluation.metrics import COMPONENTS_LIST, compute_aggregate_component_scores

# Publication-ready defaults
plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "figure.figsize": (10, 5),
        "savefig.bbox": "tight",
    }
)
sns.set_theme(style="whitegrid", font_scale=1.1)

COLOR_FEW_SHOT = "#2196F3"
COLOR_SIMPLE = "#FF9800"


def plot_execution_accuracy(
    ex_few_shot: dict,
    ex_simple: dict,
    output_dir: Path,
) -> None:
    """Figure 1: Execution Accuracy by difficulty and mode."""
    fig, ax = plt.subplots(figsize=(8, 5))

    difficulties = ["Easy", "Medium", "Hard", "Overall"]
    few_shot_ex = [
        ex_few_shot["by_difficulty"].get("easy", {}).get("ex", 0) * 100,
        ex_few_shot["by_difficulty"].get("medium", {}).get("ex", 0) * 100,
        ex_few_shot["by_difficulty"].get("hard", {}).get("ex", 0) * 100,
        ex_few_shot["overall"]["ex"] * 100,
    ]
    simple_ex = [
        ex_simple["by_difficulty"].get("easy", {}).get("ex", 0) * 100,
        ex_simple["by_difficulty"].get("medium", {}).get("ex", 0) * 100,
        ex_simple["by_difficulty"].get("hard", {}).get("ex", 0) * 100,
        ex_simple["overall"]["ex"] * 100,
    ]

    x = np.arange(len(difficulties))
    width = 0.35

    bars1 = ax.bar(x - width / 2, few_shot_ex, width, label="Few-Shot + FAISS", color=COLOR_FEW_SHOT)
    bars2 = ax.bar(x + width / 2, simple_ex, width, label="Simple Prompting", color=COLOR_SIMPLE)

    ax.set_ylabel("Execution Accuracy (%)")
    ax.set_title("Execution Accuracy by Difficulty Level")
    ax.set_xticks(x)
    ax.set_xticklabels(difficulties)
    ax.legend()
    ax.set_ylim(0, 105)
    ax.bar_label(bars1, fmt="%.0f%%", padding=3)
    ax.bar_label(bars2, fmt="%.0f%%", padding=3)

    plt.tight_layout()
    fig.savefig(output_dir / "execution_accuracy.png")
    fig.savefig(output_dir / "execution_accuracy.svg")
    plt.close(fig)
    print("  Saved: execution_accuracy.png / .svg")


def plot_latency_distribution(
    results_few_shot: list[dict],
    results_simple: list[dict],
    output_dir: Path,
) -> None:
    """Figure 2: Latency distribution box plot by stage and mode.

    Uses log scale to make all stages visible, since SQL Execution
    (~2 ms) is three orders of magnitude smaller than LLM stages (~2-15 s).
    """
    fig, ax = plt.subplots(figsize=(10, 5))

    latency_data = []
    for r in results_few_shot:
        if r["sql_generation_time"] is not None:
            latency_data.append({"Stage": "SQL Generation", "Time (s)": r["sql_generation_time"], "Mode": "Few-Shot"})
        if r["sql_execution_time"] is not None:
            latency_data.append({"Stage": "SQL Execution", "Time (s)": r["sql_execution_time"], "Mode": "Few-Shot"})
        if r["nl_transform_time"] is not None:
            latency_data.append({"Stage": "NL Transform", "Time (s)": r["nl_transform_time"], "Mode": "Few-Shot"})

    for r in results_simple:
        if r["sql_generation_time"] is not None:
            latency_data.append({"Stage": "SQL Generation", "Time (s)": r["sql_generation_time"], "Mode": "Simple"})
        if r["sql_execution_time"] is not None:
            latency_data.append({"Stage": "SQL Execution", "Time (s)": r["sql_execution_time"], "Mode": "Simple"})
        if r["nl_transform_time"] is not None:
            latency_data.append({"Stage": "NL Transform", "Time (s)": r["nl_transform_time"], "Mode": "Simple"})

    lat_df = pd.DataFrame(latency_data)
    sns.boxplot(data=lat_df, x="Stage", y="Time (s)", hue="Mode", palette=[COLOR_FEW_SHOT, COLOR_SIMPLE], ax=ax)
    ax.set_yscale("log")
    ax.set_ylabel("Time (s) — log scale")
    ax.set_title("Pipeline Latency Distribution by Stage")

    # Add median annotations for SQL Execution to highlight the ~ms scale
    for i, mode in enumerate(["Few-Shot", "Simple"]):
        exec_times = [r["sql_execution_time"] for r in (results_few_shot if mode == "Few-Shot" else results_simple) if r.get("sql_execution_time") is not None]
        if exec_times:
            median_ms = np.median(exec_times) * 1000
            x_pos = 1 + (i - 0.5) * 0.4  # position near SQL Execution group
            ax.annotate(
                f"{median_ms:.0f} ms",
                xy=(x_pos, np.median(exec_times)),
                xytext=(x_pos, np.median(exec_times) * 5),
                fontsize=9,
                ha="center",
                arrowprops={"arrowstyle": "->", "color": "gray", "lw": 0.8},
            )

    plt.tight_layout()
    fig.savefig(output_dir / "latency_distribution.png")
    fig.savefig(output_dir / "latency_distribution.svg")
    plt.close(fig)
    print("  Saved: latency_distribution.png / .svg")


def plot_component_heatmap(
    results_few_shot: list[dict],
    output_dir: Path,
) -> None:
    """Figure 3: Component Matching F1 heatmap by component and difficulty."""
    component_scores = compute_aggregate_component_scores(results_few_shot)

    heatmap_data = {}
    for diff in ["easy", "medium", "hard"]:
        subset = [s for s in component_scores if s["difficulty"] == diff]
        heatmap_data[diff.capitalize()] = {comp: np.mean([s[comp]["f1"] for s in subset]) for comp in COMPONENTS_LIST}

    heatmap_df = pd.DataFrame(heatmap_data)

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.heatmap(
        heatmap_df,
        annot=True,
        fmt=".2f",
        cmap="YlGnBu",
        vmin=0,
        vmax=1,
        ax=ax,
        linewidths=0.5,
    )
    ax.set_title("Component Matching F1 Score (Few-Shot + FAISS)")
    ax.set_ylabel("SQL Component")
    ax.set_xlabel("Difficulty Level")

    plt.tight_layout()
    fig.savefig(output_dir / "component_matching_heatmap.png")
    fig.savefig(output_dir / "component_matching_heatmap.svg")
    plt.close(fig)
    print("  Saved: component_matching_heatmap.png / .svg")


def plot_overall_comparison(
    ex_few_shot: dict,
    ex_simple: dict,
    ver_few_shot: dict,
    ver_simple: dict,
    output_dir: Path,
) -> None:
    """Figure 4: Overall EX + VER side-by-side bar chart."""
    fig, ax = plt.subplots(figsize=(8, 5))

    metrics_names = ["Execution\nAccuracy", "Valid Execution\nRate"]
    fs_values = [ex_few_shot["overall"]["ex"] * 100, ver_few_shot["overall"]["ver"] * 100]
    sp_values = [ex_simple["overall"]["ex"] * 100, ver_simple["overall"]["ver"] * 100]

    x = np.arange(len(metrics_names))
    width = 0.35

    bars1 = ax.bar(x - width / 2, fs_values, width, label="Few-Shot + FAISS", color=COLOR_FEW_SHOT)
    bars2 = ax.bar(x + width / 2, sp_values, width, label="Simple Prompting", color=COLOR_SIMPLE)

    ax.set_ylabel("Score (%)")
    ax.set_title("Overall Performance Comparison")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics_names)
    ax.legend()
    ax.set_ylim(0, 105)
    ax.bar_label(bars1, fmt="%.1f%%", padding=3)
    ax.bar_label(bars2, fmt="%.1f%%", padding=3)

    plt.tight_layout()
    fig.savefig(output_dir / "overall_comparison.png")
    fig.savefig(output_dir / "overall_comparison.svg")
    plt.close(fig)
    print("  Saved: overall_comparison.png / .svg")


def generate_all_figures(
    *,
    ex_few_shot: dict,
    ex_simple: dict,
    ver_few_shot: dict,
    ver_simple: dict,
    results_few_shot: list[dict],
    results_simple: list[dict],
    output_dir: Path,
) -> None:
    """Generate all 4 publication-ready figures."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print("\nGenerating figures...")

    plot_execution_accuracy(ex_few_shot, ex_simple, output_dir)
    plot_latency_distribution(results_few_shot, results_simple, output_dir)
    plot_component_heatmap(results_few_shot, output_dir)
    plot_overall_comparison(ex_few_shot, ex_simple, ver_few_shot, ver_simple, output_dir)

    print(f"All figures saved to: {output_dir}")
