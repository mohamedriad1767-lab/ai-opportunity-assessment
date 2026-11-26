"""Print the build cost of the 5 phase-0 use cases, under default assumptions."""

import json
import os
import sys

# Allow running this script directly (python scripts/check_build_costs.py) by
# making the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.assumptions import Assumptions, build_cost_eur
from core.loader import load_processes
from core.models import UseCase


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    with open("data/phase0_use_cases.json", encoding="utf-8") as f:
        raw_use_cases = json.load(f)
    use_cases = [UseCase(**item) for item in raw_use_cases]

    processes = {p.name: p for p in load_processes("data/demo_company.csv")}
    assumptions = Assumptions()

    header = f"{'process':<45} {'complexity':>10} {'off_the_shelf':>13} {'build_cost_eur':>15}"
    print(header)
    print("-" * len(header))
    for uc in use_cases:
        process = processes[uc.process_name]
        cost = build_cost_eur(uc, process, assumptions)
        print(
            f"{uc.process_name:<45} {uc.technical_complexity:>10} "
            f"{str(uc.off_the_shelf):>13} {round(cost):>15}"
        )


if __name__ == "__main__":
    main()
