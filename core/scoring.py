"""Pure scoring calculations for processes.

Functions here take explicit inputs and return a value, with no I/O,
no globals, and no printing.
"""

import math

from core.models import Process

MONTHS_PER_YEAR = 12
MINUTES_PER_HOUR = 60


def annual_hours(process: Process) -> float:
    """Return the estimated annual hours spent on a process.

    Computed as volume_per_month * MONTHS_PER_YEAR * minutes_per_occurrence / MINUTES_PER_HOUR.
    """
    return process.volume_per_month * MONTHS_PER_YEAR * process.minutes_per_occurrence / MINUTES_PER_HOUR


def annual_time_value(process: Process, hourly_cost: float) -> float:
    """Return the annual monetary value of the time spent on a process.

    Computed as annual_hours(process) * hourly_cost.
    Raises ValueError if hourly_cost is not strictly positive.
    """
    if hourly_cost <= 0:
        raise ValueError("hourly_cost must be strictly positive")
    return annual_hours(process) * hourly_cost


def normalize_log_minmax(values: list[float]) -> list[float]:
    """Map values to a 0-100 scale using min-max normalization on the natural log.

    score = (ln(v) - ln(min)) / (ln(max) - ln(min)) * 100,
    where min and max are taken over the strictly positive values only.

    Edge cases:
    - Empty input list: returns [].
    - Values <= 0: they have no defined logarithm, so they get a score of 0,
      and they are excluded when computing min/max for the other values.
    - All positive values equal, or only one positive value in the list:
      there is no information to rank them against each other, so every
      positive value gets the neutral score 50.

    Scores are rounded to 1 decimal and returned in the same order as the input.
    """
    if not values:
        return []

    positive_values = [v for v in values if v > 0]

    if not positive_values:
        return [0.0 for _ in values]

    log_values = [math.log(v) for v in positive_values]
    log_min = min(log_values)
    log_max = max(log_values)

    if log_max == log_min:
        return [50.0 if v > 0 else 0.0 for v in values]

    scores = []
    for v in values:
        if v <= 0:
            scores.append(0.0)
        else:
            score = (math.log(v) - log_min) / (log_max - log_min) * 100
            scores.append(round(score, 1))
    return scores
