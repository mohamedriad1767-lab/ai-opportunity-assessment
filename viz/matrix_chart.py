"""Render the value x feasibility quadrant chart as a Plotly figure.

This module only builds a chart from already-computed scores. It does not
score, rank, or classify anything new — classify_quadrant (core/matrix.py)
is used only to label the 4 corners, not to compute per-point positions
(those come straight from each use case's own value/feasibility scores).
"""

import plotly.graph_objects as go

from core.matrix import Quadrant
from core.models import ScoredUseCase

AI_ACT_COLORS = {
    "minimal": "#0072B2",  # blue (Okabe-Ito, colorblind-safe)
    "limited": "#E69F00",  # amber (Okabe-Ito, colorblind-safe)
    "high": "#D55E00",  # vermillion — warm alert color (Okabe-Ito, colorblind-safe)
}
AI_ACT_LABELS_FR = {"minimal": "Minimal", "limited": "Limité", "high": "Élevé"}
TYPE_LABELS_FR = {
    "assistant": "Assistant",
    "document_extraction": "Extraction de documents",
    "classification": "Classification",
    "agent": "Agent",
    "generation": "Génération",
}

# Rank-number text labels are nudged off-center when two bubbles are closer
# than this (in 0-100 score units) so neither number is obscured by the
# other bubble. Positions cycle through this palette as more overlapping
# bubbles are encountered at roughly the same spot.
OVERLAP_DISTANCE = 6.0
TEXT_POSITIONS = ["middle center", "top center", "bottom center", "middle right", "middle left"]

QUADRANT_CORNERS = {
    Quadrant.QUICK_WIN: {"x": 1, "y": 1, "xanchor": "right", "yanchor": "top"},
    Quadrant.STRUCTURAL: {"x": 0, "y": 1, "xanchor": "left", "yanchor": "top"},
    Quadrant.OPTIMIZATION: {"x": 1, "y": 0, "xanchor": "right", "yanchor": "bottom"},
    Quadrant.DISCARD: {"x": 0, "y": 0, "xanchor": "left", "yanchor": "bottom"},
}

MAX_MARKER_SIZE = 50
QUICK_WIN_SHADING_COLOR = "rgba(0, 114, 178, 0.08)"

# The rank -> name caption is a variable-length list (one line per use case),
# so the figure's bottom margin and total height scale with how many use
# cases are plotted, instead of a fixed size that would clip a large
# portfolio or waste space on a small one. The plot area itself (where the
# bubbles live) always keeps the same height, so the chart's proportions
# don't change with portfolio size.
PLOT_AREA_HEIGHT_PX = 650
MARGIN_TOP_PX = 100
CAPTION_HEADER_HEIGHT_PX = 20
CAPTION_LINE_HEIGHT_PX = 16
CAPTION_TOP_GAP_PX = 20
CAPTION_BOTTOM_PADDING_PX = 20


def _size_ref(scored_use_cases: list[ScoredUseCase]) -> float:
    """Plotly's recommended sizeref so the largest bubble fits MAX_MARKER_SIZE."""
    max_gain = max((item.annual_gain_eur for item in scored_use_cases), default=1)
    return 2.0 * max(max_gain, 1) / (MAX_MARKER_SIZE**2)


def _rank_to_name_caption(scored_use_cases: list[ScoredUseCase]) -> str:
    """Build the 'rank -> process — type' legend shown below the chart.

    The type (in French) is included, not just the process name, so two use
    cases proposed for the same process (e.g. when "Afficher tous les cas
    d'usage" is on) stay distinguishable in the legend.
    """
    ordered = sorted(scored_use_cases, key=lambda item: item.rank)
    lines = [
        f"{item.rank}. {item.use_case.process_name} — {TYPE_LABELS_FR[item.use_case.type.value]}"
        for item in ordered
    ]
    return "<b>Légende des rangs</b><br>" + "<br>".join(lines)


def _text_positions(scored_use_cases: list[ScoredUseCase]) -> dict[int, str]:
    """Assign a text position per use case (keyed by rank), nudging the rank
    number off-center whenever its bubble sits within OVERLAP_DISTANCE of an
    already-placed one, so overlapping bubbles don't hide each other's label.
    """
    positions: dict[int, str] = {}
    placed: list[tuple[float, float]] = []
    for item in sorted(scored_use_cases, key=lambda item: item.rank):
        x, y = item.scores.feasibility, item.scores.value
        overlap_count = sum(
            1 for px, py in placed if ((px - x) ** 2 + (py - y) ** 2) ** 0.5 < OVERLAP_DISTANCE
        )
        positions[item.rank] = TEXT_POSITIONS[overlap_count % len(TEXT_POSITIONS)]
        placed.append((x, y))
    return positions


def _layout_dimensions(num_items: int) -> tuple[float, float, float]:
    """Return (total_height_px, bottom_margin_px, caption_y_paper_fraction).

    Sized so the rank -> name caption (CAPTION_HEADER_HEIGHT_PX plus
    CAPTION_LINE_HEIGHT_PX per use case) always fits below the plot area,
    whatever the portfolio size.
    """
    caption_height = CAPTION_HEADER_HEIGHT_PX + CAPTION_LINE_HEIGHT_PX * num_items
    margin_bottom = CAPTION_TOP_GAP_PX + caption_height + CAPTION_BOTTOM_PADDING_PX
    total_height = MARGIN_TOP_PX + PLOT_AREA_HEIGHT_PX + margin_bottom
    caption_y = -CAPTION_TOP_GAP_PX / PLOT_AREA_HEIGHT_PX
    return total_height, margin_bottom, caption_y


def build_matrix_figure(
    scored_use_cases: list[ScoredUseCase],
    value_threshold: float = 50,
    feasibility_threshold: float = 50,
) -> go.Figure:
    """Build the value x feasibility bubble chart.

    x = feasibility (0-100), y = value (0-100), bubble size = annual gain
    (EUR), color = EU AI Act risk level. Dashed lines mark the thresholds,
    the 4 quadrant names are annotated in the corners (Quick wins lightly
    shaded), each bubble is labeled with its rank number, and a rank -> use
    case name caption is added below the chart for static/PDF export.
    """
    fig = go.Figure()
    size_ref = _size_ref(scored_use_cases)
    text_positions = _text_positions(scored_use_cases)

    for ai_act_level, color in AI_ACT_COLORS.items():
        items = [item for item in scored_use_cases if item.use_case.ai_act.value == ai_act_level]
        fig.add_trace(
            go.Scatter(
                x=[item.scores.feasibility for item in items],
                y=[item.scores.value for item in items],
                mode="markers+text",
                name=AI_ACT_LABELS_FR[ai_act_level],
                legendgroup=ai_act_level,
                showlegend=True,
                text=[str(item.rank) for item in items],
                textposition=[text_positions[item.rank] for item in items],
                # White text reads fine on the bubble itself ("middle center"),
                # but a nudged-off-center label sits on the white background
                # instead, where white would be invisible — use the bubble's
                # own color there so it stays legible either way.
                textfont=dict(
                    size=11,
                    color=["white" if text_positions[item.rank] == "middle center" else color for item in items],
                ),
                marker=dict(
                    size=[max(item.annual_gain_eur, 1) for item in items],
                    sizemode="area",
                    sizeref=size_ref,
                    sizemin=18,
                    color=color,
                    line=dict(width=1, color="white"),
                ),
                customdata=[
                    [
                        item.use_case.process_name,
                        item.use_case.description,
                        item.rank,
                        item.scores.priority,
                        item.annual_gain_eur,
                    ]
                    for item in items
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "%{customdata[1]}<br>"
                    "Priorité : %{customdata[3]:.1f}<br>"
                    "Gain annuel : %{customdata[4]:,.0f} €"
                    "<extra></extra>"
                ),
            )
        )

    fig.add_shape(
        type="rect",
        x0=feasibility_threshold,
        x1=100,
        y0=value_threshold,
        y1=100,
        fillcolor=QUICK_WIN_SHADING_COLOR,
        line=dict(width=0),
        layer="below",
    )
    fig.add_shape(
        type="line",
        x0=feasibility_threshold,
        x1=feasibility_threshold,
        y0=0,
        y1=100,
        line=dict(dash="dash", color="gray"),
    )
    fig.add_shape(
        type="line",
        x0=0,
        x1=100,
        y0=value_threshold,
        y1=value_threshold,
        line=dict(dash="dash", color="gray"),
    )

    for quadrant, corner in QUADRANT_CORNERS.items():
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=corner["x"],
            y=corner["y"],
            xanchor=corner["xanchor"],
            yanchor=corner["yanchor"],
            text=f"<b>{quadrant.value}</b>",
            showarrow=False,
            font=dict(size=16, color="#333333"),
            opacity=0.9,
        )

    total_height, margin_bottom, caption_y = _layout_dimensions(len(scored_use_cases))

    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0,
        y=caption_y,
        xanchor="left",
        yanchor="top",
        align="left",
        text=_rank_to_name_caption(scored_use_cases),
        showarrow=False,
        font=dict(size=11, color="#333333"),
    )

    fig.update_layout(
        template="simple_white",
        title=dict(
            text=(
                "Matrice valeur × faisabilité"
                "<br><sup>Taille des bulles = gain annuel (€) · couleur = niveau AI Act</sup>"
            )
        ),
        xaxis=dict(title="Faisabilité", range=[0, 100], showgrid=True, gridcolor="#eeeeee"),
        yaxis=dict(title="Valeur", range=[0, 100], showgrid=True, gridcolor="#eeeeee"),
        legend_title_text="Niveau AI Act",
        margin=dict(b=margin_bottom, t=MARGIN_TOP_PX),
        height=total_height,
    )
    return fig
