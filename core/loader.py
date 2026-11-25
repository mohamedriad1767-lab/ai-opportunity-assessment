"""CSV loading utilities for the AI Opportunity Assessment project."""

import pandas as pd

from core.models import Process


def load_processes(path: str) -> list[Process]:
    """Read a processes CSV and return a list of validated Process objects.

    The CSV is expected to have the columns: name, team, volume_per_month,
    minutes_per_occurrence, pain_points, data_used.
    """
    df = pd.read_csv(path)
    return [Process(**row) for row in df.to_dict(orient="records")]
