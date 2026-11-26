"""Prompts for generating AI use-case proposals for a process.

This module only builds prompt text. It does not call the API and does not
score or rank anything.
"""

from core.models import Company, Process

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

Output format: respond with raw JSON only. No markdown code fences, no text \
before or after the JSON. The response must be a JSON array of objects, each \
with exactly these keys: type, description (one sentence), justification (one \
to two sentences linking explicitly to the pain points), pct_time_saved.

Before answering, silently check your list: (1) no use case performs a step \
already performed by another use case in the list — if an agent would repeat \
another case's steps, drop one of them; (2) the sum of pct_time_saved is <= \
0.8; (3) each type is the simplest that fits (a tool that only retrieves and \
summarizes information for a human is an 'assistant', not an 'agent'). If any \
check fails, revise before answering."""

WORKED_EXAMPLE_PROMPT = """Context:
- Company: ExampleCo, sector: Business Services, 500 employees
- Process: Employee expense report validation
- Team: Finance
- Volume: 900 occurrences/month
- Minutes per occurrence: 6
- Pain points: Manual receipt-to-policy checking is slow; reviewers miss policy violations on complex multi-line reports; employees wait days for reimbursement
- Data used: Expense reports; receipt images; expense policy document; employee cost center
"""

WORKED_EXAMPLE_RESPONSE = """[
  {
    "type": "document_extraction",
    "description": "An AI tool that reads receipt images and expense line items and checks them against the expense policy automatically.",
    "justification": "This directly addresses the slow manual receipt-to-policy checking and the missed policy violations on complex multi-line reports, by applying the policy consistently to every line.",
    "pct_time_saved": 0.45
  },
  {
    "type": "classification",
    "description": "A classifier that flags already-checked expense reports as auto-approvable, needs-review, or policy violation, without re-doing the extraction step.",
    "justification": "This reduces the reviewer's workload to the reports that actually need attention, which shortens the days employees currently wait for reimbursement.",
    "pct_time_saved": 0.3
  }
]"""


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
of this company's data, to show you the expected output format.

{WORKED_EXAMPLE_PROMPT}
Example output:
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
