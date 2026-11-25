"""Compare log min-max vs linear min-max normalization of annual time value."""

import os
import sys

# Allow running this script directly (python scripts/check_normalization.py) by
# making the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.loader import load_processes
from core.scoring import annual_time_value, normalize_log_minmax

HOURLY_COST_EUR = 35


def normalize_linear_minmax(values: list[float]) -> list[float]:
    """Linear min-max normalization to 0-100, for comparison purposes only."""
    if not values:
        return []
    low, high = min(values), max(values)
    if high == low:
        return [50.0 for _ in values]
    return [round((v - low) / (high - low) * 100, 1) for v in values]


def main() -> None:
    processes = load_processes("data/demo_company.csv")
    values = [annual_time_value(p, HOURLY_COST_EUR) for p in processes]

    log_scores = normalize_log_minmax(values)
    linear_scores = normalize_linear_minmax(values)

    rows = list(zip(processes, values, log_scores, linear_scores))
    rows.sort(key=lambda r: r[2], reverse=True)

    header = f"{'name':<42} {'annual_value_eur':>17} {'log_score':>10} {'linear_score':>13}"
    print(header)
    print("-" * len(header))
    for process, value, log_score, linear_score in rows:
        print(f"{process.name:<42} {round(value):>17} {log_score:>10} {linear_score:>13}")


if __name__ == "__main__":
    main()
