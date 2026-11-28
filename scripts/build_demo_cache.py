"""Generate AI use cases for the 12 French demo processes and cache them to disk.

This is a one-time (re-run-on-demand) build step: it calls the real
Anthropic API once per process and saves the raw results, so the Streamlit
app can later show a full demo (ranking, matrix, roadmap, PDF) with NO API
key and NO live LLM call. This raw output is never used directly by the
app: a human reviews it and the corrections are applied on top, producing
data/demo_cache/use_cases_fr_reviewed.json (see docs/demo_review.md), which
is what the app and the demo exports actually load.

Output: a JSON list with one entry per process, shaped like a
GenerationResult (use_cases, no_fit_reason) plus the process_name.
"""

import json
import os
import sys

# Allow running this script directly (python scripts/build_demo_cache.py) by
# making the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from core.generator import GenerationError, generate_use_cases, make_client
from core.loader import load_company, load_processes

COMPANY_PROFILE_PATH = "data/demo_company_profile_fr.json"
PROCESSES_PATH = "data/demo_company_fr.csv"
OUTPUT_PATH = "data/demo_cache/use_cases_fr.json"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set. Add it to your .env file and try again.")
        sys.exit(1)

    company = load_company(COMPANY_PROFILE_PATH)
    processes = load_processes(PROCESSES_PATH)
    client = make_client(api_key)

    cache: list[dict] = []
    for process in processes:
        print(f"Generating for: {process.name}")
        try:
            result = generate_use_cases(company, process, client)
        except GenerationError as exc:
            print(f"  FAILED: {exc}")
            cache.append({"process_name": process.name, "use_cases": [], "no_fit_reason": f"[generation failed: {exc}]"})
            continue
        cache.append(
            {
                "process_name": process.name,
                "use_cases": [uc.model_dump(mode="json") for uc in result.use_cases],
                "no_fit_reason": result.no_fit_reason,
            }
        )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    total_use_cases = sum(len(entry["use_cases"]) for entry in cache)
    print(f"\nWrote {len(cache)} process results ({total_use_cases} use cases) to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
