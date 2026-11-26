"""Tests for core/assumptions.py (no API calls)."""

import pytest
from pydantic import ValidationError

from core.assumptions import Assumptions, build_cost_eur
from core.models import UseCase


def make_use_case(**overrides) -> UseCase:
    """Build a minimal valid UseCase for tests, with any field overridden."""
    defaults = dict(
        process_name="Test process",
        type="assistant",
        description="A test use case.",
        justification="For testing only.",
        pct_time_saved=0.3,
        quality_impact=3,
        strategic_alignment=3,
        data_quality=3,
        technical_complexity=3,
        adoption_risk=3,
        off_the_shelf=True,
        ai_act="minimal",
        gdpr="none",
    )
    defaults.update(overrides)
    return UseCase(**defaults)


def test_defaults_are_valid():
    """The default Assumptions() constructs without error."""
    assumptions = Assumptions()
    assert assumptions.daily_rate_eur == 650
    assert assumptions.horizon_years == 3


def test_decreasing_build_days_are_rejected():
    """A non-strictly-increasing build_days_by_complexity is rejected."""
    with pytest.raises(ValidationError):
        Assumptions(build_days_by_complexity={1: 5, 2: 10, 3: 8, 4: 35, 5: 60})


def test_adoption_scenarios_out_of_order_are_rejected():
    """adoption_rates with pessimistic > base is rejected."""
    with pytest.raises(ValidationError):
        Assumptions(adoption_rates={"pessimistic": 0.7, "base": 0.5, "optimistic": 0.85})


def test_build_cost_for_complexity_3_custom_is_13000_eur():
    """A custom (non-off-the-shelf) complexity-3 use case costs 20 days * 650 EUR = 13,000 EUR."""
    assumptions = Assumptions()
    use_case = make_use_case(technical_complexity=3, off_the_shelf=False)
    assert build_cost_eur(use_case, assumptions) == 13_000


def test_build_cost_for_complexity_3_off_the_shelf_is_5200_eur():
    """An off-the-shelf complexity-3 use case costs 20 days * 650 EUR * 0.4 = 5,200 EUR."""
    assumptions = Assumptions()
    use_case = make_use_case(technical_complexity=3, off_the_shelf=True)
    assert build_cost_eur(use_case, assumptions) == 5_200
