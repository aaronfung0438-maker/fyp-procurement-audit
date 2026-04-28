"""LLM Synthetic Participant Simulation.

Simulates G1 / G2 / G3 conditions using a local Ollama model (Qwen3-8B).

Outputs:
  data/llm_sim/llm_sim_results.csv   — one row per (po_id, group, persona, run)

Usage:
  python llm_simulate.py [--runs-per-temp N] [--model qwen3:8b]

Settings (edit constants below or pass CLI flags):
  TEMP_DET  = 0.0    deterministic run (N=1 mandatory)
  TEMP_STO  = 0.5    stochastic run    (N = --runs-per-temp, default 10)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

# ── paths ──────────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
DATA_S3 = HERE / "data" / "stage3"
DATA_S4 = HERE / "data" / "stage4"
OUT_DIR = HERE / "data" / "llm_sim"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Reuse the exact same participant briefing markdown shown in the Streamlit
# webapp so that the LLM "reads" the same context as a human participant.
BRIEFING_DIR = HERE.parent / "webapp"

TS_RE = re.compile(r"(\d{8}_\d{6})")


def _latest(paths: list[Path]) -> Path:
    if not paths:
        raise FileNotFoundError("No matching files")
    return max(paths, key=lambda p: (m := TS_RE.search(p.name)) and m.group(1) or "")


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ── load artefacts ──────────────────────────────────────────────────────────
def load_data():
    exp_csv = _latest([
        p for p in DATA_S3.glob("experiment_32qs_*.csv")
        if "_KEY" not in p.name and "rag_corpus" not in p.name
    ])
    key_xlsx = _latest(list(DATA_S3.glob("experiment_32qs_*_KEY.xlsx")))
    g2_json  = _latest(list(DATA_S4.glob("g2_verdicts_exp_*.json")))
    g3_json  = _latest(list(DATA_S4.glob("g3_evidence_exp_*.json")))

    exp_df  = pd.read_csv(exp_csv, encoding="utf-8-sig")
    key_df  = pd.read_excel(key_xlsx)
    g2_data = _load_json(g2_json)
    g3_data = _load_json(g3_json)

    truth = {
        str(po).strip(): ("normal" if str(plan).strip().lower() == "none" else "anomaly")
        for po, plan in zip(key_df["po_id"], key_df["injection_plan"])
    }

    print(f"Loaded {len(exp_df)} experiment orders; {sum(v=='anomaly' for v in truth.values())} anomalies")
    return exp_df, truth, g2_data, g3_data


def load_briefings() -> dict[str, str]:
    """Load briefing markdown shown to human participants in the webapp.

    Returns dict mapping group -> full briefing text (common + group-specific).
    """
    common = (BRIEFING_DIR / "briefing_common.md").read_text(encoding="utf-8")
    out = {}
    for g in ("G1", "G2", "G3"):
        per_group = (BRIEFING_DIR / f"briefing_{g.lower()}.md").read_text(encoding="utf-8")
        out[g] = f"{common}\n\n---\n\n{per_group}"
    return out


# ── prompt builders ─────────────────────────────────────────────────────────
STUDENT_PERSONA = (
    "You are a university business student with no prior procurement or auditing experience. "
    "You follow instructions carefully and try your best to judge each order."
)

AUDITOR_PERSONA = (
    "You are a senior internal auditor with 10 years of experience in procurement fraud detection. "
    "You rely on your own professional judgment and are not easily swayed by automated tools."
)

REPLY_FORMAT = """\
Respond with ONLY a JSON object, no other text, no preamble, no explanation:
{
  "judgment": "normal" or "suspicious",
  "confidence": <integer 1-7>,
  "reasoning": "<one short sentence>"
}"""


def build_system_prompt(persona: str, briefing: str) -> str:
    """Combine persona + full participant briefing into the system message.

    The briefing is identical to what human participants read on the
    webapp's Briefing screen (common + group-specific markdown).
    """
    return (
        f"{persona}\n\n"
        "You have been recruited as a participant in the following study. "
        "Read the briefing carefully — it tells you everything you need to "
        "know about the company context, what each section means, and how "
        "to make your decision. Then you will be shown one purchase order "
        "at a time and must reply in JSON only.\n\n"
        "================ PARTICIPANT BRIEFING ================\n"
        f"{briefing}\n"
        "================ END BRIEFING ========================\n"
    )


def build_prompt_g1(row: pd.Series) -> str:
    """G1: Section A + B + E only, no AI panel."""
    sec_a = _section_a(row)
    sec_b = _section_b(row)
    sec_e = _section_e(row)
    return (
        "You are now shown one purchase order. Make your decision now.\n\n"
        f"{sec_a}\n\n{sec_b}\n\n{sec_e}\n\n{REPLY_FORMAT}"
    )


def build_prompt_g2(row: pd.Series, g2_data: dict) -> str:
    """G2: Section A + B + E + AI Verdict panel.

    AI panel matches the webapp wording for human participants:
        ##### AI Verdict (Group 2)
        **Suspicious** — <reason>
    """
    pid = str(row["po_id"]).strip()
    verdict = g2_data.get(pid, {})
    raw_judgment = str(verdict.get("judgment", "")).strip().lower()
    reason = verdict.get("reason", "")

    if raw_judgment == "suspicious":
        verdict_line = f"**Suspicious** — {reason}"
    elif raw_judgment == "normal":
        verdict_line = f"**Normal** — {reason}"
    elif raw_judgment:
        verdict_line = f"**{raw_judgment}** — {reason}"
    else:
        verdict_line = "_No AI verdict available for this order._"

    ai_panel = f"##### AI Verdict (Group 2)\n{verdict_line}"

    sec_a = _section_a(row)
    sec_b = _section_b(row)
    sec_e = _section_e(row)
    return (
        "You are now shown one purchase order. Make your decision now.\n\n"
        f"{sec_a}\n\n{sec_b}\n\n{sec_e}\n\n{ai_panel}\n\n{REPLY_FORMAT}"
    )


def build_prompt_g3(row: pd.Series, g3_data: dict) -> str:
    """G3: Section A + B + E + AI Noteworthy Features panel.

    AI panel matches the webapp wording for human participants:
        ##### AI Noteworthy Features (Group 3)
        | Feature | Current value | Reference value | Why noteworthy |
        | ------- | ------------- | --------------- | -------------- |
        | …       | …             | …               | …              |
    """
    pid = str(row["po_id"]).strip()
    evidence = g3_data.get(pid, {})
    features = evidence.get("noteworthy_features", [])

    if features:
        header = (
            "| Feature | Current value | Reference value | Why noteworthy |\n"
            "| ------- | ------------- | --------------- | -------------- |"
        )
        body = "\n".join(
            f"| {f.get('feature','')} | {f.get('current_value','')} | "
            f"{f.get('reference_value','')} | {f.get('why_noteworthy','')} |"
            for f in features
        )
        ai_panel = (
            "##### AI Noteworthy Features (Group 3)\n"
            f"{header}\n{body}"
        )
    else:
        ai_panel = (
            "##### AI Noteworthy Features (Group 3)\n"
            "_No AI evidence available for this order._"
        )

    sec_a = _section_a(row)
    sec_b = _section_b(row)
    sec_e = _section_e(row)
    return (
        "You are now shown one purchase order. Make your decision now.\n\n"
        f"{sec_a}\n\n{sec_b}\n\n{sec_e}\n\n{ai_panel}\n\n{REPLY_FORMAT}"
    )


# ── section formatters ───────────────────────────────────────────────────────
def _v(row: pd.Series, col: str, default: str = "N/A") -> str:
    if col not in row.index:
        return default
    v = row[col]
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    return str(v).strip() or default


def _section_a(row: pd.Series) -> str:
    return (
        "SECTION A — ORDER DETAILS\n"
        f"  PO ID       : {_v(row,'po_id')}\n"
        f"  Item        : {_v(row,'item_category')} — {_v(row,'item_sku')} — {_v(row,'item_description')}\n"
        f"  Quantity    : {_v(row,'quantity')}\n"
        f"  Unit price  : ${_v(row,'unit_price_usd')}\n"
        f"  Total       : ${_v(row,'total_amount_usd')}\n"
        f"  Requester   : {_v(row,'requester_id')}\n"
        f"  Approver    : {_v(row,'approver_id')}\n"
        f"  Supplier    : {_v(row,'supplier_id')}\n"
        f"  Created     : {_v(row,'created_date')}\n"
        f"  Approval lag: {_v(row,'approval_lag_days')} days\n"
        f"  Lead time   : {_v(row,'expected_delivery_lag_days')} days"
    )


def _section_b(row: pd.Series) -> str:
    return (
        "SECTION B — FREE-TEXT NOTES\n"
        f"  Purchase note   : {_v(row,'purchase_note_human')}\n"
        f"  Supplier profile: {_v(row,'supplier_profile_human')}"
    )


def _section_e(row: pd.Series) -> str:
    def _f(col):
        try:
            return float(_v(row, col, "nan"))
        except ValueError:
            return None

    lines = ["SECTION E — DEVIATION SENTENCES"]
    up, upe, upr = _f("unit_price_usd"), _f("expected_unit_price_usd"), _f("unit_price_ratio")
    if up and upe and upr:
        lines.append(f"  Unit price ${up:.4f} vs SKU median ${upe:.4f} (ratio {upr:.2f}×)")

    qty, qtye, qtyr = _f("quantity"), _f("expected_quantity"), _f("quantity_ratio")
    if qty and qtye and qtyr:
        lines.append(f"  Quantity {int(qty)} vs SKU median {int(qtye)} (ratio {qtyr:.2f}×)")

    lead, lm, ls, lz = _f("expected_delivery_lag_days"), _f("expected_delivery_lag_mean"), \
                        _f("expected_delivery_lag_sigma"), _f("delivery_lag_z")
    if lead and lm and ls and lz is not None:
        lines.append(f"  Lead time {int(lead)} days (typical {int(lm)} ± {int(ls)}; z={lz:+.2f})")

    al, az = _f("approval_lag_days"), _f("approval_lag_z")
    if al and az is not None:
        lines.append(f"  Approval lag {al:.2f} days (z={az:+.2f} vs this approver's pattern)")

    total, gap = _f("total_amount_usd"), _f("total_vs_approval_gap")
    if total and gap is not None:
        lines.append(f"  Threshold gap: total ${total:,.2f}, distance ${gap:+,.2f}")

    return "\n".join(lines)


# ── Ollama call ──────────────────────────────────────────────────────────────
def call_ollama(
    prompt: str,
    system_prompt: str,
    model: str,
    temperature: float,
    timeout: int = 180,
) -> dict:
    """Call local Ollama and return parsed JSON or error dict."""
    # Qwen3 thinking mode emits <think>…</think> blocks before the answer.
    # We strip them post-hoc; need a generous num_predict so the JSON
    # reply itself is not truncated.
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": 2048},
    }
    try:
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        content = resp.json()["message"]["content"].strip()
        # strip <think>...</think> blocks (Qwen3 thinking mode)
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        # extract first JSON object
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if not m:
            return {"error": "no_json", "raw": content[:300]}
        parsed = json.loads(m.group())
        judgment = str(parsed.get("judgment", "")).strip().lower()
        if judgment not in ("normal", "suspicious"):
            judgment = "unknown"
        confidence = int(parsed.get("confidence", 4))
        confidence = max(1, min(7, confidence))
        return {
            "judgment": judgment,
            "confidence": confidence,
            "reasoning": str(parsed.get("reasoning", ""))[:400],
        }
    except Exception as exc:
        return {"error": str(exc)[:200]}


# ── main simulation loop ─────────────────────────────────────────────────────
GROUPS = ("G1", "G2", "G3")
PERSONAS = {
    "student": STUDENT_PERSONA,
    "auditor": AUDITOR_PERSONA,
}
PERSONAS_PER_GROUP = {
    "G1": ("student", "auditor"),
    "G2": ("student",),
    "G3": ("student",),
}


def run_simulation(
    exp_df: pd.DataFrame,
    truth: dict,
    g2_data: dict,
    g3_data: dict,
    briefings: dict[str, str],
    model: str,
    runs_stochastic: int,
    out_path: Path,
) -> None:
    fieldnames = [
        "po_id", "group", "persona", "temperature", "run",
        "judgment", "confidence", "reasoning",
        "truth", "correct", "error",
    ]

    # Resume support: read existing rows so we can skip already-done calls.
    existing: set[tuple] = set()
    file_exists = out_path.exists() and out_path.stat().st_size > 0
    if file_exists:
        try:
            prev = pd.read_csv(out_path, encoding="utf-8-sig")
            for _, r in prev.iterrows():
                existing.add((
                    str(r["po_id"]).strip(),
                    str(r["group"]),
                    str(r["persona"]),
                    float(r["temperature"]),
                    int(r["run"]),
                ))
            print(f"Resume: found {len(existing)} existing rows, skipping them.")
        except Exception as exc:
            print(f"Warning: could not read existing CSV ({exc}); starting fresh.")
            file_exists = False

    rows_written = 0
    open_mode = "a" if file_exists else "w"

    with out_path.open(open_mode, newline="", encoding="utf-8-sig") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        for group in GROUPS:
            for persona_key in PERSONAS_PER_GROUP[group]:
                persona_text = PERSONAS[persona_key]
                # System prompt = persona + full participant briefing
                # (identical to what humans read on the webapp Briefing screen).
                system_prompt = build_system_prompt(persona_text, briefings[group])

                # build prompts for all 32 orders
                prompts = {}
                for _, row in exp_df.iterrows():
                    pid = str(row["po_id"]).strip()
                    if group == "G1":
                        prompts[pid] = build_prompt_g1(row)
                    elif group == "G2":
                        prompts[pid] = build_prompt_g2(row, g2_data)
                    else:
                        prompts[pid] = build_prompt_g3(row, g3_data)

                # deterministic run (temp=0, run=0)
                temps_and_runs = [(0.0, 1), (0.5, runs_stochastic)]

                for temperature, n_runs in temps_and_runs:
                    for run_i in range(n_runs):
                        run_id = run_i if temperature > 0 else 0
                        print(
                            f"  {group} | {persona_key} | T={temperature} | run={run_id} "
                            f"| {len(prompts)} orders …"
                        )
                        for pid, prompt in prompts.items():
                            key = (pid, group, persona_key, temperature, run_id)
                            if key in existing:
                                continue
                            result = call_ollama(prompt, system_prompt, model, temperature)
                            gt = truth.get(pid, "unknown")
                            judgment = result.get("judgment", "unknown")
                            # Map LLM "suspicious" → ground-truth "anomaly"
                            # so truth ∈ {normal, anomaly} matches judgment ∈ {normal, suspicious}.
                            if judgment == "unknown":
                                correct = None
                            else:
                                judgment_norm = "anomaly" if judgment == "suspicious" else judgment
                                correct = (judgment_norm == gt)
                            writer.writerow({
                                "po_id":      pid,
                                "group":      group,
                                "persona":    persona_key,
                                "temperature": temperature,
                                "run":        run_id,
                                "judgment":   judgment,
                                "confidence": result.get("confidence", ""),
                                "reasoning":  result.get("reasoning", ""),
                                "truth":      gt,
                                "correct":    correct,
                                "error":      result.get("error", ""),
                            })
                            fout.flush()
                            rows_written += 1
                            time.sleep(0.2)  # be gentle with Ollama

    print(f"\nDone. {rows_written} rows → {out_path}")


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("--runs-per-temp", type=int, default=10,
                    help="Number of stochastic (T=0.5) runs per (order, group, persona)")
    ap.add_argument("--out", default=str(OUT_DIR / "llm_sim_results.csv"))
    args = ap.parse_args()

    print("=" * 72)
    print(f"LLM Simulation | model={args.model} | stochastic_runs={args.runs_per_temp}")
    print("=" * 72)

    exp_df, truth, g2_data, g3_data = load_data()
    briefings = load_briefings()
    print(f"Loaded briefings: G1={len(briefings['G1'])} chars, "
          f"G2={len(briefings['G2'])} chars, G3={len(briefings['G3'])} chars")

    total_calls = (
        len(exp_df) * (
            (1 + args.runs_per_temp) * len(PERSONAS_PER_GROUP["G1"]) +
            (1 + args.runs_per_temp) * len(PERSONAS_PER_GROUP["G2"]) +
            (1 + args.runs_per_temp) * len(PERSONAS_PER_GROUP["G3"])
        )
    )
    print(f"Estimated Ollama calls: {total_calls}")
    print(f"Output: {args.out}\n")

    run_simulation(
        exp_df, truth, g2_data, g3_data, briefings,
        model=args.model,
        runs_stochastic=args.runs_per_temp,
        out_path=Path(args.out),
    )


if __name__ == "__main__":
    main()
