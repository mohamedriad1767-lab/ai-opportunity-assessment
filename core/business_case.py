"""Turn a use case into a 3-scenario business case (TCO, ROI, payback).

Functions here are pure: given a use case, its process, an hourly cost, and
a set of assumptions, they compute numbers. No I/O, no printing.
"""

from pydantic import BaseModel, Field

from core.assumptions import Assumptions, build_cost_eur, change_cost_eur
from core.models import Process, UseCase
from core.scoring import annual_time_value


class BusinessCase(BaseModel):
    """The computed business case for a use case, under one adoption scenario."""

    scenario: str
    annual_gain_eur: float
    one_off_cost_eur: float
    annual_run_cost_eur: float
    tco_eur: float
    net_benefit_eur: float
    roi: float
    payback_months: float | None = Field(
        description="Months to pay back the one-off cost; None means it never pays back "
        "(annual gain does not exceed annual run cost)."
    )


def compute_business_cases(
    use_case: UseCase,
    process: Process,
    hourly_cost: float,
    assumptions: Assumptions,
) -> dict[str, BusinessCase]:
    """Compute the business case for a use case under each adoption scenario.

    annual_gain = annual_time_value(process, hourly_cost) * pct_time_saved * adoption_rate
    one_off = build_cost + change_cost
    annual_run = maintenance_pct * build_cost + (license if off-the-shelf else 0)
                 + llm_cost_per_occurrence * volume_per_month * 12
    tco = one_off + horizon_years * annual_run
    net_benefit = horizon_years * annual_gain - tco
    roi = net_benefit / tco
    payback_months = one_off / (annual_gain - annual_run) * 12, or None if
                      annual_gain does not exceed annual_run.

    Returns one BusinessCase per scenario key in assumptions.adoption_rates
    (pessimistic, base, optimistic).
    """
    build_cost = build_cost_eur(use_case, process, assumptions)
    change_cost = change_cost_eur(use_case, assumptions)
    one_off = build_cost + change_cost

    license_cost = assumptions.annual_license_eur_off_the_shelf if use_case.off_the_shelf else 0.0
    llm_cost = assumptions.llm_cost_per_occurrence_eur * process.volume_per_month * 12
    annual_run = assumptions.maintenance_pct_of_build * build_cost + license_cost + llm_cost

    base_annual_value = annual_time_value(process, hourly_cost) * use_case.pct_time_saved

    cases: dict[str, BusinessCase] = {}
    for scenario, adoption_rate in assumptions.adoption_rates.items():
        annual_gain = base_annual_value * adoption_rate
        tco = one_off + assumptions.horizon_years * annual_run
        net_benefit = assumptions.horizon_years * annual_gain - tco
        roi = net_benefit / tco

        if annual_gain > annual_run:
            payback_months = one_off / (annual_gain - annual_run) * 12
        else:
            payback_months = None

        cases[scenario] = BusinessCase(
            scenario=scenario,
            annual_gain_eur=annual_gain,
            one_off_cost_eur=one_off,
            annual_run_cost_eur=annual_run,
            tco_eur=tco,
            net_benefit_eur=net_benefit,
            roi=roi,
            payback_months=payback_months,
        )

    return cases
