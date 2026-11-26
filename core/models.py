"""Pydantic v2 data models for the AI Opportunity Assessment project.

This module only defines data shapes. Scoring logic lives elsewhere.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


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


class UseCaseProposal(BaseModel):
    """A single AI use case as proposed by the LLM, before process_name is attached.

    process_name is deliberately absent here: it is set by the code
    (to_use_cases), never by the LLM, so the LLM cannot misattribute a
    proposal to a different process.
    """

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
    # "prohibited" is allowed here (unlike scoring) so the code can detect
    # and exclude prohibited proposals rather than the LLM silently omitting them.
    ai_act: AIActLevel
    gdpr: GDPRLevel
    criteria_rationale: dict[str, str] = Field(
        default_factory=dict,
        description="One short line of rationale per criterion (quality_impact, "
        "strategic_alignment, data_quality, technical_complexity, adoption_risk, "
        "off_the_shelf, ai_act, gdpr).",
    )


class UseCase(UseCaseProposal):
    """A UseCaseProposal attached to a specific process, with scoring inputs.

    Adds only process_name on top of UseCaseProposal: every other field is
    inherited unchanged.
    """

    process_name: str


class ProposalBatch(BaseModel):
    """A batch of 0 to 3 use-case proposals for a single process.

    0 use cases is allowed for a genuine "no good AI fit" answer, but then
    no_fit_reason is required so the absence of use cases is always explained.
    """

    use_cases: list[UseCaseProposal] = Field(min_length=0, max_length=3)
    no_fit_reason: str | None = None

    @model_validator(mode="after")
    def check_pct_time_saved_sum(self) -> "ProposalBatch":
        """Reject a batch whose pct_time_saved values sum above 0.8."""
        total = sum(uc.pct_time_saved for uc in self.use_cases)
        if total > 0.8:
            raise ValueError(f"Sum of pct_time_saved must be <= 0.8, got {total}")
        return self

    @model_validator(mode="after")
    def check_no_fit_reason_required_when_empty(self) -> "ProposalBatch":
        """Require no_fit_reason when 0 use cases are proposed."""
        if not self.use_cases and not self.no_fit_reason:
            raise ValueError("no_fit_reason is required when use_cases is empty")
        return self


def to_use_cases(batch: ProposalBatch, process_name: str) -> list[UseCase]:
    """Convert a validated ProposalBatch into UseCase objects for one process.

    process_name is supplied by the caller (code), not by the LLM.
    """
    return [
        UseCase(process_name=process_name, **proposal.model_dump())
        for proposal in batch.use_cases
    ]


class Scores(BaseModel):
    """Computed scoring outputs for a use case, on a 0-100 scale."""

    value: float = Field(ge=0, le=100)
    feasibility: float = Field(ge=0, le=100)
    risk: float = Field(ge=0, le=100)
    priority: float = Field(ge=0, le=100)


class ScoredUseCase(BaseModel):
    """A use case bundled with its computed gain, scores, and portfolio rank."""

    use_case: UseCase
    annual_gain_eur: float = Field(ge=0)
    scores: Scores
    rank: int = Field(ge=1)
