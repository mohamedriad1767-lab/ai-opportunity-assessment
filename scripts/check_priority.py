"""Score and rank the phase-0 use cases plus one prohibited AI Act case."""

import json
import os
import sys

# Allow running this script directly (python scripts/check_priority.py) by
# making the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.loader import load_processes
from core.models import UseCase
from core.scoring import score_use_cases

HOURLY_COST_EUR = 35

PROHIBITED_USE_CASE = {
    "process_name": "Customer complaint handling",
    "type": "classification",
    "description": "Emotion detection on customer service agents' calls, used to flag or score agents based on their emotional state during calls.",
    "justification": "Would let supervisors monitor agent stress and sentiment in real time without manual call review.",
    "pct_time_saved": 0.30,
    "quality_impact": 2,
    "strategic_alignment": 2,
    "data_quality": 3,
    "technical_complexity": 4,
    "adoption_risk": 5,
    "off_the_shelf": True,
    "ai_act": "prohibited",
    "gdpr": "sensitive",
}


def main() -> None:
    with open("data/phase0_use_cases.json", encoding="utf-8") as f:
        raw_use_cases = json.load(f)
    use_cases = [UseCase(**item) for item in raw_use_cases]
    use_cases.append(UseCase(**PROHIBITED_USE_CASE))

    processes = load_processes("data/demo_company.csv")
    processes_by_name = {p.name: p for p in processes}

    scored, excluded = score_use_cases(use_cases, processes_by_name, HOURLY_COST_EUR)

    header = (
        f"{'rank':>4} {'use_case':<45} {'value':>7} {'feasibility':>12} "
        f"{'risk':>7} {'priority':>9} {'annual_gain_eur':>16}"
    )
    print(header)
    print("-" * len(header))
    for item in scored:
        uc = item.use_case
        s = item.scores
        print(
            f"{item.rank:>4} {uc.process_name:<45} {s.value:>7} {s.feasibility:>12} "
            f"{s.risk:>7} {s.priority:>9} {round(item.annual_gain_eur):>16}"
        )

    print("\nExcluded (prohibited under the EU AI Act):")
    for uc in excluded:
        print(f"- {uc.process_name}: {uc.description} (ai_act={uc.ai_act.value})")


if __name__ == "__main__":
    main()
