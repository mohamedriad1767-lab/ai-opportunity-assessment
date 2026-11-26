"""Generate AI use cases for a process via Anthropic tool use + Pydantic validation.

Handles transient API errors with retries and malformed model output with a
repair loop, so callers get either a valid list of UseCase objects or a
GenerationError explaining why generation failed.
"""

import logging
import re
import time

import anthropic
from pydantic import ValidationError

from core.config import MODEL_NAME
from core.models import Company, GenerationResult, Process, ProposalBatch, to_use_cases
from core.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

TOOL_NAME = "submit_use_cases"
MAX_TOKENS = 2000
CLIENT_TIMEOUT_SECONDS = 30
MAX_TRANSIENT_RETRIES = 2
TRANSIENT_RETRY_DELAYS_SECONDS = [1, 2]
MAX_REPAIR_ATTEMPTS = 2

# Prompt instructions are probabilistic; what code can check, code checks.
# A no_fit_reason that cites regulatory risk is rejected regardless of what
# the system prompt says, since the scoring layer (not the generator) is the
# place risk is handled.
RISK_REFUSAL_PATTERN = re.compile(
    r"ai act|high-risk|high risk|gdpr|legal|compliance|annex iii|regulat",
    re.IGNORECASE,
)
RISK_REFUSAL_REPAIR_MESSAGE = (
    "Regulatory risk is not a valid reason to return zero use cases. Propose "
    "the use cases and classify their ai_act and gdpr levels honestly; the "
    "scoring layer handles risk."
)


class GenerationError(Exception):
    """Raised when use-case generation fails after exhausting retries and repairs."""


def make_client(api_key: str) -> anthropic.Anthropic:
    """Build an Anthropic client with an explicit timeout and no built-in retries.

    max_retries=0 so retry behavior lives entirely in this module, where it
    is explicit and testable.
    """
    return anthropic.Anthropic(api_key=api_key, timeout=CLIENT_TIMEOUT_SECONDS, max_retries=0)


def _build_tool() -> dict:
    """Build the submit_use_cases tool definition from the ProposalBatch schema."""
    return {
        "name": TOOL_NAME,
        "description": "Submit the proposed AI use cases for this process.",
        "input_schema": ProposalBatch.model_json_schema(),
    }


def _call_model(
    client: anthropic.Anthropic, messages: list[dict], sleep, model: str
) -> anthropic.types.Message:
    """Call the model, retrying transient errors with exponential backoff.

    Permanent errors (authentication, bad request, other 4xx) raise
    GenerationError immediately, with no retry. Transient errors (connection,
    timeout, rate limit, 5xx) retry up to MAX_TRANSIENT_RETRIES more times.
    """
    last_error: Exception | None = None
    for attempt in range(MAX_TRANSIENT_RETRIES + 1):
        try:
            return client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=[_build_tool()],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=messages,
            )
        except anthropic.AuthenticationError as exc:
            raise GenerationError(f"Authentication failed: {exc}") from exc
        except anthropic.BadRequestError as exc:
            raise GenerationError(f"Bad request: {exc}") from exc
        except anthropic.RateLimitError as exc:
            last_error = exc
        except anthropic.APIStatusError as exc:
            if exc.status_code < 500:
                raise GenerationError(f"Permanent API error ({exc.status_code}): {exc}") from exc
            last_error = exc
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
            last_error = exc

        if attempt < MAX_TRANSIENT_RETRIES:
            delay = TRANSIENT_RETRY_DELAYS_SECONDS[attempt]
            logger.warning(
                "Transient error on attempt %d/%d: %s. Retrying in %ss.",
                attempt + 1,
                MAX_TRANSIENT_RETRIES + 1,
                last_error,
                delay,
            )
            sleep(delay)
        else:
            logger.error(
                "Exhausted all %d attempts. Last error: %s",
                MAX_TRANSIENT_RETRIES + 1,
                last_error,
            )

    raise GenerationError(
        f"API call failed after {MAX_TRANSIENT_RETRIES + 1} attempts: {last_error}"
    ) from last_error


def _find_tool_use_block(response: anthropic.types.Message):
    """Return the first tool_use content block in a response, or None."""
    return next((block for block in response.content if block.type == "tool_use"), None)


def _build_repair_messages(
    messages: list[dict], response: anthropic.types.Message, tool_use_block, error_text: str
) -> list[dict]:
    """Append the failed assistant turn and an error result asking the model to resubmit.

    If a tool_use block exists, the error is sent back as a tool_result with
    is_error=True (matching its tool_use_id). If there was no tool_use block
    at all, the error is sent back as plain user text instead, since there
    is no tool call to attach a tool_result to.
    """
    new_messages = [*messages, {"role": "assistant", "content": response.content}]
    if tool_use_block is not None:
        new_messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "content": error_text,
                        "is_error": True,
                    }
                ],
            }
        )
    else:
        new_messages.append(
            {
                "role": "user",
                "content": (
                    f"Your response did not call the {TOOL_NAME} tool. {error_text} "
                    f"Please call the {TOOL_NAME} tool now with valid input."
                ),
            }
        )
    return new_messages


def _record_usage(response: anthropic.types.Message, stats_accumulator: dict) -> None:
    """Add a response's token usage to the running stats_accumulator totals."""
    usage = getattr(response, "usage", None)
    if usage is not None:
        stats_accumulator["input_tokens"] += getattr(usage, "input_tokens", 0) or 0
        stats_accumulator["output_tokens"] += getattr(usage, "output_tokens", 0) or 0


def _mentions_risk_or_compliance(no_fit_reason: str | None) -> bool:
    """Return True if a no_fit_reason cites EU AI Act / GDPR / legal / compliance grounds."""
    if not no_fit_reason:
        return False
    return bool(RISK_REFUSAL_PATTERN.search(no_fit_reason))


def _fill_stats(stats: dict, stats_accumulator: dict, first_attempt_valid: bool) -> None:
    """Write the final stats_accumulator values into the caller's stats dict."""
    stats["api_calls"] = stats_accumulator["api_calls"]
    stats["repair_attempts"] = stats_accumulator["repair_attempts"]
    stats["first_attempt_valid"] = first_attempt_valid
    stats["input_tokens"] = stats_accumulator["input_tokens"]
    stats["output_tokens"] = stats_accumulator["output_tokens"]


def generate_use_cases(
    company: Company,
    process: Process,
    client: anthropic.Anthropic,
    sleep=time.sleep,
    stats: dict | None = None,
    model: str = MODEL_NAME,
) -> GenerationResult:
    """Ask the model for 0-3 AI use cases for a process, via forced tool use.

    Retries transient API errors with backoff (see _call_model), and repairs
    malformed model output (missing tool_use, max_tokens cutoff, schema
    violations, or a no_fit_reason that cites regulatory risk instead of a
    genuine lack of information-processing pain point) by feeding the error
    back to the model, up to MAX_REPAIR_ATTEMPTS times. Raises GenerationError
    if generation still fails after that.

    The returned GenerationResult always carries no_fit_reason alongside
    use_cases, so a "no good AI fit" answer is never silently dropped.

    model defaults to MODEL_NAME but can be overridden, e.g. to compare
    generator models without editing core/config.py.

    If stats is given, it is filled with: api_calls, repair_attempts,
    first_attempt_valid (bool), input_tokens, output_tokens (summed across
    all calls made for this process).
    """
    messages = [{"role": "user", "content": build_user_prompt(company, process)}]
    last_error_text = ""
    stats_accumulator = {"api_calls": 0, "repair_attempts": 0, "input_tokens": 0, "output_tokens": 0}

    for repair_attempt in range(MAX_REPAIR_ATTEMPTS + 1):
        response = _call_model(client, messages, sleep, model)
        stats_accumulator["api_calls"] += 1
        _record_usage(response, stats_accumulator)
        tool_use_block = _find_tool_use_block(response)

        if tool_use_block is None:
            last_error_text = "No tool_use block was found in the response."
        elif response.stop_reason == "max_tokens":
            last_error_text = (
                "The response was cut off at max_tokens before completing the tool call."
            )
        else:
            try:
                batch = ProposalBatch.model_validate(tool_use_block.input)
            except ValidationError as exc:
                last_error_text = str(exc)
            else:
                if not batch.use_cases and _mentions_risk_or_compliance(batch.no_fit_reason):
                    last_error_text = RISK_REFUSAL_REPAIR_MESSAGE
                else:
                    if stats is not None:
                        _fill_stats(stats, stats_accumulator, first_attempt_valid=repair_attempt == 0)
                    return GenerationResult(
                        use_cases=to_use_cases(batch, process.name),
                        no_fit_reason=batch.no_fit_reason,
                    )

        logger.warning(
            "Invalid generation output on attempt %d/%d: %s",
            repair_attempt + 1,
            MAX_REPAIR_ATTEMPTS + 1,
            last_error_text,
        )
        stats_accumulator["repair_attempts"] += 1
        messages = _build_repair_messages(messages, response, tool_use_block, last_error_text)

    if stats is not None:
        _fill_stats(stats, stats_accumulator, first_attempt_valid=False)

    raise GenerationError(
        f"Failed to generate valid use cases after {MAX_REPAIR_ATTEMPTS + 1} attempts: "
        f"{last_error_text}"
    )
