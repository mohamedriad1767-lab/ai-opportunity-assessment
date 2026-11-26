# Business case assumptions

**These are starting hypotheses for a demo, not market benchmarks.** Every value below
is a reasonable guess used to produce a first, directional business case. None of them
should be quoted to a client as a fact — the "to calibrate with client" column flags
which ones must be replaced with real client inputs (or at least sanity-checked with
them) before any number derived from them goes into a report.

| Assumption | Value | Unit | Rationale | To calibrate with client |
|---|---|---|---|---|
| daily_rate_eur | 650 | EUR/day | A blended day rate across the roles typically needed to build an AI use case (data, ML/AI engineering, product); a round, mid-market planning number. | Yes |
| build_days_by_complexity[1] | 5 | days | Trivial build: a thin wrapper or prompt-only solution. | Yes |
| build_days_by_complexity[2] | 10 | days | Simple build: light integration, mostly off-the-shelf components. | Yes |
| build_days_by_complexity[3] | 20 | days | Moderate build: real integration work, some custom logic. | Yes |
| build_days_by_complexity[4] | 35 | days | Complex build: multiple systems, non-trivial custom logic or fine-tuning. | Yes |
| build_days_by_complexity[5] | 60 | days | Very complex build: novel engineering, heavy integration, or a custom model. | Yes |
| off_the_shelf_build_factor | 0.4 | fraction | An "off-the-shelf" tool still needs integration, configuration, and testing; assumed to take ~40% of a custom build at the same complexity level, not 0%. | Yes |
| annual_license_eur_off_the_shelf | 6000 | EUR/year | A placeholder recurring license cost for an off-the-shelf tool, in the absence of a real vendor quote. | Yes |
| llm_cost_per_occurrence_eur | 0.01 | EUR/occurrence | A rough per-call API cost for a custom LLM-based use case at typical prompt/output sizes; actual cost depends heavily on the model and token volume. | Yes |
| maintenance_pct_of_build | 0.15 | fraction/year | Ongoing maintenance (bug fixes, monitoring, small adjustments), assumed as a recurring fraction of the one-off build cost — a common software rule of thumb. | Yes |
| change_management_pct_of_build | 0.25 | fraction, one-off | Training, communication, and process redesign needed to actually adopt the use case, as a fraction of build cost; change management is usually under-budgeted. | Yes |
| adoption_rates.pessimistic | 0.40 | fraction | Share of the eligible volume actually processed by the use case in a slow-adoption scenario. | Yes |
| adoption_rates.base | 0.65 | fraction | Share of the eligible volume actually processed by the use case in the expected scenario. | Yes |
| adoption_rates.optimistic | 0.85 | fraction | Share of the eligible volume actually processed by the use case in a fast-adoption scenario; never 100%, since some volume always stays manual (exceptions, edge cases). | Yes |
| horizon_years | 3 | years | Standard business-case horizon for an internal AI investment; long enough to amortize build cost, short enough to stay credible given how fast the technology moves. | Yes |
