"""Post-experiment trust survey (5 items per group).

Items adapted from Jian, Bisantz & Drury (2000) "Checklist for Trust
between People and Automation". See methodology §3.4 for construct
mapping and rationale for the 5-item simplification.

Two parallel instruments are defined so that all three groups answer
the same five constructs:

* ``TRUST_ITEMS_AI``     — used by G2 and G3; subject of each item is
  the AI system that participants saw.
* ``TRUST_ITEMS_SECTION_E`` — used by G1; subject of each item is the
  Section E deviation sentences (G1's analogous information source).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrustItem:
    item_id: str
    text: str
    construct: str


TRUST_ITEMS_AI: list[TrustItem] = [
    TrustItem(
        item_id="Q1",
        text="I can trust the information provided by the AI system.",
        construct="trust_reliability",
    ),
    TrustItem(
        item_id="Q2",
        text=(
            "The AI system's output is dependable enough for me to rely on "
            "when making my decision."
        ),
        construct="trust_dependability",
    ),
    TrustItem(
        item_id="Q3",
        text=(
            "The information the AI presented made it clear to me why this "
            "order was noteworthy."
        ),
        construct="clarity_explanation_quality",
    ),
    TrustItem(
        item_id="Q4",
        text="The AI provided substantive help to my final judgment.",
        construct="perceived_usefulness",
    ),
    TrustItem(
        item_id="Q5",
        text=(
            "After seeing the AI's output, I still feel I made the final "
            "decision myself rather than simply following the AI."
        ),
        construct="autonomy_automation_bias_awareness",
    ),
]

TRUST_ITEMS_SECTION_E: list[TrustItem] = [
    TrustItem(
        item_id="Q1",
        text=(
            "I can trust the information shown in Section E "
            "(the deviation sentences)."
        ),
        construct="trust_reliability",
    ),
    TrustItem(
        item_id="Q2",
        text=(
            "The Section E deviation sentences were dependable enough for "
            "me to rely on when making my decision."
        ),
        construct="trust_dependability",
    ),
    TrustItem(
        item_id="Q3",
        text=(
            "The Section E deviation sentences made it clear to me why "
            "an order might be noteworthy."
        ),
        construct="clarity_explanation_quality",
    ),
    TrustItem(
        item_id="Q4",
        text=(
            "Section E provided substantive help to my final judgment."
        ),
        construct="perceived_usefulness",
    ),
    TrustItem(
        item_id="Q5",
        text=(
            "I made the final decision myself based on my own analysis, "
            "rather than simply following whatever Section E suggested."
        ),
        construct="autonomy_automation_bias_awareness",
    ),
]


def items_for_group(group: str) -> list[TrustItem]:
    """Return the 5-item instrument appropriate for the participant's group."""
    if group == "G1":
        return TRUST_ITEMS_SECTION_E
    return TRUST_ITEMS_AI


LIKERT_LABELS = [
    "1 — Strongly disagree",
    "2",
    "3",
    "4 — Neutral",
    "5",
    "6",
    "7 — Strongly agree",
]
