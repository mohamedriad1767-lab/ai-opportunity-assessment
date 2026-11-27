"""Render the 3-wave roadmap as a horizontal timeline (Plotly figure).

This module only builds a chart from an already-built roadmap. It does not
decide wave assignments or reasons — that logic lives in core/roadmap.py
(build_roadmap). Only planned items are drawn; archived items have no wave
and therefore no place on a timeline.
"""

import plotly.graph_objects as go

from core.roadmap import WAVE_LABELS, RoadmapItem

WAVE_BOUNDS_MONTHS: dict[int, tuple[float, float]] = {
    1: (0, 3),
    2: (3, 9),
    3: (9, 18),
}
WAVE_BAND_COLORS: dict[int, str] = {
    1: "rgba(0, 114, 178, 0.07)",
    2: "rgba(230, 159, 0, 0.07)",
    3: "rgba(213, 94, 0, 0.07)",
}

AI_ACT_COLORS = {
    "minimal": "#0072B2",  # blue (Okabe-Ito, colorblind-safe) — same palette as the matrix chart
    "limited": "#E69F00",  # amber (Okabe-Ito, colorblind-safe)
    "high": "#D55E00",  # vermillion — warm alert color (Okabe-Ito, colorblind-safe)
}
AI_ACT_LABELS_FR = {"minimal": "Minimal", "limited": "Limité", "high": "Élevé"}


def build_roadmap_figure(planned: list[RoadmapItem]) -> go.Figure:
    """Build the horizontal roadmap timeline.

    One horizontal bar per planned use case, spanning its wave's time band
    (0-3, 3-9, 9-18 months), labeled on the y axis with its rank and process
    name, and colored by EU AI Act risk level (same palette as the matrix
    chart). Rows are ordered top-to-bottom in the same order build_roadmap
    returns them (wave ascending, then priority descending within a wave).
    """
    # Plotly draws horizontal-bar y categories bottom-to-top, so reverse the
    # planned order to get the first planned item drawn at the top.
    ordered = list(reversed(planned))
    labels = [f"{item.scored_use_case.rank}. {item.scored_use_case.use_case.process_name}" for item in ordered]

    fig = go.Figure()

    for ai_act_level, color in AI_ACT_COLORS.items():
        items = [item for item in ordered if item.scored_use_case.use_case.ai_act.value == ai_act_level]
        item_labels = [
            f"{item.scored_use_case.rank}. {item.scored_use_case.use_case.process_name}" for item in items
        ]
        starts = [WAVE_BOUNDS_MONTHS[item.wave][0] for item in items]
        ends = [WAVE_BOUNDS_MONTHS[item.wave][1] for item in items]
        fig.add_trace(
            go.Bar(
                x=[end - start for start, end in zip(starts, ends)],
                y=item_labels,
                base=starts,
                orientation="h",
                name=AI_ACT_LABELS_FR[ai_act_level],
                showlegend=True,
                marker=dict(color=color, line=dict(width=1, color="white")),
                customdata=[
                    [
                        item.scored_use_case.use_case.process_name,
                        WAVE_LABELS[item.wave],
                        item.scored_use_case.scores.priority,
                        item.scored_use_case.annual_gain_eur,
                        item.reason,
                    ]
                    for item in items
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Vague : %{customdata[1]}<br>"
                    "Priorité : %{customdata[2]:.1f}<br>"
                    "Gain annuel : %{customdata[3]:,.0f} €<br>"
                    "%{customdata[4]}"
                    "<extra></extra>"
                ),
            )
        )

    for wave, (start, end) in WAVE_BOUNDS_MONTHS.items():
        fig.add_shape(
            type="rect",
            x0=start,
            x1=end,
            y0=-0.5,
            y1=len(labels) - 0.5,
            fillcolor=WAVE_BAND_COLORS[wave],
            line=dict(width=0),
            layer="below",
        )
        fig.add_annotation(
            x=(start + end) / 2,
            y=1.0,
            yref="paper",
            yanchor="bottom",
            xanchor="center",
            text=f"<b>Vague {wave}</b> ({WAVE_LABELS[wave]})",
            showarrow=False,
            font=dict(size=13, color="#333333"),
        )

    fig.update_layout(
        template="simple_white",
        title=dict(text="Feuille de route en 3 vagues"),
        xaxis=dict(title="Mois", range=[0, 18], showgrid=True, gridcolor="#eeeeee"),
        yaxis=dict(
            title="",
            categoryorder="array",
            categoryarray=labels,
        ),
        legend_title_text="Niveau AI Act",
        margin=dict(t=120, l=250),
        height=max(350, 80 + 50 * len(labels)),
    )
    return fig
