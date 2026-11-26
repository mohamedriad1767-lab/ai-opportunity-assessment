"""Tests for ProposalBatch validation and conversion (no API calls)."""

import pytest
from pydantic import ValidationError

from core.models import ProposalBatch, UseCase, to_use_cases


def make_proposal(**overrides) -> dict:
    """Build a minimal valid UseCaseProposal dict, with any field overridden."""
    defaults = dict(
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
        criteria_rationale={},
    )
    defaults.update(overrides)
    return defaults


def test_batch_with_pct_sum_above_0_8_is_rejected():
    """A batch whose pct_time_saved values sum above 0.8 is rejected."""
    with pytest.raises(ValidationError):
        ProposalBatch(
            use_cases=[
                make_proposal(pct_time_saved=0.5),
                make_proposal(pct_time_saved=0.4),
            ]
        )


def test_batch_with_zero_use_cases_is_rejected():
    """A batch with 0 use cases is rejected."""
    with pytest.raises(ValidationError):
        ProposalBatch(use_cases=[])


def test_batch_with_four_use_cases_is_rejected():
    """A batch with 4 use cases is rejected (max is 3)."""
    with pytest.raises(ValidationError):
        ProposalBatch(
            use_cases=[
                make_proposal(pct_time_saved=0.1),
                make_proposal(pct_time_saved=0.1),
                make_proposal(pct_time_saved=0.1),
                make_proposal(pct_time_saved=0.1),
            ]
        )


def test_valid_batch_converts_to_use_cases_with_given_process_name():
    """A valid batch converts to UseCase objects carrying the given process_name."""
    batch = ProposalBatch(
        use_cases=[
            make_proposal(pct_time_saved=0.3),
            make_proposal(pct_time_saved=0.2),
        ]
    )

    use_cases = to_use_cases(batch, "Supplier invoice processing")

    assert len(use_cases) == 2
    assert all(isinstance(uc, UseCase) for uc in use_cases)
    assert all(uc.process_name == "Supplier invoice processing" for uc in use_cases)
