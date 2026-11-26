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

## Prompt v4: allow "no good AI fit", tighten AI Act guidance and overlap rule, de-anchor the example

v3 over-proposed use cases for worker-evaluation processes under "limited" AI Act risk and let siblings overlap; v4 adds a 0-use-case "no_fit_reason" option, explicit Annex III worker-evaluation guidance, a "different pain point per use case" overlap rule, and a second contrasting worked example with different pct_time_saved values so the model stops anchoring on the first example's numbers.
Measured on the same 10-process eval set: AI Act error rate 19.05% -> 6.67%, overlap rate 19.05% -> 6.67%, 2 processes correctly returned a no-fit answer (0 in v3), avg use cases/process 2.10 -> 1.50, judge relevance 4.57 -> 4.60, judge realism 3.81 -> 3.73, cost $0.083279 -> $0.077979 for the same 10 processes.
