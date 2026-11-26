"""Generate use cases via structured tool use for 3 processes, then score and rank them."""

import json
import os
import sys

# Allow running this script directly (python scripts/try_structured.py) by
# making the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from core.generator import generate_use_cases, make_client
from core.loader import load_processes
from core.models import Company
from core.scoring import score_use_cases

PROCESS_NAMES = [
    "Supplier invoice processing",
    "Customer complaint handling",
    "CV screening for open positions",
]
HOURLY_COST_EUR = 35


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set. Add it to your .env file and try again.")
        sys.exit(1)

    with open("data/demo_company_profile.json", encoding="utf-8") as f:
        company = Company(**json.load(f))

    all_processes = {p.name: p for p in load_processes("data/demo_company.csv")}
    client = make_client(api_key)

    all_use_cases = []
    for name in PROCESS_NAMES:
        process = all_processes[name]
        use_cases = generate_use_cases(company, process, client)
        print(f"=== {name} ({len(use_cases)} use case(s) generated) ===")
        for uc in use_cases:
            print(f"- [{uc.type.value}] {uc.description} (ai_act={uc.ai_act.value}, pct_time_saved={uc.pct_time_saved})")
        print()
        all_use_cases.extend(use_cases)

    scored, excluded = score_use_cases(all_use_cases, all_processes, HOURLY_COST_EUR)

    header = (
        f"{'rank':>4} {'process':<42} {'value':>7} {'feasibility':>12} "
        f"{'risk':>7} {'priority':>9} {'annual_gain_eur':>16}"
    )
    print("=== Ranked table ===")
    print(header)
    print("-" * len(header))
    for item in scored:
        uc = item.use_case
        s = item.scores
        print(
            f"{item.rank:>4} {uc.process_name:<42} {s.value:>7} {s.feasibility:>12} "
            f"{s.risk:>7} {s.priority:>9} {round(item.annual_gain_eur):>16}"
        )

    print("\n=== Excluded (prohibited under the EU AI Act) ===")
    if not excluded:
        print("(none)")
    for uc in excluded:
        print(f"- {uc.process_name}: {uc.description} (ai_act={uc.ai_act.value})")


if __name__ == "__main__":
    main()
