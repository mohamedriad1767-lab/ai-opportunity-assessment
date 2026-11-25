"""Compute value/feasibility/risk scores for the phase-0 use cases and compare
them against the reference values from docs/manual_scoring.xlsx.
"""

import json
import os
import sys

# Allow running this script directly (python scripts/check_axes.py) by making
# the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.loader import load_processes
from core.models import UseCase
from core.scoring import (
    annual_time_value,
    feasibility_score,
    normalize_log_minmax,
    risk_score,
    value_score,
)

HOURLY_COST_EUR = 35

# Reference scores from docs/manual_scoring.xlsx (linear min-max gain
# normalization), kept here only for side-by-side comparison in this script.
XLSX_REFERENCE = {
    "Supplier invoice processing": {"value": 85.4, "feasibility": 72.5, "risk": 22.5},
    "Order status inquiries": {"value": 80.0, "feasibility": 91.2, "risk": 30.0},
    "Quote generation": {"value": 61.8, "feasibility": 37.5, "risk": 15.0},
    "CV screening for open positions": {"value": 24.3, "feasibility": 53.8, "risk": 92.5},
    "Monthly management reporting consolidation": {"value": 32.5, "feasibility": 28.8, "risk": 7.5},
}


def main() -> None:
    with open("data/phase0_use_cases.json", encoding="utf-8") as f:
        raw_use_cases = json.load(f)
    use_cases = [UseCase(**item) for item in raw_use_cases]

    processes = load_processes("data/demo_company.csv")
    processes_by_name = {p.name: p for p in processes}

    gains = [
        annual_time_value(processes_by_name[uc.process_name], HOURLY_COST_EUR) * uc.pct_time_saved
        for uc in use_cases
    ]
    gain_scores = normalize_log_minmax(gains)

    header = (
        f"{'use_case':<45} {'value':>7} {'xlsx_value':>10} "
        f"{'feasibility':>12} {'xlsx_feas':>10} {'risk':>7} {'xlsx_risk':>10}"
    )
    print(header)
    print("-" * len(header))
    for uc, gain_score in zip(use_cases, gain_scores):
        value = value_score(uc, gain_score)
        feasibility = feasibility_score(uc)
        risk = risk_score(uc)
        ref = XLSX_REFERENCE[uc.process_name]
        print(
            f"{uc.process_name:<45} {value:>7} {ref['value']:>10} "
            f"{feasibility:>12} {ref['feasibility']:>10} {risk:>7} {ref['risk']:>10}"
        )


if __name__ == "__main__":
    main()
