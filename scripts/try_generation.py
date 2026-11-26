"""Try the use-case generation prompt on two real demo processes."""

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

    for name in PROCESS_NAMES:
        process = processes[name]
        user_prompt = build_user_prompt(company, process)

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

        try:
            parsed = json.loads(text)
            parses = True
            pct_sum = sum(item["pct_time_saved"] for item in parsed)
        except (json.JSONDecodeError, KeyError, TypeError):
            parses = False
            pct_sum = None

        print(f"=== {name} ===")
        print(text)
        print(f"\nparses_as_json={parses}")
        print(f"pct_time_saved_sum={pct_sum}")
        print(f"input_tokens={input_tokens} output_tokens={output_tokens} cost=${cost:.6f}")
        print()


if __name__ == "__main__":
    main()
