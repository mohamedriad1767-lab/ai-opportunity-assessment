"""Value x feasibility quadrant classification.

Pure classification only — no I/O, no printing.
"""

import statistics
from enum import Enum

from core.models import ScoredUseCase


class Quadrant(str, Enum):
    """The 4 quadrants of the value x feasibility matrix."""

    QUICK_WIN = "Quick wins"
    STRUCTURAL = "Projets structurants"
    OPTIMIZATION = "Optimisations"
    DISCARD = "À écarter"


class ThresholdMode(str, Enum):
    """How the quadrant thresholds are set.

    ABSOLUTE: fixed bar (e.g. 50/50), independent of the portfolio.
    RELATIVE: the portfolio's own median value/feasibility, so quadrants
    split the actual portfolio in half rather than against a fixed bar.
    """

    ABSOLUTE = "absolute"
    RELATIVE = "relative"


def portfolio_thresholds(
    scored_use_cases: list[ScoredUseCase],
    mode: ThresholdMode,
    absolute_value: float = 50,
    absolute_feasibility: float = 50,
) -> tuple[float, float]:
    """Return (value_threshold, feasibility_threshold) for the quadrant matrix.

    In ABSOLUTE mode, always returns (absolute_value, absolute_feasibility).
    In RELATIVE mode, returns the portfolio's median value and median
    feasibility: useful when LLM-prefilled criteria cluster scores together
    (see docs/decisions.md), which otherwise pushes most of the portfolio
    into a single quadrant under a fixed 50/50 bar. Falls back to absolute
    mode for an empty portfolio, since a median is undefined with no data.
    """
    if mode == ThresholdMode.ABSOLUTE or not scored_use_cases:
        return absolute_value, absolute_feasibility
    values = [item.scores.value for item in scored_use_cases]
    feasibilities = [item.scores.feasibility for item in scored_use_cases]
    return statistics.median(values), statistics.median(feasibilities)


def classify_quadrant(
    value: float,
    feasibility: float,
    value_threshold: float = 50,
    feasibility_threshold: float = 50,
) -> Quadrant:
    """Classify a use case into one of the 4 quadrants.

    high value + high feasibility -> QUICK_WIN
    high value + low feasibility  -> STRUCTURAL
    low value + high feasibility  -> OPTIMIZATION
    low value + low feasibility   -> DISCARD

    A score exactly equal to its threshold counts as "high".
    """
    high_value = value >= value_threshold
    high_feasibility = feasibility >= feasibility_threshold

    if high_value and high_feasibility:
        return Quadrant.QUICK_WIN
    if high_value:
        return Quadrant.STRUCTURAL
    if high_feasibility:
        return Quadrant.OPTIMIZATION
    return Quadrant.DISCARD
