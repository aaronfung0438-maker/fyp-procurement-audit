"""
generate_semantics.py
====================================================================
ABC Electronics Ltd. — Stage 2: Semantic Field Filler

Reads the latest Stage 1 output (orders_<TS>.csv) and uses
DeepSeek (deepseek-chat) to fill two empty columns:

    purchase_note      one-line internal note about the purchase
    supplier_profile   short supplier description from buyer's view

Output: orders_stage2_<TS>.csv  (same row order, same po_id)

Design notes
------------
* Normal rows (injection_plan == "none") get neutral, plausible text.
* Anomaly rows get text that subtly hints at the PACE indicator
  (so a downstream LLM auditor has a chance to spot it).
* Resumes automatically: if orders_stage2_<TS>.csv already exists,
  rows whose purchase_note is non-empty are skipped.
* Saves to disk every SAVE_EVERY rows so a crash never wipes progress.
* DeepSeek API key is read from the env var DEEPSEEK_API_KEY
  (loaded from dataset/.env via python-dotenv if available).

Run:
    pip install -r requirements.txt
    python dataset\\generate_semantics.py
    # or specify a different input file:
    python dataset\\generate_semantics.py --input data\\orders_20260420_015519.csv
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

import pandas as pd
import requests
from openpyxl.utils import get_column_letter

# ====================================================================
# CONFIG
# ====================================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL     = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL   = "deepseek-chat"

DATA_DIR    = Path(__file__).parent / "data"
CSV_DIR     = DATA_DIR / "csv"          # all CSV checkpoints go here
SAVE_EVERY  = 10        # checkpoint to disk every N rows
MAX_RETRIES = 3         # per row, on transient API failure
API_TIMEOUT = 30        # seconds
TEMPERATURE = 0.7       # mild creativity, still controlled
LANGUAGE    = "English" # change to "Traditional Chinese" if needed

# ====================================================================
# PACE ANOMALY HINTS  (used only for anomaly rows)
# ====================================================================
# Each hint tells the LLM what kind of subtle clue to weave into the
# purchase_note / supplier_profile so that a downstream auditor model
# has linguistic evidence (not only numerical) to detect the anomaly.
PACE_HINTS = {
    "item_spending":
        "Pricing seems higher than usual for this part; the requester "
        "argues urgency or a 'premium grade' justifies it.",
    "vendor_spending":
        "This is yet another order to the same supplier this quarter; "
        "the buyer mentions a long-standing relationship.",
    "border_value":
        "Total is conveniently just under the next approval tier; the "
        "note hints at splitting or careful sizing to avoid escalation.",
    "unusual_vendor":
        "Supplier is a recent or unfamiliar vendor; profile reads as a "
        "newly-onboarded trading company with little track record.",
    "approval_bypass":
        "Note is terse and operational, no approver mentioned, treated "
        "as an internal/expedited transaction.",
    "quote_manipulation":
        "Mentions a single quote received or that a competing quote was "
        "withdrawn; phrasing slightly defensive.",
    "bank_account_change":
        "Note flags that the supplier recently updated banking details "
        "and asked to wire to a different account.",
    "conflict_of_interest":
        "Supplier profile hints at a personal or prior employment link "
        "with the requester (e.g. 'recommended by R-ENG-...').",
}

# ====================================================================
# PROMPT BUILDER
# ====================================================================
SYSTEM_PROMPT = (
    "You write concise, realistic procurement notes for an internal ERP "
    "system at a small Hong Kong IoT hardware company (ABC Electronics Ltd.). "
    "Always reply with a SINGLE JSON object using exactly the keys "
    "'purchase_note' and 'supplier_profile'. No prose outside JSON, no markdown. "
    f"Write in {LANGUAGE}. Each value should be ONE short sentence "
    "(20-40 words), written from the buyer's point of view, plausible "
    "and matter-of-fact."
)


def build_user_prompt(row: pd.Series) -> str:
    """Build the per-row prompt. Anomaly rows get an extra HINT line."""
    base = (
        f"Order: {row['po_id']}\n"
        f"Item:  {row['item_sku']}  ({row['item_category']})\n"
        f"Desc:  {row['item_description']}\n"
        f"Qty x Unit = {row['quantity']} x ${row['unit_price_usd']:.4f} "
        f"= ${row['total_amount_usd']:.2f} {row['currency']}\n"
        f"Requester: {row['requester_id']}\n"
        f"Approver:  {row['approver_id'] or '(none)'}\n"
        f"Supplier:  {row['supplier_id']}\n"
        f"Approval lag: {row['approval_lag_days']} days   "
        f"Lead time: {row['expected_delivery_lag_days']} days"
    )
    plan = str(row.get("injection_plan", "none"))
    if plan != "none" and plan in PACE_HINTS:
        base += (
            f"\n\nINTERNAL HINT (do NOT mention explicitly, just weave "
            f"into tone): {PACE_HINTS[plan]}"
        )
    base += (
        "\n\nReturn JSON: "
        '{"purchase_note": "...", "supplier_profile": "..."}'
    )
    return base


# ====================================================================
# DEEPSEEK CALL
# ====================================================================
class DeepSeekError(RuntimeError):
    pass


def call_deepseek(user_prompt: str) -> dict:
    """One API call. Returns parsed JSON dict with the two keys."""
    if not DEEPSEEK_API_KEY:
        raise DeepSeekError(
            "DEEPSEEK_API_KEY not set. Put it in dataset/.env or as env var.")

    payload = {
        "model": DEEPSEEK_MODEL,
        "temperature": TEMPERATURE,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type":  "application/json",
    }

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(DEEPSEEK_URL, headers=headers,
                                 json=payload, timeout=API_TIMEOUT)
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                time.sleep(1.5 * attempt)
                continue
            data    = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed  = json.loads(content)
            if "purchase_note" not in parsed or "supplier_profile" not in parsed:
                raise DeepSeekError(f"missing keys in: {parsed}")
            return {
                "purchase_note":    str(parsed["purchase_note"]).strip(),
                "supplier_profile": str(parsed["supplier_profile"]).strip(),
            }
        except (requests.RequestException, json.JSONDecodeError) as exc:
            last_err = str(exc)
            time.sleep(1.5 * attempt)
    raise DeepSeekError(f"failed after {MAX_RETRIES} attempts: {last_err}")


# ====================================================================
# I/O HELPERS
# ====================================================================
def find_latest_orders_csv() -> Path:
    candidates = sorted(DATA_DIR.glob("orders_*.csv"))
    candidates = [c for c in candidates if "stage2" not in c.name]
    if not candidates:
        raise FileNotFoundError(
            f"No orders_*.csv found in {DATA_DIR}. Run generate_dataset.py first.")
    return candidates[-1]


def find_latest_stage2_csv() -> Path | None:
    """Return the latest stage2 CSV from data/csv/ (preferred) or data/."""
    in_csv = sorted(CSV_DIR.glob("orders_stage2_*.csv")) if CSV_DIR.exists() else []
    in_data = sorted(DATA_DIR.glob("orders_stage2_*.csv"))
    all_c = sorted(set(in_csv + in_data), key=lambda p: p.name)
    return all_c[-1] if all_c else None


def output_path_for(input_csv: Path) -> tuple[Path, Path]:
    """orders_<TS>.csv  →  (data/csv/orders_stage2_<TS>.csv, data/orders_stage2_<TS>.xlsx)"""
    m = re.search(r"orders_(\d{8}_\d{6})\.csv$", input_csv.name)
    ts = m.group(1) if m else datetime.now().strftime("%Y%m%d_%H%M%S")
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    return (
        CSV_DIR  / f"orders_stage2_{ts}.csv",
        DATA_DIR / f"orders_stage2_{ts}.xlsx",
    )


def auto_fit_columns(ws, df: pd.DataFrame, max_width: int = 60) -> None:
    for col_idx, col_name in enumerate(df.columns, start=1):
        values  = df[col_name].fillna("").astype(str)
        longest = max(len(str(col_name)), values.str.len().max() or 0)
        ws.column_dimensions[get_column_letter(col_idx)].width = min(
            longest + 2, max_width)


def save_excel(df: pd.DataFrame, xlsx_path: Path) -> None:
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="orders_stage2",
                    index=False, freeze_panes=(1, 0))
        auto_fit_columns(writer.sheets["orders_stage2"], df)
    print(f"  Excel : {xlsx_path.name}")


def load_or_init_output(input_csv: Path, out_csv: Path) -> pd.DataFrame:
    """Load resume file if present, else copy input."""
    if out_csv.exists():
        df = pd.read_csv(out_csv)
        print(f"  Resuming from existing  {out_csv.name}")
    else:
        df = pd.read_csv(input_csv)

    for col in ("purchase_note", "supplier_profile",
                "purchase_note_human", "supplier_profile_human"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("")
    return df


# ====================================================================
# MAIN LOOP
# ====================================================================
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=str, default=None,
                   help="Path to orders_<TS>.csv (default: latest in data/)")
    p.add_argument("--limit", type=int, default=None,
                   help="Process only first N pending rows (debug).")
    p.add_argument("--to-excel", action="store_true",
                   help="Convert existing stage2 CSV → Excel only, no API calls.")
    args = p.parse_args()

    # ── Quick CSV → Excel mode (no API) ──────────────────────────────
    if args.to_excel:
        if args.input:
            src = Path(args.input)
        else:
            # search both data/ and data/csv/
            candidates = sorted(DATA_DIR.glob("orders_stage2_*.csv")) + \
                         sorted(CSV_DIR.glob("orders_stage2_*.csv") if CSV_DIR.exists() else [])
            candidates = sorted(set(candidates), key=lambda p: p.name)
            if not candidates:
                print("No orders_stage2_*.csv found. Run without --to-excel first.")
                sys.exit(1)
            src = candidates[-1]

        m   = re.search(r"orders_stage2_(\d{8}_\d{6})\.csv$", src.name)
        ts  = m.group(1) if m else datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = DATA_DIR / f"orders_stage2_{ts}.xlsx"

        print(f"  Reading : {src}")
        df_conv = pd.read_csv(src)

        # ensure human columns exist (even if CSV was created before this change)
        for col in ("purchase_note_human", "supplier_profile_human"):
            if col not in df_conv.columns:
                df_conv[col] = ""
            df_conv[col] = df_conv[col].fillna("")

        save_excel(df_conv, dst)
        print(f"  Done.")
        return

    input_csv          = Path(args.input) if args.input else find_latest_orders_csv()
    out_csv, out_xlsx  = output_path_for(input_csv)

    print("=" * 72)
    print(f"Stage 2 — Semantic Filler   model={DEEPSEEK_MODEL}   lang={LANGUAGE}")
    print("=" * 72)
    print(f"  Input  : {input_csv.name}")
    print(f"  Output : {out_csv.name}")
    print(f"  Excel  : {out_xlsx.name}")

    df = load_or_init_output(input_csv, out_csv)

    pending = df[df["purchase_note"].astype(str).str.strip() == ""].index.tolist()
    if args.limit:
        pending = pending[: args.limit]
    print(f"  Total rows   : {len(df)}")
    print(f"  Already done : {len(df) - len(pending)}")
    print(f"  Pending      : {len(pending)}")
    if not pending:
        print("\n  Nothing to do.")
        return

    done = 0
    failed = []
    t0 = time.time()
    for idx in pending:
        row    = df.loc[idx]
        prompt = build_user_prompt(row)
        try:
            result = call_deepseek(prompt)
        except DeepSeekError as exc:
            failed.append((row["po_id"], str(exc)))
            print(f"  [FAIL] {row['po_id']}: {exc}")
            continue

        df.at[idx, "purchase_note"]    = result["purchase_note"]
        df.at[idx, "supplier_profile"] = result["supplier_profile"]
        done += 1

        plan = row["injection_plan"]
        tag  = "  " if plan == "none" else f" [{plan}]"
        print(f"  [{done:>3}/{len(pending)}] {row['po_id']}{tag}  ok")

        if done % SAVE_EVERY == 0:
            df.to_csv(out_csv, index=False, encoding="utf-8")
            save_excel(df, out_xlsx)
            elapsed = time.time() - t0
            rate    = done / max(elapsed, 1e-3)
            eta     = (len(pending) - done) / max(rate, 1e-3)
            print(f"  -- checkpoint saved  ({done} rows, "
                  f"{rate:.2f} rows/s, ETA {eta/60:.1f} min) --")

    df.to_csv(out_csv, index=False, encoding="utf-8")
    save_excel(df, out_xlsx)

    print("\n" + "-" * 72)
    print(f"DONE.  filled = {done}   failed = {len(failed)}")
    print(f"  CSV   : {out_csv}")
    print(f"  Excel : {out_xlsx}")
    if failed:
        print("\n  Failed rows (re-run will retry them):")
        for po, err in failed:
            print(f"    {po}  ::  {err[:120]}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Partial output already saved to disk.")
        sys.exit(130)
