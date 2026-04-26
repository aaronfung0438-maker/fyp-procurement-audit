"""Procurement-audit experiment — Streamlit entry point.

State machine:
    LANDING -> BRIEFING -> BACKGROUND -> PRACTICE -> EXPERIMENT
            -> TRUST_SURVEY (G2/G3 only) -> THANKS

Routing is handled exclusively through ``st.session_state['stage']`` so
that browser back / sidebar navigation cannot bypass the controlled
flow. Each stage corresponds to one render function below.

This file currently implements LANDING + BRIEFING fully (M0+M1) and
stubs out PRACTICE / EXPERIMENT / SURVEY (M2-M5) so the skeleton can be
exercised end-to-end before the real question screens land.
"""

from __future__ import annotations

import re
from pathlib import Path

import streamlit as st

from data_loader import load_frozen_bundle, truth_lookup
from sheets_backend import SheetsClient, from_streamlit_secrets

APP_DIR = Path(__file__).resolve().parent

STAGES = [
    "LANDING",
    "BRIEFING",
    "BACKGROUND",
    "PRACTICE",
    "EXPERIMENT",
    "TRUST_SURVEY",
    "THANKS",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalise_name(raw: str) -> str:
    """Lowercase, strip, and collapse internal whitespace."""
    return re.sub(r"\s+", " ", raw.strip().lower())


@st.cache_resource(show_spinner=False)
def _bundle():
    return load_frozen_bundle()


@st.cache_resource(show_spinner=False)
def _sheets() -> SheetsClient:
    return from_streamlit_secrets(st.secrets)


def _load_briefing(name: str) -> str:
    return (APP_DIR / name).read_text(encoding="utf-8")


def _ensure_state() -> None:
    defaults = {
        "stage": "LANDING",
        "participant_id": None,
        "group": None,
        "slot_idx": None,
        "background": None,
        "practice_idx": 0,
        "experiment_idx": 0,
        "experiment_order": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _go(stage: str) -> None:
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage}")
    st.session_state["stage"] = stage
    st.rerun()


# ---------------------------------------------------------------------------
# Stage renderers
# ---------------------------------------------------------------------------


def render_landing() -> None:
    st.title("Procurement Audit Study")
    st.write(
        "Welcome. Before you start, please enter the name you registered "
        "with for this study. Spelling doesn't matter — capitalisation "
        "and extra spaces are normalised automatically."
    )

    with st.form("landing_form", clear_on_submit=False):
        raw = st.text_input("Your name", key="landing_name_input")
        consent = st.checkbox(
            "I have been told this study takes 35–45 minutes and I am "
            "ready to start now without interruption.",
            key="landing_consent",
        )
        submitted = st.form_submit_button("Begin")

    if not submitted:
        return

    pid = normalise_name(raw)
    if not pid:
        st.error("Please enter a name.")
        return
    if not consent:
        st.error("Please confirm you are ready to start.")
        return

    sheets = _sheets()
    existing = sheets.lookup_existing_assignment(pid)
    if existing is not None:
        slot_idx, group = existing
        st.info(
            f"Welcome back, **{pid}**. You are already registered as "
            f"slot {slot_idx} ({group})."
        )
    else:
        slot_idx, group = sheets.claim_next_slot(pid)
        st.success(
            f"Registered as slot {slot_idx} → group **{group}**."
        )

    st.session_state["participant_id"] = pid
    st.session_state["slot_idx"] = slot_idx
    st.session_state["group"] = group
    _go("BRIEFING")


def render_briefing() -> None:
    group = st.session_state["group"]
    common = _load_briefing("briefing_common.md")
    group_specific = _load_briefing(f"briefing_{group.lower()}.md")

    st.markdown(common)
    st.markdown("---")
    st.markdown(group_specific)

    if st.button("Continue", type="primary", key="briefing_continue"):
        _go("BACKGROUND")


def render_background() -> None:
    st.header("Background — 3 short questions")
    st.write(
        "Your answers are anonymised and used only to describe the "
        "participant pool in aggregate."
    )
    with st.form("background_form"):
        year = st.selectbox(
            "Year of study",
            ["Year 1", "Year 2", "Year 3", "Year 4", "PG / Other"],
            key="bg_year",
        )
        major = st.text_input(
            "Major / Programme",
            key="bg_major",
            placeholder="e.g. IELM, BBA, COMP",
        )
        proc_exp = st.radio(
            "Have you done procurement / auditing work before?",
            ["No", "Yes — internship / part-time", "Yes — full-time"],
            key="bg_proc_exp",
        )
        submitted = st.form_submit_button("Continue")
    if submitted:
        st.session_state["background"] = {
            "year": year,
            "major": major.strip(),
            "proc_exp": proc_exp,
        }
        _go("PRACTICE")


def render_practice_stub() -> None:
    st.header("Practice (stub — M3)")
    st.info(
        "Practice screen will load 2 questions from "
        f"`practice_2qs_{_bundle().timestamp}.xlsx` with feedback."
    )
    bundle = _bundle()
    pra_truth = truth_lookup(bundle.practice_key_df)
    st.write(f"Practice POs and truth: {pra_truth}")
    if st.button("Skip practice (stub) → Experiment", key="practice_skip"):
        _go("EXPERIMENT")


def render_experiment_stub() -> None:
    st.header("Experiment (stub — M4)")
    st.info(
        "Experiment screen will iterate the 32 questions in a "
        "participant-specific shuffled order. Group decides whether "
        "G2 verdict / G3 noteworthy_features panel is shown."
    )
    bundle = _bundle()
    st.write(f"Loaded {len(bundle.experiment_df)} experiment questions.")
    st.write(f"Bundle timestamp: `{bundle.timestamp}`")
    if st.button("Skip experiment (stub) → Survey", key="exp_skip"):
        if st.session_state["group"] == "G1":
            _go("THANKS")
        else:
            _go("TRUST_SURVEY")


def render_trust_survey_stub() -> None:
    st.header("Trust Survey (stub — M5)")
    st.info(
        "5 Likert questions adapted from Jian, Bisantz & Drury (2000). "
        "G1 skips this stage entirely."
    )
    if st.button("Skip survey (stub) → Done", key="survey_skip"):
        _go("THANKS")


def render_thanks() -> None:
    st.balloons()
    st.title("Thank you!")
    st.write(
        "Your responses have been recorded. You may close this tab."
    )
    st.write(
        f"Participant: `{st.session_state['participant_id']}` · "
        f"Group: `{st.session_state['group']}` · "
        f"Slot: `{st.session_state['slot_idx']}`"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="Procurement Audit Study",
        page_icon="📋",
        layout="wide",
    )
    _ensure_state()

    stage = st.session_state["stage"]
    renderers = {
        "LANDING": render_landing,
        "BRIEFING": render_briefing,
        "BACKGROUND": render_background,
        "PRACTICE": render_practice_stub,
        "EXPERIMENT": render_experiment_stub,
        "TRUST_SURVEY": render_trust_survey_stub,
        "THANKS": render_thanks,
    }
    renderers[stage]()


if __name__ == "__main__":
    main()
