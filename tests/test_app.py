"""Tests for app.py using streamlit.testing.v1.AppTest (no real API calls)."""

import os

from streamlit.testing.v1 import AppTest

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
RUN_TIMEOUT = 30

LOAD_DEMO_COMPANY_LABEL = "Charger l'entreprise de démo"
LOAD_DEMO_USE_CASES_LABEL = "Charger les cas de démo"

PHASE0_RANKING_ORDER = [
    "Supplier invoice processing",
    "Order status inquiries",
    "Quote generation",
    "Monthly management reporting consolidation",
    "CV screening for open positions",
]


def _click_button(at: AppTest, label: str) -> AppTest:
    """Click the first button matching the given label and rerun."""
    button = next(b for b in at.button if b.label == label)
    return button.click().run(timeout=RUN_TIMEOUT)


def _ranking_dataframe(at: AppTest):
    """Return the ranking dataframe (the one with a 'Rang' column)."""
    return next(df for df in at.dataframe if "Rang" in df.value.columns)


def test_app_runs_without_exception():
    """The app runs end to end with no exception on first load."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=RUN_TIMEOUT)

    assert not at.exception


def test_loading_demo_company_gives_12_processes():
    """Clicking the demo-company button loads exactly 12 processes."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=RUN_TIMEOUT)

    at = _click_button(at, LOAD_DEMO_COMPANY_LABEL)

    assert not at.exception
    assert len(at.session_state["processes"]) == 12


def test_loading_demo_use_cases_reproduces_phase0_ranking_order():
    """Loading demo processes + demo use cases reproduces the known phase-0 ranking order."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=RUN_TIMEOUT)
    at = _click_button(at, LOAD_DEMO_COMPANY_LABEL)
    at = _click_button(at, LOAD_DEMO_USE_CASES_LABEL)

    assert not at.exception
    ranking_df = _ranking_dataframe(at)
    assert ranking_df.value["Processus"].tolist() == PHASE0_RANKING_ORDER


def test_setting_priority_risk_weight_to_zero_ranks_cv_screening_above_monthly_reporting():
    """Zeroing the priority axis's risk weight ranks CV screening above monthly reporting."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=RUN_TIMEOUT)
    at = _click_button(at, LOAD_DEMO_COMPANY_LABEL)
    at = _click_button(at, LOAD_DEMO_USE_CASES_LABEL)

    slider = at.slider(key="weight_priority_risk")
    at = slider.set_value(0.0).run(timeout=RUN_TIMEOUT)

    assert not at.exception
    ranking_df = _ranking_dataframe(at)
    ranks_by_process = dict(zip(ranking_df.value["Processus"], ranking_df.value["Rang"]))
    assert ranks_by_process["CV screening for open positions"] < ranks_by_process[
        "Monthly management reporting consolidation"
    ]


# Demo mode: no API key in the environment. setenv (not delenv) is required —
# app.py calls load_dotenv() on every run, which would otherwise silently
# restore the real key from .env (load_dotenv never overrides a key that is
# already present in os.environ, even an empty one).
def test_app_runs_without_exception_with_no_api_key(monkeypatch):
    """The app runs end to end with no exception when no API key is configured."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=RUN_TIMEOUT)

    assert not at.exception


def test_ranking_is_visible_on_first_load_with_no_click(monkeypatch):
    """The French demo company and cached use cases are auto-loaded: the ranking
    table is populated immediately, with no button click."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=RUN_TIMEOUT)

    assert not at.exception
    ranking_df = _ranking_dataframe(at)
    assert len(ranking_df.value) > 0


def test_generate_with_ai_button_is_disabled_without_api_key(monkeypatch):
    """The 'Générer avec l'IA' button is disabled when no API key is configured."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=RUN_TIMEOUT)

    generate_button = next(b for b in at.button if b.label == "Générer avec l'IA")
    assert generate_button.disabled


def test_pdf_download_button_is_present_on_first_load(monkeypatch):
    """The PDF download button is present immediately, with no button click."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=RUN_TIMEOUT)

    assert not at.exception
    assert any(b.label == "Télécharger le rapport PDF" for b in at.download_button)
