"""Tests for core/assumptions.py (no API calls)."""

import pytest
from pydantic import ValidationError

from core.assumptions import Assumptions, build_cost_eur, change_cost_eur
from core.models import Process, UseCase


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


def make_process(**overrides) -> Process:
    """Build a minimal valid Process for tests, with 2 data sources by default."""
    defaults = dict(
        name="Test process",
        team="Ops",
        volume_per_month=100,
        minutes_per_occurrence=5,
        pain_points="Pain point one",
        data_used="Data source A; Data source B",
    )
    defaults.update(overrides)
    return Process(**defaults)


def test_defaults_are_valid():
    """The default Assumptions() constructs without error."""
    assumptions = Assumptions()
    assert assumptions.daily_rate_eur == 650
    assert assumptions.horizon_years == 3


def test_decreasing_build_days_are_rejected():
    """A non-strictly-increasing build_days_by_complexity is rejected."""
    with pytest.raises(ValidationError):
        Assumptions(build_days_by_complexity={1: 5, 2: 10, 3: 8, 4: 35, 5: 60})


def test_decreasing_change_management_days_are_rejected():
    """A non-strictly-increasing change_management_days_by_adoption_risk is rejected."""
    with pytest.raises(ValidationError):
        Assumptions(change_management_days_by_adoption_risk={1: 2, 2: 5, 3: 4, 4: 20, 5: 30})


def test_adoption_scenarios_out_of_order_are_rejected():
    """adoption_rates with pessimistic > base is rejected."""
    with pytest.raises(ValidationError):
        Assumptions(adoption_rates={"pessimistic": 0.7, "base": 0.5, "optimistic": 0.85})


def test_build_cost_for_complexity_3_custom_with_two_data_sources_is_16900_eur():
    """Custom complexity-3, 2 data sources: (20*1 + 3*2) * 650 = 16,900 EUR."""
    assumptions = Assumptions()
    use_case = make_use_case(technical_complexity=3, off_the_shelf=False)
    process = make_process()
    assert build_cost_eur(use_case, process, assumptions) == 16_900


def test_build_cost_for_complexity_3_off_the_shelf_with_two_data_sources_is_9100_eur():
    """Off-the-shelf complexity-3, 2 data sources: (20*0.4 + 3*2) * 650 = 9,100 EUR."""
    assumptions = Assumptions()
    use_case = make_use_case(technical_complexity=3, off_the_shelf=True)
    process = make_process()
    assert build_cost_eur(use_case, process, assumptions) == 9_100


def test_change_cost_for_adoption_risk_3_is_6500_eur():
    """adoption_risk 3: 10 days * 650 EUR = 6,500 EUR."""
    assumptions = Assumptions()
    use_case = make_use_case(adoption_risk=3)
    assert change_cost_eur(use_case, assumptions) == 6_500
