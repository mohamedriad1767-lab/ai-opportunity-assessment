"""Compare prompt-version evaluation runs (v3, v4, v4.1) side by side."""

import csv
import json
import os
import sys

# Allow running this script directly (python evals/compare.py) by making the
# project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import MODEL_NAME, PRICE_INPUT_PER_MTOK_USD, PRICE_OUTPUT_PER_MTOK_USD

VERSIONS = ["v3", "v4", "v4.1"]
EVAL_PROCESSES_PATH = "evals/eval_processes.csv"
TARGET_PROCESS_FOR_AI_ACT_DUMP = "Annual performance review drafting and calibration"


def load_results(version: str) -> list[dict]:
    path = f"evals/results/{version}_{MODEL_NAME}.jsonl"
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_judge_rows(version: str) -> list[dict]:
    path = f"evals/grading_{version}_judge.csv"
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_expected_fit() -> dict[str, str]:
    """Load the expected_fit ground truth column, keyed by process name."""
    with open(EVAL_PROCESSES_PATH, encoding="utf-8", newline="") as f:
        return {row["name"]: row["expected_fit"].strip().lower() for row in csv.DictReader(f)}


def compute_no_fit_accuracy(results: list[dict], expected_fit: dict[str, str]) -> float | None:
    """Share of processes where the model's fit/no-fit decision matches expected_fit."""
    decidable = [r for r in results if r["error"] is None]
    if not decidable:
        return None
    matches = 0
    for r in decidable:
        decided_no_fit = len(r["use_cases"]) == 0
        decided = "no" if decided_no_fit else "yes"
        if decided == expected_fit.get(r["process"]):
            matches += 1
    return matches / len(decidable)


def compute_metrics(version: str, expected_fit: dict[str, str]) -> dict:
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
        "no_fit_accuracy": compute_no_fit_accuracy(results, expected_fit),
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
    ("no_fit_accuracy", "No-fit accuracy"),
    ("avg_relevance", "Avg relevance (judge)"),
    ("avg_realism", "Avg realism (judge)"),
    ("overlap_rate", "Overlap rate (judge)"),
    ("ai_act_error_rate", "AI Act error rate (judge)"),
    ("distinct_pct_time_saved_values", "Distinct pct_time_saved values"),
    ("cost_usd", "Cost (USD)"),
]


def _get_no_fit_reason(record: dict) -> str | None:
    """Read no_fit_reason from a result record, falling back to stats for
    older jsonl files written before it was stored at the top level.
    """
    return record.get("no_fit_reason") or (record.get("stats") or {}).get("no_fit_reason")


def print_no_fit_reasons(version: str) -> None:
    """Print the no_fit_reason of every no-fit answer for one version."""
    results = load_results(version)
    no_fit_results = [r for r in results if r["error"] is None and len(r["use_cases"]) == 0]
    print(f"\n--- {version}: no-fit reasons ({len(no_fit_results)}) ---")
    if not no_fit_results:
        print("(none)")
    for r in no_fit_results:
        print(f"- {r['process']}: {_get_no_fit_reason(r)}")


def print_ai_act_levels_for_target_process(version: str) -> None:
    """Print the ai_act level of every use case generated for the target process."""
    results = load_results(version)
    record = next((r for r in results if r["process"] == TARGET_PROCESS_FOR_AI_ACT_DUMP), None)
    print(f"\n--- {version}: ai_act levels for '{TARGET_PROCESS_FOR_AI_ACT_DUMP}' ---")
    if record is None:
        print("(process not found in this version's results)")
    elif not record["use_cases"]:
        print(f"(0 use cases — no_fit_reason: {_get_no_fit_reason(record)})")
    else:
        for uc in record["use_cases"]:
            print(f"- [{uc['type']}] ai_act={uc['ai_act']} — {uc['description']}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    expected_fit = load_expected_fit()
    metrics = {version: compute_metrics(version, expected_fit) for version in VERSIONS}

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

    for version in VERSIONS:
        print_no_fit_reasons(version)

    for version in VERSIONS:
        print_ai_act_levels_for_target_process(version)


if __name__ == "__main__":
    main()
