"""Build the demo PDF report from the French demo cache and save it to docs/demo_report.pdf."""

import os
import sys

# Allow running this script directly (python scripts/export_report.py) by
# making the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.assumptions import Assumptions
from core.loader import load_company, load_demo_cache, load_processes
from core.matrix import ThresholdMode, portfolio_thresholds
from core.roadmap import build_roadmap
from core.scoring import DEFAULT_WEIGHTS, score_use_cases, split_prohibited
from export.pdf_report import build_report

OUTPUT_PATH = "docs/demo_report.pdf"
HOURLY_COST_EUR = 35


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    company = load_company("data/demo_company_profile_fr.json")
    processes = load_processes("data/demo_company_fr.csv")
    use_cases, no_fit = load_demo_cache("data/demo_cache/use_cases_fr_reviewed.json")

    processes_by_name = {p.name: p for p in processes}
    _, excluded = split_prohibited(use_cases)
    scored, _ = score_use_cases(use_cases, processes_by_name, HOURLY_COST_EUR)
    value_threshold, feasibility_threshold = portfolio_thresholds(scored, ThresholdMode.RELATIVE)
    planned, archived = build_roadmap(scored, value_threshold, feasibility_threshold)

    build_report(
        company=company,
        processes=processes,
        scored_use_cases=scored,
        excluded=excluded,
        no_fit=no_fit,
        roadmap_planned=planned,
        roadmap_archived=archived,
        assumptions=Assumptions(),
        weights=DEFAULT_WEIGHTS,
        output_path=OUTPUT_PATH,
    )

    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
