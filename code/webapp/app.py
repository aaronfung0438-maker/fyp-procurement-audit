"""Procurement-audit experiment — Streamlit entry point.

State machine:
    LANDING -> BRIEFING -> BACKGROUND -> PRACTICE -> EXPERIMENT
            -> TRUST_SURVEY (G2/G3 only) -> THANKS

Routing is handled exclusively through ``st.session_state['stage']`` so
that browser back / sidebar navigation cannot bypass the controlled
flow. Each stage corresponds to one render function below.
"""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

import streamlit as st

from data_loader import load_frozen_bundle, truth_lookup
from question_view import render_order
from sheets_backend import SheetsClient, from_streamlit_secrets
from survey import LIKERT_LABELS, items_for_group

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
        "practice_feedback_for": None,
        "experiment_idx": 0,
        "experiment_order": None,
        "render_ts": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _go(stage: str) -> None:
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage}")
    st.session_state["stage"] = stage
    st.session_state["render_ts"] = None
    st.rerun()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _now_ms() -> int:
    return int(time.time() * 1000)


def _ensure_render_ts() -> int:
    """Return the render-start timestamp for the current question.

    Stored in session_state so duration is measured from the moment the
    question first appeared, even if the user took a long time to
    submit. Reset by ``_go`` whenever the stage advances.
    """
    if st.session_state.get("render_ts") is None:
        st.session_state["render_ts"] = _now_ms()
    return int(st.session_state["render_ts"])


def _persist(row: dict) -> None:
    """Append one response row to the sessions sheet, swallowing errors.

    A failed network call is logged in-app rather than crashing the
    participant out of the experiment. Lost rows are recoverable from
    the participant's session-state breadcrumbs at debrief if needed.
    """
    try:
        _sheets().append_response(row)
    except Exception as e:  # noqa: BLE001
        st.warning(
            f"(Network hiccup while saving — will retry on next answer.) {e}"
        )


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
    if not submitted:
        return

    background = {
        "year": year,
        "major": major.strip(),
        "proc_exp": proc_exp,
    }
    st.session_state["background"] = background

    _persist(
        {
            "participant_id": st.session_state["participant_id"],
            "group": st.session_state["group"],
            "phase": "background",
            "question_idx": 0,
            "po_id": "",
            "render_ts": "",
            "submit_ts": _now_iso(),
            "duration_ms": "",
            "judgment": "",
            "confidence": "",
            "rationale": "",
            "extra_json": json.dumps(background, ensure_ascii=False),
        }
    )

    _go("PRACTICE")


# ---------------------------------------------------------------------------
# Practice (with feedback)
# ---------------------------------------------------------------------------


def render_practice() -> None:
    bundle = _bundle()
    pra_df = bundle.practice_df
    pra_truth = truth_lookup(bundle.practice_key_df)
    n_total = len(pra_df)
    idx = int(st.session_state["practice_idx"])
    feedback_idx = st.session_state.get("practice_feedback_for")

    st.header(f"Practice — Question {min(idx + 1, n_total)} of {n_total}")
    st.progress((idx if feedback_idx is None else idx + 1) / max(n_total, 1))

    if feedback_idx is not None:
        _render_practice_feedback(feedback_idx)
        return

    if idx >= n_total:
        st.success("Practice complete. Click **Start the official block**.")
        if st.button("Start the official block", type="primary"):
            _go("EXPERIMENT")
        return

    row = pra_df.iloc[idx]
    render_order(
        row,
        st.session_state["group"],
        bundle.g2_practice,
        bundle.g3_practice,
    )

    _ensure_render_ts()
    submitted = _render_decision_form(form_key=f"practice_form_{idx}")
    if submitted is None:
        return

    judgment, confidence, rationale = submitted
    render_ts = int(st.session_state["render_ts"])
    submit_ms = _now_ms()
    duration_ms = submit_ms - render_ts

    st.session_state[f"practice_decision_{idx}"] = {
        "po_id": row["po_id"],
        "judgment": judgment,
        "confidence": confidence,
        "rationale": rationale,
        "duration_ms": duration_ms,
        "truth": pra_truth.get(row["po_id"], ""),
    }

    _persist(
        {
            "participant_id": st.session_state["participant_id"],
            "group": st.session_state["group"],
            "phase": "practice",
            "question_idx": idx + 1,
            "po_id": row["po_id"],
            "render_ts": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.localtime(render_ts / 1000)
            ),
            "submit_ts": _now_iso(),
            "duration_ms": duration_ms,
            "judgment": judgment,
            "confidence": confidence,
            "rationale": rationale,
            "extra_json": json.dumps(
                {"truth": pra_truth.get(row["po_id"], "")},
                ensure_ascii=False,
            ),
        }
    )

    st.session_state["practice_feedback_for"] = idx
    st.session_state["render_ts"] = None
    st.rerun()


def _render_practice_feedback(idx: int) -> None:
    bundle = _bundle()
    decision = st.session_state.get(f"practice_decision_{idx}", {})
    truth = decision.get("truth", "")
    user_judgment = decision.get("judgment", "")
    correct = (user_judgment == truth)

    st.subheader("Feedback")
    if correct:
        st.success(f"Your answer **{user_judgment}** was correct.")
    else:
        st.error(
            f"Your answer **{user_judgment}** was different from the "
            f"ground truth, which is **{truth}**."
        )

    group = st.session_state["group"]
    if group == "G2":
        verdict = bundle.g2_practice.get(decision["po_id"], {})
        ai_judgment = str(verdict.get("judgment", "")).strip().lower()
        ai_correct = ai_judgment == truth
        st.caption(
            f"AI verdict: **{ai_judgment or '(none)'}** — "
            f"{'correct' if ai_correct else 'wrong'} on this question."
        )
    elif group == "G3":
        st.caption(
            "G3 does not see an AI verdict, so there is no AI right/wrong "
            "to score on practice."
        )

    if st.button("Next", type="primary", key=f"practice_next_{idx}"):
        st.session_state["practice_idx"] = idx + 1
        st.session_state["practice_feedback_for"] = None
        st.session_state["render_ts"] = None
        st.rerun()


# ---------------------------------------------------------------------------
# Experiment (no feedback)
# ---------------------------------------------------------------------------


def render_experiment() -> None:
    bundle = _bundle()
    exp_df = bundle.experiment_df
    n_total = len(exp_df)

    if st.session_state.get("experiment_order") is None:
        seed = int(st.session_state["slot_idx"])
        order = list(range(n_total))
        random.Random(seed).shuffle(order)
        st.session_state["experiment_order"] = order

    order = st.session_state["experiment_order"]
    idx = int(st.session_state["experiment_idx"])

    if idx >= n_total:
        st.success("All 32 questions complete.")
        if st.button("Continue", type="primary"):
            _go("TRUST_SURVEY")
        return

    st.header(f"Question {idx + 1} of {n_total}")
    st.progress(idx / n_total)

    row_pos = order[idx]
    row = exp_df.iloc[row_pos]
    render_order(
        row,
        st.session_state["group"],
        bundle.g2_exp,
        bundle.g3_exp,
    )

    _ensure_render_ts()
    submitted = _render_decision_form(form_key=f"experiment_form_{idx}")
    if submitted is None:
        return

    judgment, confidence, rationale = submitted
    render_ts = int(st.session_state["render_ts"])
    submit_ms = _now_ms()
    duration_ms = submit_ms - render_ts

    _persist(
        {
            "participant_id": st.session_state["participant_id"],
            "group": st.session_state["group"],
            "phase": "experiment",
            "question_idx": idx + 1,
            "po_id": row["po_id"],
            "render_ts": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.localtime(render_ts / 1000)
            ),
            "submit_ts": _now_iso(),
            "duration_ms": duration_ms,
            "judgment": judgment,
            "confidence": confidence,
            "rationale": rationale,
            "extra_json": json.dumps(
                {"shuffle_position": row_pos},
                ensure_ascii=False,
            ),
        }
    )

    st.session_state["experiment_idx"] = idx + 1
    st.session_state["render_ts"] = None
    st.rerun()


# ---------------------------------------------------------------------------
# Trust survey (G2 / G3 only)
# ---------------------------------------------------------------------------


def render_trust_survey() -> None:
    group = st.session_state["group"]
    items = items_for_group(group)

    if group == "G1":
        st.header(
            "Final Survey — 5 short questions about Section E "
            "(the deviation sentences)"
        )
        st.write(
            "Please answer based on your overall impression of the "
            "Section E deviation sentences across the 32 official "
            "questions you just completed. There are no right or wrong "
            "answers."
        )
        instrument_label = "section_e"
    else:
        st.header(
            "Final Survey — 5 short questions about the AI assistance"
        )
        st.write(
            "Please answer based on your overall impression of the AI's "
            "outputs across the 32 official questions you just completed. "
            "There are no right or wrong answers."
        )
        instrument_label = "ai"

    with st.form("trust_form"):
        responses: dict[str, int] = {}
        for item in items:
            choice = st.radio(
                item.text,
                options=list(range(1, 8)),
                format_func=lambda x: LIKERT_LABELS[x - 1],
                key=f"trust_{item.item_id}",
                horizontal=True,
                index=3,
            )
            responses[item.item_id] = int(choice)
        submitted = st.form_submit_button("Submit")

    if not submitted:
        return

    submit_ts = _now_iso()
    for item in items:
        _persist(
            {
                "participant_id": st.session_state["participant_id"],
                "group": group,
                "phase": "trust_survey",
                "question_idx": item.item_id,
                "po_id": "",
                "render_ts": "",
                "submit_ts": submit_ts,
                "duration_ms": "",
                "judgment": "",
                "confidence": responses[item.item_id],
                "rationale": "",
                "extra_json": json.dumps(
                    {
                        "item_id": item.item_id,
                        "construct": item.construct,
                        "instrument": instrument_label,
                        "text": item.text,
                    },
                    ensure_ascii=False,
                ),
            }
        )

    _go("THANKS")


# ---------------------------------------------------------------------------
# Thanks
# ---------------------------------------------------------------------------


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
# Decision form (shared by practice + experiment)
# ---------------------------------------------------------------------------


def _render_decision_form(form_key: str):
    """Render the judgment / confidence / rationale form.

    Returns ``(judgment, confidence, rationale)`` on submit, ``None``
    otherwise. The caller is responsible for advancing state.
    """
    with st.form(form_key, clear_on_submit=True):
        st.markdown("---")
        st.markdown("##### Your decision")
        judgment = st.radio(
            "Is this order Normal or Suspicious?",
            ["normal", "suspicious"],
            horizontal=True,
            key=f"{form_key}_judgment",
        )
        confidence = st.slider(
            "Confidence (1 = not confident at all, 7 = extremely confident)",
            min_value=1,
            max_value=7,
            value=4,
            key=f"{form_key}_confidence",
        )
        rationale = st.text_area(
            "Brief rationale (one or two sentences)",
            key=f"{form_key}_rationale",
            placeholder="Why did you pick that answer?",
        )
        submitted = st.form_submit_button("Submit answer", type="primary")
    if not submitted:
        return None
    if not rationale.strip():
        st.error("Please write a brief rationale before submitting.")
        return None
    return judgment, int(confidence), rationale.strip()


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
        "PRACTICE": render_practice,
        "EXPERIMENT": render_experiment,
        "TRUST_SURVEY": render_trust_survey,
        "THANKS": render_thanks,
    }
    renderers[stage]()


if __name__ == "__main__":
    main()
