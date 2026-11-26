"""Business-case assumptions used to turn use cases into costs.

These are starting hypotheses for a demo, not market benchmarks — see
docs/assumptions.md for the rationale behind each default and which ones
should be calibrated with the client before the numbers go in a report.
"""

from pydantic import BaseModel, Field, field_validator

from core.models import Process, UseCase

EXPECTED_COMPLEXITY_KEYS = {1, 2, 3, 4, 5}
EXPECTED_ADOPTION_KEYS = {"pessimistic", "base", "optimistic"}


def _check_days_by_scale(value: dict[int, float], field_name: str) -> dict[int, float]:
    """Shared validation for the two 1-5-keyed day tables: exactly keys 1-5,
    all non-negative, strictly increasing.
    """
    if set(value.keys()) != EXPECTED_COMPLEXITY_KEYS:
        raise ValueError(
            f"{field_name} must have exactly keys {sorted(EXPECTED_COMPLEXITY_KEYS)}, "
            f"got {sorted(value.keys())}"
        )
    if any(days < 0 for days in value.values()):
        raise ValueError(f"{field_name} values must be >= 0")
    ordered_days = [value[level] for level in sorted(value)]
    if any(ordered_days[i] >= ordered_days[i + 1] for i in range(len(ordered_days) - 1)):
        raise ValueError(f"{field_name} values must strictly increase with the 1-5 level")
    return value


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
    integration_days_per_data_source: float = Field(
        default=3,
        ge=0,
        description="Extra build days per data source the process uses, on top of "
        "the complexity-based build days",
    )
    annual_license_eur_off_the_shelf: float = Field(default=6000, ge=0)
    llm_cost_per_occurrence_eur: float = Field(
        default=0.01, ge=0, description="API cost per processed occurrence"
    )
    maintenance_pct_of_build: float = Field(
        default=0.15, ge=0, le=1, description="Annual maintenance cost, as a fraction of build cost"
    )
    change_management_days_by_adoption_risk: dict[int, float] = Field(
        default_factory=lambda: {1: 2, 2: 5, 3: 10, 4: 20, 5: 30},
        description="One-off change management effort in days (training, communication, "
        "process redesign), keyed by adoption_risk (1-5)",
    )
    adoption_rates: dict[str, float] = Field(
        default_factory=lambda: {"pessimistic": 0.40, "base": 0.65, "optimistic": 0.85}
    )
    horizon_years: int = Field(default=3, ge=1, description="Business-case time horizon")

    @field_validator("build_days_by_complexity")
    @classmethod
    def check_build_days_by_complexity(cls, value: dict[int, float]) -> dict[int, float]:
        return _check_days_by_scale(value, "build_days_by_complexity")

    @field_validator("change_management_days_by_adoption_risk")
    @classmethod
    def check_change_management_days(cls, value: dict[int, float]) -> dict[int, float]:
        return _check_days_by_scale(value, "change_management_days_by_adoption_risk")

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


def build_cost_eur(use_case: UseCase, process: Process, assumptions: Assumptions) -> float:
    """Return the one-off build cost in EUR for a use case on a given process.

    = (build_days_by_complexity[technical_complexity] *
       (off_the_shelf_build_factor if off-the-shelf, else 1) +
       integration_days_per_data_source * number of data sources used by the process)
      * daily_rate_eur.
    """
    base_days = assumptions.build_days_by_complexity[use_case.technical_complexity]
    factor = assumptions.off_the_shelf_build_factor if use_case.off_the_shelf else 1.0
    integration_days = assumptions.integration_days_per_data_source * len(process.data_used)
    total_days = base_days * factor + integration_days
    return total_days * assumptions.daily_rate_eur


def change_cost_eur(use_case: UseCase, assumptions: Assumptions) -> float:
    """Return the one-off change management cost in EUR for a use case.

    = change_management_days_by_adoption_risk[adoption_risk] * daily_rate_eur.
    """
    days = assumptions.change_management_days_by_adoption_risk[use_case.adoption_risk]
    return days * assumptions.daily_rate_eur
