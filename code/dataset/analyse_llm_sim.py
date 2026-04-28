"""
Full LLM-simulation analysis for RQ1, RQ2, RQ3.
Run:  python analyse_llm_sim.py
"""
import json, glob
import pandas as pd
import numpy as np

# ── Load data ──────────────────────────────────────────────────────────────
df = pd.read_csv("data/llm_sim/llm_sim_results.csv", encoding="utf-8-sig")
df["correct"] = df["correct"].map({"True": True, "False": False, True: True, False: False})

key = pd.read_excel(
    "data/stage3/experiment_32qs_20260426_040739_KEY.xlsx",
    usecols=["po_id", "experiment_block", "injection_plan"],
)
key["truth"] = key["injection_plan"].apply(lambda x: "normal" if x == "none" else "anomaly")

# Signal-type classification
NUMERICAL_BLOCKS = {"B"}          # clear numerical signal
TEXT_BLOCKS       = {"C2a"}        # text signal dominates
MIXED_BLOCKS      = {"C2b"}        # both

# Stage 4 AI verdicts
g2v_file = sorted(glob.glob("data/stage4/g2_verdicts_exp_*.json"))[-1]
with open(g2v_file) as f:
    g2v = json.load(f)

truth_map = dict(zip(key["po_id"], key["truth"]))
ai_judgment = {pid: v["judgment"] for pid, v in g2v.items()}
ai_correct_map = {
    pid: (("anomaly" if j == "suspicious" else "normal") == truth_map.get(pid, "?"))
    for pid, j in ai_judgment.items()
}
ai_wrong_pids = {pid for pid, ok in ai_correct_map.items() if not ok}

# ── Helpers ────────────────────────────────────────────────────────────────
def cliffs_delta(a, b):
    a, b = list(a), list(b)
    gt = sum(ai > bi for ai in a for bi in b)
    lt = sum(ai < bi for ai in a for bi in b)
    return (gt - lt) / (len(a) * len(b))

def bootstrap_ci(a, b, stat_fn=None, B=5000, seed=42):
    if stat_fn is None:
        stat_fn = cliffs_delta
    rng = np.random.default_rng(seed)
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    boots = [
        stat_fn(rng.choice(a, len(a), replace=True), rng.choice(b, len(b), replace=True))
        for _ in range(B)
    ]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return lo, hi

def hedges_g(a, b):
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    na, nb = len(a), len(b)
    pooled_std = np.sqrt(((na - 1) * a.std(ddof=1)**2 + (nb - 1) * b.std(ddof=1)**2) / (na + nb - 2))
    if pooled_std == 0:
        return 0.0
    g = (a.mean() - b.mean()) / pooled_std
    # Hedges correction factor
    cf = 1 - 3 / (4 * (na + nb - 2) - 1)
    return g * cf

def per_question_acc(sub_df):
    """Return array length 32: fraction correct per question over stochastic runs."""
    return sub_df.groupby("po_id")["correct"].mean().values

SEP = "=" * 62

# ═══════════════════════════════════════════════════════════════
print(SEP)
print("STAGE 4 AI PERFORMANCE (baseline)")
print(SEP)
ai_acc = sum(ai_correct_map.values()) / len(ai_correct_map)
ai_sus = sum(1 for j in ai_judgment.values() if j == "suspicious") / len(ai_judgment)
print(f"  Accuracy : {sum(ai_correct_map.values())}/32 = {ai_acc:.3f}")
print(f"  Suspicious rate: {ai_sus:.3f}")
print(f"  Wrong on {len(ai_wrong_pids)} orders: {sorted(ai_wrong_pids)}")

# ═══════════════════════════════════════════════════════════════
print()
print(SEP)
print("RQ1 — ACCURACY BY GROUP (student persona)")
print(SEP)

# T=0 deterministic
t0_stu = df[(df["temperature"] == 0.0) & (df["persona"] == "student")]
print("\nT=0 (deterministic, 1 run):")
for g in ["G1", "G2", "G3"]:
    sub = t0_stu[t0_stu["group"] == g]
    n_c = sub["correct"].sum()
    acc = n_c / len(sub)
    tp = ((sub["judgment"] == "suspicious") & (sub["truth"] == "anomaly")).sum()
    fn = ((sub["judgment"] == "normal")    & (sub["truth"] == "anomaly")).sum()
    fp = ((sub["judgment"] == "suspicious") & (sub["truth"] == "normal")).sum()
    tn = ((sub["judgment"] == "normal")    & (sub["truth"] == "normal")).sum()
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    spec   = tn / (tn + fp) if (tn + fp) > 0 else 0
    sus_r  = (sub["judgment"] == "suspicious").mean()
    print(f"  {g}: acc={acc:.3f} ({n_c}/32)  recall={recall:.2f}  spec={spec:.2f}  sus_rate={sus_r:.2f}")

# T=0.5 stochastic (10 runs per question)
t5_stu = df[(df["temperature"] == 0.5) & (df["persona"] == "student")]
print("\nT=0.5 (stochastic, 10 runs — per-question mean accuracy):")
pq = {}
for g in ["G1", "G2", "G3"]:
    sub = t5_stu[t5_stu["group"] == g]
    q_acc = per_question_acc(sub)
    pq[g] = q_acc
    sus_r = (sub["judgment"] == "suspicious").mean()
    print(f"  {g}: mean_acc={q_acc.mean():.3f}  std={q_acc.std():.3f}  sus_rate={sus_r:.3f}")

print("\nEffect sizes (T=0.5 per-question accuracy):")
pairs = [("G3", "G1"), ("G3", "G2"), ("G2", "G1")]
for ga, gb in pairs:
    d  = cliffs_delta(pq[ga], pq[gb])
    g  = hedges_g(pq[ga], pq[gb])
    lo, hi = bootstrap_ci(pq[ga], pq[gb])
    print(f"  {ga} vs {gb}: Cliff's d={d:+.3f}  Hedges' g={g:+.3f}  95% CI=[{lo:+.3f},{hi:+.3f}]")

# Also compare G1-auditor vs G1-student
print("\nG1-auditor vs G1-student (persona effect):")
t5_aud  = df[(df["temperature"] == 0.5) & (df["persona"] == "auditor") & (df["group"] == "G1")]
t5_stu1 = df[(df["temperature"] == 0.5) & (df["persona"] == "student") & (df["group"] == "G1")]
q_aud   = per_question_acc(t5_aud)
q_stu1  = per_question_acc(t5_stu1)
for name, q in [("G1-auditor", q_aud), ("G1-student", q_stu1)]:
    sus_r = (df[(df["temperature"]==0.5)&(df["persona"]==name.split("-")[1])&(df["group"]=="G1")]["judgment"]=="suspicious").mean() if "-" in name else None
    print(f"  {name}: mean_acc={q.mean():.3f}  std={q.std():.3f}")
d_aud = cliffs_delta(q_aud, q_stu1)
print(f"  Cliff's d (auditor vs student): {d_aud:+.3f}")

# ═══════════════════════════════════════════════════════════════
print()
print(SEP)
print("RQ2 — SIGNAL TYPE SUBGROUP ANALYSIS (student persona, T=0.5)")
print(SEP)

# Merge block info onto df
df2 = df.merge(key[["po_id", "experiment_block", "truth"]], on="po_id", how="left", suffixes=("", "_key"))
t5s = df2[(df2["temperature"] == 0.5) & (df2["persona"] == "student")]

signal_map = {
    "B":   "Numerical-dominant (Block B)",
    "C2a": "Text-dominant (Block C2a)",
    "C2b": "Mixed signal (Block C2b)",
    "A":   "Normal routine (Block A)",
    "C1":  "Normal hi-Mahal (Block C1)",
}

for blk, label in signal_map.items():
    sub_blk = t5s[t5s["experiment_block"] == blk]
    if sub_blk.empty:
        continue
    print(f"\n  {label}:")
    for g in ["G1", "G2", "G3"]:
        sg = sub_blk[sub_blk["group"] == g]
        if sg.empty:
            continue
        pq_blk = sg.groupby("po_id")["correct"].mean().values
        print(f"    {g}: mean_acc={pq_blk.mean():.3f}  n_qs={len(pq_blk)}")

# RQ2 core: G3 advantage largest in text-dominant?
print("\n  RQ2 focus — G3 advantage per signal type:")
for blk, label in [("B", "Numerical"), ("C2a", "Text-dominant"), ("C2b", "Mixed")]:
    sub_blk = t5s[t5s["experiment_block"] == blk]
    g1_q = sub_blk[sub_blk["group"]=="G1"].groupby("po_id")["correct"].mean().values
    g2_q = sub_blk[sub_blk["group"]=="G2"].groupby("po_id")["correct"].mean().values
    g3_q = sub_blk[sub_blk["group"]=="G3"].groupby("po_id")["correct"].mean().values
    if len(g3_q) == 0 or len(g1_q) == 0:
        continue
    d31 = cliffs_delta(g3_q, g1_q)
    d32 = cliffs_delta(g3_q, g2_q)
    print(f"    {label}: G3 vs G1 d={d31:+.3f}  G3 vs G2 d={d32:+.3f}")

# ═══════════════════════════════════════════════════════════════
print()
print(SEP)
print("RQ3 — AI OVERRIDE RATE (when Stage 4 AI was WRONG)")
print(SEP)

wrong_orders = sorted(ai_wrong_pids)
print(f"\n  Stage 4 AI wrong on {len(wrong_orders)} orders:")
for pid in wrong_orders:
    blk = key.loc[key["po_id"] == pid, "experiment_block"].values[0]
    inj = key.loc[key["po_id"] == pid, "injection_plan"].values[0]
    ai_j = ai_judgment.get(pid, "?")
    tr = truth_map.get(pid, "?")
    print(f"    {pid} | block={blk} | truth={tr} | AI said={ai_j} | anomaly_type={inj}")

print("\n  Override Rate (T=0.5 student): fraction correct on AI-wrong orders")
t5s_wrong = t5s[t5s["po_id"].isin(wrong_orders)]
for g in ["G1", "G2", "G3"]:
    sg = t5s_wrong[t5s_wrong["group"] == g]
    aor = sg["correct"].mean()
    n_correct = sg["correct"].sum()
    n_total   = len(sg)
    print(f"  {g}: AOR = {aor:.3f}  ({n_correct}/{n_total} correct responses on AI-wrong orders)")

# Per-order detail for G2 vs G3 on AI-wrong orders
print("\n  Per-order: G2 vs G3 correct rate on AI-wrong orders:")
print(f"  {'PO-ID':<16} {'Block':<6} {'AI_verdict':<12} {'Truth':<8} {'G2_cor':<8} {'G3_cor':<8} {'G1_cor'}")
for pid in wrong_orders:
    blk = key.loc[key["po_id"] == pid, "experiment_block"].values[0]
    ai_j = ai_judgment.get(pid, "?")
    tr = truth_map.get(pid, "?")
    g1r = t5s_wrong[(t5s_wrong["po_id"]==pid)&(t5s_wrong["group"]=="G1")]["correct"].mean()
    g2r = t5s_wrong[(t5s_wrong["po_id"]==pid)&(t5s_wrong["group"]=="G2")]["correct"].mean()
    g3r = t5s_wrong[(t5s_wrong["po_id"]==pid)&(t5s_wrong["group"]=="G3")]["correct"].mean()
    print(f"  {pid:<16} {blk:<6} {ai_j:<12} {tr:<8} {g2r:<8.2f} {g3r:<8.2f} {g1r:.2f}")

print()
print(SEP)
print("SUMMARY TABLE")
print(SEP)
print("\n  T=0.5 student accuracy:")
print(f"  {'Group':<6} {'Mean Acc':<10} {'Recall':<9} {'Spec':<9} {'Sus Rate'}")
for g in ["G1", "G2", "G3"]:
    sub = t5_stu[t5_stu["group"] == g]
    acc  = sub["correct"].mean()
    tp   = ((sub["judgment"]=="suspicious")&(sub["truth"]=="anomaly")).sum()
    fn   = ((sub["judgment"]=="normal")    &(sub["truth"]=="anomaly")).sum()
    fp   = ((sub["judgment"]=="suspicious")&(sub["truth"]=="normal")).sum()
    tn   = ((sub["judgment"]=="normal")    &(sub["truth"]=="normal")).sum()
    rec  = tp/(tp+fn) if (tp+fn)>0 else 0
    spec = tn/(tn+fp) if (tn+fp)>0 else 0
    sus_r= (sub["judgment"]=="suspicious").mean()
    print(f"  {g:<6} {acc:<10.3f} {rec:<9.3f} {spec:<9.3f} {sus_r:.3f}")
