"""Try the use-case generation prompt on two real demo processes, 3 times each
to observe run-to-run variance. Writes the full output to checkpoint.txt.
"""

import json
import os
import sys

# Allow running this script directly (python scripts/try_generation.py) by
# making the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from dotenv import load_dotenv

from core.config import MODEL_NAME, PRICE_INPUT_PER_MTOK_USD, PRICE_OUTPUT_PER_MTOK_USD
from core.loader import load_processes
from core.models import Company
from core.prompts import SYSTEM_PROMPT, build_user_prompt

PROCESS_NAMES = ["Supplier invoice processing", "Customer complaint handling"]
RUNS_PER_PROCESS = 3


def compute_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * PRICE_INPUT_PER_MTOK_USD
        + output_tokens / 1_000_000 * PRICE_OUTPUT_PER_MTOK_USD
    )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set. Add it to your .env file and try again.")
        sys.exit(1)

    with open("data/demo_company_profile.json", encoding="utf-8") as f:
        company = Company(**json.load(f))

    processes = {p.name: p for p in load_processes("data/demo_company.csv")}
    client = anthropic.Anthropic(api_key=api_key)

    output_lines = []

    def emit(line: str = "") -> None:
        print(line)
        output_lines.append(line)

    emit("SYSTEM_PROMPT:")
    emit(SYSTEM_PROMPT)
    emit()

    total_cost = 0.0

    for name in PROCESS_NAMES:
        process = processes[name]
        user_prompt = build_user_prompt(company, process)

        for run_number in range(1, RUNS_PER_PROCESS + 1):
            response = client.messages.create(
                model=MODEL_NAME,
                max_tokens=1000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            text = "".join(block.text for block in response.content if block.type == "text")
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = compute_cost(input_tokens, output_tokens)
            total_cost += cost

            try:
                parsed = json.loads(text)
                parses = True
                pct_sum = sum(item["pct_time_saved"] for item in parsed)
            except (json.JSONDecodeError, KeyError, TypeError):
                parses = False
                pct_sum = None

            emit(f"=== {name} — run {run_number}/{RUNS_PER_PROCESS} ===")
            emit(text)
            emit(f"\nparses_as_json={parses}")
            emit(f"pct_time_saved_sum={pct_sum}")
            emit(f"input_tokens={input_tokens} output_tokens={output_tokens} cost=${cost:.6f}")
            emit()

    emit(f"TOTAL_COST=${total_cost:.6f}")

    with open("checkpoint.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines) + "\n")


if __name__ == "__main__":
    main()
