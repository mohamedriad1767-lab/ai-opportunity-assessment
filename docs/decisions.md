# Decisions

Running log of project decisions and the reasoning behind them.

## Only manual order entry is valued; EDI/webshop orders are excluded

EDI and webshop orders are already automated and require no further AI intervention.
Including them would inflate the estimated gains for a process that is not actually a pain point.

## The LLM proposes use cases but never scores them

Scoring is deterministic Python code applied to structured inputs (notes, percentages, flags).
This keeps every number traceable and reproducible, instead of depending on an LLM's judgment call.

## Gain normalization: log min-max

Gains span two orders of magnitude (96 h to 9,000 h/year in the demo); linear min-max let a single outlier crush all other cases, while rank-based scoring lost the magnitude of differences.

## High-risk AI Act cases: penalized, not excluded from wave 1

Penalized in the risk score AND never placed in wave 1 (applied in the roadmap, step 4.2).
High risk is legal but requires compliance work (documentation, human oversight, data governance) incompatible with a 0-3 month quick win.

## Prohibited cases are removed before gain normalization

Prohibited cases are removed before gain normalization, so they cannot distort the min/max of the remaining portfolio.
