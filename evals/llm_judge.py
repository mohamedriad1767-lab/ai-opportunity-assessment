"""LLM-as-judge: grade every row of the generation grading sheet with a
stronger model than the one used for generation, via forced tool use.

Reuses the retry style of core/generator.py (transient errors retry with
backoff; permanent errors raise immediately), kept local to this script
since the judge uses its own model, tool, and schema.
"""

import csv
import json
import logging
import os
import sys
import time

# Allow running this script directly (python evals/llm_judge.py) by making
# the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from core.config import JUDGE_MODEL_NAME, MODEL_NAME
from core.loader import load_processes
from core.models import Process
from core.prompts import PROMPT_VERSION

GRADING_PATH = f"evals/grading_{PROMPT_VERSION}.csv"
JUDGE_OUTPUT_PATH = f"evals/grading_{PROMPT_VERSION}_judge.csv"
RESULTS_PATH_TEMPLATE = "evals/results/{prompt_version}_{model_name}.jsonl"
EVAL_PROCESSES_PATH = "evals/eval_processes.csv"

TOOL_NAME = "submit_judgment"
MAX_TOKENS = 500
CLIENT_TIMEOUT_SECONDS = 30
MAX_TRANSIENT_RETRIES = 2
TRANSIENT_RETRY_DELAYS_SECONDS = [1, 2]

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """You are a senior AI strategy consultant acting as an \
independent reviewer of AI use cases that were proposed by a separate, \
weaker model for a client's business processes. You are strict and precise, \
not encouraging.

For the use case you are given, rate it on these criteria:
- relevance (1-5): 1 = off-topic, does not address the process's pain points; \
5 = I would present this use case to a client as-is.
- realism (1-5): 1 = the pct_time_saved or the assigned EU AI Act / GDPR risk \
level is absurd given the process; 5 = the numbers and risk levels are \
defensible in front of a CFO.
- overlaps_another (bool): true if this use case redoes a step already \
performed by another use case proposed for the SAME process (you will be \
shown every use case proposed for that process).
- ai_act_correct (bool): true if the ai_act level assigned to this use case \
is correct under the EU AI Act. Note that Annex III explicitly lists both \
recruitment AND evaluation of workers' performance or behaviour as high-risk \
use cases — watch for use cases mislabeled as lower risk than that.
- comment: one sentence explaining your ratings.

Respond by calling the submit_judgment tool. Do not respond with plain text."""


class JudgeVerdict(BaseModel):
    """A judge's verdict on a single generated use case."""

    relevance: int = Field(ge=1, le=5)
    realism: int = Field(ge=1, le=5)
    overlaps_another: bool
    ai_act_correct: bool
    comment: str


class JudgeError(Exception):
    """Raised when judging a use case fails after exhausting retries."""


def _build_tool() -> dict:
    return {
        "name": TOOL_NAME,
        "description": "Submit your judgment of the use case.",
        "input_schema": JudgeVerdict.model_json_schema(),
    }


def _call_judge(client: anthropic.Anthropic, user_prompt: str, sleep=time.sleep):
    """Call the judge model, retrying transient errors with exponential backoff.

    Permanent errors (authentication, bad request, other 4xx) raise
    JudgeError immediately, with no retry.
    """
    last_error: Exception | None = None
    for attempt in range(MAX_TRANSIENT_RETRIES + 1):
        try:
            return client.messages.create(
                model=JUDGE_MODEL_NAME,
                max_tokens=MAX_TOKENS,
                system=JUDGE_SYSTEM_PROMPT,
                tools=[_build_tool()],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=[{"role": "user", "content": user_prompt}],
            )
        except (anthropic.AuthenticationError, anthropic.BadRequestError) as exc:
            raise JudgeError(f"Permanent API error: {exc}") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code < 500:
                raise JudgeError(f"Permanent API error ({exc.status_code}): {exc}") from exc
            last_error = exc
        except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.RateLimitError) as exc:
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

    raise JudgeError(f"Judge call failed after {MAX_TRANSIENT_RETRIES + 1} attempts: {last_error}") from last_error


def build_judge_prompt(process: Process, use_cases: list[dict], target_idx: int) -> str:
    """Build the judging prompt for one use case, including its process context
    and the sibling use cases proposed for the same process (for overlap checks).
    """
    target = use_cases[target_idx]
    others = [uc for i, uc in enumerate(use_cases) if i != target_idx]
    others_text = "\n".join(f"- [{uc['type']}] {uc['description']}" for uc in others) or (
        "(none — this is the only use case proposed for this process)"
    )

    return f"""Process context:
- Process: {process.name}
- Team: {process.team}
- Volume: {process.volume_per_month} occurrences/month
- Minutes per occurrence: {process.minutes_per_occurrence}
- Pain points: {"; ".join(process.pain_points)}
- Data used: {"; ".join(process.data_used)}

Use case to judge:
- type: {target["type"]}
- description: {target["description"]}
- justification: {target["justification"]}
- pct_time_saved: {target["pct_time_saved"]}
- ai_act: {target["ai_act"]}
- gdpr: {target["gdpr"]}

Other use cases proposed for this SAME process (for checking overlap):
{others_text}

Judge the use case above. Call the submit_judgment tool with your ratings."""


def judge_use_case(
    client: anthropic.Anthropic, process: Process, use_cases: list[dict], target_idx: int, sleep=time.sleep
) -> JudgeVerdict:
    """Ask the judge model to grade one use case, returning a validated JudgeVerdict."""
    user_prompt = build_judge_prompt(process, use_cases, target_idx)
    response = _call_judge(client, user_prompt, sleep)
    tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use_block is None:
        raise JudgeError("No tool_use block was found in the judge's response.")
    try:
        return JudgeVerdict.model_validate(tool_use_block.input)
    except ValidationError as exc:
        raise JudgeError(f"Judge returned an invalid verdict: {exc}") from exc


def load_results_by_process(model_name: str) -> dict[str, list[dict]]:
    """Load the generation results jsonl, keyed by process name."""
    path = RESULTS_PATH_TEMPLATE.format(prompt_version=PROMPT_VERSION, model_name=model_name)
    results_by_process = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            results_by_process[record["process"]] = record["use_cases"]
    return results_by_process


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set. Add it to your .env file and try again.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key, timeout=CLIENT_TIMEOUT_SECONDS, max_retries=0)
    processes = {p.name: p for p in load_processes(EVAL_PROCESSES_PATH)}
    results_by_process = load_results_by_process(MODEL_NAME)

    with open(GRADING_PATH, encoding="utf-8", newline="") as f:
        grading_rows = list(csv.DictReader(f))

    judge_rows = []
    for row in grading_rows:
        process_name = row["process"]
        idx = int(row["idx"])
        process = processes[process_name]
        use_cases = results_by_process[process_name]

        print(f"Judging: {process_name} [{idx}]")
        verdict = judge_use_case(client, process, use_cases, idx)

        judge_rows.append(
            {
                "process": process_name,
                "idx": idx,
                "judge_relevance": verdict.relevance,
                "judge_realism": verdict.realism,
                "judge_overlaps_another": verdict.overlaps_another,
                "judge_ai_act_correct": verdict.ai_act_correct,
                "judge_comment": verdict.comment,
            }
        )

    fieldnames = [
        "process",
        "idx",
        "judge_relevance",
        "judge_realism",
        "judge_overlaps_another",
        "judge_ai_act_correct",
        "judge_comment",
    ]
    with open(JUDGE_OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(judge_rows)

    print(f"\nWrote {len(judge_rows)} judged rows to {JUDGE_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
