"""3-wave implementation roadmap built from the value x feasibility matrix.

Pure functions only — no I/O, no printing. The roadmap takes already-scored
use cases and the already-computed quadrant classification and turns them
into a wave assignment (planned) or an explicit exclusion (archived).
"""

from enum import Enum

from pydantic import BaseModel

from core.matrix import Quadrant, classify_quadrant
from core.models import AIActLevel, ScoredUseCase

REASON_DISCARD = "Valeur et faisabilité faibles"
REASON_CAPACITY = "Report pour capacité"


class Wave(int, Enum):
    """The 3 implementation waves of the roadmap."""

    WAVE_1 = 1
    WAVE_2 = 2
    WAVE_3 = 3


WAVE_LABELS: dict[Wave, str] = {
    Wave.WAVE_1: "0-3 mois",
    Wave.WAVE_2: "3-9 mois",
    Wave.WAVE_3: "9-18 mois",
}


class RoadmapItem(BaseModel):
    """A single use case placed on the roadmap (or archived)."""

    scored_use_case: ScoredUseCase
    quadrant: Quadrant
    wave: int | None
    reason: str


def _default_wave_and_reason(quadrant: Quadrant, feasibility: float) -> tuple[int | None, str]:
    """Return the default (wave, reason) for a quadrant, before the AI Act and capacity rules.

    Quick wins -> wave 1. Optimisations -> wave 2. Projets structurants -> wave 2
    if feasibility >= 35, else wave 3 (more preparation needed). A écarter -> archived
    (wave None), with the exact reason "Valeur et faisabilité faibles".
    """
    if quadrant == Quadrant.QUICK_WIN:
        return 1, "Quick win : forte valeur et forte faisabilité."
    if quadrant == Quadrant.OPTIMIZATION:
        return 2, "Optimisation : faisabilité suffisante mais valeur plus limitée."
    if quadrant == Quadrant.STRUCTURAL:
        if feasibility >= 35:
            return 2, "Projet structurant avec une faisabilité suffisante (>= 35) pour démarrer en vague 2."
        return 3, "Projet structurant nécessitant une préparation plus longue (faisabilité < 35)."
    return None, REASON_DISCARD


def build_roadmap(
    scored_use_cases: list[ScoredUseCase],
    value_threshold: float = 50,
    feasibility_threshold: float = 50,
    max_per_wave: int = 3,
) -> tuple[list[RoadmapItem], list[RoadmapItem]]:
    """Build the 3-wave roadmap, returning (planned, archived).

    Rules, applied in this order:
    (a) Quadrant decides the default wave: Quick wins -> 1; Optimisations -> 2;
        Projets structurants -> 2 if feasibility >= 35 else 3; A écarter -> archived
        (wave None, reason "Valeur et faisabilité faibles").
    (b) A HIGH AI Act risk use case is never placed in wave 1: it is moved to
        wave 2, with a reason mentioning the compliance work this requires.
    (c) Capacity: waves are processed in order (1, then 2, then 3). Within a
        wave, items are sorted by priority descending; items beyond
        max_per_wave are pushed into the next wave with the reason
        "Report pour capacité". Overflow pushed out of wave 3 has nowhere
        left to go and stays in wave 3.

    scored_use_cases is not mutated. Planned items are returned ordered by
    wave, then by priority descending within each wave.
    """
    archived: list[RoadmapItem] = []
    buckets: dict[int, list[RoadmapItem]] = {1: [], 2: [], 3: []}

    for item in scored_use_cases:
        quadrant = classify_quadrant(
            item.scores.value, item.scores.feasibility, value_threshold, feasibility_threshold
        )
        wave, reason = _default_wave_and_reason(quadrant, item.scores.feasibility)

        if wave is None:
            archived.append(RoadmapItem(scored_use_case=item, quadrant=quadrant, wave=None, reason=reason))
            continue

        if item.use_case.ai_act == AIActLevel.HIGH and wave == 1:
            wave = 2
            reason = (
                "Risque AI Act élevé : un travail de conformité (documentation, supervision "
                "humaine) est requis avant toute mise en œuvre, incompatible avec un quick win."
            )

        buckets[wave].append(RoadmapItem(scored_use_case=item, quadrant=quadrant, wave=wave, reason=reason))

    for wave in (1, 2):
        buckets[wave].sort(key=lambda roadmap_item: roadmap_item.scored_use_case.scores.priority, reverse=True)
        overflow = buckets[wave][max_per_wave:]
        buckets[wave] = buckets[wave][:max_per_wave]
        for roadmap_item in overflow:
            buckets[wave + 1].append(
                RoadmapItem(
                    scored_use_case=roadmap_item.scored_use_case,
                    quadrant=roadmap_item.quadrant,
                    wave=wave + 1,
                    reason=REASON_CAPACITY,
                )
            )

    buckets[3].sort(key=lambda roadmap_item: roadmap_item.scored_use_case.scores.priority, reverse=True)

    planned = buckets[1] + buckets[2] + buckets[3]
    return planned, archived
