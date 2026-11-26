"""Generate AI use cases for a process via Anthropic tool use + Pydantic validation."""

import anthropic

from core.config import MODEL_NAME
from core.models import Company, ProposalBatch, Process, UseCase, to_use_cases
from core.prompts import SYSTEM_PROMPT, build_user_prompt

TOOL_NAME = "submit_use_cases"


def generate_use_cases(
    company: Company, process: Process, client: anthropic.Anthropic
) -> list[UseCase]:
    """Ask the model for 1-3 AI use cases for a process, via forced tool use.

    The model's output is validated against ProposalBatch before being
    converted to UseCase objects. No retries on validation failure yet
    (that is step 2.4).
    """
    tool = {
        "name": TOOL_NAME,
        "description": "Submit the proposed AI use cases for this process.",
        "input_schema": ProposalBatch.model_json_schema(),
    }

    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=[tool],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=[{"role": "user", "content": build_user_prompt(company, process)}],
    )

    tool_use_block = next(block for block in response.content if block.type == "tool_use")
    batch = ProposalBatch.model_validate(tool_use_block.input)
    return to_use_cases(batch, process.name)
