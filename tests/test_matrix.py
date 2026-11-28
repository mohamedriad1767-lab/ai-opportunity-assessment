"""Tests for core/matrix.py (no API calls)."""

from core.matrix import Quadrant, ThresholdMode, classify_quadrant, portfolio_thresholds
from core.models import AIActLevel, GDPRLevel, ScoredUseCase, Scores, UseCase, UseCaseType


def test_high_value_high_feasibility_is_quick_win():
    """High value and high feasibility classify as QUICK_WIN."""
    assert classify_quadrant(80, 80) == Quadrant.QUICK_WIN


def test_high_value_low_feasibility_is_structural():
    """High value and low feasibility classify as STRUCTURAL."""
    assert classify_quadrant(80, 20) == Quadrant.STRUCTURAL


def test_low_value_high_feasibility_is_optimization():
    """Low value and high feasibility classify as OPTIMIZATION."""
    assert classify_quadrant(20, 80) == Quadrant.OPTIMIZATION


def test_low_value_low_feasibility_is_discard():
    """Low value and low feasibility classify as DISCARD."""
    assert classify_quadrant(20, 20) == Quadrant.DISCARD


def test_score_exactly_at_threshold_counts_as_high():
    """A score exactly equal to its threshold counts as high (boundary case)."""
    assert classify_quadrant(50, 50, value_threshold=50, feasibility_threshold=50) == Quadrant.QUICK_WIN


def _make_scored_use_case(value: float, feasibility: float, rank: int) -> ScoredUseCase:
    """Build a minimal fabricated ScoredUseCase for threshold tests."""
    use_case = UseCase(
        process_name=f"Process {rank}",
        type=UseCaseType.ASSISTANT,
        description="Fabricated use case.",
        justification="Test fixture.",
        pct_time_saved=0.5,
        quality_impact=3,
        strategic_alignment=3,
        data_quality=3,
        technical_complexity=3,
        adoption_risk=3,
        off_the_shelf=True,
        ai_act=AIActLevel.MINIMAL,
        gdpr=GDPRLevel.NONE,
    )
    scores = Scores(value=value, feasibility=feasibility, risk=0.0, priority=value)
    return ScoredUseCase(use_case=use_case, annual_gain_eur=1000.0, scores=scores, rank=rank)


def test_absolute_mode_always_returns_fixed_thresholds():
    """ABSOLUTE mode ignores the portfolio and returns the fixed thresholds."""
    portfolio = [_make_scored_use_case(value=10, feasibility=90, rank=1)]
    assert portfolio_thresholds(portfolio, ThresholdMode.ABSOLUTE) == (50, 50)
    assert portfolio_thresholds(portfolio, ThresholdMode.ABSOLUTE, 40, 60) == (40, 60)


def test_relative_mode_splits_a_fabricated_portfolio_roughly_in_half():
    """RELATIVE mode uses the portfolio's own median, splitting it roughly in half."""
    portfolio = [
        _make_scored_use_case(value=v, feasibility=f, rank=i)
        for i, (v, f) in enumerate([(10, 15), (30, 35), (50, 55), (70, 75), (90, 95)], start=1)
    ]
    value_threshold, feasibility_threshold = portfolio_thresholds(portfolio, ThresholdMode.RELATIVE)
    assert value_threshold == 50
    assert feasibility_threshold == 55

    high_value_count = sum(1 for item in portfolio if item.scores.value >= value_threshold)
    high_feasibility_count = sum(1 for item in portfolio if item.scores.feasibility >= feasibility_threshold)
    assert high_value_count == 3  # 50, 70, 90 (median counts as high)
    assert high_feasibility_count == 3  # 55, 75, 95


def test_relative_mode_on_empty_portfolio_falls_back_to_absolute():
    """RELATIVE mode on an empty portfolio falls back to the absolute thresholds."""
    assert portfolio_thresholds([], ThresholdMode.RELATIVE) == (50, 50)
    assert portfolio_thresholds([], ThresholdMode.RELATIVE, 42, 58) == (42, 58)
