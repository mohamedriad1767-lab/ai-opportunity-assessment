"""Print annual hours and annual time value for a couple of sample processes."""

import os
import sys

# Allow running this script directly (python scripts/check_time_value.py) by
# making the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.loader import load_processes
from core.scoring import annual_hours, annual_time_value

HOURLY_COST_EUR = 35
TARGET_PROCESS_NAMES = ["Order entry", "Supplier invoice processing"]


def main() -> None:
    processes = load_processes("data/demo_company.csv")
    by_name = {p.name: p for p in processes}

    for name in TARGET_PROCESS_NAMES:
        process = by_name[name]
        hours = annual_hours(process)
        value = annual_time_value(process, HOURLY_COST_EUR)
        print(f"{name}: annual hours = {round(hours)} h, annual time value = {round(value)} EUR")


if __name__ == "__main__":
    main()
