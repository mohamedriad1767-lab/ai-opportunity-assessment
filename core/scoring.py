"""Pure scoring calculations for processes.

Functions here take explicit inputs and return a value, with no I/O,
no globals, and no printing.
"""

import math

from core.models import AIActLevel, GDPRLevel, Process, ScoredUseCase, Scores, UseCase

MONTHS_PER_YEAR = 12
MINUTES_PER_HOUR = 60

# Default weights for each scoring axis. Each axis's sub-weights must sum to 1.0.
DEFAULT_WEIGHTS = {
    "value": {"gain": 0.50, "quality": 0.30, "alignment": 0.20},
    "feasibility": {"data": 0.40, "complexity": 0.35, "market": 0.25},
    "risk": {"ai_act": 0.40, "gdpr": 0.30, "adoption": 0.30},
    "priority": {"value": 0.45, "feasibility": 0.35, "risk": 0.20},
}

_WEIGHT_SUM_TOLERANCE = 1e-9


def annual_hours(process: Process) -> float:
    """Return the estimated annual hours spent on a process.

    Computed as volume_per_month * MONTHS_PER_YEAR * minutes_per_occurrence / MINUTES_PER_HOUR.
    """
    return process.volume_per_month * MONTHS_PER_YEAR * process.minutes_per_occurrence / MINUTES_PER_HOUR


def annual_time_value(process: Process, hourly_cost: float) -> float:
    """Return the annual monetary value of the time spent on a process.

    Computed as annual_hours(process) * hourly_cost.
    Raises ValueError if hourly_cost is not strictly positive.
    """
    if hourly_cost <= 0:
        raise ValueError("hourly_cost must be strictly positive")
    return annual_hours(process) * hourly_cost


def normalize_log_minmax(values: list[float]) -> list[float]:
    """Map values to a 0-100 scale using min-max normalization on the natural log.

    score = (ln(v) - ln(min)) / (ln(max) - ln(min)) * 100,
    where min and max are taken over the strictly positive values only.

    Edge cases:
    - Empty input list: returns [].
    - Values <= 0: they have no defined logarithm, so they get a score of 0,
      and they are excluded when computing min/max for the other values.
    - All positive values equal, or only one positive value in the list:
      there is no information to rank them against each other, so every
      positive value gets the neutral score 50.

    Scores are rounded to 1 decimal and returned in the same order as the input.
    """
    if not values:
        return []

    positive_values = [v for v in values if v > 0]

    if not positive_values:
        return [0.0 for _ in values]

    log_values = [math.log(v) for v in positive_values]
    log_min = min(log_values)
    log_max = max(log_values)

    if log_max == log_min:
        return [50.0 if v > 0 else 0.0 for v in values]

    scores = []
    for v in values:
        if v <= 0:
            scores.append(0.0)
        else:
            score = (math.log(v) - log_min) / (log_max - log_min) * 100
            scores.append(round(score, 1))
    return scores


def validate_weights(weights: dict[str, dict[str, float]]) -> None:
    """Validate that each axis's sub-weights sum to 1.0 (within a 1e-9 tolerance).

    Accepts a full weights dict (one entry per axis) or a partial one
    (only the axes that matter for the caller); every axis present is checked.
    Raises ValueError if any axis's sub-weights do not sum to 1.0.
    """
    for axis, sub_weights in weights.items():
        total = sum(sub_weights.values())
        if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"Weights for axis '{axis}' must sum to 1.0, got {total}")


def note_to_100(note: int) -> float:
    """Convert a 1-5 note to a 0-100 scale: (note - 1) / 4 * 100.

    Raises ValueError if note is outside the 1-5 range.
    """
    if note < 1 or note > 5:
        raise ValueError(f"note must be between 1 and 5, got {note}")
    return (note - 1) / 4 * 100


def ai_act_to_100(level: AIActLevel) -> float:
    """Convert an AI Act risk level to a 0-100 scale: minimal=0, limited=50, high=100.

    "prohibited" is deliberately not scored here: it must be filtered out of the
    pipeline before scoring (planned for step 1.5), so it raises ValueError.
    """
    mapping = {
        AIActLevel.MINIMAL: 0.0,
        AIActLevel.LIMITED: 50.0,
        AIActLevel.HIGH: 100.0,
    }
    if level not in mapping:
        raise ValueError(f"AI Act level '{level}' is not scored; it must be filtered out beforehand")
    return mapping[level]


def gdpr_to_100(level: GDPRLevel) -> float:
    """Convert a GDPR sensitivity level to a 0-100 scale: none=0, indirect=50, sensitive=100."""
    mapping = {
        GDPRLevel.NONE: 0.0,
        GDPRLevel.INDIRECT: 50.0,
        GDPRLevel.SENSITIVE: 100.0,
    }
    return mapping[level]


def off_the_shelf_to_100(off_the_shelf: bool) -> float:
    """Convert the off_the_shelf flag to a 0-100 scale: True=100, False=0."""
    return 100.0 if off_the_shelf else 0.0


def value_score(
    use_case: UseCase,
    gain_score: float,
    weights: dict[str, dict[str, float]] | None = None,
) -> float:
    """Compute the value score (0-100) of a use case.

    gain_score is the already-normalized 0-100 gain (e.g. from normalize_log_minmax).
    Combines gain, quality_impact and strategic_alignment using weights["value"].
    weights defaults to DEFAULT_WEIGHTS and is never mutated.
    """
    weights = weights if weights is not None else DEFAULT_WEIGHTS
    validate_weights(weights)
    w = weights["value"]
    quality_100 = note_to_100(use_case.quality_impact)
    alignment_100 = note_to_100(use_case.strategic_alignment)
    score = w["gain"] * gain_score + w["quality"] * quality_100 + w["alignment"] * alignment_100
    return round(score, 1)


def feasibility_score(
    use_case: UseCase,
    weights: dict[str, dict[str, float]] | None = None,
) -> float:
    """Compute the feasibility score (0-100) of a use case.

    Combines data_quality, technical_complexity (inverted: 5 -> 0) and
    off_the_shelf using weights["feasibility"].
    weights defaults to DEFAULT_WEIGHTS and is never mutated.
    """
    weights = weights if weights is not None else DEFAULT_WEIGHTS
    validate_weights(weights)
    w = weights["feasibility"]
    data_100 = note_to_100(use_case.data_quality)
    complexity_100 = 100 - note_to_100(use_case.technical_complexity)
    market_100 = off_the_shelf_to_100(use_case.off_the_shelf)
    score = w["data"] * data_100 + w["complexity"] * complexity_100 + w["market"] * market_100
    return round(score, 1)


def risk_score(
    use_case: UseCase,
    weights: dict[str, dict[str, float]] | None = None,
) -> float:
    """Compute the risk score (0-100) of a use case.

    Combines ai_act, gdpr and adoption_risk using weights["risk"].
    weights defaults to DEFAULT_WEIGHTS and is never mutated.
    """
    weights = weights if weights is not None else DEFAULT_WEIGHTS
    validate_weights(weights)
    w = weights["risk"]
    ai_act_100 = ai_act_to_100(use_case.ai_act)
    gdpr_100 = gdpr_to_100(use_case.gdpr)
    adoption_100 = note_to_100(use_case.adoption_risk)
    score = w["ai_act"] * ai_act_100 + w["gdpr"] * gdpr_100 + w["adoption"] * adoption_100
    return round(score, 1)


def priority_score(
    value: float,
    feasibility: float,
    risk: float,
    weights: dict[str, dict[str, float]] | None = None,
) -> float:
    """Compute the overall priority score (0-100) from the three axes.

    priority = w_value * value + w_feasibility * feasibility + w_risk * (100 - risk),
    using weights["priority"]. weights defaults to DEFAULT_WEIGHTS and is never mutated.
    """
    weights = weights if weights is not None else DEFAULT_WEIGHTS
    validate_weights(weights)
    w = weights["priority"]
    score = w["value"] * value + w["feasibility"] * feasibility + w["risk"] * (100 - risk)
    return round(score, 1)


def split_prohibited(use_cases: list[UseCase]) -> tuple[list[UseCase], list[UseCase]]:
    """Split use cases into (allowed, excluded), where excluded have ai_act == prohibited."""
    allowed = [uc for uc in use_cases if uc.ai_act != AIActLevel.PROHIBITED]
    excluded = [uc for uc in use_cases if uc.ai_act == AIActLevel.PROHIBITED]
    return allowed, excluded


def score_use_cases(
    use_cases: list[UseCase],
    processes: dict[str, Process],
    hourly_cost: float,
    weights: dict[str, dict[str, float]] | None = None,
) -> tuple[list[ScoredUseCase], list[UseCase]]:
    """Score and rank a portfolio of use cases, filtering out prohibited ones.

    Order of operations:
    (a) exclude prohibited use cases first (they are never scored or ranked);
    (b) compute each gain = annual_time_value(process, hourly_cost) * pct_time_saved;
    (c) normalize gains with normalize_log_minmax, over the allowed use cases only,
        so a prohibited outlier cannot distort the min/max of the remaining portfolio;
    (d) compute value, feasibility, risk and priority for each allowed use case;
    (e) sort by priority descending and assign rank 1..n.

    weights defaults to DEFAULT_WEIGHTS and is never mutated.
    Returns (scored_use_cases, excluded_use_cases).
    """
    weights = weights if weights is not None else DEFAULT_WEIGHTS
    validate_weights(weights)

    allowed, excluded = split_prohibited(use_cases)

    gains = []
    for uc in allowed:
        if uc.process_name not in processes:
            raise ValueError(f"Unknown process_name '{uc.process_name}': no matching process was provided")
        gains.append(annual_time_value(processes[uc.process_name], hourly_cost) * uc.pct_time_saved)
    gain_scores = normalize_log_minmax(gains)

    unranked: list[tuple[UseCase, float, Scores]] = []
    for uc, gain, gain_score in zip(allowed, gains, gain_scores):
        value = value_score(uc, gain_score, weights)
        feasibility = feasibility_score(uc, weights)
        risk = risk_score(uc, weights)
        priority = priority_score(value, feasibility, risk, weights)
        scores = Scores(value=value, feasibility=feasibility, risk=risk, priority=priority)
        unranked.append((uc, gain, scores))

    unranked.sort(key=lambda item: item[2].priority, reverse=True)

    scored = [
        ScoredUseCase(use_case=uc, annual_gain_eur=gain, scores=scores, rank=rank)
        for rank, (uc, gain, scores) in enumerate(unranked, start=1)
    ]
    return scored, excluded
