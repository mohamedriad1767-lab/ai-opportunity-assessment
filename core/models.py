"""Pydantic v2 data models for the AI Opportunity Assessment project.

This module only defines data shapes. Scoring logic lives elsewhere.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Company(BaseModel):
    """A client company for which we assess AI opportunities."""

    name: str
    sector: str
    employees: int = Field(gt=0)
    hourly_cost_eur: float = Field(gt=0, description="Loaded hourly cost in EUR")
    ai_budget_eur: float | None = Field(default=None, ge=0)


class Process(BaseModel):
    """A business process that could be automated or augmented with AI."""

    name: str
    team: str
    volume_per_month: int = Field(ge=0)
    minutes_per_occurrence: float = Field(gt=0)
    pain_points: list[str]
    data_used: list[str]

    @field_validator("pain_points", "data_used", mode="before")
    @classmethod
    def split_semicolon_string(cls, value: str | list[str]) -> list[str]:
        """Split a "; "-separated string (as stored in the CSV) into a clean list.

        Accepts an already-built list as-is, so the validator is idempotent.
        """
        if isinstance(value, str):
            return [item.strip() for item in value.split(";") if item.strip()]
        return value


class UseCaseType(str, Enum):
    """Kind of AI solution proposed for a process."""

    ASSISTANT = "assistant"
    DOCUMENT_EXTRACTION = "document_extraction"
    CLASSIFICATION = "classification"
    AGENT = "agent"
    GENERATION = "generation"


class AIActLevel(str, Enum):
    """EU AI Act risk tier for a use case."""

    PROHIBITED = "prohibited"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"


class GDPRLevel(str, Enum):
    """Sensitivity of personal data involved in a use case."""

    NONE = "none"
    INDIRECT = "indirect"
    SENSITIVE = "sensitive"


class UseCase(BaseModel):
    """An AI use case proposed for a given process, with scoring inputs."""

    process_name: str
    type: UseCaseType
    description: str
    justification: str
    pct_time_saved: float = Field(gt=0, le=1)

    # Criteria notes, each on a 1-5 scale.
    quality_impact: int = Field(ge=1, le=5)
    strategic_alignment: int = Field(ge=1, le=5)
    data_quality: int = Field(ge=1, le=5)
    technical_complexity: int = Field(ge=1, le=5)
    adoption_risk: int = Field(ge=1, le=5)

    off_the_shelf: bool
    ai_act: AIActLevel
    gdpr: GDPRLevel


class Scores(BaseModel):
    """Computed scoring outputs for a use case, on a 0-100 scale."""

    value: float = Field(ge=0, le=100)
    feasibility: float = Field(ge=0, le=100)
    risk: float = Field(ge=0, le=100)
    priority: float = Field(ge=0, le=100)
