"""Streamlit UI for the AI Opportunity Assessment project.

This file contains NO business logic: it only collects inputs, calls
functions from core/, and renders their outputs. All formulas (scoring,
cost, business case) and all LLM calls live in core/.
"""

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from pydantic import ValidationError

from core.assumptions import Assumptions
from core.business_case import compute_business_cases
from core.generator import GenerationError, generate_use_cases, make_client
from core.loader import load_company, load_processes, load_use_cases, validate_records
from core.models import AIActLevel, Company, GDPRLevel, Process, UseCase, UseCaseType
from core.scoring import DEFAULT_WEIGHTS, normalize_weights, score_use_cases, split_prohibited, validate_weights

load_dotenv()

DEMO_COMPANY_PATH = "data/demo_company_profile.json"
DEMO_PROCESSES_PATH = "data/demo_company.csv"
DEMO_USE_CASES_PATH = "data/phase0_use_cases.json"

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
SCENARIO_LABELS = {"pessimistic": "Pessimiste", "base": "Base", "optimistic": "Optimiste"}


@st.cache_data
def _cached_load_company(path: str) -> Company:
    """Load a company profile JSON file (cached — file loading only)."""
    return load_company(path)


@st.cache_data
def _cached_load_processes(path: str) -> list[Process]:
    """Load a processes CSV file (cached — file loading only)."""
    return load_processes(path)


@st.cache_data
def _cached_load_use_cases(path: str) -> list[UseCase]:
    """Load a use-cases JSON file (cached — file loading only)."""
    return load_use_cases(path)


def _init_session_state() -> None:
    """Initialize all session_state keys used across tabs, once."""
    if "company" not in st.session_state:
        st.session_state.company = _cached_load_company(DEMO_COMPANY_PATH)
    if "assumptions" not in st.session_state:
        st.session_state.assumptions = Assumptions()
    if "processes" not in st.session_state:
        st.session_state.processes = []
    if "use_cases" not in st.session_state:
        st.session_state.use_cases = []
    if "no_fit_reasons" not in st.session_state:
        st.session_state.no_fit_reasons = []


def render_contexte_tab() -> None:
    """Company profile form + an expander exposing every Assumptions field."""
    st.header("Contexte entreprise")
    company = st.session_state.company

    name = st.text_input("Nom de l'entreprise", value=company.name)
    sector = st.text_input("Secteur", value=company.sector)
    employees = st.number_input("Nombre d'employés", value=company.employees, min_value=1, step=1)
    hourly_cost = st.number_input(
        "Coût horaire chargé (€)", value=company.hourly_cost_eur, min_value=0.0, step=1.0
    )
    ai_budget = st.number_input(
        "Budget IA annuel (€) — 0 si non défini",
        value=company.ai_budget_eur or 0.0,
        min_value=0.0,
        step=1000.0,
    )

    try:
        st.session_state.company = Company(
            name=name,
            sector=sector,
            employees=int(employees),
            hourly_cost_eur=hourly_cost,
            ai_budget_eur=ai_budget if ai_budget > 0 else None,
        )
    except ValidationError as exc:
        st.error(f"Entreprise invalide : {exc}")

    with st.expander("Hypothèses du business case"):
        assumptions = st.session_state.assumptions

        daily_rate = st.number_input(
            "Taux journalier (€)", value=assumptions.daily_rate_eur, min_value=0.0, step=10.0
        )

        st.markdown("**Jours de build par complexité technique (1 à 5)**")
        build_days_cols = st.columns(5)
        build_days = {
            level: build_days_cols[level - 1].number_input(
                f"Complexité {level}",
                value=assumptions.build_days_by_complexity[level],
                min_value=0.0,
                key=f"build_days_{level}",
            )
            for level in range(1, 6)
        }

        off_the_shelf_factor = st.slider(
            "Facteur de build pour un outil sur étagère", 0.0, 1.0, assumptions.off_the_shelf_build_factor
        )
        integration_days = st.number_input(
            "Jours d'intégration par source de données",
            value=assumptions.integration_days_per_data_source,
            min_value=0.0,
            step=0.5,
        )
        annual_license = st.number_input(
            "Licence annuelle (outil sur étagère, €)",
            value=assumptions.annual_license_eur_off_the_shelf,
            min_value=0.0,
            step=100.0,
        )
        llm_cost = st.number_input(
            "Coût LLM par occurrence (€)",
            value=assumptions.llm_cost_per_occurrence_eur,
            min_value=0.0,
            step=0.001,
            format="%.4f",
        )
        maintenance_pct = st.slider(
            "Maintenance annuelle (% du coût de build)", 0.0, 1.0, assumptions.maintenance_pct_of_build
        )

        st.markdown("**Jours de change management par risque d'adoption (1 à 5)**")
        change_days_cols = st.columns(5)
        change_days = {
            level: change_days_cols[level - 1].number_input(
                f"Risque {level}",
                value=assumptions.change_management_days_by_adoption_risk[level],
                min_value=0.0,
                key=f"change_days_{level}",
            )
            for level in range(1, 6)
        }

        st.markdown("**Taux d'adoption par scénario**")
        adoption_cols = st.columns(3)
        pessimistic = adoption_cols[0].slider("Pessimiste", 0.0, 1.0, assumptions.adoption_rates["pessimistic"])
        base = adoption_cols[1].slider("Base", 0.0, 1.0, assumptions.adoption_rates["base"])
        optimistic = adoption_cols[2].slider("Optimiste", 0.0, 1.0, assumptions.adoption_rates["optimistic"])

        horizon_years = st.number_input("Horizon (années)", value=assumptions.horizon_years, min_value=1, step=1)

        try:
            st.session_state.assumptions = Assumptions(
                daily_rate_eur=daily_rate,
                build_days_by_complexity=build_days,
                off_the_shelf_build_factor=off_the_shelf_factor,
                integration_days_per_data_source=integration_days,
                annual_license_eur_off_the_shelf=annual_license,
                llm_cost_per_occurrence_eur=llm_cost,
                maintenance_pct_of_build=maintenance_pct,
                change_management_days_by_adoption_risk=change_days,
                adoption_rates={"pessimistic": pessimistic, "base": base, "optimistic": optimistic},
                horizon_years=int(horizon_years),
            )
        except ValidationError as exc:
            st.error(f"Hypothèses invalides : {exc}")


def render_processus_tab() -> None:
    """Demo-load button, CSV upload, and an editable table of processes."""
    st.header("Processus métier")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Charger l'entreprise de démo"):
            st.session_state.processes = _cached_load_processes(DEMO_PROCESSES_PATH)
    with col2:
        uploaded_file = st.file_uploader(
            "Importer un CSV de processus (mêmes colonnes que la démo)", type="csv"
        )
        if uploaded_file is not None:
            uploaded_df = pd.read_csv(uploaded_file)
            valid, errors = validate_records(uploaded_df.to_dict(orient="records"), Process)
            for error in errors:
                st.error(error)
            if valid:
                st.session_state.processes = valid
                st.success(f"{len(valid)} processus importés.")

    st.subheader("Tableau des processus (éditable)")
    if not st.session_state.processes:
        st.info("Aucun processus chargé. Chargez la démo ou importez un CSV.")
        return

    display_df = pd.DataFrame([p.model_dump() for p in st.session_state.processes])
    display_df["pain_points"] = display_df["pain_points"].apply(lambda items: "; ".join(items))
    display_df["data_used"] = display_df["data_used"].apply(lambda items: "; ".join(items))

    edited_df = st.data_editor(display_df, key="processes_editor", width="stretch", num_rows="dynamic")

    valid, errors = validate_records(edited_df.to_dict(orient="records"), Process)
    if errors:
        st.warning("Certaines lignes sont invalides et ne sont pas prises en compte :")
        for error in errors:
            st.error(error)
    st.caption(f"{len(valid)} processus valides sur {len(edited_df)} ligne(s).")
    st.session_state.processes = valid


def render_cas_usage_tab() -> None:
    """AI generation / demo loading, editable criteria table, no-fit and excluded lists."""
    st.header("Cas d'usage IA")
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    col1, col2 = st.columns(2)
    with col1:
        if api_key:
            if st.button("Générer avec l'IA"):
                if not st.session_state.processes:
                    st.warning("Chargez d'abord des processus dans l'onglet «Processus».")
                else:
                    client = make_client(api_key)
                    all_use_cases: list[UseCase] = []
                    no_fit_reasons: list[tuple[str, str]] = []
                    generation_errors: list[str] = []
                    progress_bar = st.progress(0)
                    processes = st.session_state.processes
                    for index, process in enumerate(processes):
                        try:
                            result = generate_use_cases(st.session_state.company, process, client)
                            all_use_cases.extend(result.use_cases)
                            if result.no_fit_reason:
                                no_fit_reasons.append((process.name, result.no_fit_reason))
                        except GenerationError as exc:
                            generation_errors.append(f"{process.name} : {exc}")
                        progress_bar.progress((index + 1) / len(processes))
                    st.session_state.use_cases = all_use_cases
                    st.session_state.no_fit_reasons = no_fit_reasons
                    for error in generation_errors:
                        st.error(error)
        else:
            st.info(
                "Clé API Anthropic manquante (ANTHROPIC_API_KEY). Ajoutez-la dans votre "
                "fichier .env pour activer la génération par IA."
            )
    with col2:
        if st.button("Charger les cas de démo"):
            st.session_state.use_cases = _cached_load_use_cases(DEMO_USE_CASES_PATH)
            st.session_state.no_fit_reasons = []

    allowed, excluded = split_prohibited(st.session_state.use_cases)

    st.subheader("Critères des cas d'usage (éditable)")
    if allowed:
        editable_columns = [
            "process_name",
            "type",
            "description",
            "quality_impact",
            "strategic_alignment",
            "data_quality",
            "technical_complexity",
            "adoption_risk",
            "off_the_shelf",
            "ai_act",
            "gdpr",
        ]
        display_df = pd.DataFrame([uc.model_dump(mode="json") for uc in allowed])[editable_columns]

        note_column = lambda: st.column_config.NumberColumn(min_value=1, max_value=5, step=1)
        edited_df = st.data_editor(
            display_df,
            key="use_case_editor",
            width="stretch",
            disabled=["process_name", "description"],
            column_config={
                "quality_impact": note_column(),
                "strategic_alignment": note_column(),
                "data_quality": note_column(),
                "technical_complexity": note_column(),
                "adoption_risk": note_column(),
                "type": st.column_config.SelectboxColumn(options=[level.value for level in UseCaseType]),
                "ai_act": st.column_config.SelectboxColumn(options=[level.value for level in AIActLevel]),
                "gdpr": st.column_config.SelectboxColumn(options=[level.value for level in GDPRLevel]),
            },
        )

        updated_use_cases: list[UseCase] = []
        edit_errors: list[str] = []
        for row_index, row in edited_df.iterrows():
            original = allowed[row_index]
            try:
                merged = original.model_copy(update=row.to_dict())
                validated = UseCase.model_validate(merged.model_dump())
            except ValidationError as exc:
                edit_errors.append(f"Ligne {row_index} ({original.process_name}) : {exc}")
                updated_use_cases.append(original)
            else:
                updated_use_cases.append(validated)
        for error in edit_errors:
            st.error(error)
        st.session_state.use_cases = updated_use_cases + excluded
    else:
        st.info("Aucun cas d'usage. Générez-en avec l'IA ou chargez les cas de démo.")

    st.subheader("Processus sans cas d'usage retenu")
    if st.session_state.no_fit_reasons:
        for process_name, reason in st.session_state.no_fit_reasons:
            st.markdown(f"**{process_name}** : {reason}")
    else:
        st.caption("Aucun processus sans cas d'usage.")

    st.subheader("Cas exclus (interdits au titre de l'AI Act)")
    if excluded:
        for use_case in excluded:
            st.markdown(
                f"**{use_case.process_name}** ({use_case.type.value}) : {use_case.description} "
                f"— _interdit, ai_act={use_case.ai_act.value}_"
            )
    else:
        st.caption("Aucun cas exclu.")


def render_ponderation_tab() -> None:
    """Weight sliders (auto-normalized), live ranking, and per-use-case business case."""
    st.header("Pondérations et classement")

    if not st.session_state.use_cases:
        st.info("Chargez ou générez des cas d'usage dans l'onglet «Cas d'usage».")
        return

    st.subheader("Pondérations")
    raw_weights: dict[str, dict[str, float]] = {}
    axis_columns = st.columns(4)
    for column, axis in zip(axis_columns, DEFAULT_WEIGHTS):
        with column:
            st.markdown(f"**{AXIS_LABELS[axis]}**")
            raw_weights[axis] = {
                sub_key: st.slider(
                    SUB_WEIGHT_LABELS[axis][sub_key],
                    0.0,
                    1.0,
                    default_value,
                    key=f"weight_{axis}_{sub_key}",
                )
                for sub_key, default_value in DEFAULT_WEIGHTS[axis].items()
            }

    normalized_weights = normalize_weights(raw_weights)
    st.markdown("**Pondérations effectives (normalisées à 1)**")
    for axis, sub_weights in normalized_weights.items():
        details = ", ".join(f"{SUB_WEIGHT_LABELS[axis][key]}={value:.2f}" for key, value in sub_weights.items())
        st.caption(f"{AXIS_LABELS[axis]} : {details}")

    try:
        validate_weights(normalized_weights)
    except ValueError as exc:
        st.error(f"Pondérations invalides : {exc}")
        return

    processes_by_name = {process.name: process for process in st.session_state.processes}
    try:
        scored, _ = score_use_cases(
            st.session_state.use_cases,
            processes_by_name,
            st.session_state.company.hourly_cost_eur,
            normalized_weights,
        )
    except ValueError as exc:
        st.error(f"Erreur de classement : {exc}")
        return

    if not scored:
        st.info("Aucun cas d'usage classable (vérifiez les processus chargés).")
        return

    st.subheader("Classement")
    ranking_rows = [
        {
            "Rang": item.rank,
            "Processus": item.use_case.process_name,
            "Cas d'usage": item.use_case.description,
            "Valeur": item.scores.value,
            "Faisabilité": item.scores.feasibility,
            "Risque": item.scores.risk,
            "Priorité": item.scores.priority,
            "Gain annuel (€)": round(item.annual_gain_eur),
        }
        for item in scored
    ]
    st.dataframe(pd.DataFrame(ranking_rows), width="stretch")

    st.subheader("Business case détaillé")
    options = {
        f"{item.rank}. {item.use_case.process_name} — {item.use_case.description[:60]}...": item
        for item in scored
    }
    selected_label = st.selectbox("Choisir un cas d'usage", list(options.keys()))
    selected_item = options[selected_label]
    process = processes_by_name[selected_item.use_case.process_name]

    cases = compute_business_cases(
        selected_item.use_case, process, st.session_state.company.hourly_cost_eur, st.session_state.assumptions
    )

    scenario_columns = st.columns(3)
    for column, scenario in zip(scenario_columns, ("pessimistic", "base", "optimistic")):
        case = cases[scenario]
        payback = f"{case.payback_months:.1f} mois" if case.payback_months is not None else "jamais remboursé"
        with column:
            st.markdown(f"**{SCENARIO_LABELS[scenario]}**")
            st.metric("Gain annuel", f"{case.annual_gain_eur:,.0f} €")
            st.metric("Coût initial", f"{case.one_off_cost_eur:,.0f} €")
            st.metric("Coût annuel", f"{case.annual_run_cost_eur:,.0f} €")
            st.metric("TCO", f"{case.tco_eur:,.0f} €")
            st.metric("ROI", f"{case.roi:.1%}")
            st.metric("Retour sur investissement", payback)


def main() -> None:
    st.set_page_config(page_title="AI Opportunity Assessment", layout="wide")
    st.title("AI Opportunity Assessment")

    _init_session_state()

    tab_contexte, tab_processus, tab_cas_usage, tab_ponderation = st.tabs(
        ["Contexte", "Processus", "Cas d'usage", "Pondérations & classement"]
    )

    with tab_contexte:
        render_contexte_tab()
    with tab_processus:
        render_processus_tab()
    with tab_cas_usage:
        render_cas_usage_tab()
    with tab_ponderation:
        render_ponderation_tab()


main()
