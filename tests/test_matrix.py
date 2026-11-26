"""Tests for core/matrix.py (no API calls)."""

from core.matrix import Quadrant, classify_quadrant


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
