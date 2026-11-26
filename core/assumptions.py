"""Business-case assumptions used to turn use cases into costs.

These are starting hypotheses for a demo, not market benchmarks — see
docs/assumptions.md for the rationale behind each default and which ones
should be calibrated with the client before the numbers go in a report.
"""

from pydantic import BaseModel, Field, field_validator

from core.models import UseCase

EXPECTED_COMPLEXITY_KEYS = {1, 2, 3, 4, 5}
EXPECTED_ADOPTION_KEYS = {"pessimistic", "base", "optimistic"}


class Assumptions(BaseModel):
    """Editable cost and adoption assumptions for the business case.

    Every field has a default so the model works out of the box, but every
    field is meant to be edited later (e.g. in a UI) once real client inputs
    are available.
    """

    daily_rate_eur: float = Field(default=650, ge=0, description="Blended build team day rate")
    build_days_by_complexity: dict[int, float] = Field(
        default_factory=lambda: {1: 5, 2: 10, 3: 20, 4: 35, 5: 60},
        description="Build effort in days, keyed by technical_complexity (1-5)",
    )
    off_the_shelf_build_factor: float = Field(
        default=0.4,
        ge=0,
        le=1,
        description="An off-the-shelf tool still needs integration/configuration, "
        "roughly this fraction of a custom build's effort",
    )
    annual_license_eur_off_the_shelf: float = Field(default=6000, ge=0)
    llm_cost_per_occurrence_eur: float = Field(
        default=0.01, ge=0, description="API cost per processed occurrence"
    )
    maintenance_pct_of_build: float = Field(
        default=0.15, ge=0, le=1, description="Annual maintenance cost, as a fraction of build cost"
    )
    change_management_pct_of_build: float = Field(
        default=0.25,
        ge=0,
        le=1,
        description="One-off change management cost (training, communication, "
        "process redesign), as a fraction of build cost",
    )
    adoption_rates: dict[str, float] = Field(
        default_factory=lambda: {"pessimistic": 0.40, "base": 0.65, "optimistic": 0.85}
    )
    horizon_years: int = Field(default=3, ge=0, description="Business-case time horizon")

    @field_validator("build_days_by_complexity")
    @classmethod
    def check_build_days_by_complexity(cls, value: dict[int, float]) -> dict[int, float]:
        """Require exactly keys 1-5, all non-negative, strictly increasing by complexity."""
        if set(value.keys()) != EXPECTED_COMPLEXITY_KEYS:
            raise ValueError(
                f"build_days_by_complexity must have exactly keys {sorted(EXPECTED_COMPLEXITY_KEYS)}, "
                f"got {sorted(value.keys())}"
            )
        if any(days < 0 for days in value.values()):
            raise ValueError("build_days_by_complexity values must be >= 0")
        ordered_days = [value[complexity] for complexity in sorted(value)]
        if any(ordered_days[i] >= ordered_days[i + 1] for i in range(len(ordered_days) - 1)):
            raise ValueError(
                "build_days_by_complexity values must strictly increase with complexity"
            )
        return value

    @field_validator("adoption_rates")
    @classmethod
    def check_adoption_rates(cls, value: dict[str, float]) -> dict[str, float]:
        """Require exactly the 3 scenario keys, each in [0, 1], pessimistic <= base <= optimistic."""
        if set(value.keys()) != EXPECTED_ADOPTION_KEYS:
            raise ValueError(
                f"adoption_rates must contain exactly the keys {sorted(EXPECTED_ADOPTION_KEYS)}, "
                f"got {sorted(value.keys())}"
            )
        if any(not (0 <= rate <= 1) for rate in value.values()):
            raise ValueError("adoption_rates values must be between 0 and 1")
        if not (value["pessimistic"] <= value["base"] <= value["optimistic"]):
            raise ValueError("adoption_rates must satisfy pessimistic <= base <= optimistic")
        return value


def build_cost_eur(use_case: UseCase, assumptions: Assumptions) -> float:
    """Return the one-off build cost in EUR for a use case.

    = build_days_by_complexity[technical_complexity] * daily_rate_eur *
    (off_the_shelf_build_factor if the use case is off-the-shelf, else 1).
    """
    build_days = assumptions.build_days_by_complexity[use_case.technical_complexity]
    factor = assumptions.off_the_shelf_build_factor if use_case.off_the_shelf else 1.0
    return build_days * assumptions.daily_rate_eur * factor
