"""Compare two prompt-version evaluation runs (v3 vs v4) side by side."""

import csv
import json
import os
import sys

# Allow running this script directly (python evals/compare.py) by making the
# project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import MODEL_NAME, PRICE_INPUT_PER_MTOK_USD, PRICE_OUTPUT_PER_MTOK_USD

VERSIONS = ["v3", "v4"]


def load_results(version: str) -> list[dict]:
    path = f"evals/results/{version}_{MODEL_NAME}.jsonl"
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_judge_rows(version: str) -> list[dict]:
    path = f"evals/grading_{version}_judge.csv"
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def compute_metrics(version: str) -> dict:
    """Compute the comparison metrics for one prompt version."""
    results = load_results(version)
    judge_rows = load_judge_rows(version)

    total_processes = len(results)
    successful = [r for r in results if r["error"] is None]
    total_use_cases = sum(len(r["use_cases"]) for r in results)
    no_fit_count = sum(1 for r in results if r["error"] is None and len(r["use_cases"]) == 0)

    distinct_pct_values = {
        uc["pct_time_saved"] for r in results for uc in r["use_cases"]
    }

    total_input_tokens = sum(r["stats"].get("input_tokens", 0) for r in results if r.get("stats"))
    total_output_tokens = sum(r["stats"].get("output_tokens", 0) for r in results if r.get("stats"))
    cost_usd = (
        total_input_tokens / 1_000_000 * PRICE_INPUT_PER_MTOK_USD
        + total_output_tokens / 1_000_000 * PRICE_OUTPUT_PER_MTOK_USD
    )

    relevance_values = [int(r["judge_relevance"]) for r in judge_rows]
    realism_values = [int(r["judge_realism"]) for r in judge_rows]
    overlaps = [r["judge_overlaps_another"].strip().lower() == "true" for r in judge_rows]
    ai_act_correct = [r["judge_ai_act_correct"].strip().lower() == "true" for r in judge_rows]

    return {
        "valid_rate": len(successful) / total_processes if total_processes else 0.0,
        "avg_use_cases_per_process": total_use_cases / total_processes if total_processes else 0.0,
        "no_fit_count": no_fit_count,
        "avg_relevance": sum(relevance_values) / len(relevance_values) if relevance_values else None,
        "avg_realism": sum(realism_values) / len(realism_values) if realism_values else None,
        "overlap_rate": sum(overlaps) / len(overlaps) if overlaps else None,
        "ai_act_error_rate": 1 - sum(ai_act_correct) / len(ai_act_correct) if ai_act_correct else None,
        "distinct_pct_time_saved_values": len(distinct_pct_values),
        "cost_usd": cost_usd,
    }


def format_cell(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float) and 0 <= value <= 1:
        return f"{value:.2%}"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


ROWS = [
    ("valid_rate", "Valid output rate"),
    ("avg_use_cases_per_process", "Avg use cases / process"),
    ("no_fit_count", "No-fit answers"),
    ("avg_relevance", "Avg relevance (judge)"),
    ("avg_realism", "Avg realism (judge)"),
    ("overlap_rate", "Overlap rate (judge)"),
    ("ai_act_error_rate", "AI Act error rate (judge)"),
    ("distinct_pct_time_saved_values", "Distinct pct_time_saved values"),
    ("cost_usd", "Cost (USD)"),
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    metrics = {version: compute_metrics(version) for version in VERSIONS}

    label_width = max(len(label) for _, label in ROWS) + 2
    header = f"{'metric':<{label_width}}" + "".join(f"{v:>12}" for v in VERSIONS)
    print(header)
    print("-" * len(header))
    for key, label in ROWS:
        row = f"{label:<{label_width}}"
        for version in VERSIONS:
            value = metrics[version][key]
            if key == "cost_usd":
                cell = f"${value:.6f}"
            else:
                cell = format_cell(value)
            row += f"{cell:>12}"
        print(row)


if __name__ == "__main__":
    main()
