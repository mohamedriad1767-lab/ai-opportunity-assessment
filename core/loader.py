"""File loading and validation utilities for the AI Opportunity Assessment project."""

import json

import pandas as pd
from pydantic import BaseModel, ValidationError

from core.models import Company, Process, UseCase


def load_processes(path: str) -> list[Process]:
    """Read a processes CSV and return a list of validated Process objects.

    The CSV is expected to have the columns: name, team, volume_per_month,
    minutes_per_occurrence, pain_points, data_used.
    """
    df = pd.read_csv(path)
    return [Process(**row) for row in df.to_dict(orient="records")]


def load_company(path: str) -> Company:
    """Read a company profile JSON file and return a validated Company object."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return Company(**data)


def load_use_cases(path: str) -> list[UseCase]:
    """Read a use-cases JSON file (a list of UseCase-shaped objects) and
    return a list of validated UseCase objects.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [UseCase(**item) for item in data]


def load_demo_cache(path: str) -> tuple[list[UseCase], list[tuple[str, str]]]:
    """Read a cached generation file (one GenerationResult per process, plus
    its process_name) and return (use_cases, no_fit_reasons).

    use_cases is the flattened list of UseCase objects across every process.
    no_fit_reasons is the list of (process_name, reason) pairs for processes
    that had no good AI fit, in the same shape as the "Générer avec l'IA"
    button builds live in app.py.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    use_cases: list[UseCase] = []
    no_fit_reasons: list[tuple[str, str]] = []
    for entry in data:
        use_cases.extend(UseCase(**item) for item in entry["use_cases"])
        if entry.get("no_fit_reason"):
            no_fit_reasons.append((entry["process_name"], entry["no_fit_reason"]))
    return use_cases, no_fit_reasons


def validate_records(records: list[dict], model_cls: type[BaseModel]) -> tuple[list, list[str]]:
    """Validate a list of dict records against a Pydantic model.

    Returns (valid_objects, error_messages) instead of raising on the first
    invalid record, so callers can report every bad row without silently
    dropping the rest.
    """
    valid: list = []
    errors: list[str] = []
    for index, record in enumerate(records):
        try:
            valid.append(model_cls(**record))
        except ValidationError as exc:
            errors.append(f"Row {index}: {exc}")
    return valid, errors
