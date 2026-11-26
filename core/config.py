"""Constants for calling the Anthropic API."""

MODEL_NAME = "claude-haiku-4-5"

# A stronger model than MODEL_NAME, used as an independent LLM judge for
# evaluation grading (never for generation).
JUDGE_MODEL_NAME = "claude-sonnet-5"

# Prices in USD per million tokens (MTok). These must be re-checked on the
# Anthropic pricing page (https://platform.claude.com/docs/en/pricing) before
# relying on them for real cost reporting, as pricing can change over time.
PRICE_INPUT_PER_MTOK_USD = 1.00
PRICE_OUTPUT_PER_MTOK_USD = 5.00
