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

QUADRANT_CORNERS = {
    Quadrant.QUICK_WIN: {"x": 1, "y": 1, "xanchor": "right", "yanchor": "top"},
    Quadrant.STRUCTURAL: {"x": 0, "y": 1, "xanchor": "left", "yanchor": "top"},
    Quadrant.OPTIMIZATION: {"x": 1, "y": 0, "xanchor": "right", "yanchor": "bottom"},
    Quadrant.DISCARD: {"x": 0, "y": 0, "xanchor": "left", "yanchor": "bottom"},
}

MAX_MARKER_SIZE = 50


def _size_ref(scored_use_cases: list[ScoredUseCase]) -> float:
    """Plotly's recommended sizeref so the largest bubble fits MAX_MARKER_SIZE."""
    max_gain = max((item.annual_gain_eur for item in scored_use_cases), default=1)
    return 2.0 * max(max_gain, 1) / (MAX_MARKER_SIZE**2)


def build_matrix_figure(
    scored_use_cases: list[ScoredUseCase],
    value_threshold: float = 50,
    feasibility_threshold: float = 50,
) -> go.Figure:
    """Build the value x feasibility bubble chart.

    x = feasibility (0-100), y = value (0-100), bubble size = annual gain
    (EUR), color = EU AI Act risk level. Dashed lines mark the thresholds,
    and the 4 quadrant names are annotated in the corners.
    """
    fig = go.Figure()
    size_ref = _size_ref(scored_use_cases)

    for ai_act_level, color in AI_ACT_COLORS.items():
        items = [item for item in scored_use_cases if item.use_case.ai_act.value == ai_act_level]
        if not items:
            continue
        fig.add_trace(
            go.Scatter(
                x=[item.scores.feasibility for item in items],
                y=[item.scores.value for item in items],
                mode="markers",
                name=AI_ACT_LABELS_FR[ai_act_level],
                marker=dict(
                    size=[max(item.annual_gain_eur, 1) for item in items],
                    sizemode="area",
                    sizeref=size_ref,
                    sizemin=8,
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
            text=quadrant.value,
            showarrow=False,
            font=dict(size=13, color="gray"),
            opacity=0.8,
        )

    fig.update_layout(
        title="Matrice valeur x faisabilité",
        xaxis=dict(title="Faisabilité", range=[0, 100]),
        yaxis=dict(title="Valeur", range=[0, 100]),
        legend_title_text="Niveau AI Act",
    )
    return fig
