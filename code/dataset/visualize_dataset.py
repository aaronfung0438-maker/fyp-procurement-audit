"""
visualize_dataset.py
====================
Generate the full set of exploratory / verification plots for the procurement
dataset produced by `generate_dataset.py` (Stage 1) and optionally enriched by
`generate_semantics.py` (Stage 2).

Outputs
-------
Every figure is written as PNG (300 dpi) into

    data/visualizations/<TS>/

where <TS> is the dataset timestamp parsed from the input Excel file name.

Usage
-----
    # from  code/dataset/
    python visualize_dataset.py
    # explicit file
    python visualize_dataset.py --input data/dataset_20260420_015519.xlsx

The script auto-detects the most recent `dataset_*.xlsx` if no input is given.

Dependencies: pandas, matplotlib, numpy, seaborn, openpyxl, scipy.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import lognorm, truncnorm

# ─── Style ───────────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", context="talk")
plt.rcParams.update({
    "figure.dpi":        110,
    "savefig.dpi":       300,
    "savefig.bbox":      "tight",
    "axes.titleweight":  "bold",
    "axes.titlesize":    14,
    "axes.labelsize":    12,
    "legend.fontsize":   10,
})

PALETTE_MAIN     = "#2E86AB"
PALETTE_ANOMALY  = "#E63946"
PALETTE_NEUTRAL  = "#6C757D"


# ═════════════════════════════════════════════════════════════════════════════
# I/O helpers
# ═════════════════════════════════════════════════════════════════════════════
def find_latest_dataset(data_dir: Path) -> Path:
    candidates = sorted(data_dir.glob("dataset_*.xlsx"), reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No dataset_*.xlsx found in {data_dir}")
    return candidates[0]


def parse_timestamp(path: Path) -> str:
    m = re.search(r"dataset_(\d{8}_\d{6})", path.name)
    return m.group(1) if m else "unknown"


def load_all(xlsx: Path) -> dict:
    sheets = pd.read_excel(xlsx, sheet_name=None)
    required = {"orders", "suppliers", "components", "injections", "metadata"}
    missing  = required - set(sheets.keys())
    if missing:
        raise ValueError(f"Missing sheets: {missing}")
    # Parse date columns
    sheets["orders"]["created_date"]    = pd.to_datetime(sheets["orders"]["created_date"])
    sheets["orders"]["approved_date"]   = pd.to_datetime(sheets["orders"]["approved_date"])
    return sheets


def save(fig, out_dir: Path, name: str) -> None:
    path = out_dir / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    print(f"  [ok] {path.name}")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 01 — daily order count (Poisson process verification)
# ═════════════════════════════════════════════════════════════════════════════
def plot_orders_over_time(orders: pd.DataFrame, out: Path) -> None:
    daily = orders.groupby(orders["created_date"].dt.date).size()
    daily = daily.reindex(
        pd.date_range(daily.index.min(), daily.index.max()),
        fill_value=0,
    )

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7))

    ax1.plot(daily.index, daily.values, color=PALETTE_MAIN, lw=0.8)
    ax1.fill_between(daily.index, daily.values, alpha=0.3, color=PALETTE_MAIN)
    ax1.set_title("Daily order arrivals (Poisson process)")
    ax1.set_ylabel("orders / day")
    ax1.axhline(daily.mean(), ls="--", color="black",
                label=f"mean λ ≈ {daily.mean():.2f}")
    ax1.legend()

    counts = daily.values
    bins   = np.arange(counts.min(), counts.max() + 2) - 0.5
    ax2.hist(counts, bins=bins, color=PALETTE_MAIN, alpha=0.7,
             edgecolor="white", label="observed")
    # Poisson pmf overlay
    from scipy.stats import poisson
    lam = counts.mean()
    xs  = np.arange(0, counts.max() + 2)
    ax2.plot(xs, poisson.pmf(xs, lam) * len(counts),
             "o-", color=PALETTE_ANOMALY, label=f"Poisson(λ={lam:.2f})")
    ax2.set_title("Daily count distribution vs theoretical Poisson")
    ax2.set_xlabel("orders / day")
    ax2.set_ylabel("frequency")
    ax2.legend()

    plt.tight_layout()
    save(fig, out, "01_orders_over_time")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 02 — monthly aggregation
# ═════════════════════════════════════════════════════════════════════════════
def plot_monthly_volume(orders: pd.DataFrame, out: Path) -> None:
    monthly = orders.groupby(orders["created_date"].dt.to_period("M")).agg(
        n_orders=("po_id", "count"),
        total_usd=("total_amount_usd", "sum"),
    )

    fig, ax1 = plt.subplots(figsize=(11, 5))
    x = monthly.index.astype(str)
    ax1.bar(x, monthly["n_orders"], color=PALETTE_MAIN, alpha=0.8,
            label="order count")
    ax1.set_ylabel("orders")
    ax1.set_xlabel("month")
    ax1.tick_params(axis="x", rotation=45)

    ax2 = ax1.twinx()
    ax2.plot(x, monthly["total_usd"], "o-", color=PALETTE_ANOMALY,
             lw=2, label="USD spend")
    ax2.set_ylabel("total spend (USD)")
    ax2.grid(False)

    ax1.set_title("Monthly order volume and spend")
    lines1, lbl1 = ax1.get_legend_handles_labels()
    lines2, lbl2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, lbl1 + lbl2, loc="upper left")
    plt.tight_layout()
    save(fig, out, "02_monthly_volume")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 03 — requester distribution
# ═════════════════════════════════════════════════════════════════════════════
def plot_requester_distribution(orders: pd.DataFrame, out: Path) -> None:
    counts = orders["requester_id"].value_counts().sort_index()
    weights_expected = {
        "R-ENG-01": 0.18, "R-ENG-02": 0.16, "R-ENG-03": 0.14, "R-ENG-04": 0.13,
        "R-ENG-05": 0.12, "R-ENG-06": 0.10, "R-ENG-07": 0.09, "R-ENG-08": 0.08,
    }
    expected = pd.Series({k: v * len(orders) for k, v in weights_expected.items()})

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(counts))
    ax.bar(x - 0.2, counts.values, width=0.4, color=PALETTE_MAIN,
           label="actual")
    ax.bar(x + 0.2, expected.values, width=0.4, color=PALETTE_NEUTRAL,
           alpha=0.6, label="expected from weights")
    ax.set_xticks(x)
    ax.set_xticklabels(counts.index, rotation=30)
    ax.set_ylabel("orders")
    ax.set_title("Orders per engineer — actual vs weighted-expected")
    ax.legend()
    plt.tight_layout()
    save(fig, out, "03_requester_distribution")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 04 — supplier distribution with anomaly pool highlighted
# ═════════════════════════════════════════════════════════════════════════════
def plot_supplier_distribution(orders: pd.DataFrame, suppliers: pd.DataFrame,
                               out: Path) -> None:
    counts = (orders["supplier_id"].value_counts()
              .reindex(suppliers["supplier_id"], fill_value=0))
    pool   = suppliers.set_index("supplier_id")["is_anomaly_pool"]
    colors = [PALETTE_ANOMALY if pool[sid] else PALETTE_MAIN
              for sid in counts.index]

    fig, ax = plt.subplots(figsize=(13, 5.5))
    ax.bar(counts.index, counts.values, color=colors)
    ax.set_xticks(range(len(counts)))
    ax.set_xticklabels(counts.index, rotation=75, fontsize=9)
    ax.set_ylabel("orders received")
    ax.set_title(
        "Orders per supplier (red = anomaly pool S-026…S-030, "
        "each normal order should NEVER land here)"
    )
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=PALETTE_MAIN, label="normal (S-001…S-025)"),
        Patch(color=PALETTE_ANOMALY, label="anomaly pool (S-026…S-030)"),
    ])
    plt.tight_layout()
    save(fig, out, "04_supplier_distribution")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 05 — orders per SKU
# ═════════════════════════════════════════════════════════════════════════════
def plot_component_distribution(orders: pd.DataFrame, components: pd.DataFrame,
                                out: Path) -> None:
    counts = (orders["item_sku"].value_counts()
              .reindex(components["sku"], fill_value=0))
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(counts.index, counts.values, color=PALETTE_MAIN)
    ax.set_xticklabels(counts.index, rotation=35, ha="right")
    ax.set_ylabel("orders")
    ax.set_title("Orders per SKU (should be roughly uniform ≈ 50 each)")
    ax.axhline(len(orders) / len(components), ls="--", color="black",
               label=f"expected = {len(orders)/len(components):.0f}")
    ax.legend()
    plt.tight_layout()
    save(fig, out, "05_component_distribution")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 06 — unit price box-plot per SKU (log y-axis)
# ═════════════════════════════════════════════════════════════════════════════
def plot_unit_price_by_sku(orders: pd.DataFrame, components: pd.DataFrame,
                           out: Path) -> None:
    order = components["sku"].tolist()
    fig, ax = plt.subplots(figsize=(13, 6))
    sns.boxplot(data=orders, x="item_sku", y="unit_price_usd",
                order=order, color=PALETTE_MAIN, ax=ax)

    # overlay Mouser geo-mean
    for i, sku in enumerate(order):
        gm = components.loc[components["sku"] == sku, "price_median_usd"].iloc[0]
        ax.hlines(gm, i - 0.35, i + 0.35, color=PALETTE_ANOMALY, lw=2)

    ax.set_yscale("log")
    ax.set_ylabel("unit price (USD, log-scale)")
    ax.set_xlabel("")
    ax.set_title("Unit price per SKU (red bar = Mouser geo-mean; Log-Normal scatter)")
    ax.set_xticklabels(order, rotation=35, ha="right")
    plt.tight_layout()
    save(fig, out, "06_unit_price_by_sku")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 07 — quantity box-plot per SKU
# ═════════════════════════════════════════════════════════════════════════════
def plot_quantity_by_sku(orders: pd.DataFrame, components: pd.DataFrame,
                         out: Path) -> None:
    order = components["sku"].tolist()
    fig, ax = plt.subplots(figsize=(13, 6))
    sns.boxplot(data=orders, x="item_sku", y="quantity",
                order=order, color=PALETTE_MAIN, ax=ax)
    for i, sku in enumerate(order):
        med = components.loc[components["sku"] == sku, "qty_median"].iloc[0]
        ax.hlines(med, i - 0.35, i + 0.35, color=PALETTE_ANOMALY, lw=2)
    ax.set_yscale("log")
    ax.set_ylabel("quantity (log-scale)")
    ax.set_xlabel("")
    ax.set_title("Quantity per SKU (red bar = design-median; Log-Normal scatter)")
    ax.set_xticklabels(order, rotation=35, ha="right")
    plt.tight_layout()
    save(fig, out, "07_quantity_by_sku")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 08 — total amount distribution with approval thresholds
# ═════════════════════════════════════════════════════════════════════════════
def plot_total_amount(orders: pd.DataFrame, out: Path) -> None:
    normal = orders[orders["injection_plan"] == "none"]["total_amount_usd"]
    anom   = orders[orders["injection_plan"] != "none"]["total_amount_usd"]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    bins = np.logspace(np.log10(max(1, orders["total_amount_usd"].min())),
                       np.log10(orders["total_amount_usd"].max()), 60)
    ax.hist(normal, bins=bins, alpha=0.7, color=PALETTE_MAIN, label="normal")
    ax.hist(anom,   bins=bins, alpha=0.8, color=PALETTE_ANOMALY, label="anomaly")
    ax.axvline(1000, ls="--", color="black", lw=1)
    ax.axvline(5000, ls="--", color="black", lw=1)
    ax.text(1000, ax.get_ylim()[1] * 0.9, "  $1 000\n  → CTO",
            fontsize=9, va="top")
    ax.text(5000, ax.get_ylim()[1] * 0.9, "  $5 000\n  → CEO",
            fontsize=9, va="top")
    ax.set_xscale("log")
    ax.set_xlabel("total amount (USD, log-scale)")
    ax.set_ylabel("frequency")
    ax.set_title("Total amount distribution — normal vs anomaly, with approval thresholds")
    ax.legend()
    plt.tight_layout()
    save(fig, out, "08_total_amount")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 09 — approval lag histogram with TruncNormal overlay
# ═════════════════════════════════════════════════════════════════════════════
def plot_approval_lag(orders: pd.DataFrame, out: Path) -> None:
    normal = orders[orders["injection_plan"] == "none"]["approval_lag_days"]
    bypass = orders[orders["injection_plan"] == "approval_bypass"]["approval_lag_days"]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.hist(normal, bins=40, alpha=0.7, color=PALETTE_MAIN, label="normal",
            density=True)
    if len(bypass):
        ax.hist(bypass, bins=15, alpha=0.85, color=PALETTE_ANOMALY,
                label="approval_bypass (fast variant)", density=True)

    # theoretical TruncNormal(μ=2, σ=1.5, [0.1, 14])
    μ, σ = 2.0, 1.5
    a, b = (0.1 - μ) / σ, (14 - μ) / σ
    xs   = np.linspace(0, 14, 400)
    ax.plot(xs, truncnorm.pdf(xs, a, b, loc=μ, scale=σ),
            color="black", lw=2, label="TruncNormal(μ=2, σ=1.5, [0.1, 14])")
    ax.set_xlabel("approval lag (days)")
    ax.set_ylabel("density")
    ax.set_title("Approval lag distribution — natural vs bypass-fast")
    ax.legend()
    plt.tight_layout()
    save(fig, out, "09_approval_lag")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 10 — delivery lag by SKU
# ═════════════════════════════════════════════════════════════════════════════
def plot_delivery_lag(orders: pd.DataFrame, components: pd.DataFrame,
                      out: Path) -> None:
    order = components.sort_values("lead_time_median_days")["sku"].tolist()
    fig, ax = plt.subplots(figsize=(13, 6))
    sns.boxplot(data=orders, x="item_sku", y="expected_delivery_lag_days",
                order=order, color=PALETTE_MAIN, ax=ax)
    for i, sku in enumerate(order):
        mu = components.loc[components["sku"] == sku,
                            "lead_time_median_days"].iloc[0]
        ax.hlines(mu, i - 0.35, i + 0.35, color=PALETTE_ANOMALY, lw=2)
    ax.set_ylabel("expected delivery lag (days)")
    ax.set_xlabel("")
    ax.set_title("Delivery lag per SKU (red = Mouser LeadTime; TruncNormal scatter)")
    ax.set_xticklabels(order, rotation=35, ha="right")
    plt.tight_layout()
    save(fig, out, "10_delivery_lag_by_sku")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 11 — approver distribution (pie)
# ═════════════════════════════════════════════════════════════════════════════
def plot_approver_distribution(orders: pd.DataFrame, out: Path) -> None:
    counts = orders["approver_id"].fillna("(empty)").replace("", "(empty)").value_counts()
    fig, ax = plt.subplots(figsize=(7, 7))
    colors = []
    for a in counts.index:
        if a == "(empty)":   colors.append(PALETTE_ANOMALY)
        elif a == "A-PROC-01": colors.append("#4C8FCF")
        elif a == "A-CTO":   colors.append("#69B578")
        elif a == "A-CEO":   colors.append("#E0A458")
        else:                colors.append(PALETTE_NEUTRAL)
    ax.pie(counts, labels=counts.index, colors=colors, autopct="%1.1f%%",
           startangle=90, wedgeprops={"edgecolor": "white", "linewidth": 1.5})
    ax.set_title("Approver distribution (empty = approval_bypass anomaly)")
    plt.tight_layout()
    save(fig, out, "11_approver_distribution")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 12 — anomaly-category counts
# ═════════════════════════════════════════════════════════════════════════════
def plot_anomaly_counts(injections: pd.DataFrame, out: Path) -> None:
    order = [
        "item_spending", "vendor_spending", "border_value", "unusual_vendor",
        "approval_bypass", "quote_manipulation", "bank_account_change",
        "conflict_of_interest",
    ]
    counts = injections["indicator"].value_counts().reindex(order, fill_value=0)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.barh(counts.index, counts.values, color=PALETTE_ANOMALY)
    for i, v in enumerate(counts.values):
        ax.text(v + 0.15, i, str(v), va="center")
    ax.set_xlabel("number of injected orders")
    ax.set_title(f"Anomaly category breakdown — {counts.sum()} / 500 orders "
                 f"({counts.sum()/5:.1f}% of dataset)")
    ax.invert_yaxis()
    plt.tight_layout()
    save(fig, out, "12_anomaly_counts")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 13 — price × quantity scatter, colored by injection_plan
# ═════════════════════════════════════════════════════════════════════════════
def plot_price_qty_scatter(orders: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 7))
    normal = orders[orders["injection_plan"] == "none"]
    ax.scatter(normal["unit_price_usd"], normal["quantity"],
               s=18, alpha=0.45, color=PALETTE_MAIN, label="normal")
    anom = orders[orders["injection_plan"] != "none"]
    cmap = plt.cm.tab10
    for i, cat in enumerate(anom["injection_plan"].unique()):
        sub = anom[anom["injection_plan"] == cat]
        ax.scatter(sub["unit_price_usd"], sub["quantity"],
                   s=55, alpha=0.85, color=cmap(i), label=cat,
                   edgecolor="black", linewidth=0.4)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("unit price (USD, log)")
    ax.set_ylabel("quantity (log)")
    ax.set_title("Price × Quantity (log-log) — normal cloud vs anomaly classes")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
    plt.tight_layout()
    save(fig, out, "13_price_quantity_scatter")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 14 — border-value zoom
# ═════════════════════════════════════════════════════════════════════════════
def plot_border_zoom(orders: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    ranges = [(800, 1100, 1000, "$1 000 threshold"),
              (4500, 5200, 5000, "$5 000 threshold")]
    for ax, (lo, hi, th, title) in zip(axes, ranges):
        sub    = orders[(orders["total_amount_usd"] >= lo) &
                        (orders["total_amount_usd"] <= hi)]
        normal = sub[sub["injection_plan"] == "none"]
        border = sub[sub["injection_plan"] == "border_value"]
        ax.hist(normal["total_amount_usd"], bins=30, alpha=0.7,
                color=PALETTE_MAIN, label="normal")
        ax.hist(border["total_amount_usd"], bins=30, alpha=0.85,
                color=PALETTE_ANOMALY, label="border_value")
        ax.axvline(th, ls="--", color="black")
        ax.set_title(title)
        ax.set_xlabel("total amount (USD)")
        ax.set_ylabel("frequency")
        ax.legend()
    plt.suptitle("Border-value anomaly zoom — clustering just below each threshold",
                 y=1.02)
    plt.tight_layout()
    save(fig, out, "14_border_value_zoom")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 15 — requester × supplier heatmap
# ═════════════════════════════════════════════════════════════════════════════
def plot_requester_supplier_heatmap(orders: pd.DataFrame,
                                    suppliers: pd.DataFrame,
                                    out: Path) -> None:
    mat = (orders.groupby(["requester_id", "supplier_id"]).size()
           .unstack(fill_value=0)
           .reindex(columns=suppliers["supplier_id"].tolist(), fill_value=0))
    fig, ax = plt.subplots(figsize=(15, 5))
    sns.heatmap(mat, cmap="rocket_r", linewidths=0.3, linecolor="white",
                cbar_kws={"label": "order count"}, ax=ax)
    ax.set_title("Requester × Supplier heat-map  "
                 "(Markov preferences visible; anomaly-pool columns mostly empty except injections)")
    ax.set_xlabel("supplier")
    ax.set_ylabel("requester")
    plt.tight_layout()
    save(fig, out, "15_requester_supplier_heatmap")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 16 — Log-Normal fit verification (one SKU: BME280)
# ═════════════════════════════════════════════════════════════════════════════
def plot_lognormal_fit(orders: pd.DataFrame, components: pd.DataFrame,
                       out: Path, sku: str = "BME280") -> None:
    comp   = components[components["sku"] == sku].iloc[0]
    sample = orders.loc[
        (orders["item_sku"] == sku) & (orders["injection_plan"] == "none"),
        "unit_price_usd",
    ].to_numpy()
    μ      = np.log(comp["price_median_usd"])
    σ      = comp["price_sigma_log"]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.hist(sample, bins=25, density=True, alpha=0.7, color=PALETTE_MAIN,
            label=f"observed ({sku}, n={len(sample)})")
    xs = np.linspace(sample.min() * 0.8, sample.max() * 1.2, 400)
    ax.plot(xs, lognorm.pdf(xs, s=σ, scale=np.exp(μ)),
            color=PALETTE_ANOMALY, lw=2,
            label=f"LogNormal(μ=ln {comp['price_median_usd']:.4f}, σ={σ:.3f})")
    ax.axvline(comp["price_median_usd"], ls="--", color="black",
               label=f"Mouser geo-mean ${comp['price_median_usd']:.4f}")
    ax.set_xlabel("unit price (USD)")
    ax.set_ylabel("density")
    ax.set_title(f"Log-Normal price fit verification — {sku}")
    ax.legend(fontsize=9)
    plt.tight_layout()
    save(fig, out, f"16_lognormal_fit_{sku}")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 17 — 4-D feature pairplot (Mahalanobis preview)
# ═════════════════════════════════════════════════════════════════════════════
def plot_mahalanobis_preview(orders: pd.DataFrame, out: Path) -> None:
    cols = ["unit_price_usd", "quantity",
            "approval_lag_days", "expected_delivery_lag_days"]
    sub  = orders[cols + ["injection_plan"]].copy()
    sub["is_anomaly"] = sub["injection_plan"] != "none"

    # log-transform the two log-normal columns for readability
    sub["unit_price_usd"] = np.log10(sub["unit_price_usd"])
    sub["quantity"]       = np.log10(sub["quantity"])
    sub = sub.rename(columns={
        "unit_price_usd":             "log10(unit_price)",
        "quantity":                   "log10(quantity)",
        "approval_lag_days":          "approval_lag",
        "expected_delivery_lag_days": "delivery_lag",
    })

    g = sns.pairplot(
        sub, vars=["log10(unit_price)", "log10(quantity)",
                   "approval_lag", "delivery_lag"],
        hue="is_anomaly", corner=True, diag_kind="kde",
        palette={True: PALETTE_ANOMALY, False: PALETTE_MAIN},
        plot_kws={"s": 18, "alpha": 0.55},
        height=2.6,
    )
    g.fig.suptitle("4-D feature pair-plot — Mahalanobis input space  "
                   "(anomalies visibly separate in some panels)",
                   y=1.02, fontsize=14)
    g.fig.savefig(out / "17_mahalanobis_preview.png", dpi=300,
                  bbox_inches="tight")
    plt.close(g.fig)
    print("  [ok] 17_mahalanobis_preview.png")


# ═════════════════════════════════════════════════════════════════════════════
# Plot 18 — normal vs anomaly boxplots (4 features side-by-side)
# ═════════════════════════════════════════════════════════════════════════════
def plot_normal_vs_anomaly(orders: pd.DataFrame, out: Path) -> None:
    df = orders.copy()
    df["class"] = np.where(df["injection_plan"] == "none", "normal", "anomaly")

    fig, axes = plt.subplots(1, 4, figsize=(16, 5))
    cols = [
        ("unit_price_usd",             "unit price (USD)",     True),
        ("quantity",                   "quantity",             True),
        ("approval_lag_days",          "approval lag (days)",  False),
        ("expected_delivery_lag_days", "delivery lag (days)",  False),
    ]
    for ax, (c, lbl, log) in zip(axes, cols):
        sns.boxplot(data=df, x="class", y=c, ax=ax,
                    palette={"normal": PALETTE_MAIN,
                             "anomaly": PALETTE_ANOMALY})
        if log:
            ax.set_yscale("log")
        ax.set_title(lbl)
        ax.set_xlabel("")
    plt.suptitle("Feature distributions — normal vs anomaly", y=1.03)
    plt.tight_layout()
    save(fig, out, "18_normal_vs_anomaly_boxplots")


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=None,
                        help="Path to dataset_*.xlsx. If omitted, latest is used.")
    parser.add_argument("--outdir", type=Path, default=None,
                        help="Output folder. If omitted, "
                             "data/visualizations/<TS>/ is used.")
    args = parser.parse_args()

    here      = Path(__file__).resolve().parent
    data_dir  = here / "data"
    xlsx      = args.input or find_latest_dataset(data_dir)
    ts        = parse_timestamp(xlsx)
    out_dir   = args.outdir or (data_dir / "visualizations" / ts)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"  input       : {xlsx}")
    print(f"  output dir  : {out_dir}\n")

    sheets     = load_all(xlsx)
    orders     = sheets["orders"]
    suppliers  = sheets["suppliers"]
    components = sheets["components"]
    injections = sheets["injections"]

    # Fixed component order for the plots that use it
    components = components.copy().reset_index(drop=True)

    plot_orders_over_time       (orders, out_dir)
    plot_monthly_volume         (orders, out_dir)
    plot_requester_distribution (orders, out_dir)
    plot_supplier_distribution  (orders, suppliers, out_dir)
    plot_component_distribution (orders, components, out_dir)
    plot_unit_price_by_sku      (orders, components, out_dir)
    plot_quantity_by_sku        (orders, components, out_dir)
    plot_total_amount           (orders, out_dir)
    plot_approval_lag           (orders, out_dir)
    plot_delivery_lag           (orders, components, out_dir)
    plot_approver_distribution  (orders, out_dir)
    plot_anomaly_counts         (injections, out_dir)
    plot_price_qty_scatter      (orders, out_dir)
    plot_border_zoom            (orders, out_dir)
    plot_requester_supplier_heatmap(orders, suppliers, out_dir)
    plot_lognormal_fit          (orders, components, out_dir, sku="BME280")
    plot_mahalanobis_preview    (orders, out_dir)
    plot_normal_vs_anomaly      (orders, out_dir)

    print(f"\n  Done. {len(list(out_dir.glob('*.png')))} figures in {out_dir}")


if __name__ == "__main__":
    main()
