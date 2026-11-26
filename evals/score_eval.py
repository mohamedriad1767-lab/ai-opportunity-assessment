"""Score an evaluation run: automatic metrics from the jsonl, human grading
metrics once the grading CSV has been filled in, LLM-judge metrics once the
judge has run, and the human-vs-judge agreement on rows graded by both.
"""

import csv
import json
import os
import sys

# Allow running this script directly (python evals/score_eval.py) by making
# the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import MODEL_NAME, PRICE_INPUT_PER_MTOK_USD, PRICE_OUTPUT_PER_MTOK_USD
from core.prompts import PROMPT_VERSION

RESULTS_PATH = f"evals/results/{PROMPT_VERSION}_{MODEL_NAME}.jsonl"
GRADING_PATH = f"evals/grading_{PROMPT_VERSION}.csv"
JUDGE_PATH = f"evals/grading_{PROMPT_VERSION}_judge.csv"


def load_results(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_csv_rows(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def compute_automatic_metrics(results: list[dict]) -> dict:
    """Compute metrics derivable from the jsonl alone (no human grading needed)."""
    total_processes = len(results)
    successful = [r for r in results if r["error"] is None]
    with_stats = [r for r in results if r.get("stats")]

    total_use_cases = sum(len(r["use_cases"]) for r in results)
    total_input_tokens = sum(r["stats"].get("input_tokens", 0) for r in with_stats)
    total_output_tokens = sum(r["stats"].get("output_tokens", 0) for r in with_stats)
    total_cost_usd = (
        total_input_tokens / 1_000_000 * PRICE_INPUT_PER_MTOK_USD
        + total_output_tokens / 1_000_000 * PRICE_OUTPUT_PER_MTOK_USD
    )

    first_attempt_valid_count = sum(
        1 for r in with_stats if r["stats"].get("first_attempt_valid")
    )

    return {
        "total_processes": total_processes,
        "final_valid_output_rate": len(successful) / total_processes if total_processes else 0.0,
        "first_attempt_valid_rate": (
            first_attempt_valid_count / len(with_stats) if with_stats else 0.0
        ),
        "avg_use_cases_per_process": (
            total_use_cases / total_processes if total_processes else 0.0
        ),
        "total_cost_usd": total_cost_usd,
    }


def compute_grading_metrics(grading_rows: list[dict]) -> dict | None:
    """Compute human-grading metrics, or None if the grading sheet is still empty."""
    relevance_values = [float(r["relevance"]) for r in grading_rows if r["relevance"].strip()]
    realism_values = [float(r["realism"]) for r in grading_rows if r["realism"].strip()]
    overlap_values = [
        r["overlaps_another"].strip().lower() for r in grading_rows if r["overlaps_another"].strip()
    ]

    if not relevance_values and not realism_values and not overlap_values:
        return None

    return {
        "avg_relevance": sum(relevance_values) / len(relevance_values) if relevance_values else None,
        "avg_realism": sum(realism_values) / len(realism_values) if realism_values else None,
        "overlap_rate": (
            overlap_values.count("yes") / len(overlap_values) if overlap_values else None
        ),
    }


def compute_judge_metrics(judge_rows: list[dict]) -> dict | None:
    """Compute LLM-judge metrics, or None if the judge has not been run yet."""
    if not judge_rows:
        return None

    relevance_values = [int(r["judge_relevance"]) for r in judge_rows]
    realism_values = [int(r["judge_realism"]) for r in judge_rows]
    overlaps = [r["judge_overlaps_another"].strip().lower() == "true" for r in judge_rows]
    ai_act_correct = [r["judge_ai_act_correct"].strip().lower() == "true" for r in judge_rows]

    return {
        "avg_relevance": sum(relevance_values) / len(relevance_values),
        "avg_realism": sum(realism_values) / len(realism_values),
        "overlap_rate": sum(overlaps) / len(overlaps),
        "ai_act_error_rate": 1 - sum(ai_act_correct) / len(ai_act_correct),
    }


def compute_human_vs_judge(grading_rows: list[dict], judge_rows: list[dict]) -> dict | None:
    """Compare human and judge grades on rows graded by both, or None if there are none."""
    judge_by_key = {(r["process"], r["idx"]): r for r in judge_rows}

    paired = []
    for row in grading_rows:
        key = (row["process"], row["idx"])
        if row["relevance"].strip() and row["realism"].strip() and key in judge_by_key:
            paired.append((row, judge_by_key[key]))

    if not paired:
        return None

    relevance_diffs = [abs(float(h["relevance"]) - float(j["judge_relevance"])) for h, j in paired]
    realism_diffs = [abs(float(h["realism"]) - float(j["judge_realism"])) for h, j in paired]

    overlap_agreements = []
    for human_row, judge_row in paired:
        if human_row["overlaps_another"].strip():
            human_overlaps = human_row["overlaps_another"].strip().lower() == "yes"
            judge_overlaps = judge_row["judge_overlaps_another"].strip().lower() == "true"
            overlap_agreements.append(human_overlaps == judge_overlaps)

    return {
        "n": len(paired),
        "mae_relevance": sum(relevance_diffs) / len(relevance_diffs),
        "mae_realism": sum(realism_diffs) / len(realism_diffs),
        "overlap_agreement_rate": (
            sum(overlap_agreements) / len(overlap_agreements) if overlap_agreements else None
        ),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    results = load_results(RESULTS_PATH)
    grading_rows = load_csv_rows(GRADING_PATH)
    judge_rows = load_csv_rows(JUDGE_PATH)

    automatic = compute_automatic_metrics(results)
    print(f"=== Automatic metrics ({PROMPT_VERSION}, {MODEL_NAME}) ===")
    print(f"Processes evaluated: {automatic['total_processes']}")
    print(f"Final valid output rate: {automatic['final_valid_output_rate']:.2%}")
    print(f"First-attempt valid rate: {automatic['first_attempt_valid_rate']:.2%}")
    print(f"Avg use cases per process: {automatic['avg_use_cases_per_process']:.2f}")
    print(f"Total cost: ${automatic['total_cost_usd']:.6f}")

    judge = compute_judge_metrics(judge_rows)
    if judge is not None:
        print("\n=== LLM-judge metrics ===")
        print(f"Avg relevance: {judge['avg_relevance']:.2f}")
        print(f"Avg realism: {judge['avg_realism']:.2f}")
        print(f"Overlap rate: {judge['overlap_rate']:.2%}")
        print(f"AI Act error rate: {judge['ai_act_error_rate']:.2%}")
    else:
        print("\nJudge has not been run yet (evals/grading_*_judge.csv not found) — skipped.")

    grading = compute_grading_metrics(grading_rows)
    if grading is None:
        print("\nGrading sheet is empty — human grading metrics skipped.")
        return

    print("\n=== Human grading metrics ===")
    if grading["avg_relevance"] is not None:
        print(f"Avg relevance: {grading['avg_relevance']:.2f}")
    if grading["avg_realism"] is not None:
        print(f"Avg realism: {grading['avg_realism']:.2f}")
    if grading["overlap_rate"] is not None:
        print(f"Overlap rate: {grading['overlap_rate']:.2%}")

    comparison = compute_human_vs_judge(grading_rows, judge_rows)
    if comparison is None:
        print("\nNo rows graded by both human and judge yet — comparison skipped.")
        return

    print(f"\n=== Human vs judge agreement (n={comparison['n']}) ===")
    print(f"Mean absolute difference — relevance: {comparison['mae_relevance']:.2f}")
    print(f"Mean absolute difference — realism: {comparison['mae_realism']:.2f}")
    if comparison["overlap_agreement_rate"] is not None:
        print(f"Agreement on overlaps_another: {comparison['overlap_agreement_rate']:.2%}")


if __name__ == "__main__":
    main()
