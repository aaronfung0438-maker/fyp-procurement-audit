#!/usr/bin/env python3
"""
Stage 3 — prepare experiment artefacts (32 questions, A/B/C stratification).

Pipeline
--------
1. Load Stage-1 (`dataset_*.xlsx`, sheets: components, suppliers) and Stage-2
   (`orders_stage2_semantics.xlsx`) outputs.

2. Compute Section E deviation features (8+ columns) per order.
     - Visible to all human groups (G1/G2/G3) as participant reference.
     - STRIPPED from RAG corpus and LLM prompt context.
     - Stage 4 will translate them into natural-language sentences for the UI.

3. Fit a dual-track Mahalanobis detector on normal orders only:
     (a) Linear D² on the raw 4-D vector
         [unit_price_usd, quantity, approval_lag_days, expected_delivery_lag_days]
     (b) Log    D² on log(.) of the same vector — captures multiplicative
         outliers (e.g. approval_bypass Variant B with lag = 0.05d) that
         linear D² under-weights.
   Plus a complementary `policy_violation` rule flag for categorical breaches
   (missing approver, skip-tier approval).

4. Stratified sampling for 32 experiment questions:

     A    10  normal_obvious                 — clearly normal
     B     8  anomaly_<class>                — one per class, highest signal
     C1    6  edge_normal_high_D2            — normal but D² in [85, 95] pct
                                                 and below χ²(4, 0.99) = 13.28
     C2a   3  edge_anomaly_low_D2_numeric    — item_spending, border_value,
                                                 approval_bypass (Variant B)
     C2b   5  edge_anomaly_low_D2_text       — bank_account_change,
                                                 unusual_vendor, vendor_spending,
                                                 quote_manipulation,
                                                 conflict_of_interest

5. Auto-generate an English `reason` column per experiment row using
   per-stratum templates filled with the row's actual numbers.

6. Pick a 2-question practice batch (1 obvious normal + 1 obvious anomaly).
   Practice questions are excluded from BOTH the experiment set AND the
   RAG corpus.

7. Write artefacts (under data/stage3/):

     stage3_full_with_truth_<TS>.xlsx    500 rows, full truth + dual D² +
                                         policy_violation + reason +
                                         experiment / practice markers
                                         (researcher master file)
     experiment_32qs_<TS>.xlsx           32 rows, UI-safe (truth + detector
                                         signals stripped; Section E retained
                                         as participant reference)
     experiment_32qs_<TS>_KEY.xlsx       po_id ↔ stratum ↔ class ↔ truth ↔
                                         reason (for offline scoring)
     practice_2qs_<TS>.xlsx              2 rows, UI-safe
     practice_2qs_<TS>_KEY.xlsx          po_id ↔ practice_role ↔ truth ↔
                                         reason
     rag_corpus_466_<TS>.jsonl           500 − 32 − 2 = 466 holdout orders,
                                         fully sanitised (no truth, no
                                         detector, no Section E)

Truth definition
----------------
`injection_plan` from Stage 1 is the ONLY ground truth.
Mahalanobis (linear + log) and `policy_violation` are RESEARCHER analytical
instruments, used solely for (a) sample selection in this script and (b) the
Chapter-4 Statistical Baseline detector. They are NEVER shown to G1/G2/G3
participants via the UI.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import chi2


# ────────────────────────────────────────────────────────────────────────────
# Paths
# ────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR   = SCRIPT_DIR / "data"
STAGE1_DIR = DATA_DIR / "stage1"
STAGE2_DIR = DATA_DIR / "stage2"
STAGE3_DIR = DATA_DIR / "stage3"

RANDOM_SEED = 42


# ────────────────────────────────────────────────────────────────────────────
# Population parameters (kept in sync with generate_dataset.py)
# ────────────────────────────────────────────────────────────────────────────
APPROVAL_LAG_MEAN = 2.0
APPROVAL_LAG_STD  = 1.5

# Firm's published approval thresholds. Approver hierarchy:
#   < $1,000           → A-PROC-01
#   $1,000 – $5,000    → A-CTO
#   > $5,000           → A-CEO
APPROVAL_THRESHOLDS = (1_000.0, 5_000.0)
APPROVER_PROC = "A-PROC-01"
APPROVER_CTO  = "A-CTO"
APPROVER_CEO  = "A-CEO"

# 4-D feature vector for Mahalanobis
FEATS = [
    "unit_price_usd",
    "quantity",
    "approval_lag_days",
    "expected_delivery_lag_days",
]

# χ²(4) critical values for D² under the null
D95 = float(chi2.ppf(0.95, df=4))   # ≈ 9.488
D99 = float(chi2.ppf(0.99, df=4))   # ≈ 13.277


# ────────────────────────────────────────────────────────────────────────────
# Anomaly class taxonomy
# ────────────────────────────────────────────────────────────────────────────
ALL_CLASSES = (
    "item_spending",
    "border_value",
    "approval_bypass",
    "bank_account_change",
    "unusual_vendor",
    "vendor_spending",
    "quote_manipulation",
    "conflict_of_interest",
)

# Classes whose Stage-1 mutation shows up primarily in the 4-D numeric vector
NUMERIC_CLASSES = {
    "item_spending",
    "border_value",
    "approval_bypass",
    "bank_account_change",
}
# Classes whose Stage-1 mutation lives in IDs / Stage-2 text only
TEXT_CLASSES = {
    "unusual_vendor",
    "vendor_spending",
    "quote_manipulation",
    "conflict_of_interest",
}

# Block C2a — subtle numeric anomalies (low D², still injected)
C2A_CLASSES = ("item_spending", "border_value", "approval_bypass")

# Block C2b — subtle text anomalies (low D², text-only signal)
C2B_CLASSES = (
    "bank_account_change",
    "unusual_vendor",
    "vendor_spending",
    "quote_manipulation",
    "conflict_of_interest",
)

# Smoking-gun keywords for text-class signal scoring.
# Heuristic: count how many of these phrases appear in purchase_note +
# supplier_profile (case-insensitive substring match). Higher score = more
# blatant text signal. Used to:
#   • pick the most obvious instance for Block B (text classes)
#   • verify the chosen Block C2b instance still carries some signal
TEXT_SIGNAL_KEYWORDS = {
    "unusual_vendor": [
        "newly established", "newly-onboarded", "newly onboarded",
        "trading company", "no prior", "no track record",
        "first-time", "trading ltd", "little track record",
        "recently incorporated",
    ],
    "vendor_spending": [
        "another order", "third order", "fourth order", "frequent",
        "this quarter", "consecutive", "long-standing",
        "long standing", "preferred supplier", "regular supplier",
    ],
    "quote_manipulation": [
        "single quote", "only one quote", "only quote", "withdrawn",
        "sole quotation", "no other vendors", "no competing",
        "competing quote", "sole bid",
    ],
    "conflict_of_interest": [
        "recommended by r-", "personal acquaintance", "personal link",
        "previously employed", "referred by", "family", "relative",
        "acquaintance", "connection",
    ],
    "bank_account_change": [
        "new account", "updated banking", "updated bank", "wire to",
        "different account", "changed account", "new bank",
        "previous account closed", "banking details",
    ],
}

# ────────────────────────────────────────────────────────────────────────────
# Block sizes — experiment = 32 questions; practice = 2 questions
# ────────────────────────────────────────────────────────────────────────────
N_BLOCK_A   = 10
N_BLOCK_B   = 8
N_BLOCK_C1  = 6
N_BLOCK_C2A = 3
N_BLOCK_C2B = 5
N_TOTAL     = N_BLOCK_A + N_BLOCK_B + N_BLOCK_C1 + N_BLOCK_C2A + N_BLOCK_C2B
assert N_TOTAL == 32

# Practice / onboarding batch — separate from experiment AND from RAG corpus
N_PRACTICE_NORMAL  = 1
N_PRACTICE_ANOMALY = 1
N_PRACTICE         = N_PRACTICE_NORMAL + N_PRACTICE_ANOMALY


# ────────────────────────────────────────────────────────────────────────────
# I/O helpers
# ────────────────────────────────────────────────────────────────────────────
def find_latest_dataset_excel(data_dir: Path) -> Path:
    """Search Stage-1 dataset_*.xlsx; fall back to data/ for backward compat."""
    for d in (STAGE1_DIR, data_dir):
        if not d.exists():
            continue
        cands = sorted(d.glob("dataset_*.xlsx"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if cands:
            return cands[0]
    raise FileNotFoundError(
        f"No dataset_*.xlsx found under {STAGE1_DIR} or {data_dir}. "
        "Run generate_dataset.py first."
    )


def load_inputs(stage2_path: Path, dataset_path: Path):
    orders     = pd.read_excel(stage2_path)
    components = pd.read_excel(dataset_path, sheet_name="components")
    suppliers  = pd.read_excel(dataset_path, sheet_name="suppliers")
    return orders, components, suppliers


# ────────────────────────────────────────────────────────────────────────────
# Section E — deviation features (kept in UI; stripped from RAG/LLM prompts)
# ────────────────────────────────────────────────────────────────────────────
def add_deviation_features(orders: pd.DataFrame,
                           components: pd.DataFrame) -> pd.DataFrame:
    """Attach pre-computed deviation features per order. These are participant
    reference info (humans are not procurement experts), but Stage-4 will
    render them as natural-language sentences before showing them in the UI."""
    comp = components.set_index("sku")
    df = orders.copy()

    # Price deviation
    df["expected_unit_price_usd"] = df["item_sku"].map(comp["price_median_usd"])
    df["unit_price_ratio"]        = df["unit_price_usd"] / df["expected_unit_price_usd"]

    # Quantity deviation
    df["expected_quantity"]       = df["item_sku"].map(comp["qty_median"])
    df["quantity_ratio"]          = df["quantity"] / df["expected_quantity"]

    # Delivery lag deviation (z-score against per-SKU mean / sigma)
    df["expected_delivery_lag_mean"]  = df["item_sku"].map(comp["lead_time_median_days"])
    df["expected_delivery_lag_sigma"] = df["item_sku"].map(comp["lead_time_sigma_days"])
    df["delivery_lag_z"] = (
        (df["expected_delivery_lag_days"] - df["expected_delivery_lag_mean"])
        / df["expected_delivery_lag_sigma"]
    )

    # Approval lag deviation — linear z and log z (the latter catches
    # multiplicative outliers like approval_bypass Variant B with lag=0.05d).
    df["approval_lag_z"] = (
        (df["approval_lag_days"] - APPROVAL_LAG_MEAN) / APPROVAL_LAG_STD
    )
    log_lag_all = np.log(np.maximum(orders["approval_lag_days"].astype(float), 1e-3))
    is_normal   = (orders["injection_plan"] == "none").to_numpy()
    mu_log_lag  = float(log_lag_all[is_normal].mean())
    sd_log_lag  = float(log_lag_all[is_normal].std(ddof=1))
    df["approval_lag_z_log"] = (
        (np.log(np.maximum(df["approval_lag_days"].astype(float), 1e-3)) - mu_log_lag)
        / sd_log_lag
    )

    # Distance to nearest approval threshold (signed; useful for border_value)
    def _gap(total: float) -> float:
        return min((total - th for th in APPROVAL_THRESHOLDS), key=abs)
    df["total_vs_approval_gap"] = df["total_amount_usd"].apply(_gap)

    for col in ("unit_price_ratio", "quantity_ratio",
                "delivery_lag_z", "approval_lag_z",
                "approval_lag_z_log", "total_vs_approval_gap"):
        df[col] = df[col].astype(float).round(3)

    return df


# ────────────────────────────────────────────────────────────────────────────
# Mahalanobis (linear + log) and policy_violation
# ────────────────────────────────────────────────────────────────────────────
def _fit(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu  = X.mean(axis=0)
    cov = np.cov(X, rowvar=False, ddof=1)
    return mu, cov


def _d2(X: np.ndarray, mu: np.ndarray, cov: np.ndarray) -> np.ndarray:
    diff = X - mu
    inv  = np.linalg.inv(cov)
    return np.einsum("ij,jk,ik->i", diff, inv, diff)


def _to_log(X: np.ndarray, eps: float = 1e-3) -> np.ndarray:
    return np.log(np.maximum(X, eps))


def _percentile_against_normals(d2_all: np.ndarray,
                                is_normal: np.ndarray) -> np.ndarray:
    """For each order, return the percentile of its D² inside the normal-only
    distribution. Higher percentile = more unusual. Range 0–100."""
    normals = np.sort(d2_all[is_normal])
    n = len(normals)
    ranks = np.searchsorted(normals, d2_all, side="right")
    return np.round(100.0 * ranks / n, 2)


def _tier(d2: np.ndarray) -> np.ndarray:
    return np.where(d2 > D99, "anomaly",
            np.where(d2 > D95, "borderline", "normal"))


def add_mahalanobis(df: pd.DataFrame) -> pd.DataFrame:
    """Add four columns: linear D², log D², their normal-percentile, tiers."""
    df = df.copy()
    is_normal = (df["injection_plan"] == "none").to_numpy()

    X     = df[FEATS].to_numpy(dtype=float)
    X_log = _to_log(X)

    mu_lin, cov_lin = _fit(X[is_normal])
    mu_log, cov_log = _fit(X_log[is_normal])

    df["mahalanobis_D2"]     = np.round(_d2(X,     mu_lin, cov_lin), 3)
    df["mahalanobis_D2_log"] = np.round(_d2(X_log, mu_log, cov_log), 3)

    df["D2_percentile"]     = _percentile_against_normals(
        df["mahalanobis_D2"].to_numpy(), is_normal)
    df["D2_log_percentile"] = _percentile_against_normals(
        df["mahalanobis_D2_log"].to_numpy(), is_normal)

    df["risk_tier"]     = _tier(df["mahalanobis_D2"].to_numpy())
    df["risk_tier_log"] = _tier(df["mahalanobis_D2_log"].to_numpy())

    return df


def add_policy_violation(df: pd.DataFrame) -> pd.DataFrame:
    """Categorical rule check, complementary to D².

    Flags an order as policy_violation = 1 if any of the following holds:
      • approver missing                 (Variant A of approval_bypass)
      • amount ≥ $1,000 with A-PROC-01   (skipped CTO tier)
      • amount ≥ $5,000 with A-CTO       (skipped CEO tier)
    """
    df = df.copy()
    appr  = df["approver_id"].fillna("").astype(str).str.strip()
    total = df["total_amount_usd"].astype(float)

    missing      = appr == ""
    skip_to_proc = (total >= APPROVAL_THRESHOLDS[0]) & (appr == APPROVER_PROC)
    skip_to_cto  = (total >= APPROVAL_THRESHOLDS[1]) & (appr == APPROVER_CTO)

    df["policy_violation"] = (missing | skip_to_proc | skip_to_cto).astype(int)
    return df


# ────────────────────────────────────────────────────────────────────────────
# Text signal scoring
# ────────────────────────────────────────────────────────────────────────────
def text_signal_score(row: pd.Series, plan: str) -> int:
    text = " ".join([
        str(row.get("purchase_note") or ""),
        str(row.get("supplier_profile") or ""),
    ]).lower()
    return sum(kw in text for kw in TEXT_SIGNAL_KEYWORDS.get(plan, []))


# ────────────────────────────────────────────────────────────────────────────
# Stratified sampling for 32 experiment questions
# ────────────────────────────────────────────────────────────────────────────
def select_experiment_32(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    picks: list = []        # row indices in `df`
    strata: list = []
    blocks: list = []
    classes: list = []

    def take(idx_list, stratum, block, plan):
        for i in idx_list:
            if i in picks:
                continue
            picks.append(i)
            strata.append(stratum)
            blocks.append(block)
            classes.append(plan)

    # ─── Block A — 10 normal_obvious ────────────────────────────────────────
    d2_med     = df["mahalanobis_D2"].median()
    d2_log_med = df["mahalanobis_D2_log"].median()
    pool_a = df[
        (df["injection_plan"] == "none")
        & (df["policy_violation"] == 0)
        & (df["mahalanobis_D2"]     < d2_med)
        & (df["mahalanobis_D2_log"] < d2_log_med)
    ]
    if len(pool_a) < N_BLOCK_A:
        print(f"  WARN Block A: only {len(pool_a)} candidates "
              f"(target {N_BLOCK_A}); will take what is available.")
    pick_a = pool_a.sample(min(N_BLOCK_A, len(pool_a)),
                           random_state=seed).index.tolist()
    take(pick_a, "normal_obvious", "A", "none")

    # ─── Block B — 8 anomaly_<class>, one per class ─────────────────────────
    for cls in ALL_CLASSES:
        cand = df[(df["injection_plan"] == cls) & (~df.index.isin(picks))].copy()
        if cand.empty:
            print(f"  WARN Block B: class '{cls}' has no eligible candidate.")
            continue

        if cls == "approval_bypass":
            # Prefer Variant A (policy_violation=1, missing approver) — the
            # most extreme version. Tie-break by highest log-D².
            v_a = cand[cand["policy_violation"] == 1]
            chosen = v_a if not v_a.empty else cand
            best = chosen.sort_values("mahalanobis_D2_log",
                                      ascending=False).head(1)

        elif cls in NUMERIC_CLASSES:
            # Numeric classes: highest linear D²
            best = cand.sort_values("mahalanobis_D2", ascending=False).head(1)

        else:  # text class
            cand["__sig"] = cand.apply(
                lambda r: text_signal_score(r, cls), axis=1)
            best = cand.sort_values(
                ["__sig", "mahalanobis_D2"], ascending=[False, False]
            ).head(1)

        take(best.index.tolist(), f"anomaly_{cls}", "B", cls)

    # ─── Block C1 — 6 edge_normal_high_D2 (false-positive trap) ─────────────
    pool_c1 = df[
        (df["injection_plan"] == "none")
        & (df["policy_violation"] == 0)
        & (df["D2_percentile"] >= 85.0)
        & (df["D2_percentile"] <= 95.0)
        & (df["mahalanobis_D2"] < D99)        # exclude extreme outliers
        & (~df.index.isin(picks))
    ]
    if len(pool_c1) < N_BLOCK_C1:
        print(f"  WARN Block C1: only {len(pool_c1)} candidates "
              f"(target {N_BLOCK_C1}); will take what is available.")
    pick_c1 = pool_c1.sample(min(N_BLOCK_C1, len(pool_c1)),
                             random_state=seed + 1).index.tolist()
    take(pick_c1, "edge_normal_high_D2", "C1", "none")

    # ─── Block C2a — 3 edge_anomaly_low_D2_numeric ──────────────────────────
    # Note: item_spending / border_value / approval_bypass mutations are
    # designed to push D² up. We don't impose a hard percentile threshold;
    # instead we pick the SUBTLEST instance of each class (lowest linear D²).
    # For approval_bypass we additionally prefer Variant B (small lag,
    # approver kept) — that's the textbook example of where linear D² fails
    # and Log D² succeeds.
    for cls in C2A_CLASSES:
        cand = df[
            (df["injection_plan"] == cls)
            & (~df.index.isin(picks))
        ].copy()

        if cls == "approval_bypass":
            v_b = cand[
                (cand["policy_violation"] == 0)
                & (cand["approval_lag_days"] < 0.20)
            ]
            cand = v_b if not v_b.empty else cand

        if cand.empty:
            print(f"  WARN Block C2a: class '{cls}' has no candidate.")
            continue

        best = cand.sort_values("mahalanobis_D2", ascending=True).head(1)
        take(best.index.tolist(),
             f"edge_anomaly_low_D2_numeric_{cls}", "C2a", cls)

    # ─── Block C2b — 5 edge_anomaly_low_D2_text ─────────────────────────────
    for cls in C2B_CLASSES:
        cand = df[
            (df["injection_plan"] == cls)
            & (df["D2_percentile"] < 50.0)
            & (~df.index.isin(picks))
        ].copy()
        if cand.empty:
            cand = df[(df["injection_plan"] == cls)
                      & (~df.index.isin(picks))].copy()
        if cand.empty:
            print(f"  WARN Block C2b: class '{cls}' has no candidate.")
            continue

        # Among low-D² candidates, prefer one whose text contains at least one
        # smoking-gun keyword — otherwise the LLM has nothing to detect.
        cand["__sig"] = cand.apply(
            lambda r: text_signal_score(r, cls), axis=1)
        with_sig = cand[cand["__sig"] >= 1]
        cand = with_sig if not with_sig.empty else cand

        # Lowest D² (most "looks normal"); tie-break by highest text signal.
        best = cand.sort_values(
            ["mahalanobis_D2", "__sig"], ascending=[True, False]
        ).head(1)
        take(best.index.tolist(),
             f"edge_anomaly_low_D2_text_{cls}", "C2b", cls)

    if len(picks) != N_TOTAL:
        print(f"  WARN: assembled {len(picks)} questions "
              f"(target {N_TOTAL}). Some strata short-handed.")

    result = df.loc[picks].copy()
    result["experiment_stratum"] = strata
    result["experiment_block"]   = blocks
    result["target_class"]       = classes

    # Shuffle presentation order so participants don't see strata grouped.
    result = result.sample(frac=1,
                           random_state=int(rng.integers(1, 1_000_000))) \
                   .reset_index(drop=True)
    return result


# ────────────────────────────────────────────────────────────────────────────
# Practice / onboarding batch
# ────────────────────────────────────────────────────────────────────────────
def select_practice(df: pd.DataFrame,
                    used_po_ids: set,
                    seed: int) -> pd.DataFrame:
    """Pick a small practice batch (default 1 normal + 1 anomaly) used to
    train participants on the task interface BEFORE the 32-question block.
    Excluded from both the experiment set and the RAG corpus.

    Selection rules:
      • Normal example   : injection_plan == 'none', no policy violation,
                           D² in the lowest 30% (clearly typical).
      • Anomaly example  : item_spending or border_value with D² > χ²(4,0.99),
                           i.e. a clearly-anomalous numeric case that is
                           pedagogically intuitive (price too high / total
                           just under threshold).
    Falls back gracefully if a strict pool is empty.
    """
    rng_seed = seed + 99

    # 1) Obvious normal
    pool_n = df[
        (df["injection_plan"] == "none")
        & (df["policy_violation"] == 0)
        & (df["mahalanobis_D2"] < df["mahalanobis_D2"].quantile(0.30))
        & (~df["po_id"].isin(used_po_ids))
    ]
    if pool_n.empty:
        pool_n = df[
            (df["injection_plan"] == "none")
            & (~df["po_id"].isin(used_po_ids))
        ]
    pick_n = pool_n.sample(N_PRACTICE_NORMAL,
                           random_state=rng_seed).copy()
    pick_n["practice_role"] = "normal"
    used_po_ids = set(used_po_ids) | set(pick_n["po_id"])

    # 2) Obvious anomaly (prefer item_spending / border_value)
    pool_a = df[
        (df["injection_plan"].isin(["item_spending", "border_value"]))
        & (df["mahalanobis_D2"] > D99)
        & (~df["po_id"].isin(used_po_ids))
    ]
    if pool_a.empty:
        pool_a = df[
            (df["injection_plan"] != "none")
            & (df["mahalanobis_D2"] > D95)
            & (~df["po_id"].isin(used_po_ids))
        ]
    if pool_a.empty:
        pool_a = df[
            (df["injection_plan"] != "none")
            & (~df["po_id"].isin(used_po_ids))
        ]
    pick_a = pool_a.sample(N_PRACTICE_ANOMALY,
                           random_state=rng_seed + 1).copy()
    pick_a["practice_role"] = "anomaly"

    practice = pd.concat([pick_n, pick_a], ignore_index=True)
    return practice


def make_practice_reason(row: pd.Series) -> str:
    """Brief English reason for practice questions, in the same style as the
    experiment templates."""
    role = row["practice_role"]
    plan = (row.get("injection_plan") or "none").strip() or "none"
    k = _row_kit(row)

    if role == "normal":
        return (
            f"Practice — Normal example. "
            f"Linear D2={k['d2_lin']:.2f} (pct {k['pct_lin']:.0f}); "
            f"Log D2={k['d2_log']:.2f} (pct {k['pct_log']:.0f}). "
            f"Unit price ${k['up']:.2f} vs SKU median ${k['sku_med']:.2f} "
            f"({k['upr']:.2f}x). Quantity {k['qty']} vs median "
            f"{int(k['qty_med'])}. Approval lag {k['al']:.2f}d "
            f"(z={k['al_z']:.2f}). Approver {k['appr']}. "
            f"All values within population norms; no policy violation."
        )

    return (
        f"Practice — Obvious anomaly example ({plan}). "
        + _explain_class(plan, k)
    )


# ────────────────────────────────────────────────────────────────────────────
# Reason generator — English explanation per question
# ────────────────────────────────────────────────────────────────────────────
def _asciify(s: str) -> str:
    """Replace Unicode punctuation/math chars with ASCII equivalents so the
    `reason` cell renders correctly in Excel regardless of the user's
    locale/font/CSV-codepage. Keeps the templates readable in source while
    guaranteeing a clean Excel display."""
    if not s:
        return s
    return (s
            .replace("\u2014", "-")     # em dash
            .replace("\u2013", "-")     # en dash
            .replace("\u00b2", "2")     # superscript 2
            .replace("\u03c7", "chi")   # Greek chi
            .replace("\u2265", ">=")    # >= sign
            .replace("\u2264", "<=")    # <= sign
            .replace("\u00d7", "x")     # multiplication sign
            .replace("\u2022", "*")     # bullet
            .replace("\u2018", "'")     # left single quote
            .replace("\u2019", "'")     # right single quote
            .replace("\u201c", '"')     # left double quote
            .replace("\u201d", '"'))    # right double quote



def make_reason(row: pd.Series) -> str:
    """Generate a detailed English reason string for the truth file. Templates
    dispatch by experiment_block. Numbers are filled from the row, so each
    reason stands alone (no need to cross-reference other columns)."""
    block = row["experiment_block"]
    plan  = row["target_class"]

    if not block:
        return ""

    k = _row_kit(row)

    if block == "A":
        return (
            f"Block A — Normal (clearly typical). "
            f"Linear D2={k['d2_lin']:.2f} (pct {k['pct_lin']:.0f}); "
            f"Log D2={k['d2_log']:.2f} (pct {k['pct_log']:.0f}). "
            f"Unit price ${k['up']:.2f} vs SKU median ${k['sku_med']:.2f} "
            f"({k['upr']:.2f}x). Quantity {k['qty']} vs median "
            f"{int(k['qty_med'])} ({k['qty_r']:.2f}x). "
            f"Approval lag {k['al']:.2f}d (z={k['al_z']:.2f}). "
            f"Approver {k['appr']}. Supplier {k['sup']} from preferred pool. "
            f"No policy violation. Semantic fields read as routine."
        )

    if block == "B":
        return (f"Block B — Obvious anomaly: {plan}. "
                + _explain_class(plan, k))

    if block == "C1":
        return (
            f"Block C1 — False-positive trap (normal but D² looks high). "
            f"Linear D2={k['d2_lin']:.2f} (pct {k['pct_lin']:.0f}, "
            f"falls in 85–95 range and below χ²(4, 0.99)=13.28). "
            f"Log D2={k['d2_log']:.2f} (pct {k['pct_log']:.0f}). "
            f"Largest deviations: unit_price_ratio={k['upr']:.2f}, "
            f"quantity_ratio={k['qty_r']:.2f}, delivery_lag_z={k['dl_z']:.2f}. "
            f"injection_plan='none' (no anomaly injected); "
            f"no policy violation. "
            f"Trap: a D²-only baseline would flag this; semantic context "
            f"should reveal it is a routine order."
        )

    if block == "C2a":
        return (f"Block C2a — Subtle numeric anomaly: {plan}. "
                + _explain_class(plan, k))

    if block == "C2b":
        return (f"Block C2b — Subtle text anomaly: {plan}. "
                + _explain_class(plan, k))

    return ""


def _row_kit(row: pd.Series) -> dict:
    """Pre-extract all the fields a reason template might need."""
    appr_raw = (row.get("approver_id") or "")
    appr     = str(appr_raw).strip() or "(none)"
    return {
        "d2_lin":   float(row["mahalanobis_D2"]),
        "d2_log":   float(row["mahalanobis_D2_log"]),
        "pct_lin":  float(row["D2_percentile"]),
        "pct_log":  float(row["D2_log_percentile"]),
        "upr":      float(row["unit_price_ratio"]),
        "qty_r":    float(row["quantity_ratio"]),
        "al_z":     float(row["approval_lag_z"]),
        "al_z_log": float(row["approval_lag_z_log"]),
        "dl_z":     float(row["delivery_lag_z"]),
        "pv":       int(row["policy_violation"]),
        "gap":      float(row["total_vs_approval_gap"]),
        "sku":      row["item_sku"],
        "up":       float(row["unit_price_usd"]),
        "sku_med":  float(row["expected_unit_price_usd"]),
        "qty":      int(row["quantity"]),
        "qty_med":  float(row["expected_quantity"]),
        "al":       float(row["approval_lag_days"]),
        "total":    float(row["total_amount_usd"]),
        "sup":      row["supplier_id"],
        "appr":     appr,
        "note":     str(row.get("purchase_note") or "").strip(),
        "profile":  str(row.get("supplier_profile") or "").strip(),
    }


def _explain_class(plan: str, k: dict) -> str:
    """Per-class detail used by Blocks B / C2a / C2b."""
    if plan == "item_spending":
        return (
            f"Stage-1 mutation: unit_price *= U(2.5, 4.0). "
            f"Unit price ${k['up']:.4f} = {k['upr']:.2f}x SKU median "
            f"${k['sku_med']:.4f}. Total ${k['total']:.2f}. "
            f"Linear D2={k['d2_lin']:.2f} (pct {k['pct_lin']:.0f}); "
            f"Log D2={k['d2_log']:.2f} (pct {k['pct_log']:.0f})."
        )

    if plan == "border_value":
        return (
            f"Stage-1 mutation: total set to just under approval threshold. "
            f"Total ${k['total']:.2f}; nearest threshold gap "
            f"${k['gap']:+.2f}. Quantity {k['qty']} = {k['qty_r']:.2f}x SKU "
            f"median {int(k['qty_med'])}. Approver {k['appr']} "
            f"(no escalation). "
            f"Linear D2={k['d2_lin']:.2f} (pct {k['pct_lin']:.0f})."
        )

    if plan == "approval_bypass":
        if k["pv"] == 1:
            v_desc = "A (approver missing)"
            extra = ("Variant A: rule-based policy_violation captures the "
                     "missing approver. If the original total was below $1k, "
                     "qty was bumped to push total ≥ $1.5k, which often "
                     "raises linear D² as well.")
        else:
            v_desc = "B (lag near zero)"
            extra = ("Linear D² often misses Variant B because lag is in the "
                     "TruncNormal tail but linear scaling under-weights it; "
                     "Log D² amplifies it.")
        return (
            f"Stage-1 mutation: Variant {v_desc}. "
            f"approver_id={k['appr']}, approval_lag={k['al']:.3f}d "
            f"(linear z={k['al_z']:.2f}; log z={k['al_z_log']:.2f}). "
            f"policy_violation={k['pv']}. "
            f"Linear D2={k['d2_lin']:.2f} (pct {k['pct_lin']:.0f}); "
            f"Log D2={k['d2_log']:.2f} (pct {k['pct_log']:.0f}). "
            + extra
        )

    if plan == "bank_account_change":
        return (
            f"Stage-1 mutation: if total<$2k, qty bumped so total~$2.5k–3k; "
            f"approver re-decided. Stage-2 added a banking-change line in "
            f"purchase_note. "
            f"Total ${k['total']:.2f}, qty {k['qty']} ({k['qty_r']:.2f}x med). "
            f"Linear D2={k['d2_lin']:.2f} (pct {k['pct_lin']:.0f}). "
            f"Note excerpt: \"{k['note'][:160]}\"."
        )

    if plan == "unusual_vendor":
        return (
            f"Stage-1 mutation: supplier swapped to anomaly-pool vendor "
            f"(S-026..S-030, 2024-onboarded). Numerical fields untouched. "
            f"Supplier {k['sup']}. Linear D2={k['d2_lin']:.2f} "
            f"(pct {k['pct_lin']:.0f}). "
            f"Profile excerpt: \"{k['profile'][:160]}\"."
        )

    if plan == "vendor_spending":
        return (
            f"Stage-1: same supplier appears in repeated orders this quarter. "
            f"No field mutated; signal lives in note phrasing. "
            f"Supplier {k['sup']}. Linear D2={k['d2_lin']:.2f} "
            f"(pct {k['pct_lin']:.0f}). "
            f"Note excerpt: \"{k['note'][:160]}\"."
        )

    if plan == "quote_manipulation":
        return (
            f"Stage-1: no field mutated. Stage-2 inserted a phrase about "
            f"a single quote received or competing quote withdrawn. "
            f"Linear D2={k['d2_lin']:.2f} (pct {k['pct_lin']:.0f}). "
            f"Note excerpt: \"{k['note'][:160]}\"."
        )

    if plan == "conflict_of_interest":
        return (
            f"Stage-1: supplier swapped to anomaly-pool vendor; "
            f"Stage-2 added an undisclosed personal/recommendation link. "
            f"Supplier {k['sup']}. Linear D2={k['d2_lin']:.2f} "
            f"(pct {k['pct_lin']:.0f}). "
            f"Profile excerpt: \"{k['profile'][:160]}\"."
        )

    return f"(no template for class '{plan}')"


# ────────────────────────────────────────────────────────────────────────────
# RAG corpus serialisation (truth + detector + Section E all stripped)
# ────────────────────────────────────────────────────────────────────────────
def _fmt_date(val: Any) -> str:
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.strftime("%Y-%m-%d")
    return str(val)[:10]


def to_rag_document(row: pd.Series) -> dict:
    """Build a single JSON line: id + natural-language text + raw metadata.

    No ratios, z-scores, D², policy_violation, or stratum information is
    surfaced. The LLM at Stage 4 must derive any comparison itself from this
    document and the other retrieved historical orders."""
    approver = row.get("approver_id") or ""
    note     = str(row.get("purchase_note") or "").strip()
    profile  = str(row.get("supplier_profile") or "").strip()

    text = (
        f"{row['po_id']} ({_fmt_date(row['created_date'])}): "
        f"Requester {row['requester_id']} ordered {int(row['quantity'])} units "
        f"of {row['item_sku']} ({row['item_category']}) from supplier "
        f"{row['supplier_id']} at ${float(row['unit_price_usd']):.4f}/unit, "
        f"total ${float(row['total_amount_usd']):.2f}. "
        f"Approver: {approver or '(none)'}. "
        f"Approval lag: {float(row['approval_lag_days']):.2f} days. "
        f"Expected delivery: {int(row['expected_delivery_lag_days'])} days. "
        f"Purchase note: {note or '(none)'} "
        f"Supplier profile: {profile or '(none)'}"
    )

    meta = {
        "po_id":             row["po_id"],
        "created_date":      _fmt_date(row["created_date"]),
        "requester_id":      row["requester_id"],
        "approver_id":       approver,
        "supplier_id":       row["supplier_id"],
        "item_sku":          row["item_sku"],
        "item_category":     row["item_category"],
        "quantity":          int(row["quantity"]),
        "unit_price_usd":    float(row["unit_price_usd"]),
        "total_amount_usd":  float(row["total_amount_usd"]),
        "approval_lag_days": float(row["approval_lag_days"]),
        "expected_delivery_lag_days": int(row["expected_delivery_lag_days"]),
    }
    return {"id": row["po_id"], "text": text, "metadata": meta}


def write_rag_jsonl(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            f.write(json.dumps(to_rag_document(row), ensure_ascii=False) + "\n")


# ────────────────────────────────────────────────────────────────────────────
# Column hygiene
# ────────────────────────────────────────────────────────────────────────────
TRUTH_COLS = (
    "injection_plan", "injection_seed",
    "experiment_stratum", "experiment_block", "target_class", "reason",
    "practice_role",
)
DETECTOR_COLS = (
    "mahalanobis_D2", "mahalanobis_D2_log",
    "D2_percentile",  "D2_log_percentile",
    "risk_tier",      "risk_tier_log",
    "policy_violation",
)
DERIVED_COLS = (
    "expected_unit_price_usd", "unit_price_ratio",
    "expected_quantity",       "quantity_ratio",
    "expected_delivery_lag_mean", "expected_delivery_lag_sigma",
    "delivery_lag_z", "approval_lag_z", "approval_lag_z_log",
    "total_vs_approval_gap",
)


def drop_cols(df: pd.DataFrame, cols) -> pd.DataFrame:
    return df.drop(columns=[c for c in cols if c in df.columns])


def make_ui_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Experiment Excel shown to participants:
       • strip ground truth (injection_plan/seed/stratum/block/class/reason)
       • strip detector signals (D², percentiles, tiers, policy_violation)
       • KEEP Section E deviation features as participant reference."""
    return drop_cols(drop_cols(df, TRUTH_COLS), DETECTOR_COLS)


def make_rag_safe(df: pd.DataFrame) -> pd.DataFrame:
    """RAG corpus / any LLM-facing artefact:
       • strip ground truth, detector signals, AND Section E deviation
         features. The LLM must reason from raw fields + retrieved similar
         historical orders, not from a pre-computed ratio table."""
    return drop_cols(drop_cols(drop_cols(df, TRUTH_COLS), DETECTOR_COLS),
                     DERIVED_COLS)


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage2-input", default=None,
                    help="Path to orders_stage2_semantics.xlsx "
                         "(default: data/stage2/orders_stage2_semantics.xlsx)")
    ap.add_argument("--dataset-input", default=None,
                    help="Path to Stage-1 dataset_<TS>.xlsx (default: latest)")
    ap.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = ap.parse_args()

    STAGE3_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve Stage-2 input path
    if args.stage2_input:
        stage2_path = Path(args.stage2_input)
    else:
        for cand in (STAGE2_DIR / "orders_stage2_semantics.xlsx",
                     DATA_DIR   / "orders_stage2_semantics.xlsx"):
            if cand.exists():
                stage2_path = cand
                break
        else:
            sys.exit(
                f"ERROR: Stage-2 file not found in {STAGE2_DIR} or {DATA_DIR}. "
                "Pass --stage2-input <path> if it lives elsewhere."
            )
    if not stage2_path.exists():
        sys.exit(f"ERROR: Stage-2 file not found at {stage2_path}")

    dataset_path = Path(args.dataset_input) if args.dataset_input \
                   else find_latest_dataset_excel(DATA_DIR)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 78)
    print(f"Stage 3 prepare — run {ts}")
    print(f"  Stage-2 input   : {stage2_path}")
    print(f"  Stage-1 dataset : {dataset_path}")
    print(f"  Random seed     : {args.seed}")
    print(f"  Target Q count  : {N_TOTAL}  "
          f"(A={N_BLOCK_A}, B={N_BLOCK_B}, C1={N_BLOCK_C1}, "
          f"C2a={N_BLOCK_C2A}, C2b={N_BLOCK_C2B})")
    print("=" * 78)

    # 1. Load
    orders, components, suppliers = load_inputs(stage2_path, dataset_path)
    if len(orders) != 500:
        print(f"  [!] Expected 500 orders, got {len(orders)}")
    print(f"  Loaded {len(orders)} orders, "
          f"{len(components)} components, {len(suppliers)} suppliers.")

    # 2. Section E deviation features
    orders = add_deviation_features(orders, components)
    print(f"  Added Section E deviation features.  "
          f"unit_price_ratio range "
          f"[{orders['unit_price_ratio'].min():.2f}, "
          f"{orders['unit_price_ratio'].max():.2f}].")

    # 3. Mahalanobis (linear + log) and policy_violation
    orders = add_mahalanobis(orders)
    orders = add_policy_violation(orders)

    n_normals = int((orders["injection_plan"] == "none").sum())
    print(f"  Mahalanobis fitted on {n_normals} normals; "
          f"chi2(4): 95%={D95:.3f}, 99%={D99:.3f}.")
    print(f"  risk_tier  (linear): "
          f"{orders['risk_tier'].value_counts().to_dict()}")
    print(f"  risk_tier  (log)  : "
          f"{orders['risk_tier_log'].value_counts().to_dict()}")
    print(f"  policy_violation==1 orders: "
          f"{int(orders['policy_violation'].sum())}")

    # 4. Stratified sampling for 32 questions
    exp_full = select_experiment_32(orders, seed=args.seed)
    print(f"  Sampled {len(exp_full)} questions; block counts: "
          f"{exp_full['experiment_block'].value_counts().to_dict()}")
    print(f"  Class coverage in experiment: "
          f"{exp_full['target_class'].value_counts().to_dict()}")

    # 5. Generate English `reason` per experiment row (ASCII-clean for Excel)
    exp_full["reason"] = exp_full.apply(make_reason, axis=1).apply(_asciify)

    # 5b. Practice / onboarding batch (1 normal + 1 obvious anomaly).
    #     Excluded from both experiment AND RAG corpus.
    practice = select_practice(
        orders,
        used_po_ids=set(exp_full["po_id"]),
        seed=args.seed,
    )
    practice["reason"] = practice.apply(make_practice_reason,
                                        axis=1).apply(_asciify)
    print(f"  Sampled {len(practice)} practice questions: "
          f"{practice['practice_role'].tolist()}  "
          f"(plans: {practice['injection_plan'].tolist()})")

    # 6. Inject markers back into the full table for the truth file
    full = orders.copy()
    full["experiment_stratum"] = ""
    full["experiment_block"]   = ""
    full["target_class"]       = ""
    full["practice_role"]      = ""
    full["reason"]             = ""
    full = full.set_index("po_id")
    for _, r in exp_full.iterrows():
        po = r["po_id"]
        full.at[po, "experiment_stratum"] = r["experiment_stratum"]
        full.at[po, "experiment_block"]   = r["experiment_block"]
        full.at[po, "target_class"]       = r["target_class"]
        full.at[po, "reason"]             = r["reason"]
    for _, r in practice.iterrows():
        po = r["po_id"]
        full.at[po, "experiment_block"]   = "P"
        full.at[po, "experiment_stratum"] = f"practice_{r['practice_role']}"
        full.at[po, "target_class"]       = r.get("injection_plan") or "none"
        full.at[po, "practice_role"]      = r["practice_role"]
        full.at[po, "reason"]             = r["reason"]
    full = full.reset_index()

    # 7. Write artefacts
    full_out = STAGE3_DIR / f"stage3_full_with_truth_{ts}.xlsx"
    full.to_excel(full_out, index=False)
    full.to_csv(STAGE3_DIR / f"stage3_full_with_truth_{ts}.csv",
                index=False, encoding="utf-8-sig")
    print(f"  Wrote {full_out.name}  "
          f"({len(full)} rows; full truth + dual D² + reason)")

    exp_ui = make_ui_safe(exp_full)
    exp_out = STAGE3_DIR / f"experiment_{N_TOTAL}qs_{ts}.xlsx"
    exp_ui.to_excel(exp_out, index=False)
    exp_ui.to_csv(STAGE3_DIR / f"experiment_{N_TOTAL}qs_{ts}.csv",
                  index=False, encoding="utf-8-sig")
    print(f"  Wrote {exp_out.name}  "
          f"({N_TOTAL} rows, UI-safe; Section E retained as reference)")

    key_cols = [
        "po_id", "experiment_block", "experiment_stratum", "target_class",
        "injection_plan", "policy_violation",
        "mahalanobis_D2", "D2_percentile",
        "mahalanobis_D2_log", "D2_log_percentile",
        "risk_tier", "risk_tier_log", "reason",
    ]
    key_out = STAGE3_DIR / f"experiment_{N_TOTAL}qs_{ts}_KEY.xlsx"
    exp_full[key_cols].to_excel(key_out, index=False)
    print(f"  Wrote {key_out.name}  (stratum + truth + reason)")

    # 7b. Practice files
    prac_ui  = make_ui_safe(practice)
    prac_out = STAGE3_DIR / f"practice_{N_PRACTICE}qs_{ts}.xlsx"
    prac_ui.to_excel(prac_out, index=False)
    prac_ui.to_csv(STAGE3_DIR / f"practice_{N_PRACTICE}qs_{ts}.csv",
                   index=False, encoding="utf-8-sig")
    print(f"  Wrote {prac_out.name}  "
          f"({N_PRACTICE} rows, UI-safe; practice_role hidden)")

    prac_key_cols = [
        "po_id", "practice_role", "injection_plan", "policy_violation",
        "mahalanobis_D2", "D2_percentile",
        "mahalanobis_D2_log", "D2_log_percentile",
        "risk_tier", "risk_tier_log", "reason",
    ]
    prac_key_out = STAGE3_DIR / f"practice_{N_PRACTICE}qs_{ts}_KEY.xlsx"
    practice[prac_key_cols].to_excel(prac_key_out, index=False)
    print(f"  Wrote {prac_key_out.name}  (role + truth + reason)")

    # 8. RAG corpus = orders MINUS experiment MINUS practice (= 466 docs)
    exclude_ids = set(exp_full["po_id"]) | set(practice["po_id"])
    rag_pool    = orders[~orders["po_id"].isin(exclude_ids)].copy()
    rag_safe    = make_rag_safe(rag_pool)
    rag_out     = STAGE3_DIR / f"rag_corpus_{len(rag_safe)}_{ts}.jsonl"
    write_rag_jsonl(rag_safe, rag_out)
    rag_safe.to_csv(STAGE3_DIR / f"rag_corpus_{len(rag_safe)}_{ts}.csv",
                    index=False, encoding="utf-8-sig")
    print(f"  Wrote {rag_out.name}  "
          f"({len(rag_safe)} documents; truth, detector, Section E stripped)")

    print("-" * 78)
    print("Stage 3 complete.")
    print("Next: build_rag.py (embed the JSONL into Chroma).")


if __name__ == "__main__":
    main()
