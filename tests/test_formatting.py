"""Tests for export/formatting.py (no API calls)."""

from export.formatting import NBSP, fmt_eur, fmt_months, fmt_pct


def test_fmt_eur_groups_thousands_with_nbsp_and_rounds():
    """156065.4 formats as '156 065 €' (non-breaking spaces, no decimals)."""
    assert fmt_eur(156065.4) == f"156{NBSP}065{NBSP}€"


def test_fmt_eur_small_amount_has_no_thousands_separator():
    """An amount below 1000 has no separator at all."""
    assert fmt_eur(650) == f"650{NBSP}€"


def test_fmt_eur_negative_amount_keeps_the_sign():
    """A negative amount keeps its minus sign in front."""
    assert fmt_eur(-1200) == f"-1{NBSP}200{NBSP}€"


def test_fmt_pct_uses_a_comma_decimal():
    """A 2.412 ratio (241.2%) formats as '241,2 %'."""
    assert fmt_pct(2.412) == f"241,2{NBSP}%"


def test_fmt_pct_rounds_to_one_decimal():
    """0.6534 (65.34%) rounds to '65,3 %'."""
    assert fmt_pct(0.6534) == f"65,3{NBSP}%"


def test_fmt_months_uses_a_comma_decimal():
    """2.9 formats as '2,9 mois'."""
    assert fmt_months(2.9) == "2,9 mois"


def test_fmt_months_none_is_never_paid_back():
    """None formats as the French 'jamais remboursé'."""
    assert fmt_months(None) == "jamais remboursé"
