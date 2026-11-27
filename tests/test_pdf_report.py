"""Tests for export/pdf_report.py (no API calls)."""

import json
from pathlib import Path

import pypdf
import pytest

from core.assumptions import Assumptions
from core.loader import load_company, load_processes
from core.models import UseCase
from core.roadmap import build_roadmap
from core.scoring import DEFAULT_WEIGHTS, score_use_cases, split_prohibited
from export.pdf_report import build_report

DEMO_CSV_PATH = "data/demo_company.csv"
DEMO_COMPANY_PATH = "data/demo_company_profile.json"
PHASE0_JSON_PATH = "data/phase0_use_cases.json"
HOURLY_COST_EUR = 35

MIN_PAGES = 6
MAX_PAGES = 10


@pytest.fixture
def demo_report_path(tmp_path: Path) -> Path:
    """Build the demo report (same pipeline as scripts/export_report.py) into a temp file."""
    company = load_company(DEMO_COMPANY_PATH)
    processes = load_processes(DEMO_CSV_PATH)
    processes_by_name = {p.name: p for p in processes}

    with open(PHASE0_JSON_PATH, encoding="utf-8") as f:
        raw_use_cases = json.load(f)
    use_cases = [UseCase(**item) for item in raw_use_cases]

    _, excluded = split_prohibited(use_cases)
    scored, _ = score_use_cases(use_cases, processes_by_name, HOURLY_COST_EUR)
    planned, archived = build_roadmap(scored)

    output_path = tmp_path / "demo_report.pdf"
    build_report(
        company=company,
        processes=processes,
        scored_use_cases=scored,
        excluded=excluded,
        no_fit=[],
        roadmap_planned=planned,
        roadmap_archived=archived,
        assumptions=Assumptions(),
        weights=DEFAULT_WEIGHTS,
        output_path=str(output_path),
    )
    return output_path


def test_report_is_created(demo_report_path: Path):
    """build_report writes a non-empty PDF file at output_path."""
    assert demo_report_path.exists()
    assert demo_report_path.stat().st_size > 0


def test_report_has_6_to_10_pages(demo_report_path: Path):
    """The demo report has between 6 and 10 A4 pages."""
    reader = pypdf.PdfReader(str(demo_report_path))
    assert MIN_PAGES <= len(reader.pages) <= MAX_PAGES


def test_report_text_contains_expected_content(demo_report_path: Path):
    """The extracted text contains the decision call-out, the company name, and the
    wave-1 use case names (Supplier invoice processing, Order status inquiries)."""
    reader = pypdf.PdfReader(str(demo_report_path))
    full_text = "\n".join(page.extract_text() for page in reader.pages)

    assert "Décision attendue" in full_text
    assert "NordIndus Distribution" in full_text
    assert "Supplier invoice processing" in full_text
    assert "Order status inquiries" in full_text


def test_synthesis_main_risk_is_highest_risk_across_all_waves(demo_report_path: Path):
    """The main risk is the highest-risk planned case across ALL waves, not just wave 1:
    for the demo, that is the wave-2 CV screening case (high AI Act risk), not a wave-1 one."""
    reader = pypdf.PdfReader(str(demo_report_path))
    full_text = "\n".join(page.extract_text() for page in reader.pages)

    assert "Risque principal : CV screening for open positions" in full_text
    assert "Élevé, vague 2" in full_text
