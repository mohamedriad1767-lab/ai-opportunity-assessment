"""Tests for the pure scoring functions in core/scoring.py."""

import copy
import json

import pytest

from core.loader import load_processes
from core.models import AIActLevel, Process, UseCase
from core.scoring import (
    DEFAULT_WEIGHTS,
    annual_hours,
    annual_time_value,
    best_per_process,
    feasibility_score,
    note_to_100,
    normalize_log_minmax,
    score_use_cases,
    validate_weights,
)

DEMO_CSV_PATH = "data/demo_company.csv"
PHASE0_JSON_PATH = "data/phase0_use_cases.json"
HOURLY_COST_EUR = 35


@pytest.fixture
def processes() -> dict[str, Process]:
    """Demo-company processes keyed by name, loaded from the real CSV fixture."""
    return {p.name: p for p in load_processes(DEMO_CSV_PATH)}


@pytest.fixture
def use_cases() -> list[UseCase]:
    """The 5 phase-0 use cases, loaded from the real JSON fixture."""
    with open(PHASE0_JSON_PATH, encoding="utf-8") as f:
        raw_use_cases = json.load(f)
    return [UseCase(**item) for item in raw_use_cases]


def make_use_case(**overrides) -> UseCase:
    """Build a minimal valid UseCase for unit tests, with any field overridden."""
    defaults = dict(
        process_name="Test process",
        type="assistant",
        description="A test use case.",
        justification="For testing only.",
        pct_time_saved=0.5,
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


def test_annual_hours_of_order_entry(processes):
    """annual_hours of "Order entry" equals 2400."""
    assert annual_hours(processes["Order entry"]) == 2400


def test_annual_time_value_of_order_entry_at_35_eur(processes):
    """annual_time_value of "Order entry" at 35 EUR/h equals 84000."""
    assert annual_time_value(processes["Order entry"], HOURLY_COST_EUR) == 84000


def test_annual_time_value_raises_for_non_positive_hourly_cost(processes):
    """annual_time_value raises ValueError when hourly_cost is zero or negative."""
    with pytest.raises(ValueError):
        annual_time_value(processes["Order entry"], 0)
    with pytest.raises(ValueError):
        annual_time_value(processes["Order entry"], -10)


def test_note_to_100_maps_boundaries_correctly():
    """note_to_100 maps 1 to 0 and 5 to 100."""
    assert note_to_100(1) == 0
    assert note_to_100(5) == 100


def test_note_to_100_raises_outside_1_to_5_range():
    """note_to_100 raises ValueError for notes of 0 or 6, outside the 1-5 range."""
    with pytest.raises(ValueError):
        note_to_100(0)
    with pytest.raises(ValueError):
        note_to_100(6)


def test_normalize_log_minmax_empty_list_returns_empty_list():
    """normalize_log_minmax returns an empty list for an empty input."""
    assert normalize_log_minmax([]) == []


def test_normalize_log_minmax_all_equal_values_score_50():
    """normalize_log_minmax gives every value the neutral score 50 when all are equal."""
    assert normalize_log_minmax([10, 10, 10]) == [50.0, 50.0, 50.0]


def test_normalize_log_minmax_non_positive_values_score_0_without_affecting_others():
    """normalize_log_minmax scores non-positive values at 0, and ignores them when scoring the others."""
    result = normalize_log_minmax([-5, 10, 100])
    result_without_non_positive = normalize_log_minmax([10, 100])
    assert result[0] == 0.0
    assert result[1:] == result_without_non_positive


def test_normalize_log_minmax_min_scores_0_and_max_scores_100():
    """normalize_log_minmax assigns 0 to the minimum value and 100 to the maximum value."""
    result = normalize_log_minmax([5, 50, 500])
    assert result[0] == 0.0
    assert result[-1] == 100.0


def test_feasibility_score_inverts_technical_complexity():
    """feasibility_score penalizes high technical_complexity: complexity 5 scores lower than complexity 1, all else equal."""
    low_complexity = make_use_case(technical_complexity=1)
    high_complexity = make_use_case(technical_complexity=5)
    assert feasibility_score(high_complexity) < feasibility_score(low_complexity)


def test_validate_weights_raises_when_an_axis_does_not_sum_to_1():
    """validate_weights raises ValueError when an axis's sub-weights do not sum to 1."""
    bad_weights = {"value": {"gain": 0.5, "quality": 0.3, "alignment": 0.1}}
    with pytest.raises(ValueError):
        validate_weights(bad_weights)


def test_custom_priority_weights_change_the_ranking(processes, use_cases):
    """With priority weights value=0.5/feasibility=0.5/risk=0.0, CV screening ranks above monthly reporting."""
    custom_weights = {**DEFAULT_WEIGHTS, "priority": {"value": 0.5, "feasibility": 0.5, "risk": 0.0}}
    scored, _ = score_use_cases(use_cases, processes, HOURLY_COST_EUR, custom_weights)
    ranks = {item.use_case.process_name: item.rank for item in scored}
    assert ranks["CV screening for open positions"] < ranks["Monthly management reporting consolidation"]


def test_prohibited_case_is_excluded_and_other_scores_are_unaffected(processes, use_cases):
    """A prohibited case is excluded from scoring, and the other cases' scores are identical with or without it."""
    prohibited = make_use_case(
        process_name="Customer complaint handling",
        ai_act="prohibited",
        gdpr="sensitive",
    )

    scored_without, excluded_without = score_use_cases(use_cases, processes, HOURLY_COST_EUR)
    scored_with, excluded_with = score_use_cases(use_cases + [prohibited], processes, HOURLY_COST_EUR)

    assert excluded_without == []
    assert len(excluded_with) == 1
    assert excluded_with[0].ai_act == AIActLevel.PROHIBITED

    scores_without = {item.use_case.process_name: item.scores for item in scored_without}
    scores_with = {item.use_case.process_name: item.scores for item in scored_with}
    assert scores_without == scores_with


def test_phase0_ranking_is_reproduced(processes, use_cases):
    """The phase-0 use cases rank: supplier invoices, order status, quote generation, monthly reporting, CV screening."""
    scored, _ = score_use_cases(use_cases, processes, HOURLY_COST_EUR)
    ranking = [item.use_case.process_name for item in scored]
    assert ranking == [
        "Supplier invoice processing",
        "Order status inquiries",
        "Quote generation",
        "Monthly management reporting consolidation",
        "CV screening for open positions",
    ]


def test_default_weights_unchanged_after_scoring_with_custom_weights(processes, use_cases):
    """DEFAULT_WEIGHTS is unchanged after running score_use_cases with custom weights."""
    original = copy.deepcopy(DEFAULT_WEIGHTS)
    custom_weights = {
        "value": {"gain": 0.3, "quality": 0.3, "alignment": 0.4},
        "feasibility": {"data": 0.3, "complexity": 0.3, "market": 0.4},
        "risk": {"ai_act": 0.3, "gdpr": 0.3, "adoption": 0.4},
        "priority": {"value": 0.3, "feasibility": 0.3, "risk": 0.4},
    }

    score_use_cases(use_cases, processes, HOURLY_COST_EUR, custom_weights)

    assert DEFAULT_WEIGHTS == original


def test_unknown_process_name_raises_value_error_mentioning_the_process(processes, use_cases):
    """An unknown process_name raises a ValueError that names the missing process."""
    bad_use_case = use_cases[0].model_copy(update={"process_name": "Nonexistent process"})
    with pytest.raises(ValueError, match="Nonexistent process"):
        score_use_cases([bad_use_case], processes, HOURLY_COST_EUR)


def test_best_per_process_keeps_only_the_highest_priority_case_per_process(processes):
    """Among several use cases proposed for the same process, only the highest-priority one is kept."""
    candidates = [
        make_use_case(process_name="Order entry", pct_time_saved=0.2, quality_impact=2),
        make_use_case(process_name="Order entry", pct_time_saved=0.7, quality_impact=5),
        make_use_case(process_name="Quote generation", pct_time_saved=0.4, quality_impact=3),
    ]
    scored, _ = score_use_cases(candidates, processes, HOURLY_COST_EUR)

    best = best_per_process(scored)

    assert {item.use_case.process_name for item in best} == {"Order entry", "Quote generation"}
    order_entry_best = next(item for item in best if item.use_case.process_name == "Order entry")
    assert order_entry_best.use_case.pct_time_saved == 0.7


def test_best_per_process_with_no_duplicate_processes_returns_everything(processes, use_cases):
    """With one use case per process (the phase-0 demo), nothing is dropped."""
    scored, _ = score_use_cases(use_cases, processes, HOURLY_COST_EUR)
    assert best_per_process(scored) == scored
