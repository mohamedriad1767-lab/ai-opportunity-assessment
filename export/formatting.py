"""French-style number formatting helpers, shared by the PDF report and the app tables.

A non-breaking space (U+00A0) is used as the thousands separator and before
the euro/percent signs. French typography ideally uses a *narrow* no-break
space (U+202F), but the Vera font bundled with reportlab (used throughout
the PDF report so it renders identically on any OS, with no system-font
dependency) has no glyph for that codepoint. A regular non-breaking space
renders correctly with Vera and still does the one thing that matters here:
it keeps a number from breaking across a line.
"""

NBSP = " "


def fmt_eur(x: float) -> str:
    """Format a euro amount with French thousands grouping and no decimals.

    e.g. 156065.4 -> "156 065 €" (non-breaking spaces as thousands
    separators and before the euro sign; 156065.4 rounds to 156065).
    """
    rounded = round(x)
    sign = "-" if rounded < 0 else ""
    grouped = f"{abs(rounded):,}".replace(",", NBSP)
    return f"{sign}{grouped}{NBSP}€"


def fmt_pct(x: float) -> str:
    """Format a ratio as a French percentage with 1 decimal and a comma.

    x is a fraction, not already multiplied by 100 (e.g. 2.412 -> "241,2 %"),
    matching how ROI is stored (0.65 means 65%, 2.412 means 241.2%).
    """
    text = f"{x * 100:.1f}".replace(".", ",")
    return f"{text}{NBSP}%"


def fmt_months(x: float | None) -> str:
    """Format a payback period in months with a comma decimal.

    Returns "jamais remboursé" (never pays back) when x is None.
    """
    if x is None:
        return "jamais remboursé"
    text = f"{x:.1f}".replace(".", ",")
    return f"{text} mois"
