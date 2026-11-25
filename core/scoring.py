"""Pure scoring calculations for processes.

Functions here take explicit inputs and return a value, with no I/O,
no globals, and no printing.
"""

from core.models import Process


def annual_hours(process: Process) -> float:
    """Return the estimated annual hours spent on a process.

    Computed as volume_per_month * 12 * minutes_per_occurrence / 60.
    """
    return process.volume_per_month * 12 * process.minutes_per_occurrence / 60


def annual_time_value(process: Process, hourly_cost: float) -> float:
    """Return the annual monetary value of the time spent on a process.

    Computed as annual_hours(process) * hourly_cost.
    Raises ValueError if hourly_cost is not strictly positive.
    """
    if hourly_cost <= 0:
        raise ValueError("hourly_cost must be strictly positive")
    return annual_hours(process) * hourly_cost
