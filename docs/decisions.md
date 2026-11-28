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

## Code guard against risk-worded no_fit_reason (v4.2)

Prompt instructions are probabilistic; what code can check, code checks. The v4.1 prompt forbade declining for EU AI Act/GDPR risk, but claude-haiku-4-5 still did it: "Annual performance review drafting and calibration" came back as a 0-use-case no-fit answer explicitly citing "EU AI Act HIGH-RISK territory (Annex III, biometric categorisation for performance monitoring)" as the reason.
That citation is also a hallucinated legal basis: performance review drafting has nothing to do with biometric categorisation, Annex III lists worker-performance evaluation as its own separate high-risk category. A model confidently inventing the wrong Annex III clause to justify a refusal is direct evidence that compliance judgments must never rely on LLM free text — core/generator.py now regex-matches no_fit_reason for risk/compliance wording (case-insensitive: "ai act", "high-risk", "gdpr", "legal", "compliance", "annex iii", "regulat", etc.) and forces a repair turn instead of trusting the model's stated reasoning.
Measured on the same 10-process eval set, holding the model fixed at claude-haiku-4-5: v4.1 -> v4.2 no-fit accuracy 90% -> 100% (the guard converted the risk-based performance-review refusal into a correctly-labeled high-risk use case), AI Act error rate 16.67% -> 10.53%, overlap rate 11.11% -> 10.53%.

## Generator model kept: claude-haiku-4-5, not claude-haiku-5-5

Compared v4.2 on claude-haiku-4-5 vs the newest available Haiku, claude-haiku-5-5, with the prompt and code guard both held fixed (one-variable-at-a-time). claude-haiku-5-5 scored better on judge relevance (4.63 -> 4.71), overlap rate (10.53% -> 4.76%), and AI Act error rate (10.53% -> 9.52%), but its no-fit accuracy regressed (100% -> 90%): it proposed use cases for "Forklift preventive maintenance", the deliberately physical no-fit test case, where claude-haiku-4-5 correctly returned zero. It is also not cheaper — note the cost figures for claude-haiku-5-5 reuse claude-haiku-4-5's per-token prices as a placeholder (its real pricing was not available to verify) and should be re-checked before this decision is revisited on cost grounds.
Given the no-fit mechanism's entire purpose is to catch exactly the kind of process claude-haiku-5-5 got wrong, and its real cost is unverified, claude-haiku-4-5 stays the generator model. Revisit if claude-haiku-5-5's no-fit accuracy improves on a larger eval set or its pricing is confirmed favorable.

## Gains are freed time, not cash

Gains are valued as freed time, not cash savings: they become cash only if capacity is reduced or redeployed. Stated in the report and README limitations.

## "Order status inquiries" AI Act level corrected: minimal -> limited

The phase-0 demo data originally classified the order-status chatbot as "minimal" risk. It is a customer-facing conversational assistant, which falls under the EU AI Act Art. 50 transparency obligation (users must be informed they are interacting with an AI system) — so it is "limited", not "minimal". This is a data correction, not a scoring rule change: `data/phase0_use_cases.json` was edited directly, and `docs/manual_scoring.xlsx` was left untouched since it predates this fix and is kept only as a historical reference snapshot.
The fix changes the phase-0 ranking: "Supplier invoice processing" becomes #1 and "Order status inquiries" becomes #2 (previously reversed). The expected order in `tests/test_scoring.py` and `tests/test_app.py` was updated to match.

## 3-wave roadmap: quadrant first, then compliance, then capacity

The roadmap (`core/roadmap.py`) turns the value x feasibility quadrant of each use case into a default wave, then applies two corrections, in this fixed order:
1. **Quadrant logic**: Quick wins start in wave 1 (0-3 months) because they need the least further validation. Optimisations start in wave 2 (3-9 months): valuable enough to pursue but not urgent quick wins. Projets structurants split on feasibility (>= 35 goes to wave 2, below stays in wave 3) because a high-value but hard-to-build case still needs significant lead time if feasibility is very low. À écarter cases are archived rather than scheduled, since scheduling a low-value, low-feasibility case would waste roadmap capacity that quick wins and structurants need.
2. **Compliance before quick win**: a HIGH EU AI Act risk use case is never placed in wave 1, even if its value/feasibility scores classify it as a Quick win. High risk requires documentation, human oversight and data-governance work that cannot realistically be completed inside a 0-3 month window, so it is bumped to wave 2 regardless of quadrant.
3. **Team capacity**: waves are capped at `max_per_wave` (default 3) because a delivery team can only realistically start a handful of use cases at once. Waves are filled in order (1, then 2, then 3), sorted by priority within each wave, so the highest-priority cases keep their earlier wave and the overflow cascades to the next one; overflow pushed past wave 3 has nowhere later to go and stays there.
These three rules are applied strictly in this order (quadrant, then compliance, then capacity) so that compliance and capacity corrections are deterministic adjustments layered on top of the business-value ranking, not ad hoc exceptions.

## Relative quadrant thresholds + best-case-per-process, to counter LLM rating bias

LLM-prefilled criteria show optimism and central-tendency bias (e.g. data_quality = 4 for 19/23 demo cases, complexity never above 3), so absolute thresholds put 17/23 cases in Quick wins. Chosen fix: relative thresholds (prioritization is relative to the portfolio) + best case per process on the matrix. Human review of criteria remains required; a portfolio-level calibration pass is a documented next step.
Mechanically: `core/matrix.py` adds `ThresholdMode` (absolute/relative) and `portfolio_thresholds()`, which returns the portfolio's own median value/feasibility in relative mode instead of a fixed 50/50 bar — so the matrix and the roadmap always split the *actual* portfolio into halves, regardless of how compressed or inflated the model's self-ratings are. The app defaults to relative mode, with absolute (and its two threshold sliders) available as an explicit opt-out. Separately, `core/scoring.py`'s `best_per_process()` keeps only the highest-priority use case per process on the matrix by default (a checkbox shows all), since several same-process bubbles clustering together was also making the chart hard to read independently of the threshold choice.
