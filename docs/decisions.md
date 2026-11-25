# Decisions

Running log of project decisions and the reasoning behind them.

## Only manual order entry is valued; EDI/webshop orders are excluded

EDI and webshop orders are already automated and require no further AI intervention.
Including them would inflate the estimated gains for a process that is not actually a pain point.

## The LLM proposes use cases but never scores them

Scoring is deterministic Python code applied to structured inputs (notes, percentages, flags).
This keeps every number traceable and reproducible, instead of depending on an LLM's judgment call.

## OPEN QUESTION: should "high" AI Act cases be capped rather than only penalized?

Currently a "high" AI Act level only lowers the priority score through the risk term, it does not block selection.
Revisit at step 1.5: consider hard-excluding "high" risk cases from wave 1 instead of just penalizing them.

## Gain normalization: log min-max

Gains span two orders of magnitude (96 h to 9,000 h/year in the demo); linear min-max let a single outlier crush all other cases, while rank-based scoring lost the magnitude of differences.
