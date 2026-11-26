"""Value x feasibility quadrant classification.

Pure classification only — no I/O, no printing.
"""

from enum import Enum


class Quadrant(str, Enum):
    """The 4 quadrants of the value x feasibility matrix."""

    QUICK_WIN = "Quick wins"
    STRUCTURAL = "Projets structurants"
    OPTIMIZATION = "Optimisations"
    DISCARD = "À écarter"


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
