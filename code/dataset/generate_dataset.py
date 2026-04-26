"""
generate_dataset.py
====================================================================
ABC Electronics Ltd. — Full Dataset Pipeline (Stage 0 + Stage 1)

Stage 0  Fetch REAL prices from Mouser using exact Mouser Part Numbers
         via the /search/partnumber endpoint.
         Skips API if mouser_raw_exact.json already exists (re-use cache).

Stage 1  Monte Carlo + Poisson + Markov simulation -> 500 procurement
         orders with 8 PACE-derived anomaly types injected.

Outputs (under ./data/)
    mouser_raw_exact.json              full Mouser API responses
    dataset_<YYYYMMDD_HHMMSS>.xlsx    orders / suppliers / components /
                                       injections / metadata  (5 sheets)
    orders_<YYYYMMDD_HHMMSS>.csv      flat orders table for quick analysis

Each order row contains a 'generated_at' timestamp column.

Run:
    pip install requests openpyxl pandas scipy numpy
    python generate_dataset.py
"""

# ====================================================================
# IMPORTS
# ====================================================================
import json
import math
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

import numpy as np
import pandas as pd
import requests
from openpyxl.utils import get_column_letter
from scipy.stats import truncnorm

# ====================================================================
# MOUSER API
# ====================================================================
MOUSER_API_KEY = os.getenv("MOUSER_API_KEY", "60c27b77-acd6-4043-a91c-428c8ee28aa4")
MOUSER_PARTNUMBER_URL = (
    "https://api.mouser.com/api/v1/search/partnumber?apiKey={key}"
)
API_DELAY_SECONDS = 0.5   # Mouser free tier: 30 req / min

# ====================================================================
# OUTPUT
# ====================================================================
OUTPUT_DIR = Path(__file__).parent / "data"
CSV_DIR    = OUTPUT_DIR / "csv"                           # all CSVs go here
RUN_TS     = datetime.now().strftime("%Y%m%d_%H%M%S")   # e.g. 20260419_153022

# ====================================================================
# THE 10 COMPONENTS (exact Mouser part numbers, confirmed from catalogue)
# ====================================================================
# Fields that cannot come from the API:
#   mouser_pn       exact Mouser part number for /search/partnumber
#   sku             short label used as item_sku in orders
#   category        used for category column in orders
#   qty_median      median purchase quantity (Log-Normal μ anchor)
#   qty_sigma_log   spread of purchase quantity
COMPONENTS_DEF = [
    {
        "mouser_pn":    "603-CFR-25JB-52-10K",
        "sku":          "CFR-25JB-52-10K",
        "category":     "Resistor",
        "qty_median":   100,
        "qty_sigma_log": 0.9,
    },
    {
        "mouser_pn":    "81-GCM21BR71H104KA7L",
        "sku":          "GCM21BR71H104KA7L",
        "category":     "Capacitor",
        "qty_median":   80,
        "qty_sigma_log": 0.9,
    },
    {
        "mouser_pn":    "511-STM32F103C8T6",
        "sku":          "STM32F103C8T6",
        "category":     "IC",
        "qty_median":   8,
        "qty_sigma_log": 0.7,
    },
    {
        "mouser_pn":    "356-ESP32WRM32EN8R2",
        "sku":          "ESP32-WROOM-32E-N8R2",
        "category":     "IC",
        "qty_median":   10,
        "qty_sigma_log": 0.7,
    },
    {
        "mouser_pn":    "358-SC0915",
        "sku":          "SC0915",
        "category":     "DevBoard",
        "qty_median":   5,
        "qty_sigma_log": 0.6,
    },
    {
        "mouser_pn":    "392-101262",
        "sku":          "Soldered-101262",
        "category":     "Sensor",
        "qty_median":   8,
        "qty_sigma_log": 0.7,
    },
    {
        "mouser_pn":    "485-4566",
        "sku":          "AHT20-4566",
        "category":     "Sensor",
        "qty_median":   5,
        "qty_sigma_log": 0.7,
    },
    {
        "mouser_pn":    "262-BME280",
        "sku":          "BME280",
        "category":     "Sensor",
        "qty_median":   8,
        "qty_sigma_log": 0.7,
    },
    {
        "mouser_pn":    "306-B4BXHAMLFSNP",
        "sku":          "B4B-XH-A",
        "category":     "Connector",
        "qty_median":   30,
        "qty_sigma_log": 0.8,
    },
    {
        "mouser_pn":    "590-588",
        "sku":          "MG-588",
        "category":     "PCB",
        "qty_median":   3,
        "qty_sigma_log": 0.6,
    },
]

# ====================================================================
# STAGE 1 SIMULATION PARAMETERS
# ====================================================================
RANDOM_SEED = 42
N_ORDERS    = 500
START_DATE  = date(2024, 1, 1)
END_DATE    = date(2024, 12, 31)

REQUESTERS = [
    {"id": "R-ENG-01", "weight": 0.18},
    {"id": "R-ENG-02", "weight": 0.16},
    {"id": "R-ENG-03", "weight": 0.14},
    {"id": "R-ENG-04", "weight": 0.13},
    {"id": "R-ENG-05", "weight": 0.12},
    {"id": "R-ENG-06", "weight": 0.10},
    {"id": "R-ENG-07", "weight": 0.09},
    {"id": "R-ENG-08", "weight": 0.08},
]

APPROVER_PROC = "A-PROC-01"   # < USD 1,000
APPROVER_CTO  = "A-CTO"       # USD 1,000 – 5,000
APPROVER_CEO  = "A-CEO"       # > USD 5,000

APPROVAL_LAG_MEAN = 2.0
APPROVAL_LAG_STD  = 1.5
APPROVAL_LAG_MIN  = 0.1
APPROVAL_LAG_MAX  = 14.0

CURRENCY_DIST = {"USD": 1.00}   # USD only — no fictional multi-currency split

ANOMALY_TARGETS = {
    "item_spending":        13,
    "vendor_spending":       9,
    "border_value":         11,
    "unusual_vendor":       10,
    "approval_bypass":       8,
    "quote_manipulation":    6,
    "bank_account_change":   9,
    "conflict_of_interest": 10,
}


# ====================================================================
# STAGE 0 — MOUSER EXACT PART NUMBER FETCH
# ====================================================================
class MouserAPIError(RuntimeError):
    pass


def _fetch_exact_pn(mouser_pn: str, api_key: str) -> dict:
    """
    POST to /search/partnumber with partSearchOptions='exact'.
    Returns the first matching Part dict.
    Raises MouserAPIError on failure.
    """
    url     = MOUSER_PARTNUMBER_URL.format(key=api_key)
    payload = {
        "SearchByPartRequest": {
            "mouserPartNumber":  mouser_pn,
            "partSearchOptions": "exact",
        }
    }
    headers = {
        "Content-Type": "application/json",
        "accept":        "application/json",
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
    except requests.RequestException as exc:
        raise MouserAPIError(f"Network error for '{mouser_pn}': {exc}") from exc

    if resp.status_code != 200:
        raise MouserAPIError(
            f"HTTP {resp.status_code} for '{mouser_pn}': {resp.text[:200]}")

    data = resp.json()
    if data.get("Errors"):
        raise MouserAPIError(
            f"API errors for '{mouser_pn}': {data['Errors']}")

    parts = data.get("SearchResults", {}).get("Parts", [])
    if not parts:
        raise MouserAPIError(f"No result for Mouser PN '{mouser_pn}'")
    return parts[0]


def _price_stats(price_breaks: list) -> tuple:
    """
    (geo_mean_usd, sigma_log)  from the PriceBreaks list.
    geo_mean  = e^(mean of ln prices)   <- correct centre for Log-Normal
    sigma_log = (ln max - ln min) / 4   <- 4-sigma rule
    """
    prices = []
    for b in price_breaks:
        cleaned = re.sub(r"[^\d.]", "", str(b.get("Price", "0")))
        p = float(cleaned) if cleaned else 0.0
        if p > 0:
            prices.append(p)
    if not prices:
        raise MouserAPIError("no usable price breaks")
    log_p    = [math.log(p) for p in prices]
    geo      = math.exp(sum(log_p) / len(log_p))
    sigma    = (math.log(max(prices)) - math.log(min(prices))) / 4 \
               if len(prices) >= 2 else 0.15
    sigma    = max(sigma, 0.05)   # floor: price cannot be perfectly fixed
    sigma    = min(sigma, 0.50)   # ceiling: cap extreme spread from 2-point breaks
    return round(geo, 4), round(sigma, 3)


def _lead_days(product: dict) -> int:
    """
    Parse Mouser LeadTime string to integer days.

    All 10 components in COMPONENTS_DEF return the format "NNN Days"
    from the Mouser API (verified in mouser_raw_exact.json):
        126 Days, 114 Days, 210 Days, 120 Days, 112 Days,
        38 Days,  90 Days,  84 Days,  112 Days, 23 Days

    The regex r"(\\d+)\\s*day" captures the real value directly.
    The fallback branches below are kept for robustness only;
    they are NOT triggered by any of the 10 components.
    """
    raw     = str(product.get("LeadTime", ""))
    lower   = raw.lower()
    range_m = re.search(r"(\d+)\s*-\s*(\d+)\s*week", raw, re.IGNORECASE)
    weeks_m = re.search(r"(\d+)\s*week",              raw, re.IGNORECASE)
    days_m  = re.search(r"(\d+)\s*day",               raw, re.IGNORECASE)
    # ── Real data paths (triggered by our 10 components) ──────────
    if range_m:
        return int(round((int(range_m.group(1)) + int(range_m.group(2))) / 2 * 7))
    if weeks_m:
        return int(weeks_m.group(1)) * 7
    if days_m:
        return int(days_m.group(1))   # ← all 10 components land here
    # ── Fallback paths (NOT triggered by our 10 components) ───────
    if "non-stock" in lower or "nonstock" in lower or "call" in lower:
        return 21
    if "stock" in lower:
        return 3
    return 14


def stage0_fetch(api_key: str) -> list:
    """
    Fetch all 10 components from Mouser.
    Returns list of fully-populated component dicts.

    Reproducibility contract:
        mouser_raw_exact.json is an IMMUTABLE research snapshot.
        Once created, every subsequent run reads the same data.
        The file records `_meta.first_fetched_at` so you always
        know when the dataset's price baseline was captured.
        Do NOT delete this file unless you want a new baseline
        (Mouser prices / lead times drift over time).
    """
    cache_path = OUTPUT_DIR / "mouser_raw_exact.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            raw_cache = json.load(f)
        meta   = raw_cache.get("_meta", {})
        stamp  = meta.get("first_fetched_at", "(unknown)")
        n_keys = sum(1 for k in raw_cache if not k.startswith("_"))
        print(f"[Stage 0] Cache found — loaded {n_keys} parts.")
        print(f"          first_fetched_at = {stamp}")
        print(f"          (delete this file only if you want to re-baseline.)")
    else:
        print("[Stage 0] No cache — fetching from Mouser Search API ...")
        raw_cache = {
            "_meta": {
                "first_fetched_at": datetime.now().isoformat(timespec="seconds"),
                "note": "Immutable baseline. Do not overwrite unless re-baselining.",
            }
        }

    components = []
    new_fetches = 0

    for i, defn in enumerate(COMPONENTS_DEF, start=1):
        mpn = defn["mouser_pn"]

        if mpn in raw_cache:
            part = raw_cache[mpn]
            src  = "cache"
        else:
            print(f"  [{i:>2}/{len(COMPONENTS_DEF)}]  {mpn:<28}  fetching ...",
                  end=" ", flush=True)
            part = _fetch_exact_pn(mpn, api_key)
            raw_cache[mpn] = part
            new_fetches += 1
            time.sleep(API_DELAY_SECONDS)
            src = "api"

        geo, sigma = _price_stats(part.get("PriceBreaks", []))
        lead       = _lead_days(part)

        comp = {
            # identity (from COMPONENTS_DEF)
            "mouser_pn":             mpn,
            "sku":                   defn["sku"],
            "category":              defn["category"],
            "qty_median":            defn["qty_median"],
            "qty_sigma_log":         defn["qty_sigma_log"],
            # from Mouser API
            "name":                  part.get("Description", defn["sku"]),
            "manufacturer":          part.get("Manufacturer", ""),
            "manufacturer_pn":       part.get("ManufacturerPartNumber", ""),
            "price_median_usd":      geo,
            "price_sigma_log":       sigma,
            "price_breaks_count":    len(part.get("PriceBreaks", [])),
            "lead_time_median_days": lead,
            "lead_time_sigma_days":  max(2, round(lead * 0.25)),
            "ref_url":               part.get("ProductDetailUrl", ""),
            "price_source":          f"mouser_partnumber_api:{mpn}",
        }
        components.append(comp)
        print(f"  [{i:>2}/{len(COMPONENTS_DEF)}]  {mpn:<28}  "
              f"${geo:>8}  lead={lead:>3}d  [{src}]")

    if new_fetches:
        raw_cache.setdefault("_meta", {})
        raw_cache["_meta"].setdefault(
            "first_fetched_at",
            datetime.now().isoformat(timespec="seconds"))
        raw_cache["_meta"]["last_modified_at"] = \
            datetime.now().isoformat(timespec="seconds")
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(raw_cache, f, indent=2, ensure_ascii=False)
        print(f"  Saved {new_fetches} new response(s) to {cache_path}")

    return components


# ====================================================================
# PARAMETER SUMMARY PRINTER
# ====================================================================
def print_all_parameters(components: list) -> None:
    """
    Print every simulation variable in a structured table so the
    analyst can verify the full parameter set before reading the output.
    """
    W = 72
    print("=" * W)
    print("  SIMULATION PARAMETER REPORT")
    print("=" * W)

    # ── Global ──────────────────────────────────────────────────────
    days = (END_DATE - START_DATE).days + 1
    lam  = N_ORDERS / days
    print("\n[Global Settings]")
    print(f"  RANDOM_SEED      = {RANDOM_SEED}")
    print(f"  N_ORDERS         = {N_ORDERS}")
    print(f"  DATE_RANGE       = {START_DATE} → {END_DATE}  ({days} days)")
    print(f"  Poisson λ        = {N_ORDERS} / {days} = {lam:.4f} orders/day")

    # ── Approval lag ────────────────────────────────────────────────
    print("\n[Approval Lag — Truncated Normal]")
    print(f"  μ  (mean)        = {APPROVAL_LAG_MEAN} days")
    print(f"  σ  (std dev)     = {APPROVAL_LAG_STD} days")
    print(f"  min / max        = {APPROVAL_LAG_MIN} / {APPROVAL_LAG_MAX} days")
    print(f"  μ in ln-space    = n/a  (Normal, not Log-Normal)")

    # ── Approver thresholds ─────────────────────────────────────────
    print("\n[Approver Thresholds]")
    print(f"  < $1,000         → {APPROVER_PROC}")
    print(f"  $1,000 – $5,000  → {APPROVER_CTO}")
    print(f"  > $5,000         → {APPROVER_CEO}")

    # ── Currency ────────────────────────────────────────────────────
    print("\n[Currency Distribution]")
    for cur, p in CURRENCY_DIST.items():
        print(f"  {cur}  = {p*100:.0f}%")

    # ── Requesters ──────────────────────────────────────────────────
    print("\n[Requesters & Weights]")
    for r in REQUESTERS:
        print(f"  {r['id']}   weight = {r['weight']:.2f}  "
              f"(~{r['weight']*N_ORDERS:.0f} orders)")

    # ── Anomaly targets ─────────────────────────────────────────────
    print("\n[Anomaly Injection Targets]")
    total_anom = sum(ANOMALY_TARGETS.values())
    for name, n in ANOMALY_TARGETS.items():
        pct = n / N_ORDERS * 100
        print(f"  {name:<26}  {n:>3} orders  ({pct:.1f}%)")
    print(f"  {'TOTAL':<26}  {total_anom:>3} orders  "
          f"({total_anom/N_ORDERS*100:.1f}%)")

    # ── Component parameters ─────────────────────────────────────────
    print("\n[Component Parameters — from Mouser API + COMPONENTS_DEF]")
    print(f"\n  {'SKU':<24} {'price_median':>12} {'μ_price':>9} "
          f"{'σ_price':>8} {'qty_med':>7} {'σ_qty':>6} "
          f"{'lead_d':>6} {'σ_lead':>6}")
    print("  " + "-" * 82)
    for c in components:
        mu_price = math.log(c["price_median_usd"])
        print(
            f"  {c['sku']:<24}"
            f"  ${c['price_median_usd']:>10.4f}"
            f"  {mu_price:>+8.4f}"
            f"  {c['price_sigma_log']:>7.3f}"
            f"  {c['qty_median']:>7}"
            f"  {c['qty_sigma_log']:>6.2f}"
            f"  {c['lead_time_median_days']:>6}"
            f"  {c['lead_time_sigma_days']:>6}"
        )
    print(f"\n  Column guide:")
    print(f"    price_median  = geo mean from Mouser price breaks  (USD)")
    print(f"    μ_price       = ln(price_median)  — the Normal mean in log space")
    print(f"    σ_price       = (ln(max)-ln(min))/4, clamped [0.05, 0.50]")
    print(f"    qty_med       = median purchase quantity  (Log-Normal μ anchor)")
    print(f"    σ_qty         = qty Log-Normal σ  (manually set in COMPONENTS_DEF)")
    print(f"    lead_d        = lead time median days  (from Mouser LeadTime field)")
    print(f"    σ_lead        = max(2, lead_d × 0.25)  days")
    print("=" * W)


# ====================================================================
# STAGE 1 — SIMULATION
# ====================================================================

# ----- Suppliers -----
def build_suppliers(rng):
    locations = ["Shenzhen", "Dongguan", "Shanghai", "Taipei",
                 "Seoul", "Tokyo", "Bangalore"]
    categories = ["Resistor", "Capacitor", "IC", "PCB",
                  "DevBoard", "Sensor", "Connector"]
    rows = []
    for i in range(1, 26):
        rows.append({
            "supplier_id":      f"S-{i:03d}",
            "name":             f"Supplier {i:03d} Electronics Co.",
            "founded_year":     int(np.clip(rng.normal(2015, 4), 2008, 2022)),
            "location":         str(rng.choice(locations)),
            "primary_category": str(rng.choice(categories)),
            "is_anomaly_pool":  False,
        })
    for i in range(26, 31):
        rows.append({
            "supplier_id":      f"S-{i:03d}",
            "name":             f"Supplier {i:03d} Trading Ltd.",
            "founded_year":     2024,
            "location":         str(rng.choice(locations)),
            "primary_category": str(rng.choice(categories)),
            "is_anomaly_pool":  True,
        })
    return pd.DataFrame(rows)


# ----- Markov-style preferences -----
def build_preferences(suppliers_df, rng):
    """Each requester gets 3 habitual suppliers (0.65 / 0.25 / 0.10)."""
    normal = suppliers_df.loc[
        ~suppliers_df["is_anomaly_pool"], "supplier_id"
    ].tolist()
    prefs = {}
    for r in REQUESTERS:
        chosen = rng.choice(normal, size=3, replace=False)
        prefs[r["id"]] = {
            "primary": str(chosen[0]),
            "secondary": str(chosen[1]),
            "tertiary": str(chosen[2]),
        }
    return prefs


def sample_supplier(requester_id, prefs, rng):
    p = prefs[requester_id]
    r = rng.random()
    if r < 0.65:
        return p["primary"]
    elif r < 0.90:
        return p["secondary"]
    else:
        return p["tertiary"]


# ----- Poisson order dates -----
def order_dates(n, rng):
    total  = (END_DATE - START_DATE).days + 1
    lam    = n / total
    counts = rng.poisson(lam, total).astype(int)
    diff   = n - int(counts.sum())
    if diff > 0:
        for i in rng.integers(0, total, size=diff):
            counts[i] += 1
    elif diff < 0:
        for _ in range(-diff):
            nz = np.where(counts > 0)[0]
            counts[int(rng.choice(nz))] -= 1
    result = []
    for offset, cnt in enumerate(counts):
        for _ in range(int(cnt)):
            result.append(START_DATE + timedelta(days=int(offset)))
    return result


# ----- Monte Carlo samplers -----
def pick_component(rng, components):
    return components[int(rng.integers(0, len(components)))]


def sample_qty(comp, rng):
    return max(1, int(rng.lognormal(
        np.log(comp["qty_median"]), comp["qty_sigma_log"])))


def sample_price(comp, rng):
    return float(rng.lognormal(
        np.log(comp["price_median_usd"]), comp["price_sigma_log"]))


def sample_approval_lag(rng):
    a = (APPROVAL_LAG_MIN - APPROVAL_LAG_MEAN) / APPROVAL_LAG_STD
    b = (APPROVAL_LAG_MAX - APPROVAL_LAG_MEAN) / APPROVAL_LAG_STD
    return float(truncnorm.rvs(a, b,
                               loc=APPROVAL_LAG_MEAN,
                               scale=APPROVAL_LAG_STD,
                               random_state=rng))


def sample_delivery_lag(comp, rng):
    mean = comp["lead_time_median_days"]
    std  = comp["lead_time_sigma_days"]
    low  = max(2, mean - 2 * std)
    high = mean + 3 * std
    a    = (low  - mean) / std
    b    = (high - mean) / std
    return int(truncnorm.rvs(a, b, loc=mean, scale=std, random_state=rng))


def sample_currency(rng):
    r, cum = rng.random(), 0.0
    for cur, prob in CURRENCY_DIST.items():
        cum += prob
        if r < cum:
            return cur
    return "USD"


def decide_approver(amount):
    if amount < 1000:
        return APPROVER_PROC
    elif amount < 5000:
        return APPROVER_CTO
    else:
        return APPROVER_CEO


# ----- Order generation -----
def generate_orders(components, suppliers_df, prefs, rng):
    req_ids     = [r["id"]     for r in REQUESTERS]
    req_weights = np.array([r["weight"] for r in REQUESTERS])
    dates       = order_dates(N_ORDERS, rng)
    batch_generated_at = datetime.now().isoformat()

    rows = []
    for i, d in enumerate(dates):
        req        = str(rng.choice(req_ids, p=req_weights))
        supplier   = sample_supplier(req, prefs, rng)
        comp       = pick_component(rng, components)
        qty        = sample_qty(comp, rng)
        unit_price = sample_price(comp, rng)
        currency   = sample_currency(rng)
        total_usd  = qty * unit_price
        approver   = decide_approver(total_usd)
        appr_lag   = sample_approval_lag(rng)
        appr_dt    = pd.Timestamp(d) + pd.Timedelta(days=appr_lag)
        del_lag    = sample_delivery_lag(comp, rng)
        exp_dt     = appr_dt + pd.Timedelta(days=del_lag)

        rows.append({
            "po_id":                      f"PO-2024-{i+1:04d}",
            "batch_generated_at":         batch_generated_at,
            "requester_id":               req,
            "approver_id":                approver,
            "supplier_id":                supplier,
            "created_date":               d.isoformat(),
            "approval_lag_days":          round(appr_lag, 3),
            "approved_date":              appr_dt.isoformat(),
            "expected_delivery_lag_days": del_lag,
            "expected_delivery_date":     exp_dt.date().isoformat(),
            "item_category":              comp["category"],
            "item_sku":                   comp["sku"],
            "item_description":           comp["name"],
            "quantity":                   qty,
            "unit_price_usd":             round(unit_price, 4),
            "total_amount_usd":           round(total_usd, 2),
            "currency":                   currency,
            "purchase_note":              "",    # filled in Stage 2
            "supplier_profile":           "",    # filled in Stage 2
            "injection_plan":             "none",
            "injection_seed":             -1,
        })
    return pd.DataFrame(rows)


# ----- Anomaly injection -----
def eligible(orders_df, indicator, used):
    avail = orders_df[~orders_df.index.isin(used)]
    if indicator == "border_value":
        return avail[(avail["unit_price_usd"] >= 1.0) &
                     (avail["unit_price_usd"] <= 100.0)].index.tolist()
    if indicator in ("vendor_spending", "unusual_vendor",
                     "conflict_of_interest"):
        normal = {f"S-{i:03d}" for i in range(1, 26)}
        return avail[avail["supplier_id"].isin(normal)].index.tolist()
    return avail.index.tolist()


def apply_anomaly(df, idx, indicator, suppliers_df, rng):
    if indicator == "item_spending":
        mult = float(rng.uniform(2.5, 4.0))
        new_p = df.at[idx, "unit_price_usd"] * mult
        df.at[idx, "unit_price_usd"]   = round(new_p, 4)
        df.at[idx, "total_amount_usd"] = round(df.at[idx, "quantity"] * new_p, 2)
        df.at[idx, "approver_id"]      = decide_approver(df.at[idx, "total_amount_usd"])

    elif indicator == "border_value":
        up = df.at[idx, "unit_price_usd"]
        target = float(rng.uniform(950, 999) if rng.random() < 0.5
                       else rng.uniform(4750, 4999))
        new_qty   = max(1, int(target / up))
        new_total = round(new_qty * up, 2)
        df.at[idx, "quantity"]         = new_qty
        df.at[idx, "total_amount_usd"] = new_total
        df.at[idx, "approver_id"]      = decide_approver(new_total)

    elif indicator == "unusual_vendor":
        pool = suppliers_df.loc[suppliers_df["is_anomaly_pool"],
                                "supplier_id"].tolist()
        df.at[idx, "supplier_id"] = str(rng.choice(pool))

    elif indicator == "approval_bypass":
        if rng.random() < 0.5:
            df.at[idx, "approver_id"] = ""   # empty = no approver assigned
            if df.at[idx, "total_amount_usd"] < 1000:
                up   = df.at[idx, "unit_price_usd"]
                nq   = max(1, int(1500 / up))
                df.at[idx, "quantity"]         = nq
                df.at[idx, "total_amount_usd"] = round(nq * up, 2)
        else:
            lag = float(rng.uniform(0.01, 0.09))
            df.at[idx, "approval_lag_days"] = round(lag, 3)
            df.at[idx, "approved_date"]     = (
                pd.Timestamp(df.at[idx, "created_date"])
                + pd.Timedelta(days=lag)).isoformat()

    elif indicator == "bank_account_change":
        if df.at[idx, "total_amount_usd"] < 2000:
            up  = df.at[idx, "unit_price_usd"]
            nq  = max(1, int(2500 / up))
            tot = round(nq * up, 2)
            df.at[idx, "quantity"]         = nq
            df.at[idx, "total_amount_usd"] = tot
            df.at[idx, "approver_id"]      = decide_approver(tot)

    elif indicator == "conflict_of_interest":
        pool = suppliers_df.loc[suppliers_df["is_anomaly_pool"],
                                "supplier_id"].tolist()
        df.at[idx, "supplier_id"] = str(rng.choice(pool))

    # vendor_spending and quote_manipulation are cross-order / semantic;
    # they are flagged here and processed in Stage 3.


def inject_anomalies(orders_df, suppliers_df, rng):
    log, used = [], set()
    for indicator, target in ANOMALY_TARGETS.items():
        pool = eligible(orders_df, indicator, used)
        if len(pool) < target:
            print(f"  WARNING: {indicator} needs {target}, "
                  f"only {len(pool)} eligible.")
            target = len(pool)
        arr = np.array(pool)
        rng.shuffle(arr)
        for idx in arr[:target].tolist():
            seed = int(rng.integers(0, 1_000_000))
            apply_anomaly(orders_df, idx, indicator, suppliers_df, rng)
            orders_df.at[idx, "injection_plan"] = indicator
            orders_df.at[idx, "injection_seed"] = seed
            used.add(idx)
            log.append({
                "po_id":     orders_df.at[idx, "po_id"],
                "indicator": indicator,
                "seed":      seed,
            })
    return log


# ====================================================================
# OUTPUT
# ====================================================================
def auto_fit_columns(ws, df, max_width=60):
    for col_idx, col_name in enumerate(df.columns, start=1):
        values  = df[col_name].fillna("").astype(str)
        longest = max(len(str(col_name)), values.str.len().max() or 0)
        ws.column_dimensions[get_column_letter(col_idx)].width = min(
            longest + 2, max_width)


def flatten_meta(d: dict) -> pd.DataFrame:
    rows = []
    for k, v in d.items():
        if isinstance(v, dict):
            for sk, sv in v.items():
                rows.append({"key": f"{k}.{sk}", "value": sv})
        else:
            rows.append({"key": k, "value": v})
    return pd.DataFrame(rows)


def save_outputs(orders_df, suppliers_df, components, log):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)

    comp_df = pd.DataFrame(components)

    # read cache fingerprint so the dataset version is traceable
    cache_meta = {}
    try:
        with open(OUTPUT_DIR / "mouser_raw_exact.json", "r", encoding="utf-8") as f:
            cache_meta = json.load(f).get("_meta", {})
    except Exception:
        pass

    metadata = {
        "generated_at":             RUN_TS,
        "random_seed":              RANDOM_SEED,
        "n_orders":                 N_ORDERS,
        "start_date":               START_DATE.isoformat(),
        "end_date":                 END_DATE.isoformat(),
        "components_count":         len(components),
        "suppliers_count":          int(len(suppliers_df)),
        "anomaly_targets":          ANOMALY_TARGETS,
        "total_anomalies_injected": sum(ANOMALY_TARGETS.values()),
        "price_source":             "mouser_partnumber_api",
        "mouser_first_fetched_at":  cache_meta.get("first_fetched_at", "(unknown)"),
        "mouser_last_modified_at":  cache_meta.get("last_modified_at", "(unchanged)"),
    }

    # ---- CSV (orders only, kept in data/csv/ subfolder) ----
    csv_path = CSV_DIR / f"orders_{RUN_TS}.csv"
    orders_df.to_csv(csv_path, index=False, encoding="utf-8")

    # ---- Excel (all sheets) ----
    xlsx_path = OUTPUT_DIR / f"dataset_{RUN_TS}.xlsx"
    sheets = [
        ("orders",      orders_df),
        ("suppliers",   suppliers_df),
        ("components",  comp_df),
        ("injections",  pd.DataFrame(log)),
        ("metadata",    flatten_meta(metadata)),
    ]
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for name, df in sheets:
            df.to_excel(writer, sheet_name=name,
                        index=False, freeze_panes=(1, 0))
            auto_fit_columns(writer.sheets[name], df)

    print(f"\n  CSV   : {csv_path}")
    print(f"  Excel : {xlsx_path}")
    return xlsx_path


# ====================================================================
# MAIN
# ====================================================================
def main():
    print("=" * 72)
    print(f"ABC Electronics Ltd. — Dataset Pipeline  [{RUN_TS}]")
    print("=" * 72)

    # Stage 0: get real prices
    components = stage0_fetch(MOUSER_API_KEY)
    print(f"\n  Loaded {len(components)} components.\n")

    # Print every parameter so analyst can verify before reading the output
    print_all_parameters(components)
    print()

    rng = np.random.default_rng(RANDOM_SEED)

    print("[1/4] Building 30 suppliers ...")
    suppliers_df = build_suppliers(rng)

    print("[2/4] Pre-assigning requester-supplier preferences ...")
    prefs = build_preferences(suppliers_df, rng)

    print(f"[3/4] Generating {N_ORDERS} orders (Monte Carlo + Poisson) ...")
    orders_df = generate_orders(components, suppliers_df, prefs, rng)

    print(f"[4/4] Injecting {sum(ANOMALY_TARGETS.values())} anomalies ...")
    log = inject_anomalies(orders_df, suppliers_df, rng)

    print("\nWriting outputs ...")
    save_outputs(orders_df, suppliers_df, components, log)

    print("\n" + "-" * 72)
    print("DONE.")
    print(f"  orders            : {N_ORDERS}")
    print(f"  anomalies injected: {sum(ANOMALY_TARGETS.values())}")
    print("\n  injection_plan distribution:")
    for k, v in orders_df["injection_plan"].value_counts().to_dict().items():
        print(f"    {k:<26}  {v:>4d}")
    print("\n  category distribution:")
    for k, v in orders_df["item_category"].value_counts().to_dict().items():
        print(f"    {k:<26}  {v:>4d}")
    print("\n  total_amount_usd stats:")
    print(orders_df["total_amount_usd"].describe().to_string())
    print("\nNext: generate_semantics.py (Stage 2, deepseek-chat).")


if __name__ == "__main__":
    try:
        main()
    except MouserAPIError as exc:
        print(f"\n*** Mouser API error: {exc}")
        raise SystemExit(1)
