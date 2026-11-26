"""Provoke the generator's error-handling paths against the real API.

(a) Use an absurdly short client timeout to trigger timeouts on every
    attempt, showing the retry logs and the final GenerationError.
(b) Use a deliberately wrong API key, hardcoded here rather than loaded
    from .env, to show the immediate authentication failure with no retry.
"""

import json
import logging
import os
import sys

# Allow running this script directly (python scripts/provoke_errors.py) by
# making the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from dotenv import load_dotenv

from core.generator import GenerationError, generate_use_cases
from core.loader import load_processes
from core.models import Company

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set. Add it to your .env file and try again.")
        sys.exit(1)

    with open("data/demo_company_profile.json", encoding="utf-8") as f:
        company = Company(**json.load(f))
    process = load_processes("data/demo_company.csv")[0]

    print("=== (a) Absurdly short timeout: expect retries then GenerationError ===")
    timeout_client = anthropic.Anthropic(api_key=api_key, timeout=0.001, max_retries=0)
    try:
        generate_use_cases(company, process, timeout_client, sleep=lambda s: None)
    except GenerationError as exc:
        print(f"GenerationError raised as expected: {exc}")
    print()

    print("=== (b) Deliberately wrong API key: expect immediate auth failure, no retry ===")
    wrong_key_client = anthropic.Anthropic(
        api_key="sk-ant-api03-deliberately-wrong-key-for-testing-000000000000",
        timeout=30,
        max_retries=0,
    )
    try:
        generate_use_cases(company, process, wrong_key_client, sleep=lambda s: None)
    except GenerationError as exc:
        print(f"GenerationError raised as expected: {exc}")


if __name__ == "__main__":
    main()
