"""Tests for core/roadmap.py (no API calls)."""

import json

import pytest

from core.loader import load_processes
from core.models import AIActLevel, GDPRLevel, Process, ScoredUseCase, Scores, UseCase, UseCaseType
from core.roadmap import REASON_CAPACITY, REASON_DISCARD, build_roadmap
from core.scoring import score_use_cases

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


def make_scored_use_case(
    *,
    process_name: str = "Some process",
    value: float,
    feasibility: float,
    risk: float = 0.0,
    priority: float | None = None,
    ai_act: AIActLevel = AIActLevel.MINIMAL,
    rank: int = 1,
    annual_gain_eur: float = 1000.0,
) -> ScoredUseCase:
    """Build a fabricated ScoredUseCase fixture for roadmap rule tests."""
    use_case = UseCase(
        process_name=process_name,
        type=UseCaseType.ASSISTANT,
        description="A fabricated use case for roadmap testing.",
        justification="Test fixture.",
        pct_time_saved=0.5,
        quality_impact=3,
        strategic_alignment=3,
        data_quality=3,
        technical_complexity=3,
        adoption_risk=3,
        off_the_shelf=True,
        ai_act=ai_act,
        gdpr=GDPRLevel.NONE,
    )
    scores = Scores(
        value=value,
        feasibility=feasibility,
        risk=risk,
        priority=priority if priority is not None else value,
    )
    return ScoredUseCase(use_case=use_case, annual_gain_eur=annual_gain_eur, scores=scores, rank=rank)


def test_quick_win_lands_in_wave_1():
    """High value and high feasibility (Quick win) is planned in wave 1."""
    scored = [make_scored_use_case(value=80, feasibility=80)]
    planned, archived = build_roadmap(scored)
    assert archived == []
    assert planned[0].wave == 1


def test_structural_low_feasibility_lands_in_wave_3():
    """High value but low feasibility (Projets structurants, feasibility < 35) lands in wave 3."""
    scored = [make_scored_use_case(value=80, feasibility=20)]
    planned, archived = build_roadmap(scored)
    assert archived == []
    assert planned[0].wave == 3


def test_discard_is_archived_with_reason():
    """Low value and low feasibility (A écarter) is archived with the documented reason."""
    scored = [make_scored_use_case(value=20, feasibility=20)]
    planned, archived = build_roadmap(scored)
    assert planned == []
    assert archived[0].wave is None
    assert archived[0].reason == REASON_DISCARD


def test_high_risk_quick_win_is_pushed_to_wave_2():
    """A HIGH AI Act risk use case is never placed in wave 1, even if it is a Quick win."""
    scored = [make_scored_use_case(value=80, feasibility=80, ai_act=AIActLevel.HIGH)]
    planned, archived = build_roadmap(scored)
    assert archived == []
    assert planned[0].wave == 2
    assert "conformité" in planned[0].reason


def test_five_quick_wins_with_capacity_3_split_3_and_2_by_priority():
    """5 quick wins with max_per_wave=3 give 3 in wave 1 and 2 in wave 2, ordered by priority."""
    scored = [
        make_scored_use_case(process_name=f"Process {i}", value=80, feasibility=80, priority=priority, rank=i)
        for i, priority in enumerate([50, 90, 70, 60, 80], start=1)
    ]
    planned, archived = build_roadmap(scored, max_per_wave=3)
    assert archived == []

    wave_1 = [item for item in planned if item.wave == 1]
    wave_2 = [item for item in planned if item.wave == 2]
    assert len(wave_1) == 3
    assert len(wave_2) == 2

    assert [item.scored_use_case.scores.priority for item in wave_1] == [90, 80, 70]
    assert [item.scored_use_case.scores.priority for item in wave_2] == [60, 50]
    assert all(item.reason == REASON_CAPACITY for item in wave_2)


def test_phase0_demo_roadmap_matches_documented_assignment(processes, use_cases):
    """The phase-0 demo cases give: invoices W1, order status W1, quote generation W2,
    CV screening W2, monthly reporting archived."""
    scored, _ = score_use_cases(use_cases, processes, HOURLY_COST_EUR)
    planned, archived = build_roadmap(scored)

    waves = {item.scored_use_case.use_case.process_name: item.wave for item in planned}
    assert waves["Supplier invoice processing"] == 1
    assert waves["Order status inquiries"] == 1
    assert waves["Quote generation"] == 2
    assert waves["CV screening for open positions"] == 2

    archived_names = {item.scored_use_case.use_case.process_name for item in archived}
    assert archived_names == {"Monthly management reporting consolidation"}
