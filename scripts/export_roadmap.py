"""Build the 3-wave roadmap for the French demo use cases and save it as a PNG."""

import os
import sys

# Allow running this script directly (python scripts/export_roadmap.py) by
# making the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.loader import load_demo_cache, load_processes
from core.matrix import ThresholdMode, portfolio_thresholds
from core.roadmap import build_roadmap
from core.scoring import score_use_cases
from viz.roadmap_chart import build_roadmap_figure

OUTPUT_PATH = "docs/img/roadmap_demo.png"
HOURLY_COST_EUR = 35


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    use_cases, _ = load_demo_cache("data/demo_cache/use_cases_fr_reviewed.json")
    processes = {p.name: p for p in load_processes("data/demo_company_fr.csv")}

    scored, _ = score_use_cases(use_cases, processes, HOURLY_COST_EUR)
    value_threshold, feasibility_threshold = portfolio_thresholds(scored, ThresholdMode.RELATIVE)
    planned, _ = build_roadmap(scored, value_threshold, feasibility_threshold)

    fig = build_roadmap_figure(planned)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    fig.write_image(OUTPUT_PATH, width=1100, scale=2)

    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
