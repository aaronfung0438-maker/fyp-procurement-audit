"""
Stage 4b -- Pre-generate frozen G2 verdicts and G3 evidence for experiment / practice questions.

Purpose:
    During the live experiment, participants see pre-generated LLM output rather than
    waiting for a live model call. This removes network latency, LLM stochasticity, and
    Ollama availability from the participant experience.

Inputs:
    data/stage3/experiment_32qs_<TS>.xlsx   -- 32 experiment questions (UI-safe; default)
    data/stage3/practice_2qs_<TS>.xlsx      -- 2 practice questions (pass via --exp-input + --label practice)
    data/stage1/dataset_<TS>.xlsx           -- Stage-1 workbook (for the `components` sheet)
    data/chroma/                            -- Chroma vector store (built by build_rag.py)

Outputs (all written to data/stage4/):
    g2_verdicts_<label>_<TS>.json       {po_id: {"judgment": "suspicious"|"normal", "reason": "..."}}
    g3_evidence_<label>_<TS>.json       {po_id: {"noteworthy_features": [{...} x4]}}
    shadow_g2_for_g3_<label>_<TS>.json  Shadow G2 call made alongside G3; used to compute AOR later.
                                        Never shown to participants.
    generation_log_<label>_<TS>.json    Per-question detail: retries, latency, success flags.

    Default <label> = "exp" (32-question experiment set).
    Use --label practice when freezing the 2-question practice set.

Design notes:
    G2 (conclusion condition):  LLM outputs a verdict + one-sentence reason.
                                Participant sees "AI says: suspicious/normal because ..."
    G3 (evidence condition):    LLM outputs 4 structured noteworthy features without a
                                verdict. Each feature may be a deviation from typical
                                patterns OR a confirming observation that the order
                                looks routine. Participant sees the 4-row feature
                                table and reaches their own verdict.
    Both conditions receive identical context:
        - Raw order fields (from experiment_32qs_*.xlsx, no Section E features)
        - SKU Mouser anchor values (price_median_usd, qty_median, lead_time_median_days)
          from the `components` sheet -- these are public market data, NOT pre-computed ratios.
        - Top-5 RAG-retrieved historical orders from Chroma (corpus = 466 sanitized orders).
    Pre-computed Section E ratios / z-scores are excluded; the LLM must reason from raw
    values + RAG only. Section E remains visible to humans via the UI layer.

Dependencies:
    pip install chromadb pandas openpyxl requests
    ollama pull nomic-embed-text qwen3:8b
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
import pandas as pd
import requests
from chromadb.utils import embedding_functions

# ── Constants ─────────────────────────────────────────────────────────────────
OLLAMA_BASE    = "http://localhost:11434"
EMBED_MODEL    = "nomic-embed-text"
ANALYSIS_MODEL = "qwen3:8b"     # main analysis model (Test A setting)
COLLECTION_NAME = "po_history"
RAG_TOP_K      = 5              # similar historical orders retrieved per question
TEMPERATURE    = 0.0            # zero temperature for deterministic frozen output
MAX_RETRIES    = 3              # max LLM retries per question per output type

BASE_DIR   = Path(__file__).parent.parent / "dataset"
STAGE3_DIR = BASE_DIR / "data" / "stage3"
STAGE4_DIR = BASE_DIR / "data" / "stage4"
CHROMA_DIR = BASE_DIR / "data" / "chroma"

# Words that must not appear in any LLM output.
# Prevents the model from revealing its internal framework or producing
# probability-style language that would break the G2/G3 manipulation.
FORBIDDEN_WORDS = {
    "fraud", "anomaly probability", "anomaly score",
    "recommend", "conclude", "likely fraud",
    "PACE", "injection", "rubric",
    "Mahalanobis", "z-score",
}

# Neutral fallback used when an LLM output cannot be salvaged after MAX_RETRIES.
# The website MUST be able to load every PO id in the JSON, so we always emit
# a record per question. The `_fallback` flag lets downstream analysis exclude
# these from RQ accuracy calculations (or treat them as a separate failure
# category, depending on the analysis plan).
G2_FALLBACK = {
    "judgment": "normal",
    "reason":   "AI inference unavailable for this order; please review using the order details only.",
    "_fallback": True,
}
G3_FALLBACK = {
    "noteworthy_features": [
        {
            "feature":         f"Observation {i}",
            "current_value":   "(unavailable)",
            "reference_value": "(unavailable)",
            "why_noteworthy":  "AI inference unavailable for this order; please review using the order details only.",
        }
        for i in range(1, 5)
    ],
    "_fallback": True,
}


# ── Ollama API ─────────────────────────────────────────────────────────────────
def ollama_chat(
    messages: list[dict],
    model: str = ANALYSIS_MODEL,
    temperature: float = TEMPERATURE,
    timeout: int = 900,
) -> str:
    """Call the Ollama /api/chat endpoint and return the response text.

    Design choice (do NOT disable thinking):
    - Qwen3-8B's reasoning capability lives in its <think>...</think> chain.
      Disabling it would degrade the model to ~4B-quality output, undermining
      the validity of G2/G3 conditions in the experiment.
    - We instead size token budgets generously so reasoning + JSON both fit:
        num_ctx     : 16384  (system + order card + 5 RAG docs + reasoning + JSON)
        num_predict : 12288  (think chain can balloon when the model has to
                              "manufacture" suspicions on a benign order, so
                              ~9k tokens reasoning + ~1.5k JSON + headroom)
    - <think> blocks are stripped post-hoc by `strip_thinking()` before JSON
      parsing, so the frozen JSON output remains clean for the website.
    """
    payload = {
        "model":    model,
        "messages": messages,
        "stream":   False,
        "options":  {
            "temperature": temperature,
            "num_predict": 12288,
            "num_ctx":     16384,
        },
    }
    resp = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


# ── Text utilities ─────────────────────────────────────────────────────────────
def strip_thinking(text: str) -> str:
    """Remove Qwen3 <think>...</think> reasoning blocks robustly.

    Handles three cases:
    1. Complete block: <think>...</think>  ->  remove the whole block.
    2. Closing tag only (no opening): leftover content before `</think>` is
       reasoning that should be dropped; keep only what follows.
    3. Opening tag only (no closing, e.g. truncated output): drop everything
       from <think> onwards (no JSON answer was emitted).
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    text = re.sub(r"<think>.*$", "", text, flags=re.DOTALL)
    return text.strip()


def extract_json_obj(text: str) -> dict:
    """Extract the JSON object from an LLM response (after stripping <think> blocks)."""
    text = strip_thinking(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # The actual JSON is typically the LAST {...} block (after any prose lead-in).
    # Use a non-greedy match anchored on balanced braces by trying the largest
    # `{...}` first, then falling back to the first one.
    candidates = re.findall(r"\{.*?\}", text, re.DOTALL)
    candidates += re.findall(r"\{.*\}",  text, re.DOTALL)
    for c in reversed(candidates):
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"No valid JSON object found in response:\n{text[:600]}")


def contains_forbidden(text: str) -> list[str]:
    """Return list of forbidden words found in text (empty list = clean)."""
    lower = text.lower()
    return [w for w in FORBIDDEN_WORDS if w.lower() in lower]


# ── Schema validation ──────────────────────────────────────────────────────────
def validate_g2(obj: dict) -> None:
    """G2 must have: judgment in {suspicious, normal}, non-empty reason."""
    if "judgment" not in obj:
        raise ValueError("G2 missing 'judgment' field")
    if obj["judgment"] not in ("suspicious", "normal"):
        raise ValueError(f"G2 judgment must be 'suspicious' or 'normal', got: {obj['judgment']!r}")
    if not str(obj.get("reason", "")).strip():
        raise ValueError("G2 missing non-empty 'reason' field")
    bad = contains_forbidden(json.dumps(obj))
    if bad:
        raise ValueError(f"G2 output contains forbidden words: {bad}")


def validate_g3(obj: dict) -> None:
    """G3 must have: noteworthy_features list with exactly 4 items, each with 4 sub-fields.

    Each `why_noteworthy` string must be 5-25 words to prevent the implicit-
    confidence-signal problem documented for G2 reasons (longer text reading
    as higher AI confidence). 25w is a generous upper bound that still keeps
    the field roughly one sentence and visually uniform across 4 features.
    """
    if "noteworthy_features" not in obj:
        raise ValueError("G3 missing 'noteworthy_features' field")
    feats = obj["noteworthy_features"]
    if not isinstance(feats, list):
        raise ValueError("G3 noteworthy_features must be a list")
    if len(feats) != 4:
        raise ValueError(f"G3 requires exactly 4 features, got {len(feats)}")
    required = {"feature", "current_value", "reference_value", "why_noteworthy"}
    for i, feat in enumerate(feats):
        missing = required - set(feat.keys())
        if missing:
            raise ValueError(f"G3 feature {i+1} missing sub-fields: {missing}")
        for k, v in feat.items():
            if not str(v).strip():
                raise ValueError(f"G3 feature {i+1} has empty '{k}'")
        wn_words = len(str(feat["why_noteworthy"]).split())
        if not 5 <= wn_words <= 25:
            raise ValueError(
                f"G3 feature {i+1} 'why_noteworthy' has {wn_words} words; "
                f"required 5-25 words to prevent length-as-confidence leakage"
            )
    bad = contains_forbidden(json.dumps(obj))
    if bad:
        raise ValueError(f"G3 output contains forbidden words: {bad}")


# ── Order card formatting ──────────────────────────────────────────────────────
def fmt_date(val: Any) -> str:
    if pd.isna(val) or val is None:
        return "(unknown)"
    try:
        return pd.Timestamp(val).strftime("%Y-%m-%d")
    except Exception:
        return str(val)


def build_order_card(row: pd.Series, comp_ref: dict | None = None) -> str:
    """Format one order row as a structured text block for the LLM prompt.

    comp_ref holds the SKU-level Mouser anchor values (price_median_usd,
    qty_median, lead_time_median_days). These are public market data used
    as reference points; the LLM still judges whether the current values
    are unusual rather than receiving a pre-computed ratio.
    """
    approver = str(row.get("approver_id") or "(none)")
    note     = str(row.get("purchase_note_human") or row.get("purchase_note") or "").strip() or "(none)"
    profile  = str(row.get("supplier_profile_human") or row.get("supplier_profile") or "").strip() or "(none)"

    lines = [
        "== Purchase Order ==",
        f"PO ID           : {row['po_id']}",
        f"Date            : {fmt_date(row['created_date'])}",
        f"Requester       : {row['requester_id']}",
        f"Approver        : {approver}",
        f"Supplier        : {row['supplier_id']}",
        f"SKU             : {row['item_sku']} ({row['item_category']})",
        f"Description     : {row.get('item_description', '')}",
        f"Quantity        : {int(row['quantity'])}",
        f"Unit price      : ${float(row['unit_price_usd']):.4f}",
        f"Total amount    : ${float(row['total_amount_usd']):.2f}",
        f"Approval lag    : {float(row['approval_lag_days']):.2f} days",
        f"Delivery lag    : {int(row['expected_delivery_lag_days'])} days (expected)",
        f"Purchase note   : {note}",
        f"Supplier profile: {profile}",
    ]

    if comp_ref:
        lines += [
            "",
            "== SKU Market Reference (Mouser public data) ==",
            f"Typical unit price : ${comp_ref['price_median_usd']:.4f}",
            f"Typical order qty  : {comp_ref['qty_median']}",
            f"Typical lead time  : {comp_ref['lead_time_median_days']} days",
        ]

    return "\n".join(lines)


def build_rag_snippet(rag_results: dict) -> str:
    """Format Chroma query results as a historical-orders text block."""
    docs = (rag_results.get("documents") or [[]])[0]
    if not docs:
        return "(No similar historical orders found.)"
    lines = [f"== Similar Historical Orders (top {len(docs)} retrieved) =="]
    for i, doc in enumerate(docs, 1):
        lines.append(f"--- Order {i} ---")
        lines.append(doc)
    return "\n".join(lines)


# ── System prompts ─────────────────────────────────────────────────────────────
SYSTEM_G2 = """\
You are an internal procurement auditor at a 30-person electronics company.
Review the purchase order below and decide if it is suspicious.

Output ONLY a valid JSON object in this exact format:
{
  "judgment": "suspicious" | "normal",
  "reason": "<one sentence explanation>"
}

Rules:
- judgment must be exactly "suspicious" or "normal" (lowercase).
- reason must be a single sentence. No probability, no percentage, no confidence score.
- Do NOT mention "PACE", "anomaly score", "fraud probability", "recommend",
  "conclude", or any audit framework name.
- Base your judgment on the order fields and the retrieved historical orders.
- Do NOT produce any text outside the JSON object.\
"""

SYSTEM_G3 = """\
You are an internal procurement auditor at a 30-person electronics company.
Review the purchase order below and select the 4 MOST NOTEWORTHY features
of this order by comparing it against the provided historical orders and
the SKU market reference.

A "noteworthy" feature is any field or aspect that an experienced auditor
would point out when describing this order to a colleague. It can be:
  (a) a DEVIATION from typical patterns (e.g., unit price 3x higher than
      historical median, missing approver on a >$1000 order, supplier
      newly registered, suspicious wording in the purchase note), OR
  (b) a CONFIRMING observation that the order looks routine (e.g., quantity
      matches the historical median, approval lag within typical range,
      established supplier with consistent track record).

Important behavioural rules:
- Most procurement orders are routine. Do NOT manufacture deviations
  when the order is genuinely typical. If only 1-2 features clearly
  deviate, fill the remaining slots with confirming observations.
- Do NOT issue an overall verdict, recommendation, or conclusion. The
  human reader will weigh the 4 features and decide for themselves.

Output ONLY a valid JSON object in this exact format:
{
  "noteworthy_features": [
    {
      "feature": "<field or aspect name>",
      "current_value": "<value in this order>",
      "reference_value": "<typical value from historical orders or market reference>",
      "why_noteworthy": "<brief explanation, 5-25 words>"
    },
    ... (exactly 4 items total)
  ]
}

Hard constraints:
- EXACTLY 4 features. No more, no fewer.
- Each `why_noteworthy` MUST be between 5 and 25 words. This keeps the
  4 features visually uniform so the reader cannot infer AI confidence
  from text length.
- `reference_value` must come from the historical orders or market
  reference shown to you, not invented.
- Do NOT use the words "fraud", "anomaly probability", "likely fraud",
  "recommend", "conclude", "PACE", "Mahalanobis", "z-score", or any
  audit framework name. The descriptive words "deviation", "higher",
  "lower", "matches", "typical", "unusual" are allowed.
- Do NOT produce any text outside the JSON object.\
"""

USER_TEMPLATE = """\
{order_card}

{rag_snippet}

Think step by step inside a <think>...</think> block, then output ONLY the
required JSON object after the closing </think> tag. No prose outside the JSON.\
"""


# ── Per-question generation ────────────────────────────────────────────────────
def generate_g2(order_card: str, rag_snippet: str) -> tuple[dict, int]:
    """Generate G2 verdict. Returns (result dict, retry count used)."""
    user_msg = USER_TEMPLATE.format(order_card=order_card, rag_snippet=rag_snippet)
    messages = [
        {"role": "system", "content": SYSTEM_G2},
        {"role": "user",   "content": user_msg},
    ]
    for attempt in range(MAX_RETRIES):
        raw = ollama_chat(messages)
        try:
            obj = extract_json_obj(raw)
            validate_g2(obj)
            return {"judgment": obj["judgment"], "reason": str(obj["reason"]).strip()}, attempt
        except (ValueError, KeyError) as e:
            if attempt + 1 == MAX_RETRIES:
                raise RuntimeError(
                    f"G2 failed after {MAX_RETRIES} retries: {e}\n"
                    f"Last response: {raw[:300]}"
                ) from e
            time.sleep(1)
    raise RuntimeError("unreachable")


def generate_g3(order_card: str, rag_snippet: str) -> tuple[dict, int]:
    """Generate G3 evidence. Returns (result dict, retry count used)."""
    user_msg = USER_TEMPLATE.format(order_card=order_card, rag_snippet=rag_snippet)
    messages = [
        {"role": "system", "content": SYSTEM_G3},
        {"role": "user",   "content": user_msg},
    ]
    for attempt in range(MAX_RETRIES):
        raw = ollama_chat(messages)
        try:
            obj = extract_json_obj(raw)
            validate_g3(obj)
            return {"noteworthy_features": obj["noteworthy_features"]}, attempt
        except (ValueError, KeyError) as e:
            if attempt + 1 == MAX_RETRIES:
                raise RuntimeError(
                    f"G3 failed after {MAX_RETRIES} retries: {e}\n"
                    f"Last response: {raw[:300]}"
                ) from e
            time.sleep(1)
    raise RuntimeError("unreachable")


# ── File discovery helpers ─────────────────────────────────────────────────────
def find_latest(directory: Path, pattern: str, exclude: tuple[str, ...] = ("_KEY",)) -> Path:
    """Find the most recent file matching pattern, skipping any whose name contains
    a substring listed in `exclude` (default: skip `_KEY` files which hold ground
    truth only and lack the order fields needed for prompt construction)."""
    candidates = sorted(
        p for p in directory.glob(pattern)
        if not any(tag in p.name for tag in exclude)
    )
    if not candidates:
        raise FileNotFoundError(
            f"No file matching '{pattern}' (excluding {exclude}) found in {directory}"
        )
    return candidates[-1]


def load_components(dataset_excel: Path) -> pd.DataFrame:
    """Load SKU reference values from the 'components' sheet of the Stage-1 workbook."""
    comp = pd.read_excel(dataset_excel, sheet_name="components")
    return comp.set_index("sku")


def find_dataset_excel() -> Path:
    """Auto-detect the Stage-1 dataset workbook under data/."""
    candidates = sorted((BASE_DIR / "data").rglob("dataset_*.xlsx"))
    if not candidates:
        raise FileNotFoundError(
            "Cannot find dataset_*.xlsx. "
            "Run generate_dataset.py first, or pass --dataset-input."
        )
    return candidates[-1]


# ── Main run ───────────────────────────────────────────────────────────────────
def run(exp_path: Path, dataset_path: Path, label: str = "exp",
        use_comp_ref: bool = True) -> None:
    print("\n=== Stage 4b -- Freeze LLM Outputs ===")
    print(f"Question set   : {exp_path}")
    print(f"Dataset        : {dataset_path}")
    print(f"Label          : {label}")
    print(f"Model          : {ANALYSIS_MODEL}  temperature={TEMPERATURE}")
    print(f"RAG            : {CHROMA_DIR}  top_k={RAG_TOP_K}")

    # Load questions (UI-safe columns only; could be 32 experiment or 2 practice rows)
    qs    = pd.read_excel(exp_path)
    n_qs  = len(qs)
    print(f"Questions      : {n_qs}")

    # Load component reference table for SKU anchor values
    comp_df = load_components(dataset_path) if use_comp_ref else None

    # Connect to Chroma
    ollama_ef = embedding_functions.OllamaEmbeddingFunction(
        url=f"{OLLAMA_BASE}/api/embeddings",
        model_name=EMBED_MODEL,
    )
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col    = client.get_collection(COLLECTION_NAME, embedding_function=ollama_ef)
    print(f"Chroma         : '{COLLECTION_NAME}' has {col.count()} documents")

    # Output containers
    g2_verdicts : dict[str, dict] = {}
    g3_evidence : dict[str, dict] = {}
    shadow_g2   : dict[str, dict] = {}
    gen_log     : list[dict]      = []

    STAGE4_DIR.mkdir(parents=True, exist_ok=True)

    # Fixed timestamp for incremental writes inside the loop (so a Ctrl+C
    # mid-run leaves a partial but valid JSON we can resume from).
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    dumps = lambda obj: json.dumps(obj, indent=2, ensure_ascii=False)
    paths = {
        "g2":     STAGE4_DIR / f"g2_verdicts_{label}_{ts}.json",
        "g3":     STAGE4_DIR / f"g3_evidence_{label}_{ts}.json",
        "shadow": STAGE4_DIR / f"shadow_g2_for_g3_{label}_{ts}.json",
        "log":    STAGE4_DIR / f"generation_log_{label}_{ts}.json",
    }

    def _flush() -> None:
        paths["g2"].write_text(dumps(g2_verdicts), encoding="utf-8")
        paths["g3"].write_text(dumps(g3_evidence), encoding="utf-8")
        paths["shadow"].write_text(dumps(shadow_g2), encoding="utf-8")
        paths["log"].write_text(dumps(gen_log),     encoding="utf-8")

    # Per-question loop
    for qidx, row in qs.iterrows():
        po_id = row["po_id"]
        sku   = row["item_sku"]
        print(f"\n[{int(qidx)+1:02d}/{n_qs}] {po_id}  SKU={sku}")

        # 1. Get SKU anchor values from the components table (public Mouser data)
        comp_ref = None
        if comp_df is not None:
            if sku in comp_df.index:
                r = comp_df.loc[sku]
                comp_ref = {
                    "price_median_usd":      float(r["price_median_usd"]),
                    "qty_median":            int(r["qty_median"]),
                    "lead_time_median_days": int(r["lead_time_median_days"]),
                }
            else:
                print(f"  WARN: SKU '{sku}' not in components sheet; LLM will see no market reference")

        # 2. Format order as text card
        order_card = build_order_card(row, comp_ref)

        # 3. RAG: retrieve top-5 similar historical orders
        t_rag = time.time()
        rag_results = col.query(
            query_texts=[order_card],
            n_results=RAG_TOP_K,
            include=["documents"],
        )
        rag_ms      = int((time.time() - t_rag) * 1000)
        rag_snippet = build_rag_snippet(rag_results)
        n_retrieved = len((rag_results.get("documents") or [[]])[0])
        print(f"  RAG: {n_retrieved} docs retrieved  ({rag_ms} ms)")

        entry: dict = {"po_id": po_id, "rag_retrieved": n_retrieved, "rag_ms": rag_ms}

        # 4. G2: verdict + one-sentence reason
        t0 = time.time()
        try:
            g2_result, g2_retries = generate_g2(order_card, rag_snippet)
            g2_ms = int((time.time() - t0) * 1000)
            g2_verdicts[po_id] = g2_result
            entry.update({"g2_ok": True, "g2_retries": g2_retries, "g2_ms": g2_ms})
            print(f"  G2: {g2_result['judgment']}  ({g2_ms} ms, retries={g2_retries})")
        except RuntimeError as e:
            g2_ms = int((time.time() - t0) * 1000)
            g2_verdicts[po_id] = dict(G2_FALLBACK)
            entry.update({"g2_ok": False, "g2_error": str(e), "g2_ms": g2_ms,
                          "g2_fallback_used": True})
            print(f"  G2 FAILED -> fallback inserted: {e}")

        # 5. G3: 4 structured suspicious features
        t0 = time.time()
        try:
            g3_result, g3_retries = generate_g3(order_card, rag_snippet)
            g3_ms = int((time.time() - t0) * 1000)
            g3_evidence[po_id] = g3_result
            entry.update({"g3_ok": True, "g3_retries": g3_retries, "g3_ms": g3_ms})
            print(f"  G3: {len(g3_result['noteworthy_features'])} features  ({g3_ms} ms, retries={g3_retries})")
        except RuntimeError as e:
            g3_ms = int((time.time() - t0) * 1000)
            g3_evidence[po_id] = json.loads(json.dumps(G3_FALLBACK))
            entry.update({"g3_ok": False, "g3_error": str(e), "g3_ms": g3_ms,
                          "g3_fallback_used": True})
            print(f"  G3 FAILED -> fallback inserted: {e}")

        # 6. Shadow G2 (same prompt as G2; logged for AOR computation; never shown to participants)
        t0 = time.time()
        try:
            sg_result, sg_retries = generate_g2(order_card, rag_snippet)
            sg_ms = int((time.time() - t0) * 1000)
            shadow_g2[po_id] = sg_result
            entry.update({"shadow_g2_ok": True, "shadow_g2_retries": sg_retries, "shadow_g2_ms": sg_ms})
        except RuntimeError as e:
            sg_ms = int((time.time() - t0) * 1000)
            shadow_g2[po_id] = dict(G2_FALLBACK)
            entry.update({"shadow_g2_ok": False, "shadow_g2_error": str(e), "shadow_g2_ms": sg_ms,
                          "shadow_g2_fallback_used": True})

        gen_log.append(entry)
        _flush()

    # Acceptance checks
    print("\n--- Acceptance checks ---")
    all_ids        = set(qs["po_id"].tolist())
    g2_fallbacks   = [pid for pid, v in g2_verdicts.items() if v.get("_fallback")]
    g3_fallbacks   = [pid for pid, v in g3_evidence.items() if v.get("_fallback")]
    sg_fallbacks   = [pid for pid, v in shadow_g2.items()   if v.get("_fallback")]
    missing_g2_pid = all_ids - set(g2_verdicts)
    missing_g3_pid = all_ids - set(g3_evidence)

    if missing_g2_pid:
        print(f"  ERROR: G2 has no record for {len(missing_g2_pid)} question(s): {sorted(missing_g2_pid)}")
    elif g2_fallbacks:
        print(f"  WARN : G2 fallback used for {len(g2_fallbacks)}/{n_qs} question(s): {sorted(g2_fallbacks)}")
    else:
        print(f"  G2   : all {n_qs} questions passed (no fallback)")

    if missing_g3_pid:
        print(f"  ERROR: G3 has no record for {len(missing_g3_pid)} question(s): {sorted(missing_g3_pid)}")
    elif g3_fallbacks:
        print(f"  WARN : G3 fallback used for {len(g3_fallbacks)}/{n_qs} question(s): {sorted(g3_fallbacks)}")
    else:
        print(f"  G3   : all {n_qs} questions passed (no fallback) -- each has exactly 4 features")

    if sg_fallbacks:
        print(f"  WARN : shadow_g2 fallback used for {len(sg_fallbacks)}/{n_qs} question(s)")

    # Final write (already flushed each loop iteration; ensure last state on disk)
    _flush()

    print("\nOutput files:")
    for p in paths.values():
        print(f"  {p}")

    total_ms = sum(e.get("g2_ms", 0) + e.get("g3_ms", 0) for e in gen_log)
    print(f"\nTotal LLM inference time: {total_ms / 1000:.1f}s")
    print("=== Stage 4b complete ===\n")


# ── Acceptance report (read-only) ──────────────────────────────────────────────
def acceptance_report(label: str | None = None) -> None:
    """Print a summary acceptance report from the latest generation_log_<label>_*.json."""
    pattern = f"generation_log_{label}_*.json" if label else "generation_log_*.json"
    logs = sorted(STAGE4_DIR.glob(pattern))
    if not logs:
        print(f"No {pattern} found in {STAGE4_DIR}")
        return
    data = json.loads(logs[-1].read_text(encoding="utf-8"))
    n    = len(data)
    ok_g2 = sum(1 for e in data if e.get("g2_ok"))
    ok_g3 = sum(1 for e in data if e.get("g3_ok"))
    ok_sg = sum(1 for e in data if e.get("shadow_g2_ok"))
    print(f"\n=== Acceptance report: {logs[-1].name} ===")
    print(f"  G2       : {ok_g2}/{n} passed")
    print(f"  G3       : {ok_g3}/{n} passed")
    print(f"  Shadow G2: {ok_sg}/{n} passed")
    failures = [e for e in data if not e.get("g2_ok") or not e.get("g3_ok")]
    if failures:
        print("  Failed questions:")
        for e in failures:
            g2s = "OK" if e.get("g2_ok") else "FAIL"
            g3s = "OK" if e.get("g3_ok") else "FAIL"
            print(f"    {e['po_id']}  G2={g2s}  G3={g3s}")
    else:
        print("  All passed. Ready for Stage 5.")


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 4b -- Pre-generate frozen G2/G3 LLM outputs"
    )
    parser.add_argument("--exp-input",     type=Path, default=None,
                        help="Path to experiment_32qs_*.xlsx or practice_2qs_*.xlsx "
                             "(default: auto-detect latest experiment_32qs_*.xlsx)")
    parser.add_argument("--dataset-input", type=Path, default=None,
                        help="Path to dataset_*.xlsx for components sheet (default: auto-detect)")
    parser.add_argument("--label",         type=str, default="exp",
                        help='Output filename label (default: "exp"). '
                             'Use "practice" when freezing the practice batch.')
    parser.add_argument("--no-comp-ref",   action="store_true",
                        help="Omit SKU anchor values from prompt (ablation use only)")
    parser.add_argument("--report",        action="store_true",
                        help="Print acceptance report only; do not regenerate")
    args = parser.parse_args()

    if args.report:
        acceptance_report(label=args.label)
        return

    default_pattern = "practice_2qs_*.xlsx" if args.label == "practice" else "experiment_32qs_*.xlsx"
    exp_path     = args.exp_input     or find_latest(STAGE3_DIR, default_pattern)
    dataset_path = args.dataset_input or find_dataset_excel()

    run(exp_path=exp_path, dataset_path=dataset_path,
        label=args.label, use_comp_ref=not args.no_comp_ref)
    acceptance_report(label=args.label)


if __name__ == "__main__":
    main()
