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
