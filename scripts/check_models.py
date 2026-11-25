"""Smoke-test script for the Process model and the CSV loader."""

import os
import sys

# Allow running this script directly (python scripts/check_models.py) by making
# the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError

from core.loader import load_processes
from core.models import Process


def main() -> None:
    processes = load_processes("data/demo_company.csv")
    print(f"Number of processes: {len(processes)}")
    print("First process:")
    print(processes[0])

    print("\nDeliberately building an invalid Process (volume_per_month=-5):")
    try:
        Process(
            name="Invalid process",
            team="Test",
            volume_per_month=-5,
            minutes_per_occurrence=10,
            pain_points="Some pain",
            data_used="Some data",
        )
    except ValidationError as exc:
        print(exc)


if __name__ == "__main__":
    main()
