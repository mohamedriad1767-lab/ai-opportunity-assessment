"""Tests for core/generator.py using a fake client — no real API calls."""

import anthropic
import httpx2
import pytest

from core.generator import GenerationError, generate_use_cases
from core.models import Company, GenerationResult, Process, UseCase


class FakeBlock:
    """A minimal stand-in for an Anthropic content block."""

    def __init__(self, type: str, **kwargs):
        self.type = type
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeUsage:
    """A minimal stand-in for an Anthropic Usage object."""

    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeMessage:
    """A minimal stand-in for an Anthropic Message response."""

    def __init__(
        self,
        content: list[FakeBlock],
        stop_reason: str = "tool_use",
        usage: FakeUsage | None = None,
    ):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage or FakeUsage(input_tokens=0, output_tokens=0)


class FakeMessagesResource:
    """Replays a scripted sequence of responses/exceptions for .create() calls."""

    def __init__(self, behaviors: list):
        self.behaviors = list(behaviors)
        self.call_count = 0

    def create(self, **kwargs):
        self.call_count += 1
        behavior = self.behaviors.pop(0)
        if isinstance(behavior, BaseException):
            raise behavior
        return behavior


class FakeClient:
    """A minimal stand-in for anthropic.Anthropic, exposing only .messages.create()."""

    def __init__(self, behaviors: list):
        self.messages = FakeMessagesResource(behaviors)


def make_proposal_dict(pct_time_saved: float = 0.3) -> dict:
    """Build a minimal valid use-case proposal dict for a fake tool_use input."""
    return {
        "type": "assistant",
        "description": "A test use case.",
        "justification": "For testing only.",
        "pct_time_saved": pct_time_saved,
        "quality_impact": 3,
        "strategic_alignment": 3,
        "data_quality": 3,
        "technical_complexity": 3,
        "adoption_risk": 3,
        "off_the_shelf": True,
        "ai_act": "minimal",
        "gdpr": "none",
        "criteria_rationale": {},
    }


def valid_tool_use_block(block_id: str = "toolu_1") -> FakeBlock:
    """A tool_use block whose input validates as a ProposalBatch."""
    return FakeBlock("tool_use", id=block_id, input={"use_cases": [make_proposal_dict(0.3)]})


def invalid_tool_use_block(block_id: str = "toolu_1") -> FakeBlock:
    """A tool_use block whose input fails ProposalBatch validation (sum > 0.8)."""
    return FakeBlock("tool_use", id=block_id, input={"use_cases": [make_proposal_dict(0.9)]})


def no_fit_tool_use_block(block_id: str = "toolu_1", reason: str = "Purely physical task.") -> FakeBlock:
    """A tool_use block whose input validates as a ProposalBatch with 0 use cases."""
    return FakeBlock("tool_use", id=block_id, input={"use_cases": [], "no_fit_reason": reason})


def no_op_sleep(_seconds: float) -> None:
    """A sleep replacement that does nothing, so tests run instantly."""


@pytest.fixture
def company() -> Company:
    return Company(name="Test Co", sector="Test sector", employees=100, hourly_cost_eur=35)


@pytest.fixture
def process() -> Process:
    return Process(
        name="Test process",
        team="Ops",
        volume_per_month=100,
        minutes_per_occurrence=5,
        pain_points="Pain point one; pain point two",
        data_used="Some data",
    )


def make_api_error(exception_class: type[BaseException], status_code: int) -> BaseException:
    """Build a real anthropic API exception instance with the given status code."""
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(
        status_code, request=request, json={"error": {"message": "test error"}}
    )
    return exception_class("test error", response=response, body=None)


def test_valid_first_answer_returns_use_cases_in_one_call(company, process):
    """A valid tool_use block on the first try returns a GenerationResult after 1 call."""
    client = FakeClient([FakeMessage([valid_tool_use_block()])])

    result = generate_use_cases(company, process, client, sleep=no_op_sleep)

    assert isinstance(result, GenerationResult)
    assert len(result.use_cases) == 1
    assert isinstance(result.use_cases[0], UseCase)
    assert result.use_cases[0].process_name == process.name
    assert result.no_fit_reason is None
    assert client.messages.call_count == 1


def test_invalid_then_valid_succeeds_after_one_repair(company, process):
    """An invalid batch followed by a valid one succeeds after exactly 2 calls."""
    client = FakeClient(
        [FakeMessage([invalid_tool_use_block()]), FakeMessage([valid_tool_use_block()])]
    )

    result = generate_use_cases(company, process, client, sleep=no_op_sleep)

    assert len(result.use_cases) == 1
    assert client.messages.call_count == 2


def test_invalid_three_times_raises_generation_error(company, process):
    """Three consecutive invalid batches exhaust repairs and raise GenerationError."""
    client = FakeClient([FakeMessage([invalid_tool_use_block()]) for _ in range(3)])

    with pytest.raises(GenerationError):
        generate_use_cases(company, process, client, sleep=no_op_sleep)

    assert client.messages.call_count == 3


def test_transient_error_twice_then_success_succeeds_after_three_calls(company, process):
    """Two transient rate-limit errors followed by success succeed after 3 calls."""
    rate_limit_error = make_api_error(anthropic.RateLimitError, 429)
    client = FakeClient([rate_limit_error, rate_limit_error, FakeMessage([valid_tool_use_block()])])
    sleep_calls = []

    result = generate_use_cases(company, process, client, sleep=sleep_calls.append)

    assert len(result.use_cases) == 1
    assert client.messages.call_count == 3
    assert sleep_calls == [1, 2]


def test_authentication_error_raises_immediately_with_one_call(company, process):
    """An authentication error raises GenerationError immediately, with no retry."""
    auth_error = make_api_error(anthropic.AuthenticationError, 401)
    client = FakeClient([auth_error])

    with pytest.raises(GenerationError):
        generate_use_cases(company, process, client, sleep=no_op_sleep)

    assert client.messages.call_count == 1


def test_no_tool_use_block_is_treated_as_invalid_and_repaired(company, process):
    """A response with no tool_use block is repaired like an invalid batch."""
    client = FakeClient(
        [
            FakeMessage([FakeBlock("text", text="I cannot help with that.")], stop_reason="end_turn"),
            FakeMessage([valid_tool_use_block()]),
        ]
    )

    result = generate_use_cases(company, process, client, sleep=no_op_sleep)

    assert len(result.use_cases) == 1
    assert client.messages.call_count == 2


def test_no_fit_reason_is_preserved_in_generation_result(company, process):
    """A 0-use-case answer with a no_fit_reason is returned, not dropped."""
    client = FakeClient([FakeMessage([no_fit_tool_use_block(reason="Purely manual labor.")])])

    result = generate_use_cases(company, process, client, sleep=no_op_sleep)

    assert result.use_cases == []
    assert result.no_fit_reason == "Purely manual labor."


def test_stats_are_filled_after_one_repair(company, process):
    """stats reflects 2 api_calls, 1 repair, first_attempt_valid=False, and summed tokens."""
    client = FakeClient(
        [
            FakeMessage([invalid_tool_use_block()], usage=FakeUsage(100, 50)),
            FakeMessage([valid_tool_use_block()], usage=FakeUsage(120, 60)),
        ]
    )
    stats: dict = {}

    generate_use_cases(company, process, client, sleep=no_op_sleep, stats=stats)

    assert stats["api_calls"] == 2
    assert stats["repair_attempts"] == 1
    assert stats["first_attempt_valid"] is False
    assert stats["input_tokens"] == 220
    assert stats["output_tokens"] == 110
