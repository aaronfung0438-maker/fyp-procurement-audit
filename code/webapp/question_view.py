"""Reusable per-order rendering helpers.

A single PO is presented as three sections (A / B / E) plus an optional
group-specific AI panel (G2 verdict / G3 noteworthy-features table).
Logic that is identical for the practice and experiment screens lives
here; the calling page is only responsible for the surrounding form
(judgment, confidence, rationale).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Section A / B / E
# ---------------------------------------------------------------------------


def render_section_a(row: pd.Series) -> None:
    """Section A — order details (deterministic facts)."""
    st.markdown("##### Section A — Order Details")
    cols = st.columns(2)
    left = {
        "PO ID": row["po_id"],
        "Item": f"{row['item_category']} · {row['item_sku']}",
        "Description": row["item_description"],
        "Quantity": int(row["quantity"]),
        "Unit price (USD)": f"${row['unit_price_usd']:.4f}",
        "Total amount (USD)": f"${row['total_amount_usd']:,.2f}",
    }
    right = {
        "Requester": row["requester_id"],
        "Approver": row["approver_id"],
        "Supplier": row["supplier_id"],
        "Created date": str(row["created_date"])[:10],
        "Approval lag (days)": f"{row['approval_lag_days']:.2f}",
        "Lead time (days)": int(row["expected_delivery_lag_days"]),
    }
    with cols[0]:
        for k, v in left.items():
            st.markdown(f"**{k}:** {v}")
    with cols[1]:
        for k, v in right.items():
            st.markdown(f"**{k}:** {v}")


def render_section_b(row: pd.Series) -> None:
    """Section B — free-text notes."""
    st.markdown("##### Section B — Free-text Notes")
    st.markdown(f"**Purchase note:** {row['purchase_note_human']}")
    st.markdown(f"**Supplier profile:** {row['supplier_profile_human']}")


def render_section_e(row: pd.Series) -> None:
    """Section E — deviation sentences computed from historical medians.

    Phrasing is kept neutral (no "suspicious" / "warning" wording);
    directional words like ``× the median`` and ``z = +0.7`` are an
    acknowledged limitation (methodology §15.9).
    """
    st.markdown("##### Section E — Deviation Sentences")

    sentences: list[str] = []

    sentences.append(
        f"- **Unit price:** ${row['unit_price_usd']:.4f} "
        f"(SKU historical median ${row['expected_unit_price_usd']:.4f}; "
        f"ratio = {row['unit_price_ratio']:.2f}×)"
    )

    sentences.append(
        f"- **Quantity:** {int(row['quantity'])} units "
        f"(SKU historical median {int(row['expected_quantity'])}; "
        f"ratio = {row['quantity_ratio']:.2f}×)"
    )

    sentences.append(
        f"- **Lead time:** {int(row['expected_delivery_lag_days'])} days "
        f"(typical mean {int(row['expected_delivery_lag_mean'])} ± "
        f"{int(row['expected_delivery_lag_sigma'])} days; "
        f"z = {row['delivery_lag_z']:+.2f})"
    )

    sentences.append(
        f"- **Approval lag:** {row['approval_lag_days']:.2f} days "
        f"(z = {row['approval_lag_z']:+.2f} relative to this approver's "
        f"typical pattern; log-z = {row['approval_lag_z_log']:+.2f})"
    )

    gap = float(row["total_vs_approval_gap"])
    sentences.append(
        f"- **Threshold gap:** total ${row['total_amount_usd']:,.2f}, "
        f"distance to nearest approval threshold = ${gap:+,.2f} "
        f"(negative = below the threshold)"
    )

    st.markdown("\n".join(sentences))


# ---------------------------------------------------------------------------
# Group-specific AI panels
# ---------------------------------------------------------------------------


def render_g2_panel(verdict: dict[str, Any] | None) -> None:
    """G2 — single-line AI verdict + reason."""
    st.markdown("##### AI Verdict (Group 2)")
    if not verdict:
        st.warning("No AI verdict available for this order.")
        return
    judgment = str(verdict.get("judgment", "")).strip().lower()
    reason = verdict.get("reason", "")
    if judgment == "suspicious":
        st.error(f"**Suspicious** — {reason}")
    elif judgment == "normal":
        st.success(f"**Normal** — {reason}")
    else:
        st.info(f"**{judgment or '(unknown)'}** — {reason}")


def render_g3_panel(evidence: dict[str, Any] | None) -> None:
    """G3 — 4-row noteworthy-features table."""
    st.markdown("##### AI Noteworthy Features (Group 3)")
    if not evidence or not evidence.get("noteworthy_features"):
        st.warning("No AI evidence available for this order.")
        return
    rows = evidence["noteworthy_features"]
    df = pd.DataFrame(
        [
            {
                "Feature": r.get("feature", ""),
                "Current value": r.get("current_value", ""),
                "Reference value": r.get("reference_value", ""),
                "Why noteworthy": r.get("why_noteworthy", ""),
            }
            for r in rows
        ]
    )
    st.dataframe(df, hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# Convenience: render a whole order screen by group
# ---------------------------------------------------------------------------


def render_order(
    row: pd.Series,
    group: str,
    g2_lookup: dict[str, dict[str, Any]],
    g3_lookup: dict[str, dict[str, Any]],
) -> None:
    """Render one full order screen, group-conditional AI panel included.

    All three groups see Section A/B/E. Only G2 sees the verdict panel;
    only G3 sees the noteworthy-features table.
    """
    render_section_a(row)
    st.markdown("---")
    render_section_b(row)
    st.markdown("---")
    render_section_e(row)

    if group == "G2":
        st.markdown("---")
        render_g2_panel(g2_lookup.get(row["po_id"]))
    elif group == "G3":
        st.markdown("---")
        render_g3_panel(g3_lookup.get(row["po_id"]))
