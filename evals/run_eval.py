"""Run use-case generation over the evaluation set and save results + a grading sheet.

For each process in evals/eval_processes.csv, generates use cases (using the
demo company profile as context), and writes one JSON line per process to
evals/results/{PROMPT_VERSION}_{model}.jsonl. Then builds an empty grading
CSV (evals/grading_{PROMPT_VERSION}_{model}.csv), one row per generated use
case, for a human to fill in relevance/realism/overlap judgments.
"""

import argparse
import csv
import json
import logging
import os
import sys

# Allow running this script directly (python evals/run_eval.py) by making the
# project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from core.config import MODEL_NAME
from core.generator import GenerationError, generate_use_cases, make_client
from core.loader import load_processes
from core.models import Company
from core.prompts import PROMPT_VERSION

EVAL_PROCESSES_PATH = "evals/eval_processes.csv"
COMPANY_PROFILE_PATH = "data/demo_company_profile.json"
RESULTS_DIR = "evals/results"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def run_one_process(company: Company, process, client, model: str) -> dict:
    """Generate use cases for one process and return a JSON-serializable result record."""
    stats: dict = {}
    try:
        result = generate_use_cases(company, process, client, stats=stats, model=model)
    except GenerationError as exc:
        return {
            "process": process.name,
            "use_cases": [],
            "no_fit_reason": None,
            "stats": stats,
            "error": str(exc),
        }

    return {
        "process": process.name,
        "use_cases": [uc.model_dump(mode="json") for uc in result.use_cases],
        "no_fit_reason": result.no_fit_reason,
        "stats": stats,
        "error": None,
    }


def write_results(results: list[dict], results_path: str) -> None:
    """Write one JSON line per process result."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result) + "\n")


def write_grading_csv(results: list[dict], grading_path: str) -> None:
    """Write an empty grading sheet, one row per generated use case."""
    fieldnames = [
        "process",
        "idx",
        "type",
        "description",
        "pct_time_saved",
        "ai_act",
        "relevance",
        "realism",
        "overlaps_another",
        "comment",
    ]
    with open(grading_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            for idx, use_case in enumerate(result["use_cases"]):
                writer.writerow(
                    {
                        "process": result["process"],
                        "idx": idx,
                        "type": use_case["type"],
                        "description": use_case["description"],
                        "pct_time_saved": use_case["pct_time_saved"],
                        "ai_act": use_case["ai_act"],
                        "relevance": "",
                        "realism": "",
                        "overlaps_another": "",
                        "comment": "",
                    }
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run use-case generation over the eval set.")
    parser.add_argument(
        "--model",
        default=MODEL_NAME,
        help=f"Model to use for generation (default: {MODEL_NAME})",
    )
    return parser.parse_args()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set. Add it to your .env file and try again.")
        sys.exit(1)

    args = parse_args()
    model = args.model
    results_path = f"{RESULTS_DIR}/{PROMPT_VERSION}_{model}.jsonl"
    grading_path = f"evals/grading_{PROMPT_VERSION}_{model}.csv"

    with open(COMPANY_PROFILE_PATH, encoding="utf-8") as f:
        company = Company(**json.load(f))

    processes = load_processes(EVAL_PROCESSES_PATH)
    client = make_client(api_key)

    results = []
    for process in processes:
        print(f"Generating for: {process.name}")
        results.append(run_one_process(company, process, client, model))

    write_results(results, results_path)
    write_grading_csv(results, grading_path)

    print(f"\nWrote {len(results)} results to {results_path}")
    total_use_cases = sum(len(r["use_cases"]) for r in results)
    print(f"Wrote {total_use_cases} grading rows to {grading_path}")


if __name__ == "__main__":
    main()
