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


def _g(row: pd.Series, key: str, default: Any = "—") -> Any:
    """Safe getter — returns default if key missing or value is NaN."""
    if key not in row.index:
        return default
    val = row[key]
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    return val


def po_id_str(row: pd.Series) -> str:
    """Return stripped po_id, or empty string if missing/invalid (for lookups / logging)."""
    v = _g(row, "po_id", "")
    if v in ("", "—", None):
        return ""
    s = str(v).strip()
    if s.lower() in ("nan", "none", ""):
        return ""
    return s


def render_section_a(row: pd.Series) -> None:
    """Section A — order details (deterministic facts)."""
    st.markdown("##### Section A — Order Details")

    cat = _g(row, "item_category")
    sku = _g(row, "item_sku")
    item_str = f"{cat} · {sku}" if cat != "—" or sku != "—" else "—"

    cols = st.columns(2)
    left = {
        "PO ID": _g(row, "po_id"),
        "Item": item_str,
        "Description": _g(row, "item_description"),
        "Quantity": int(_g(row, "quantity", 0)) if _g(row, "quantity") != "—" else "—",
        "Unit price (USD)": f"${float(_g(row, 'unit_price_usd', 0)):.4f}" if _g(row, "unit_price_usd") != "—" else "—",
        "Total amount (USD)": f"${float(_g(row, 'total_amount_usd', 0)):,.2f}" if _g(row, "total_amount_usd") != "—" else "—",
    }
    right = {
        "Requester": _g(row, "requester_id"),
        "Approver": _g(row, "approver_id"),
        "Supplier": _g(row, "supplier_id"),
        "Created date": str(_g(row, "created_date"))[:10],
        "Approval lag (days)": f"{float(_g(row, 'approval_lag_days', 0)):.2f}" if _g(row, "approval_lag_days") != "—" else "—",
        "Lead time (days)": int(_g(row, "expected_delivery_lag_days", 0)) if _g(row, "expected_delivery_lag_days") != "—" else "—",
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
    st.markdown(f"**Purchase note:** {_g(row, 'purchase_note_human')}")
    st.markdown(f"**Supplier profile:** {_g(row, 'supplier_profile_human')}")


def _f(row: pd.Series, key: str) -> float | None:
    val = _g(row, key, None)
    if val is None or val == "—":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def render_section_e(row: pd.Series) -> None:
    """Section E — deviation sentences computed from historical medians.

    Phrasing is kept neutral (no "suspicious" / "warning" wording);
    directional words like ``× the median`` and ``z = +0.7`` are an
    acknowledged limitation (methodology §15.9).
    """
    st.markdown("##### Section E — Deviation Sentences")

    sentences: list[str] = []

    up = _f(row, "unit_price_usd")
    upe = _f(row, "expected_unit_price_usd")
    upr = _f(row, "unit_price_ratio")
    if up is not None and upe is not None and upr is not None:
        sentences.append(
            f"- **Unit price:** ${up:.4f} (SKU historical median ${upe:.4f}; "
            f"ratio = {upr:.2f}×)"
        )

    qty = _f(row, "quantity")
    qtye = _f(row, "expected_quantity")
    qtyr = _f(row, "quantity_ratio")
    if qty is not None and qtye is not None and qtyr is not None:
        sentences.append(
            f"- **Quantity:** {int(qty)} units (SKU historical median {int(qtye)}; "
            f"ratio = {qtyr:.2f}×)"
        )

    lead = _f(row, "expected_delivery_lag_days")
    lm = _f(row, "expected_delivery_lag_mean")
    ls = _f(row, "expected_delivery_lag_sigma")
    lz = _f(row, "delivery_lag_z")
    if lead is not None and lm is not None and ls is not None and lz is not None:
        sentences.append(
            f"- **Lead time:** {int(lead)} days (typical mean {int(lm)} ± "
            f"{int(ls)} days; z = {lz:+.2f})"
        )

    al = _f(row, "approval_lag_days")
    az = _f(row, "approval_lag_z")
    azl = _f(row, "approval_lag_z_log")
    if al is not None and az is not None and azl is not None:
        sentences.append(
            f"- **Approval lag:** {al:.2f} days (z = {az:+.2f} relative to this "
            f"approver's typical pattern; log-z = {azl:+.2f})"
        )

    total = _f(row, "total_amount_usd")
    gap = _f(row, "total_vs_approval_gap")
    if total is not None and gap is not None:
        sentences.append(
            f"- **Threshold gap:** total ${total:,.2f}, distance to nearest "
            f"approval threshold = ${gap:+,.2f} (negative = below the threshold)"
        )

    if not sentences:
        st.warning("Section E features unavailable for this order.")
    else:
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
    pid = po_id_str(row)
    if not pid:
        st.error("This order row is missing a valid **po_id**; cannot display.")
        return

    render_section_a(row)
    st.markdown("---")
    render_section_b(row)
    st.markdown("---")
    render_section_e(row)

    if group == "G2":
        st.markdown("---")
        render_g2_panel(g2_lookup.get(pid))
    elif group == "G3":
        st.markdown("---")
        render_g3_panel(g3_lookup.get(pid))
