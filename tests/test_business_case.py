"""Tests for core/business_case.py (no API calls)."""

import json

import pytest

from core.assumptions import Assumptions
from core.business_case import compute_business_cases
from core.loader import load_processes
from core.models import Process, UseCase

HOURLY_COST_EUR = 35
TARGET_PROCESS_NAME = "Supplier invoice processing"


@pytest.fixture
def supplier_invoice_use_case() -> UseCase:
    """The real phase-0 use case for Supplier invoice processing."""
    with open("data/phase0_use_cases.json", encoding="utf-8") as f:
        raw_use_cases = json.load(f)
    by_name = {item["process_name"]: item for item in raw_use_cases}
    return UseCase(**by_name[TARGET_PROCESS_NAME])


@pytest.fixture
def supplier_invoice_process() -> Process:
    """The real demo-company process for Supplier invoice processing."""
    processes = {p.name: p for p in load_processes("data/demo_company.csv")}
    return processes[TARGET_PROCESS_NAME]


@pytest.fixture
def default_assumptions() -> Assumptions:
    return Assumptions()


def test_supplier_invoice_base_scenario_matches_expected_figures(
    supplier_invoice_use_case, supplier_invoice_process, default_assumptions
):
    """Base scenario: one_off, annual_run, tco, net_benefit, roi, and payback match hand-computed figures."""
    cases = compute_business_cases(
        supplier_invoice_use_case, supplier_invoice_process, HOURLY_COST_EUR, default_assumptions
    )
    base = cases["base"]

    assert base.one_off_cost_eur == pytest.approx(16_250)
    assert base.annual_run_cost_eur == pytest.approx(8_370)
    assert base.tco_eur == pytest.approx(41_360)
    assert base.net_benefit_eur == pytest.approx(187_960)
    assert base.roi == pytest.approx(4.5445, rel=1e-3)
    assert base.payback_months == pytest.approx(2.865, rel=1e-3)


def test_supplier_invoice_pessimistic_scenario_matches_expected_figures(
    supplier_invoice_use_case, supplier_invoice_process, default_assumptions
):
    """Pessimistic scenario: annual_gain and payback match hand-computed figures."""
    cases = compute_business_cases(
        supplier_invoice_use_case, supplier_invoice_process, HOURLY_COST_EUR, default_assumptions
    )
    pessimistic = cases["pessimistic"]

    assert pessimistic.annual_gain_eur == pytest.approx(47_040)
    assert pessimistic.payback_months == pytest.approx(5.04, rel=1e-3)


def test_scenarios_order_gain_but_share_identical_costs(
    supplier_invoice_use_case, supplier_invoice_process, default_assumptions
):
    """Annual gain increases pessimistic < base < optimistic, but one_off/run/tco are identical."""
    cases = compute_business_cases(
        supplier_invoice_use_case, supplier_invoice_process, HOURLY_COST_EUR, default_assumptions
    )
    pessimistic, base, optimistic = cases["pessimistic"], cases["base"], cases["optimistic"]

    assert pessimistic.annual_gain_eur < base.annual_gain_eur < optimistic.annual_gain_eur
    assert pessimistic.one_off_cost_eur == base.one_off_cost_eur == optimistic.one_off_cost_eur
    assert (
        pessimistic.annual_run_cost_eur == base.annual_run_cost_eur == optimistic.annual_run_cost_eur
    )
    assert pessimistic.tco_eur == base.tco_eur == optimistic.tco_eur


def test_low_gain_case_never_pays_back(default_assumptions):
    """A low-volume off-the-shelf case whose run cost exceeds its gain never pays back, no exception."""
    use_case = UseCase(
        process_name="Rarely used process",
        type="assistant",
        description="A rarely used tool.",
        justification="For testing only.",
        pct_time_saved=0.5,
        quality_impact=3,
        strategic_alignment=3,
        data_quality=3,
        technical_complexity=1,
        adoption_risk=1,
        off_the_shelf=True,
        ai_act="minimal",
        gdpr="none",
    )
    process = Process(
        name="Rarely used process",
        team="Ops",
        volume_per_month=1,
        minutes_per_occurrence=5,
        pain_points="A minor pain point",
        data_used="One data source",
    )

    cases = compute_business_cases(use_case, process, HOURLY_COST_EUR, default_assumptions)
    base = cases["base"]

    assert base.payback_months is None
    assert base.roi < 0


def test_annual_gain_exactly_equal_to_annual_run_gives_no_payback_without_division_by_zero():
    """annual_gain == annual_run exactly still returns payback_months=None, not a crash."""
    assumptions = Assumptions(
        daily_rate_eur=1000,
        build_days_by_complexity={1: 1, 2: 2, 3: 3, 4: 4, 5: 5},
        off_the_shelf_build_factor=1,
        integration_days_per_data_source=0,
        annual_license_eur_off_the_shelf=0,
        llm_cost_per_occurrence_eur=0,
        maintenance_pct_of_build=0.1,
        change_management_days_by_adoption_risk={1: 1, 2: 2, 3: 3, 4: 4, 5: 5},
        adoption_rates={"pessimistic": 0.1, "base": 0.2, "optimistic": 0.9},
        horizon_years=1,
    )
    use_case = UseCase(
        process_name="Boundary test",
        type="assistant",
        description="A boundary-case use case.",
        justification="For testing only.",
        pct_time_saved=0.5,
        quality_impact=3,
        strategic_alignment=3,
        data_quality=3,
        technical_complexity=1,
        adoption_risk=1,
        off_the_shelf=False,
        ai_act="minimal",
        gdpr="none",
    )
    process = Process(
        name="Boundary test",
        team="Ops",
        volume_per_month=100,
        minutes_per_occurrence=50,
        pain_points="A pain point",
        data_used="",
    )

    cases = compute_business_cases(use_case, process, 1, assumptions)
    base = cases["base"]

    # By construction: annual_run = 100, annual_gain (base) = 500 * 0.2 = 100.
    assert base.annual_gain_eur == pytest.approx(base.annual_run_cost_eur)
    assert base.payback_months is None


def test_zero_adoption_rate_gives_zero_gain_no_payback_and_roi_minus_one(
    supplier_invoice_use_case, supplier_invoice_process
):
    """Adoption rate 0 everywhere gives annual_gain=0, payback=None, and roi exactly -1."""
    assumptions = Assumptions(adoption_rates={"pessimistic": 0, "base": 0, "optimistic": 0})

    cases = compute_business_cases(
        supplier_invoice_use_case, supplier_invoice_process, HOURLY_COST_EUR, assumptions
    )

    for case in cases.values():
        assert case.annual_gain_eur == 0
        assert case.payback_months is None
        assert case.roi == pytest.approx(-1.0)


def test_horizon_years_changes_tco_and_roi_but_not_payback(
    supplier_invoice_use_case, supplier_invoice_process
):
    """Changing horizon_years changes tco and roi, but payback_months is unaffected."""
    assumptions_1y = Assumptions(horizon_years=1)
    assumptions_3y = Assumptions(horizon_years=3)

    case_1y = compute_business_cases(
        supplier_invoice_use_case, supplier_invoice_process, HOURLY_COST_EUR, assumptions_1y
    )["base"]
    case_3y = compute_business_cases(
        supplier_invoice_use_case, supplier_invoice_process, HOURLY_COST_EUR, assumptions_3y
    )["base"]

    assert case_1y.tco_eur != case_3y.tco_eur
    assert case_1y.roi != case_3y.roi
    assert case_1y.payback_months == pytest.approx(case_3y.payback_months)


def test_off_the_shelf_has_lower_build_cost_but_higher_run_cost_than_custom(
    supplier_invoice_process, default_assumptions
):
    """Off-the-shelf lowers one_off_cost_eur but raises annual_run_cost_eur (license) vs custom."""
    off_the_shelf_use_case = UseCase(
        process_name=TARGET_PROCESS_NAME,
        type="document_extraction",
        description="Same case, off-the-shelf.",
        justification="For testing only.",
        pct_time_saved=0.6,
        quality_impact=4,
        strategic_alignment=4,
        data_quality=4,
        technical_complexity=3,
        adoption_risk=2,
        off_the_shelf=True,
        ai_act="minimal",
        gdpr="indirect",
    )
    custom_use_case = off_the_shelf_use_case.model_copy(update={"off_the_shelf": False})

    off_the_shelf_case = compute_business_cases(
        off_the_shelf_use_case, supplier_invoice_process, HOURLY_COST_EUR, default_assumptions
    )["base"]
    custom_case = compute_business_cases(
        custom_use_case, supplier_invoice_process, HOURLY_COST_EUR, default_assumptions
    )["base"]

    assert off_the_shelf_case.one_off_cost_eur < custom_case.one_off_cost_eur
    assert off_the_shelf_case.annual_run_cost_eur > custom_case.annual_run_cost_eur
