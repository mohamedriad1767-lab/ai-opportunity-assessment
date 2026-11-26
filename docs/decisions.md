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

## Prompt v4 -> v4.1: allow "no good AI fit", tighten AI Act guidance, forbid risk-based refusal

v3 over-proposed use cases for worker-evaluation processes under "limited" AI Act risk and let siblings overlap; v4 added a 0-use-case "no_fit_reason" option, explicit Annex III worker-evaluation guidance, a "different pain point per use case" overlap rule, and a second contrasting worked example with different pct_time_saved values so the model stops anchoring on the first example's numbers. v4.1 then found that the generator itself (not just the judge) was using the no-fit option to decline on EU AI Act/GDPR grounds, so the "no good fit" rule was narrowed to physical/no-information-processing cases only, with an explicit "never decline for AI Act or GDPR risk" instruction.
Measured on the same 10-process eval set: v3 -> v4 -> v4.1 AI Act error rate 19.05% -> 6.67% -> 16.67%, overlap rate 19.05% -> 6.67% -> 11.11%, judge relevance 4.57 -> 4.60 -> 4.72, judge realism 3.81 -> 3.73 -> 4.00, cost $0.083279 -> $0.077979 -> $0.085309.
The prompt-only fix did NOT fully work on claude-haiku-4-5: "Annual performance review drafting and calibration" still returned a 0-use-case, risk-justified no-fit answer under v4.1, explicitly citing "EU AI Act HIGH-RISK" as the reason despite the instruction forbidding it — this generator model does not reliably follow that constraint from prompting alone and needs either a stronger model, a repair-loop check that rejects risk-worded no_fit_reason text, or both.

## The LLM may say "no good AI fit" but never for risk reasons

The LLM may say a process is not an AI fit, but never declines for risk reasons: risk is scored by rules, so a high-risk case stays visible to the client with its penalty.
