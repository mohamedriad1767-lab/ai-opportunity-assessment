"""First Anthropic API call: ask for 3 bullet points and report cost."""

import os
import sys

# Allow running this script directly (python scripts/first_call.py) by making
# the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from dotenv import load_dotenv

from core.config import MODEL_NAME, PRICE_INPUT_PER_MTOK_USD, PRICE_OUTPUT_PER_MTOK_USD

PROMPT = (
    "In 3 bullet points, what could AI improve in supplier invoice processing "
    "for a 800-employee B2B distributor?"
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set. Add it to your .env file and try again.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=300,
        messages=[{"role": "user", "content": PROMPT}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_usd = (
        input_tokens / 1_000_000 * PRICE_INPUT_PER_MTOK_USD
        + output_tokens / 1_000_000 * PRICE_OUTPUT_PER_MTOK_USD
    )

    print(text)
    print(f"\nInput tokens: {input_tokens}")
    print(f"Output tokens: {output_tokens}")
    print(f"Estimated cost: ${cost_usd:.6f}")


if __name__ == "__main__":
    main()
