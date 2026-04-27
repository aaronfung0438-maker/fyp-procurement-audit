"""Post-experiment trust survey (5 items, G2 / G3 only).

Items adapted from Jian, Bisantz & Drury (2000) "Checklist for Trust
between People and Automation". See methodology §3.4 for construct
mapping and rationale for the 5-item simplification.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrustItem:
    item_id: str
    text: str
    construct: str


TRUST_ITEMS: list[TrustItem] = [
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

LIKERT_LABELS = [
    "1 — Strongly disagree",
    "2",
    "3",
    "4 — Neutral",
    "5",
    "6",
    "7 — Strongly agree",
]
