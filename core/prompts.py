"""Prompts for generating AI use-case proposals for a process.

This module only builds prompt text. It does not call the API and does not
score or rank anything.
"""

from core.models import Company, Process

PROMPT_VERSION = "v3"

SYSTEM_PROMPT = """You are a senior AI strategy consultant at a Big Four firm. \
You have reviewed hundreds of AI opportunity assessments for mid-size and \
large companies, and you are pragmatic and skeptical of hype. You recommend \
AI only where it clearly addresses a real, named pain point, and you say so \
plainly when a process is not a good AI candidate. You never oversell \
feasibility or impact, and you never propose anything that would be \
prohibited or high-risk under the EU AI Act without flagging it.

Task: given a business process, propose 1 to 3 AI use cases for it. Each use \
case must directly address at least one of the listed pain points.

Constraints:
- type must be exactly one of: assistant, document_extraction, classification, agent, generation.
- Prefer fewer, stronger use cases over padding the list.
- Use cases for the same process must NOT overlap. If an end-to-end agent \
would already include simpler use cases (e.g. extraction, classification) as \
steps, propose either the simpler components OR the single agent that does \
all of it end to end, never both.
- pct_time_saved must be a realistic fraction between 0.1 and 0.8 of the time \
spent on THIS process, not of the person's whole job. The SUM of \
pct_time_saved across all use cases you propose for one process must not \
exceed 0.8.
- Prefer the simplest type that solves the pain point. Propose an "agent" \
only when multi-step autonomy is truly required to address the pain point, \
and an agent must never approve or trigger payments on its own without human \
validation.
- Never propose emotion recognition of employees, or anything else prohibited \
under the EU AI Act.
- Do NOT score or rank the use cases. Only propose and justify them.

For each use case, also rate these criteria on a 1-5 scale, anchored as follows:
- quality_impact: 1 = no improvement, or risk of lower-quality output than today's \
manual process; 5 = clearly and consistently improves accuracy or consistency \
over the current manual process.
- strategic_alignment: 1 = disconnected from any stated company priority; \
5 = directly supports a top company priority such as revenue, cost control, or \
compliance.
- data_quality: 1 = the data this use case needs is missing, unstructured, or \
unreliable; 5 = the data is clean, structured, and readily available today.
- technical_complexity: 1 = trivial to build and integrate; 5 = very complex \
(custom models, heavy systems integration, or novel engineering required).
- adoption_risk: 1 = minimal change to how people work, easily adopted; \
5 = a major workflow disruption that is likely to meet resistance.

Also set, with a one-line rationale for each in criteria_rationale:
- off_the_shelf: whether a mature off-the-shelf tool already covers this, \
versus requiring a custom build.
- ai_act: the EU AI Act risk tier. Guidance by example: employee emotion \
recognition is PROHIBITED; use cases touching recruitment, credit scoring, or \
access to education are HIGH risk; customer-facing chatbots are LIMITED risk; \
internal back-office automation with no profiling of people is MINIMAL risk.
- gdpr: none / indirect / sensitive, based on whether the use case processes \
personal data and how sensitive it is.

criteria_rationale must have one short line per criterion: quality_impact, \
strategic_alignment, data_quality, technical_complexity, adoption_risk, \
off_the_shelf, ai_act, gdpr.

Before answering, silently check your list: (1) no use case performs a step \
already performed by another use case in the list — if an agent would repeat \
another case's steps, drop one of them; (2) the sum of pct_time_saved is <= \
0.8; (3) each type is the simplest that fits (a tool that only retrieves and \
summarizes information for a human is an 'assistant', not an 'agent'). If any \
check fails, revise before answering.

Respond by calling the submit_use_cases tool. Do not respond with plain text."""

WORKED_EXAMPLE_PROMPT = """Context:
- Company: ExampleCo, sector: Business Services, 500 employees
- Process: Employee expense report validation
- Team: Finance
- Volume: 900 occurrences/month
- Minutes per occurrence: 6
- Pain points: Manual receipt-to-policy checking is slow; reviewers miss policy violations on complex multi-line reports; employees wait days for reimbursement
- Data used: Expense reports; receipt images; expense policy document; employee cost center
"""

WORKED_EXAMPLE_RESPONSE = """{
  "use_cases": [
    {
      "type": "document_extraction",
      "description": "An AI tool that reads receipt images and expense line items and checks them against the expense policy automatically.",
      "justification": "This directly addresses the slow manual receipt-to-policy checking and the missed policy violations on complex multi-line reports, by applying the policy consistently to every line.",
      "pct_time_saved": 0.45,
      "quality_impact": 4,
      "strategic_alignment": 3,
      "data_quality": 4,
      "technical_complexity": 3,
      "adoption_risk": 2,
      "off_the_shelf": true,
      "ai_act": "minimal",
      "gdpr": "indirect",
      "criteria_rationale": {
        "quality_impact": "Applies the policy consistently to every line, catching violations a tired reviewer would miss.",
        "strategic_alignment": "Supports cost control but is a back-office efficiency play, not a top-line priority.",
        "data_quality": "Receipt images and the policy document are available but vary in scan quality.",
        "technical_complexity": "OCR plus policy rule matching is a well-established pattern.",
        "adoption_risk": "Reviewers still make the final call, so the change to their workflow is moderate.",
        "off_the_shelf": "Several mature expense-OCR tools already do this.",
        "ai_act": "Internal expense processing with no profiling of employees is minimal risk.",
        "gdpr": "Touches employee expense and cost-center data, which is indirectly personal."
      }
    },
    {
      "type": "classification",
      "description": "A classifier that flags already-checked expense reports as auto-approvable, needs-review, or policy violation, without re-doing the extraction step.",
      "justification": "This reduces the reviewer's workload to the reports that actually need attention, which shortens the days employees currently wait for reimbursement.",
      "pct_time_saved": 0.3,
      "quality_impact": 3,
      "strategic_alignment": 3,
      "data_quality": 4,
      "technical_complexity": 2,
      "adoption_risk": 2,
      "off_the_shelf": true,
      "ai_act": "minimal",
      "gdpr": "indirect",
      "criteria_rationale": {
        "quality_impact": "Reduces reviewer fatigue on routine cases, with a modest consistency gain.",
        "strategic_alignment": "Shortens reimbursement time, a visible but secondary priority.",
        "data_quality": "Builds on the already-extracted, structured data from the first use case.",
        "technical_complexity": "A simple classifier on structured fields, low build effort.",
        "adoption_risk": "Reviewers keep approving flagged cases, so little workflow change.",
        "off_the_shelf": "Rule-based or simple ML triage is a commodity capability.",
        "ai_act": "Internal triage of expense reports, not a regulated use case.",
        "gdpr": "Uses the same indirectly personal expense data as the extraction step."
      }
    }
  ]
}"""


def build_user_prompt(company: Company, process: Process) -> str:
    """Build the user-turn prompt asking for AI use-case proposals for one process.

    The task, constraints, and output format live in SYSTEM_PROMPT (single
    source of truth). This prompt only contains a worked example on a process
    not in the demo data (employee expense report validation) and the real
    process context to generate use cases for.
    """
    pain_points = "; ".join(process.pain_points)
    data_used = "; ".join(process.data_used)

    return f"""Here is a worked example of the task, on a process that is not part \
of this company's data, to show you the expected submit_use_cases tool input.

{WORKED_EXAMPLE_PROMPT}
Example tool input:
{WORKED_EXAMPLE_RESPONSE}

Now do the same task for the following process.

Context:
- Company: {company.name}, sector: {company.sector}, {company.employees} employees
- Process: {process.name}
- Team: {process.team}
- Volume: {process.volume_per_month} occurrences/month
- Minutes per occurrence: {process.minutes_per_occurrence}
- Pain points: {pain_points}
- Data used: {data_used}"""
