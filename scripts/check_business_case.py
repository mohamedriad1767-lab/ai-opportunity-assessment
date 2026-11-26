"""Print the 3-scenario business case for "Supplier invoice processing"."""

import json
import os
import sys

# Allow running this script directly (python scripts/check_business_case.py)
# by making the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.assumptions import Assumptions, build_cost_eur, change_cost_eur
from core.business_case import compute_business_cases
from core.loader import load_processes
from core.models import UseCase

TARGET_PROCESS_NAME = "Supplier invoice processing"
HOURLY_COST_EUR = 35


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    with open("data/phase0_use_cases.json", encoding="utf-8") as f:
        raw_use_cases = json.load(f)
    use_cases = {item["process_name"]: UseCase(**item) for item in raw_use_cases}
    use_case = use_cases[TARGET_PROCESS_NAME]

    processes = {p.name: p for p in load_processes("data/demo_company.csv")}
    process = processes[TARGET_PROCESS_NAME]

    assumptions = Assumptions()

    build_cost = build_cost_eur(use_case, process, assumptions)
    change_cost = change_cost_eur(use_case, assumptions)

    print(f"=== {TARGET_PROCESS_NAME} ===")
    print(f"Build cost:  {build_cost:,.0f} EUR")
    print(f"Change cost: {change_cost:,.0f} EUR")
    print(f"One-off cost: {build_cost + change_cost:,.0f} EUR")
    print()

    cases = compute_business_cases(use_case, process, HOURLY_COST_EUR, assumptions)

    for scenario in ("pessimistic", "base", "optimistic"):
        case = cases[scenario]
        payback = f"{case.payback_months:,.1f} months" if case.payback_months is not None else "never"
        print(f"--- {scenario} (adoption rate {assumptions.adoption_rates[scenario]:.0%}) ---")
        print(f"Annual gain:       {case.annual_gain_eur:,.0f} EUR")
        print(f"One-off cost:      {case.one_off_cost_eur:,.0f} EUR")
        print(f"Annual run cost:   {case.annual_run_cost_eur:,.0f} EUR")
        print(f"TCO ({assumptions.horizon_years}y):          {case.tco_eur:,.0f} EUR")
        print(f"Net benefit ({assumptions.horizon_years}y):  {case.net_benefit_eur:,.0f} EUR")
        print(f"ROI:               {case.roi:.1%}")
        print(f"Payback:           {payback}")
        print()


if __name__ == "__main__":
    main()
