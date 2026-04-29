# Chapter 3: Methodology — Brief

**Research Title:** Evidence vs. Conclusion — How LLM Output Format Shapes Human-AI Collaboration in Procurement Anomaly Auditing

---

## 3.1 Research Design Overview

This study investigates how the **format of AI-generated output** influences human decision-making in procurement anomaly auditing. Three research questions guide the work:

- **RQ1**: Does presenting LLM output as **structured evidence** (four factual observations without a verdict) yield higher anomaly detection accuracy than a **binary conclusion** with a one-sentence rationale, or **no AI assistance** at all?
- **RQ2**: Does the format effect differ between anomalies detectable through **numerical deviation** versus those detectable only through **textual semantics**?
- **RQ3**: When the LLM produces an **incorrect output**, does the evidence format enable participants to **override AI errors** more effectively than the conclusion format?

The methodology comprises five interlocking pipeline stages plus a parallel computational baseline:

```
Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5 (Human Experiment, N=12)
Monte Carlo  Semantic  Anomaly  Frozen AI  Streamlit webapp
                                          ───────────────────────
                                          Stage 16: LLM Simulation
                                          (Computational Baseline)
```

All experimental stimuli are **frozen** before recruitment, so every participant — human or LLM — faces identical inputs.

---

## 3.2 Dataset Construction

A **synthetic dataset** is used because real procurement records lack verified ground truth, cannot be shared publicly, and cannot accept controlled anomaly injection without disturbing existing audit trails. Synthetic data delivers (a) **definitionally exact ground truth**, (b) **publishable** for replication, (c) **precise control** over anomaly type, frequency, and signal strength.

**Stage 1 — Monte Carlo base.** 500 orders generated for calendar year 2024 representing *ABC Electronics*, a fictional 30-person Hong Kong IoT startup. Order arrival follows a **Poisson process** (λ ≈ 1.37/day). Quantities and unit prices use **log-normal distributions** anchored to real **Mouser Electronics API** price data for 10 representative SKUs. Approval lags follow a **truncated normal** distribution. The pipeline is fully reproducible (`RANDOM_SEED = 42`).

**Stage 2 — Semantic fields.** **DeepSeek** (a production LLM distinct from the analysis model) generates the `purchase_note` and `supplier_profile` free-text fields. For anomalous orders, DeepSeek receives a **PACE hint** corresponding to the anomaly type. A different model is deliberately used here to break self-confirmation bias with the Stage 4 analysis model (Qwen3-8B).

**Stage 3 — Anomaly injection.** Following the **PACE procurement fraud taxonomy** (Westerski et al., 2021), 76 of 500 orders (15.2%) receive one of eight anomaly types: `item_spending`, `border_value`, `unusual_vendor`, `vendor_spending`, `approval_bypass`, `quote_manipulation`, `bank_account_change`, `conflict_of_interest`. The first four are **numerical-dominant**; the last four are **text-dominant**. **Ground truth is programmatic** — defined by mutation contracts in `apply_anomaly()`, never by human annotation, never seen by participants or by the AI.

**Stage 3 — Stratified sampling.** From the 500-order population, **32 questions** form the experiment set (16 anomalous + 16 normal, 50% rate elevated for subgroup analysis power) and **2 questions** form the practice set, leaving **466 orders** as the RAG corpus. Stratification uses Mahalanobis-distance blocks: A (clear normal), B (clear-numerical anomaly), C1 (statistically suspicious normal), C2a (text-dominant anomaly), C2b (mixed-signal anomaly).

---

## 3.3 AI Tool Construction (Stage 4)

Stage 4 produces the **frozen AI outputs** that Groups 2 and 3 see during the experiment. Outputs are generated **once**, before any participant begins, and never updated.

**RAG corpus.** The 466 non-experiment orders are embedded with **`nomic-embed-text`** (768-dim vectors via Ollama) and stored in **ChromaDB**. Top-5 most similar historical orders are retrieved per query. **Information-leakage prevention**: 24 sensitive columns (ground truth labels, Mahalanobis scores, z-scores, ratios, stratum tags) are blacklisted; the build pipeline aborts if any sensitive field appears in metadata.

**Frozen LLM outputs.** **Qwen3-8B** (locally deployed via Ollama, temperature = 0) generates two output types per question:

- **G2 verdict**: `{"judgment": "suspicious"|"normal", "reason": "<one sentence>"}`. The model is forbidden from emitting probability estimates, confidence scores, or framework names (`PACE`, `Mahalanobis`) via both prompt rules and a post-generation forbidden-word check.
- **G3 evidence**: `{"noteworthy_features": [{"feature", "current_value", "reference_value", "why_noteworthy"} × 4]}`. The `why_noteworthy` field is constrained to **5–25 words** to prevent the implicit confidence signal that longer text would create.

**Calibration knowledge given to the AI.** The AI tool receives **calibration context** — supplier-range conventions (S-001 to S-025 are regulars), tiered approval thresholds, and the rule of thumb that *a single weak deviation is usually explainable; multiple independent red flags or one extreme deviation are required for a Suspicious call*. This is the **same judgment standard** participants receive via the briefing. Without it, the AI tends to flag everything as suspicious, creating a confound between AI-quality effects and AI-format effects.

**Calibration knowledge withheld from the AI.** Section E pre-computed deviation values (ratios, z-scores) and the explicitly named 8-pattern fraud catalogue are **not** provided to the AI. This represents the realistic gap between human auditors (who possess analytical tools) and a deployed LLM (which must reason from raw inputs).

---

## 3.4 Experimental Design

### Three-Group Between-Subjects Design

12 participants are randomly assigned via a pre-balanced queue (4 per group) to one of three conditions:

| Group | AI Assistance | Output Format |
|---|---|---|
| **G1 — Control** | None (Section E only) | — |
| **G2 — Conclusion** | AI verdict + reason | `Suspicious / Normal — <reason>` |
| **G3 — Evidence** | 4 structured observations | Feature table, no verdict |

For each order, participants submit a **binary judgment** (Normal / Suspicious) plus a **7-point Likert confidence rating**.

### Briefing & Information Architecture

All participants read a **common briefing** covering: company scenario, definitions, supplier conventions, approver hierarchy, the 8 fraud-pattern catalogue, section explanations (A = order facts, B = free-text notes, E = deviation sentences), and procedural rules (45–75 sec/question, no going back, no pausing).

Each group then reads a **group-specific page**. G2 and G3 are explicitly told that the AI received the same calibration context they did but was *not* given Section E or the named 8-pattern catalogue, allowing participants to calibrate their trust.

### Web Application

The experiment runs on **Streamlit Community Cloud** with **Google Sheets** for assignment-queue management and response logging. Each response is committed irrevocably upon submission; practice rounds give per-question feedback; the 32-question official block does not.

### Trust Surveys

After the 32 official questions, all participants complete a **5-item Likert survey**. G2 uses an adapted **Jian et al. (2000)** AI trust scale; G3 uses a parallel scale measuring trust in the AI evidence panel; G1 uses a structurally parallel scale for the Section E deviation sentences. Cross-group comparisons of survey scores are restricted to structural indicators (a documented limitation).

---

## 3.5 Computational Baseline — LLM Synthetic Participant Simulation

In parallel with human recruitment, a computational baseline uses **Qwen3-8B as a synthetic participant** to simulate the three conditions. This serves three purposes: (a) provides a **rational-agent reference** free of cognitive biases; (b) quantifies **automation-bias potential** in the conclusion format; (c) provides **reproducible cross-checks** for the small-N human pilot.

### Two-Layer LLM Architecture

A critical architectural distinction separates the two LLM roles:

- **Layer 1 — AI Tool (Stage 4, frozen).** Generates G2 verdicts and G3 evidence once, before any participant begins. Acts as the **independent variable**.
- **Layer 2 — Synthetic Participant (Stage 16).** A second, independent Qwen3-8B call with a completely different system prompt, simulating a participant decision. Reads the full participant briefing, the order data, and the frozen Layer 1 output, then produces a judgment, confidence, and one-sentence reasoning.

The two layers are **never executed in the same call**. Layer 1 outputs are static JSON files that Layer 2 reads as an external participant would view a webapp panel.

### Simulation Setup

| Parameter | Setting |
|---|---|
| Model | Qwen3-8B (Ollama local) |
| Conditions | G1-student, G1-auditor, G2-student, G3-student |
| Deterministic run | T = 0.0, N = 1 (**reproducibility floor**) |
| Stochastic run | T = 0.5, N = 10 (**robustness check**) |
| System prompt | Persona sentence + full participant briefing |
| User prompt | Section A + B + E + (G2/G3) AI panel in webapp-matching markdown |
| Output | JSON: `{"judgment", "confidence", "reasoning"}` |

**T = 0 vs T = 0.5 — honest framing.** T = 0 gives a deterministic anchor any researcher can re-run to get identical numbers (mechanism verification). T = 0.5 with N = 10 estimates the model's behavioral sensitivity to **token-sampling randomness** (robustness check). The study **explicitly does not claim** T = 0.5 variance simulates human individual differences: human variation arises from personality, experience, and attention; LLM variation arises from softmax sampling. The two are mechanistically incomparable. The LLM simulation is positioned as a **computational reference point**, not a substitute for human behavior.

---

## 3.6 Analysis Plan

- **Primary metric**: **accuracy** (proportion correct) per participant per condition.
- **Effect size estimation** (because N = 4 per group makes NHST inappropriate): **Cliff's δ** (non-parametric ordinal effect size), **Hedges' g** (bias-corrected standardized mean difference), and **95% bootstrap confidence intervals** (B = 10,000).
- **Signal-type subgroup analysis (RQ2)**: accuracy computed separately for numerical-dominant vs text-dominant question subsets.
- **AI Override Rate (AOR) for RQ3**: proportion of participants giving the correct answer on questions where the AI was wrong; G2 and G3 compared to assess error-correction capacity.
- **Trust survey**: descriptive statistics per group; cross-group comparisons restricted to structurally equivalent items.
- **LLM simulation results** reported alongside but not merged with human results.

---

## 3.7 Key Limitations

| L | Limitation |
|---|---|
| **L1** | Synthetic data — replicates statistical properties of real procurement but cannot capture organisation-specific behaviour |
| **L2** | Elevated experimental base rate (50% vs ~5% in real settings) — affects absolute accuracy but not relative group comparisons |
| **L3** | Stylistic leakage from PACE hints — anomalous free-text may differ stylistically from normal free-text |
| **L4** | RAG top-k = 5 not systematically tuned |
| **L5** | Single model (Qwen3-8B); larger models may amplify or attenuate format effects |
| **L6** | RAG corpus contains 16% anomalous orders without labels (implicit few-shot risk) |
| **L7** | Small sample (N = 12) — proof-of-concept pilot, not confirmatory |
| **L8** | Student sample, not professional auditors |
| **L9** | Non-equivalent trust survey across groups (G1 measures statistical-deviation trust; G2/G3 measure AI trust) |
| **L10** | LLM simulation has no practice-round feedback (no trust calibration) |
| **L11** | LLM simulation lacks G2 colour cues (red/green) present in webapp |
| **L12** | Qwen3-8B's pretraining may include procurement fraud knowledge |
| **L13** | One-sentence persona = demographic-only level (Park et al., 2024) |
| **L14** | Iterative two-stage AI calibration (G2 first, G3 later) visible in commit history |
| **L15** | T = 0.5 stochastic variance reflects token-sampling noise, **not** human individual differences |

---

## 3.8 Summary

This methodology provides a **complete, reproducible apparatus** for measuring how AI output format influences human-AI collaboration in procurement auditing: a synthetic dataset with programmatic ground truth, a calibrated frozen AI tool, a three-group between-subjects experiment with 12 human participants, a parallel computational baseline using LLM-as-participant simulation, and an effect-size analysis plan suited to small samples.

The study is **explicitly positioned as a proof-of-concept pilot**. Confirmatory findings require larger samples and professional auditor populations. The contribution is the methodological apparatus that enables such follow-up work, plus initial directional evidence on the **evidence-vs-conclusion format question**.
