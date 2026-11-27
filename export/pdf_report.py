"""Build the PDF opportunity-assessment report with reportlab.

This module only renders already-computed data: it calls no LLM, and it
recomputes nothing beyond calling compute_business_cases() for the wave-1
use cases (the same pure function the UI uses). Scoring, the matrix, the
roadmap and the business case all come from core/ and viz/ as-is. All
user-facing text in the PDF is French; code comments are English.
"""

import io
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import reportlab as _reportlab
from core.assumptions import Assumptions
from core.business_case import compute_business_cases
from core.models import AIActLevel, Company, Process, ScoredUseCase, UseCase
from core.roadmap import WAVE_LABELS, RoadmapItem
from export.formatting import NBSP, fmt_eur, fmt_months, fmt_pct
from viz.matrix_chart import build_matrix_figure
from viz.roadmap_chart import build_roadmap_figure

PAGE_SIZE = A4
MARGIN_MM = 20
CONTENT_WIDTH_MM = (PAGE_SIZE[0] / mm) - 2 * MARGIN_MM

FONT_REGULAR = "Vera"
FONT_BOLD = "Vera-Bold"

AI_ACT_LABELS = {"minimal": "Minimal", "limited": "Limité", "high": "Élevé"}
GDPR_LABELS = {"none": "Aucune", "indirect": "Indirecte", "sensitive": "Sensible"}

CRITERION_LABELS = {
    "quality_impact": "Impact qualité",
    "strategic_alignment": "Alignement stratégique",
    "data_quality": "Qualité des données",
    "technical_complexity": "Complexité technique",
    "adoption_risk": "Risque d'adoption",
    "off_the_shelf": "Solution sur étagère",
    "ai_act": "Niveau AI Act",
    "gdpr": "Sensibilité RGPD",
}

AXIS_LABELS = {
    "value": "Valeur",
    "feasibility": "Faisabilité",
    "risk": "Risque",
    "priority": "Priorité globale",
}
SUB_WEIGHT_LABELS = {
    "value": {"gain": "Gain", "quality": "Qualité", "alignment": "Alignement stratégique"},
    "feasibility": {
        "data": "Qualité des données",
        "complexity": "Complexité technique (inversée)",
        "market": "Off-the-shelf",
    },
    "risk": {"ai_act": "AI Act", "gdpr": "RGPD", "adoption": "Risque d'adoption"},
    "priority": {"value": "Valeur", "feasibility": "Faisabilité", "risk": "Risque"},
}

# (label, formatter) for each Assumptions field, in display order.
ASSUMPTION_FIELDS: list[tuple[str, str, str]] = [
    ("daily_rate_eur", "Taux journalier de l'équipe projet", "eur"),
    ("off_the_shelf_build_factor", "Facteur de build pour un outil sur étagère", "pct"),
    ("integration_days_per_data_source", "Jours d'intégration par source de données", "days"),
    ("annual_license_eur_off_the_shelf", "Licence annuelle (outil sur étagère)", "eur"),
    ("llm_cost_per_occurrence_eur", "Coût LLM par occurrence", "eur_precise"),
    ("maintenance_pct_of_build", "Maintenance annuelle (% du coût de build)", "pct"),
    ("horizon_years", "Horizon du business case", "years"),
]

RISK_MITIGATIONS = {
    AIActLevel.HIGH: "mise en conformité Annexe III avant lancement, jamais en vague 1",
    AIActLevel.LIMITED: "information des utilisateurs, Art. 50",
    AIActLevel.MINIMAL: "aucune mesure de conformité spécifique requise",
}

FRENCH_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

_FONTS_DIR = os.path.join(os.path.dirname(_reportlab.__file__), "fonts")
_FONTS_REGISTERED = False


def _register_fonts() -> None:
    """Register the bundled Bitstream Vera TTF fonts so é, è, à, €, × render correctly.

    The reportlab Base-14 fonts are unreliable for text extraction of
    accented characters once round-tripped through a PDF reader, so a real
    Unicode TTF font is used throughout instead. Idempotent: safe to call
    more than once (e.g. across multiple report builds in the same process).
    """
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, os.path.join(_FONTS_DIR, "Vera.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, os.path.join(_FONTS_DIR, "VeraBd.ttf")))
    _FONTS_REGISTERED = True


def _build_styles() -> dict[str, ParagraphStyle]:
    """Build the paragraph styles used across the report, all on the Vera font family."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontName=FONT_BOLD, fontSize=22, leading=28),
        "subtitle": ParagraphStyle(
            "ReportSubtitle", parent=base["Normal"], fontName=FONT_REGULAR, fontSize=12, textColor=colors.grey
        ),
        "heading": ParagraphStyle(
            "ReportHeading", parent=base["Heading1"], fontName=FONT_BOLD, fontSize=16, spaceAfter=10
        ),
        "subheading": ParagraphStyle(
            "ReportSubheading",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=12,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle("ReportBody", parent=base["Normal"], fontName=FONT_REGULAR, fontSize=10, leading=14),
        "caption": ParagraphStyle(
            "ReportCaption", parent=base["Normal"], fontName=FONT_REGULAR, fontSize=8, textColor=colors.grey
        ),
        "cell": ParagraphStyle("ReportCell", parent=base["Normal"], fontName=FONT_REGULAR, fontSize=9, leading=11),
    }


def _cell(text: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    """Wrap a table cell's text in a Paragraph so it word-wraps inside its column."""
    return Paragraph(text, styles["cell"])


def _fmt_score(value: float) -> str:
    """Format a 0-100 score with a French comma decimal, e.g. 86.8 -> '86,8'."""
    return f"{value:.1f}".replace(".", ",")


def _table_style(header: bool = True) -> TableStyle:
    """Shared table look: light grid, grey header row, Vera font."""
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        commands += [
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.93, 0.95, 0.97)),
        ]
    return TableStyle(commands)


def _figure_image(fig, display_width_mm: float, max_height_mm: float, **to_image_kwargs) -> Image:
    """Render a Plotly figure to PNG and wrap it as a reportlab Image flowable.

    Sized to display_width_mm, unless that would exceed max_height_mm, in
    which case it is scaled down (preserving aspect ratio) to fit the height
    instead, so a long roadmap never overflows the page.
    """
    png_bytes = fig.to_image(format="png", **to_image_kwargs)
    px_width, px_height = ImageReader(io.BytesIO(png_bytes)).getSize()

    width = display_width_mm * mm
    height = width * px_height / px_width
    if height > max_height_mm * mm:
        height = max_height_mm * mm
        width = height * px_width / px_height

    return Image(io.BytesIO(png_bytes), width=width, height=height)


class _NumberedCanvas(pdf_canvas.Canvas):
    """A canvas that stamps "Page X / Y" once the total page count is known."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total_pages)
            super().showPage()
        super().save()

    def _draw_footer(self, total_pages: int) -> None:
        self.setFont(FONT_REGULAR, 8)
        self.setFillColor(colors.grey)
        self.drawCentredString(
            PAGE_SIZE[0] / 2, 12 * mm, f"Page {self.getPageNumber()} / {total_pages}"
        )


def _french_date(day: date) -> str:
    """Format a date in French, e.g. '25 novembre 2026' (locale-independent)."""
    return f"{day.day} {FRENCH_MONTHS[day.month - 1]} {day.year}"


def _cover_page(story: list, styles: dict[str, ParagraphStyle], company: Company) -> None:
    """Page 1: title, date, working-document notice."""
    story.append(Spacer(1, 70 * mm))
    story.append(Paragraph(f"Évaluation des opportunités IA — {company.name}", styles["title"]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(_french_date(date.today()), styles["subtitle"]))
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph("Document de travail — hypothèses à valider", styles["subtitle"]))
    story.append(PageBreak())


def _synthesis_page(
    story: list,
    styles: dict[str, ParagraphStyle],
    company: Company,
    processes: list[Process],
    scored_use_cases: list[ScoredUseCase],
    excluded: list[UseCase],
    no_fit: list[tuple[str, str]],
    roadmap_planned: list[RoadmapItem],
    assumptions: Assumptions,
) -> None:
    """Page 2: a short code-filled template plus a key-figures box."""
    story.append(Paragraph("Synthèse", styles["heading"]))

    wave1 = [item for item in roadmap_planned if item.wave == 1]
    total_use_cases = len(scored_use_cases) + len(excluded)
    exclusion_bits = []
    if excluded:
        exclusion_bits.append(f"{len(excluded)} interdit(s) au titre de l'AI Act")
    if no_fit:
        exclusion_bits.append(f"{len(no_fit)} processus sans cas d'usage retenu")
    exclusion_note = f" (dont {', '.join(exclusion_bits)})" if exclusion_bits else ""

    wave1_cases = [
        _wave1_business_cases(item, processes, company.hourly_cost_eur, assumptions) for item in wave1
    ]
    wave1_gain_pessimistic = sum(cases["pessimistic"].annual_gain_eur for cases in wave1_cases)
    wave1_gain_base = sum(cases["base"].annual_gain_eur for cases in wave1_cases)
    wave1_gain_optimistic = sum(cases["optimistic"].annual_gain_eur for cases in wave1_cases)
    wave1_cost = sum(cases["base"].one_off_cost_eur for cases in wave1_cases)
    wave1_names = ", ".join(item.scored_use_case.use_case.process_name for item in wave1) or "aucun"

    if roadmap_planned:
        riskiest = max(roadmap_planned, key=lambda item: item.scored_use_case.scores.risk)
        riskiest_ai_act = riskiest.scored_use_case.use_case.ai_act
        main_risk_line = (
            f"Risque principal : {riskiest.scored_use_case.use_case.process_name} "
            f"(niveau AI Act : {AI_ACT_LABELS[riskiest_ai_act.value]}, vague {riskiest.wave}) — "
            f"{RISK_MITIGATIONS[riskiest_ai_act]}."
        )
    else:
        main_risk_line = "Risque principal : aucun cas planifié."

    lines = [
        f"{len(processes)} processus et {total_use_cases} cas d'usage ont été analysés{exclusion_note}.",
        f"Cas d'usage retenus pour la vague 1 (0-3 mois) : {wave1_names}.",
        f"Gain annuel de la vague 1 : entre {fmt_eur(wave1_gain_pessimistic)} (adoption pessimiste) et "
        f"{fmt_eur(wave1_gain_optimistic)} (optimiste), {fmt_eur(wave1_gain_base)} en scénario central — "
        "valeur du temps libéré, pas une économie de trésorerie.",
        main_risk_line,
        f"Décision attendue : valider le lancement de la vague 1 "
        f"(investissement initial de {fmt_eur(wave1_cost)}).",
    ]
    for line in lines:
        story.append(Paragraph(line, styles["body"]))
        story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Chiffres clés", styles["subheading"]))
    key_figures = [
        ["Indicateur", "Valeur"],
        ["Processus analysés", str(len(processes))],
        ["Cas d'usage analysés", str(total_use_cases)],
        ["Cas d'usage en vague 1", str(len(wave1))],
        ["Gain annuel vague 1 (central)", fmt_eur(wave1_gain_base)],
        [
            "Gain annuel vague 1 (pessimiste - optimiste)",
            _cell(f"{fmt_eur(wave1_gain_pessimistic)} - {fmt_eur(wave1_gain_optimistic)}", styles),
        ],
        ["Investissement initial vague 1", fmt_eur(wave1_cost)],
    ]
    table = Table(key_figures, colWidths=[90 * mm, 70 * mm])
    table.setStyle(_table_style())
    story.append(table)
    story.append(PageBreak())


def _wave1_business_cases(
    item: RoadmapItem, processes: list[Process], hourly_cost: float, assumptions: Assumptions
) -> dict:
    """Return the 3-scenario BusinessCase dict for one planned roadmap item."""
    process = _find_process(item.scored_use_case.use_case.process_name, processes)
    return compute_business_cases(item.scored_use_case.use_case, process, hourly_cost, assumptions)


def _find_process(process_name: str, processes: list[Process]) -> Process:
    """Look up a Process by name, raising a clear error if it is missing."""
    for process in processes:
        if process.name == process_name:
            return process
    raise ValueError(f"No process named '{process_name}' was provided")


def _matrix_page(story: list, styles: dict[str, ParagraphStyle], scored_use_cases: list[ScoredUseCase]) -> None:
    """Page 3: the value x feasibility matrix, reused from viz/matrix_chart.py.

    No separate page heading here: the chart itself already carries the
    title "Matrice valeur × faisabilité" (viz/matrix_chart.py), so adding
    another one above it would duplicate it.
    """
    fig = build_matrix_figure(scored_use_cases)
    story.append(_figure_image(fig, display_width_mm=CONTENT_WIDTH_MM, max_height_mm=220, width=1000, scale=2))
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            "Lecture : plus un cas d'usage est situé en haut à droite (quick win), "
            "plus il doit être priorisé rapidement.",
            styles["caption"],
        )
    )
    story.append(PageBreak())


def _roadmap_page(
    story: list,
    styles: dict[str, ParagraphStyle],
    roadmap_planned: list[RoadmapItem],
    roadmap_archived: list[RoadmapItem],
) -> None:
    """Page 4: the roadmap timeline, the planned table, and the archived cases."""
    story.append(Paragraph("Feuille de route en 3 vagues", styles["heading"]))
    if roadmap_planned:
        fig = build_roadmap_figure(roadmap_planned)
        story.append(_figure_image(fig, display_width_mm=CONTENT_WIDTH_MM, max_height_mm=140, width=1100, scale=2))
        story.append(Spacer(1, 4 * mm))

        rows = [["Vague", "Cas d'usage", "Raison"]]
        for item in roadmap_planned:
            rows.append(
                [
                    WAVE_LABELS[item.wave],
                    f"{item.scored_use_case.rank}. {item.scored_use_case.use_case.process_name}",
                    _cell(item.reason, styles),
                ]
            )
        table = Table(rows, colWidths=[30 * mm, 60 * mm, 80 * mm], repeatRows=1)
        table.setStyle(_table_style())
        story.append(table)
    else:
        story.append(Paragraph("Aucun cas d'usage n'est planifié.", styles["body"]))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Cas écartés", styles["subheading"]))
    if roadmap_archived:
        rows = [["Cas d'usage", "Raison"]]
        for item in roadmap_archived:
            rows.append(
                [
                    f"{item.scored_use_case.rank}. {item.scored_use_case.use_case.process_name}",
                    _cell(item.reason, styles),
                ]
            )
        table = Table(rows, colWidths=[90 * mm, 80 * mm], repeatRows=1)
        table.setStyle(_table_style())
        story.append(table)
    else:
        story.append(Paragraph("Aucun cas écarté.", styles["body"]))
    story.append(PageBreak())


def _compliance_note(ai_act: AIActLevel) -> str | None:
    """Return the AI Act compliance note for a use case's risk level, or None if minimal."""
    if ai_act == AIActLevel.LIMITED:
        return (
            "Conformité AI Act : ce cas d'usage relève du niveau de risque « limité » et est "
            "soumis à une obligation de transparence (Art. 50) — les utilisateurs doivent être "
            "informés qu'ils interagissent avec un système d'IA."
        )
    if ai_act == AIActLevel.HIGH:
        return (
            "Conformité AI Act : ce cas d'usage relève du niveau de risque « élevé » (Annexe III) "
            "et est soumis à des obligations renforcées (documentation technique, supervision "
            "humaine, gestion des données, évaluation de conformité) avant toute mise en production."
        )
    return None


def _change_management_note(use_case: UseCase, assumptions: Assumptions) -> str:
    """Return a change-management note derived from the use case's adoption_risk."""
    days = assumptions.change_management_days_by_adoption_risk[use_case.adoption_risk]
    return (
        f"Conduite du changement : risque d'adoption {use_case.adoption_risk}/5, soit environ "
        f"{days:.0f} jours de formation, communication et redesign des processus à prévoir."
    )


def _wave1_use_case_page(
    story: list,
    styles: dict[str, ParagraphStyle],
    item: RoadmapItem,
    process: Process,
    hourly_cost: float,
    assumptions: Assumptions,
) -> None:
    """One page per wave-1 use case: description, scores, criteria, business case, compliance."""
    scored = item.scored_use_case
    use_case = scored.use_case

    story.append(Paragraph(f"Vague 1 — {use_case.process_name}", styles["heading"]))
    story.append(Paragraph(use_case.description, styles["body"]))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"<b>Justification :</b> {use_case.justification}", styles["body"]))

    story.append(Paragraph("Scores", styles["subheading"]))
    scores_rows = [
        ["Valeur", "Faisabilité", "Risque", "Priorité"],
        [
            _fmt_score(scored.scores.value),
            _fmt_score(scored.scores.feasibility),
            _fmt_score(scored.scores.risk),
            _fmt_score(scored.scores.priority),
        ],
    ]
    scores_table = Table(scores_rows, colWidths=[42.5 * mm] * 4)
    scores_table.setStyle(_table_style())
    story.append(scores_table)

    story.append(Paragraph("Critères", styles["subheading"]))
    criteria_values = {
        "quality_impact": str(use_case.quality_impact),
        "strategic_alignment": str(use_case.strategic_alignment),
        "data_quality": str(use_case.data_quality),
        "technical_complexity": str(use_case.technical_complexity),
        "adoption_risk": str(use_case.adoption_risk),
        "off_the_shelf": "Oui" if use_case.off_the_shelf else "Non",
        "ai_act": AI_ACT_LABELS[use_case.ai_act.value],
        "gdpr": GDPR_LABELS[use_case.gdpr.value],
    }
    criteria_rows = [["Critère", "Valeur", "Rationale"]]
    for key, value in criteria_values.items():
        criteria_rows.append(
            [CRITERION_LABELS[key], value, _cell(use_case.criteria_rationale.get(key, "—"), styles)]
        )
    criteria_table = Table(criteria_rows, colWidths=[55 * mm, 20 * mm, 95 * mm], repeatRows=1)
    criteria_table.setStyle(_table_style())
    story.append(criteria_table)

    story.append(Paragraph("Business case (3 scénarios)", styles["subheading"]))
    cases = compute_business_cases(use_case, process, hourly_cost, assumptions)
    rows = [["", "Pessimiste", "Base", "Optimiste"]]
    row_labels = [
        ("Gain annuel", lambda c: fmt_eur(c.annual_gain_eur)),
        ("Coût initial", lambda c: fmt_eur(c.one_off_cost_eur)),
        ("Coût annuel", lambda c: fmt_eur(c.annual_run_cost_eur)),
        ("TCO", lambda c: fmt_eur(c.tco_eur)),
        ("ROI", lambda c: fmt_pct(c.roi)),
        ("Retour sur investissement", lambda c: fmt_months(c.payback_months)),
    ]
    for label, formatter in row_labels:
        rows.append([label, formatter(cases["pessimistic"]), formatter(cases["base"]), formatter(cases["optimistic"])])
    business_table = Table(rows, colWidths=[55 * mm, 38.3 * mm, 38.3 * mm, 38.3 * mm])
    business_table.setStyle(_table_style())
    story.append(business_table)

    compliance_note = _compliance_note(use_case.ai_act)
    if compliance_note:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(compliance_note, styles["body"]))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(_change_management_note(use_case, assumptions), styles["body"]))
    story.append(PageBreak())


def _format_assumption_value(field_type: str, value: float) -> str:
    """Format one Assumptions field value according to its display type."""
    if field_type == "eur":
        return fmt_eur(value)
    if field_type == "eur_precise":
        text = f"{value:.4f}".replace(".", ",")
        return f"{text}{NBSP}€"
    if field_type == "pct":
        return fmt_pct(value)
    if field_type == "days":
        return f"{value:.1f}".replace(".", ",") + " jours"
    if field_type == "years":
        return f"{int(value)} ans"
    raise ValueError(f"Unknown assumption field type: {field_type}")


def _scale_table(values: dict[int, float], row_label: str, styles: dict[str, ParagraphStyle]) -> Table:
    """Build a small 1-5 scale table (e.g. build days by complexity level)."""
    levels = sorted(values)
    header = ["Niveau"] + [str(level) for level in levels]
    row = [_cell(row_label, styles)] + [f"{values[level]:.0f} j" for level in levels]
    table = Table([header, row], colWidths=[42 * mm] + [25.6 * mm] * len(levels))
    table.setStyle(_table_style())
    return table


def _adoption_rates_table(rates: dict[str, float]) -> Table:
    """Build the small 3-scenario adoption-rate table."""
    header = ["Pessimiste", "Base", "Optimiste"]
    row = [fmt_pct(rates["pessimistic"]), fmt_pct(rates["base"]), fmt_pct(rates["optimistic"])]
    table = Table([header, row], colWidths=[56.6 * mm] * 3)
    table.setStyle(_table_style())
    return table


def _annexe_page(
    story: list,
    styles: dict[str, ParagraphStyle],
    assumptions: Assumptions,
    weights: dict[str, dict[str, float]],
) -> None:
    """Last page: assumptions, weights, scoring formulas, and limitations."""
    story.append(Paragraph("Annexe", styles["heading"]))

    story.append(Paragraph("Hypothèses du business case", styles["subheading"]))
    assumption_rows = [["Hypothèse", "Valeur"]]
    for key, label, field_type in ASSUMPTION_FIELDS:
        assumption_rows.append([label, _format_assumption_value(field_type, getattr(assumptions, key))])
    assumptions_table = Table(assumption_rows, colWidths=[110 * mm, 60 * mm], repeatRows=1)
    assumptions_table.setStyle(_table_style())
    story.append(assumptions_table)

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Jours de build par complexité technique (1 à 5)", styles["body"]))
    story.append(_scale_table(assumptions.build_days_by_complexity, "Jours de build", styles))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Jours de conduite du changement par risque d'adoption (1 à 5)", styles["body"]))
    story.append(
        _scale_table(assumptions.change_management_days_by_adoption_risk, "Jours de changement", styles)
    )

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Taux d'adoption par scénario", styles["body"]))
    story.append(_adoption_rates_table(assumptions.adoption_rates))

    story.append(Paragraph("Pondérations utilisées", styles["subheading"]))
    weight_rows = [["Axe", "Sous-pondération", "Valeur"]]
    for axis, sub_weights in weights.items():
        for sub_key, sub_value in sub_weights.items():
            weight_rows.append([AXIS_LABELS[axis], SUB_WEIGHT_LABELS[axis][sub_key], fmt_pct(sub_value)])
    weights_table = Table(weight_rows, colWidths=[40 * mm, 85 * mm, 45 * mm], repeatRows=1)
    weights_table.setStyle(_table_style())
    story.append(weights_table)

    story.append(Paragraph("Formules de scoring", styles["subheading"]))
    formulas = [
        "Valeur = w_gain × gain_normalisé + w_qualité × impact_qualité + w_alignement × alignement_stratégique",
        "Faisabilité = w_données × qualité_données + w_complexité × (100 − complexité_technique) "
        "+ w_marché × sur_étagère",
        "Risque = w_ai_act × niveau_AI_Act + w_rgpd × sensibilité_RGPD + w_adoption × risque_adoption",
        "Priorité = w_valeur × valeur + w_faisabilité × faisabilité + w_risque × (100 − risque)",
        "Gain normalisé = normalisation log min-max du gain annuel (€) sur le portefeuille analysé",
        "TCO = coût initial + horizon (années) × coût annuel ; ROI = bénéfice net / TCO",
        "Retour sur investissement = coût initial / (gain annuel − coût annuel) × 12 (en mois)",
    ]
    for formula in formulas:
        story.append(Paragraph(f"• {formula}", styles["body"]))

    story.append(Paragraph("Limites", styles["subheading"]))
    limitations = [
        "Les gains sont du temps libéré, pas des économies de trésorerie.",
        "La classification AI Act est indicative, à valider par un juriste.",
        "Les hypothèses sont à calibrer en atelier avec le client.",
    ]
    for limitation in limitations:
        story.append(Paragraph(f"• {limitation}", styles["body"]))


def build_report(
    company: Company,
    processes: list[Process],
    scored_use_cases: list[ScoredUseCase],
    excluded: list[UseCase],
    no_fit: list[tuple[str, str]],
    roadmap_planned: list[RoadmapItem],
    roadmap_archived: list[RoadmapItem],
    assumptions: Assumptions,
    weights: dict[str, dict[str, float]],
    output_path: str | io.BytesIO,
) -> None:
    """Build the full PDF report and write it to output_path.

    output_path may be a filesystem path (str) or an in-memory buffer
    (io.BytesIO), so the same function serves both scripts/export_report.py
    (writes to disk) and app.py's download button (writes in memory).

    This function reuses core/ and viz/ as-is: it calls no LLM and
    recomputes nothing beyond compute_business_cases() for the wave-1 use
    cases, the same pure function the Streamlit UI calls.

    Pages: cover, synthèse, matrice, feuille de route, one page per wave-1
    use case, and a final annexe (assumptions, weights, formulas, limits).
    """
    _register_fonts()
    styles = _build_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN_MM * mm,
        rightMargin=MARGIN_MM * mm,
        topMargin=MARGIN_MM * mm,
        bottomMargin=MARGIN_MM * mm,
        title=f"Évaluation des opportunités IA — {company.name}",
    )

    story: list = []
    _cover_page(story, styles, company)
    _synthesis_page(
        story, styles, company, processes, scored_use_cases, excluded, no_fit, roadmap_planned, assumptions
    )
    _matrix_page(story, styles, scored_use_cases)
    _roadmap_page(story, styles, roadmap_planned, roadmap_archived)

    wave1_items = [item for item in roadmap_planned if item.wave == 1]
    for item in wave1_items:
        process = _find_process(item.scored_use_case.use_case.process_name, processes)
        _wave1_use_case_page(story, styles, item, process, company.hourly_cost_eur, assumptions)

    _annexe_page(story, styles, assumptions, weights)

    doc.build(story, canvasmaker=_NumberedCanvas)
