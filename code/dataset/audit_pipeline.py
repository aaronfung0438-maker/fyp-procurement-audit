"""Audit Stage 1-5 datasets and frozen artefacts before re-running LLM simulation."""
from pathlib import Path
import pandas as pd, json

base = Path("data")
SEP = "=" * 70

print(SEP); print("STAGE 1-5 DATA AUDIT"); print(SEP)

# ─── Stage 1 ───────────────────────────────────────────────────────────────
print("\n[Stage 1] Monte Carlo base dataset")
s1 = sorted(base.glob("stage1/dataset_*.xlsx"))
for f in s1:
    print(f"  {f.name}  ({f.stat().st_size // 1024} KB)")
if s1:
    df1 = pd.read_excel(s1[-1])
    print(f"  -> latest has {len(df1)} orders, {len(df1.columns)} cols")
    n_anom = (df1["injection_plan"] != "none").sum() if "injection_plan" in df1.columns else None
    if n_anom is not None:
        print(f"  -> anomalies in dataset: {n_anom}")

# ─── Stage 2 ───────────────────────────────────────────────────────────────
print("\n[Stage 2] Semantic fields (purchase_note_human, supplier_profile_human)")
if s1:
    df1 = pd.read_excel(s1[-1])
    has_pn = "purchase_note_human" in df1.columns
    has_sp = "supplier_profile_human" in df1.columns
    print(f"  purchase_note_human present: {has_pn}")
    print(f"  supplier_profile_human present: {has_sp}")
    if has_pn:
        n_filled = df1["purchase_note_human"].notna().sum()
        print(f"  rows with purchase_note_human: {n_filled}/{len(df1)}")

# ─── Stage 3 ───────────────────────────────────────────────────────────────
print("\n[Stage 3] Experiment set + KEY + RAG corpus")
exp        = sorted(base.glob("stage3/experiment_32qs_*.xlsx"))
exp_no_key = [f for f in exp if "_KEY" not in f.name]
exp_key    = [f for f in exp if "_KEY" in f.name]
prac       = sorted(base.glob("stage3/practice_2qs_*.xlsx"))
prac_no_key= [f for f in prac if "_KEY" not in f.name]
rag        = sorted(base.glob("stage3/rag_corpus_*.jsonl"))

for f in (exp_no_key + exp_key + prac + rag):
    print(f"  {f.name}  ({f.stat().st_size // 1024} KB)")

if exp_no_key:
    df3 = pd.read_excel(exp_no_key[-1])
    print(f"  -> latest exp_32qs: {len(df3)} rows")
    print(f"     first cols: {df3.columns.tolist()[:8]}")
if exp_key:
    df3k = pd.read_excel(exp_key[-1])
    n_anom = (df3k["injection_plan"] != "none").sum()
    print(f"  -> latest KEY:     {len(df3k)} rows, {n_anom} anomalies")
    print(f"     blocks: {df3k['experiment_block'].value_counts().to_dict()}")
if prac_no_key:
    dfp = pd.read_excel(prac_no_key[-1])
    print(f"  -> latest practice: {len(dfp)} rows")
if rag:
    n_lines = sum(1 for _ in rag[-1].read_text(encoding='utf-8').splitlines())
    print(f"  -> latest RAG corpus: {n_lines} lines (should be ~466)")

# ─── Stage 4 ───────────────────────────────────────────────────────────────
print("\n[Stage 4] Frozen AI outputs")
g2_files = sorted(base.glob("stage4/g2_verdicts_exp_*.json"))
g3_files = sorted(base.glob("stage4/g3_evidence_exp_*.json"))
sg_files = sorted(base.glob("stage4/shadow_g2_for_g3_exp_*.json"))

print("  -- experiment set --")
for label, files in [("g2_verdict", g2_files), ("g3_evidence", g3_files), ("shadow_g2", sg_files)]:
    if not files:
        print(f"    {label}: NONE FOUND"); continue
    for f in files:
        marker = "  <-- LATEST (data_loader picks this)" if f == files[-1] else ""
        print(f"    {f.name}  ({f.stat().st_size // 1024} KB){marker}")

# Inspect latest of each
def stats_g2(p):
    d = json.loads(p.read_text(encoding="utf-8"))
    sus = sum(1 for v in d.values() if v.get("judgment") == "suspicious")
    fb  = sum(1 for v in d.values() if v.get("_fallback"))
    return len(d), sus, fb

if g2_files:
    n, sus, fb = stats_g2(g2_files[-1])
    print(f"  Latest g2 stats: {n} POs, suspicious={sus} ({sus/n:.1%}), fallbacks={fb}")
if sg_files:
    n, sus, fb = stats_g2(sg_files[-1])
    print(f"  Latest sg stats: {n} POs, suspicious={sus} ({sus/n:.1%}), fallbacks={fb}")
if g3_files:
    d = json.loads(g3_files[-1].read_text(encoding="utf-8"))
    fb = sum(1 for v in d.values() if v.get("_fallback"))
    n_feats = [len(v.get("noteworthy_features", [])) for v in d.values() if not v.get("_fallback")]
    print(f"  Latest g3 stats: {len(d)} POs, fallbacks={fb}, feat_count={set(n_feats)}")

# ─── Stage 4 practice ──────────────────────────────────────────────────────
print("\n  -- practice set --")
for label, pat in [
    ("g2", "g2_verdicts_practice_*.json"),
    ("g3", "g3_evidence_practice_*.json"),
    ("sg", "shadow_g2_for_g3_practice_*.json"),
]:
    fs = sorted(base.glob(f"stage4/{pat}"))
    print(f"    {label}: {fs[-1].name if fs else 'NONE FOUND'}")

# ─── consistency check between latest g2 and g3 timestamps ─────────────────
print("\n[Consistency] do latest g2 / g3 timestamps match?")
g2_ts = g2_files[-1].stem.split("_")[-2:] if g2_files else None
g3_ts = g3_files[-1].stem.split("_")[-2:] if g3_files else None
print(f"  g2 latest TS: {'_'.join(g2_ts) if g2_ts else 'n/a'}")
print(f"  g3 latest TS: {'_'.join(g3_ts) if g3_ts else 'n/a'}")
if g2_ts != g3_ts:
    print("  NOTE: Different TS is OK -- data_loader picks each by its own glob.")
    print("        g2 is the calibrated (new) version, g3 is the older still-valid version.")

# ─── LLM simulation CSV state ──────────────────────────────────────────────
print("\n[LLM sim CSV state]")
csv = base / "llm_sim" / "llm_sim_results.csv"
if csv.exists():
    df = pd.read_csv(csv, encoding="utf-8-sig")
    print(f"  rows: {len(df)}")
    print(f"  groups: {df['group'].value_counts().to_dict()}")
    print(f"  temps:  {df['temperature'].value_counts().to_dict()}")
    g2_rows = (df["group"] == "G2").sum()
    expected_remain = 1056  # G1+G3 only (4 cells × (1 + 10 runs) × 32 = 1408 → 1056 after G2 removed)
    print(f"  G2 rows: {g2_rows}")
    if g2_rows == 0 and len(df) == expected_remain:
        print(f"  STATUS OK: G2 cleaned, ready to rerun simulation (will add 352 new G2 rows).")
    elif g2_rows > 0:
        print(f"  WARN: still has G2 rows -- run delete-G2 step first.")
    else:
        print(f"  WARN: row count {len(df)} != expected {expected_remain}.")
else:
    print("  CSV not found.")

# ─── Stage 5 webapp briefings (also fed into LLM sim system prompt) ────────
print("\n[Stage 5 webapp briefings]")
brief_dir = Path("../webapp")
for f in ["briefing_common.md", "briefing_g1.md", "briefing_g2.md", "briefing_g3.md"]:
    p = brief_dir / f
    if p.exists():
        n_lines = len(p.read_text(encoding="utf-8").splitlines())
        # Check for the "calibration disclosure" block in g2/g3
        if "g2" in f or "g3" in f:
            content = p.read_text(encoding="utf-8")
            has_calib = "same calibration context" in content
            print(f"  {f}: {p.stat().st_size//1024} KB, {n_lines} lines, calibration_disclosure={has_calib}")
        else:
            print(f"  {f}: {p.stat().st_size//1024} KB, {n_lines} lines")
    else:
        print(f"  {f}: NOT FOUND")

print("\n" + SEP)
print("AUDIT COMPLETE")
print(SEP)
