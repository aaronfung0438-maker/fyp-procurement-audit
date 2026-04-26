# Methodology Review + 章節草稿存檔

**審查角色**：FYP 評審教授  
**論文標題**：*Evidence vs. Conclusion: How LLM Output Format Shapes Human-AI Collaboration in Procurement Anomaly Auditing*  
**審查日期**：2026-04-26  
**最後更新**：2026-04-27

---

## 檔案結構

原 `methodology.md` 因編輯過程遺失，本檔案是重建 methodology.md 前的單一暫存點，分為兩部分：

### 🅰️ Part A — 修法定稿（§1–§六，第 22–340 行）

15 個 FYP defense 等級的問題清單，每條附**作者已確認的最終修法文字**（位於 `> ...` 區塊內）。重建 methodology.md 時逐條搬入對應章節。

### 🅱️ Part B — 章節草稿存檔（§1–§12，第 343 行起）

**舊版** `methodology.md` 的 §1–§12「資料集建置說明」內容快照（32 題重設計**之前**的版本）。雖含過時欄位，但 §1–§7 的 pipeline 描述、Mouser API 細節、PACE 對應表、Stage 1 Monte Carlo 公式仍可大量沿用，僅需依 Part B 開頭的「同步更新對照表」更新具體數字。

---

## 重建 methodology.md 的順序建議

1. **§1–§12（資料集建置）**：以 Part B 為文字底稿，依其開頭的「同步更新對照表」把 15 → 32、485 → 466、qwen3:7b → qwen3:8b 等過時數字全面更新；
2. **§3.1 / §3.2**：寫入 Part A 問題 1（Vaccaro 定義）、問題 3（G1 統計輔助控制組）的修法段落；
3. **§7.6**：寫入 Part A 問題 2（Section E vs G3 互補性）的修法段落；
4. **§8.1**：寫入 Part A 問題 10（base rate + C1 假陽性陷阱感知放大）的修法段落；
5. **§14**（實驗分析計畫）：依 Part A 問題 4 / 5 / 6 / 8 / 11 / 15 重寫，**§14.4 主分析計畫整節重寫**為「描述統計 + Cliff's δ + BF₁₀ + 非參數」三層次（**完全捨棄** mixed logit / GEE）；
6. **§14.10**「Pre-registration」章節**整章刪除**（FYP 學士層級不採用）；
7. **§16.1**：寫入 Part A 問題 6（樣本量 N=4）、問題 9（RAG 含異常訂單）的修法段落；
8. **最後核對** §0.2、§2.3、§8.4 的 RQ 措辭與 §14.1 完全同步。

---

## 一、整體評價

這份 methodology.md 在 FYP 層級已屬上乘。資料生成 pipeline 有 Mouser API 撐真實性、有 PACE 撐理論性、有固定種子撐可重現性。32 題的 A/B/C 分層設計——讓每類異常出現兩次（B 區高訊號 + C 區低訊號）——是論文最有價值的分析切入點。§14 的分析計畫完整且務實，四種結果情境的預寫策略也展現了成熟的研究思維。

以下問題按「defense 時被問到會不會扣分」排列。

---

## 二、結構性問題（會影響分數，必須在論文定稿前處理）

### 問題 1：「Human-AI Collaboration」的操作定義缺失

**問題**：論文標題寫 Human-AI Collaboration，但實驗中 AI 輸出是凍結的、單向的、不互動的。人類看完 AI 的輸出後做自己的判斷，AI 不根據人類反饋調整。這更接近 **AI-assisted decision-making** 而不是雙向 collaboration。

**為什麼重要**：評審會問「你的 collaboration 在哪裡？」如果答不出操作定義，整個標題的合法性受質疑。

**修法**：在 §3.1 或 §3.2 加入以下段落（保留 2 段 Vaccaro 直接引文，其餘以 paraphrase 主動定位 G2 / G3 的位置）：

> **本研究的「人機協作」(human-AI collaboration) 操作定義**
>
> 本研究依 Vaccaro, Almaatouq & Malone (2024) 在 *Nature Human Behaviour* 8(12), 2293–2303 的元分析操作框架界定 human-AI collaboration。Vaccaro 將其元分析的合格標準定為：
>
> > "the paper needed to present an original experiment that evaluated some instance in which **a human and an AI system worked together to perform a task**." (§4.1.1 Eligibility Criteria)
>
> 在此寬定義下，Vaccaro 將不同協作型態（AI 解釋有無、AI 信心分數有無、人機分工方式等）視為 11 項 moderator 變數而非排除條件。其中第 (8) AI explanation 與第 (9) AI confidence 兩項 moderator 直接對應本研究的核心操弄變數：
> - **G2（結論式：suspicious / normal + 一句理由）** 對應 (8) + (9) 的傳統實作 — 給結論並附簡短解釋
> - **G3（證據式：4 條結構化線索，無結論）** 是本研究獨創的格式變體，將「解釋」從附屬資訊提升為主體輸出
>
> Vaccaro 的 300+ 效果量元分析發現 (8) 與 (9) 的有無對協作表現皆**無顯著影響**，並在 Discussion 建議研究者降低對此議題的投入。本研究的學術價值正在於正面挑戰此 null finding — 透過全新的「結論式 vs. 證據式」格式對比，測試是否存在 Vaccaro 元分析未涵蓋的子型差異。
>
> 關於本研究的單向設計（人類接收凍結的 AI 輸出後做最終判斷，AI 不依人類反饋即時調整），Vaccaro 明確指出：
>
> > "**Most (>95%) of the human-AI systems in our data set involved humans making the final decisions after receiving input from the AI algorithms.**" (Discussion)
>
> 因此本研究 G2 / G3 屬 Vaccaro 元分析中佔 95% 以上的主流型態，與 "human-AI collaboration" 一詞完全相容。本研究範圍**不**包含雙向對話、AI 自主執行、AI 即時根據人類反饋學習等型態（後者列為未來工作方向）。部分文獻（如 Bansal et al., 2021）將此類設計另稱為 "AI-assisted decision-making"，兩個術語在本研究領域可互換使用。

---

### 問題 2：Section E 與 G3 AI 證據的重疊——incremental value 未論證

**問題**：三組受試者都看到 Section E 偏差特徵（例如「單價 $8.90 vs SKU 中位 $2.80 → 3.2× higher」）。G3 的 AI 證據也可能說類似的話。如果 G3 的 4 條證據只是 Section E 的重複，那 G3 vs G1 的差異不是來自「AI 證據有幫助」，而是來自「同一個訊息被說了兩遍所以更顯眼」。

**為什麼重要**：這是一個混淆變數 (confound)。§7.3 和 §7.4 花了大量篇幅辯護「Section E 不是黑盒」和「不是給答案」，但沒有正面回答「Section E 和 G3 證據有什麼不一樣」。

**修法**：在 §7 末尾加一段（建議 §7.6）：

> **7.6 Section E 與 G3 AI 證據的互補性**
>
> Section E 提供的是 SKU 層級的單變量統計偏差（例如「單價是中位數的 N 倍」），其訊號範圍嚴格限於數值欄位。G3 AI 證據則提供跨欄位語義推理的產物（例如結合 supplier\_profile 中「2024 新成立貿易公司」與 purchase\_note 中「僅收到單一報價」的交叉分析）。
>
> 兩者的重疊主要發生在**數值類異常**（item\_spending、border\_value）上——此時 Section E 的 ratio 已足以提供關鍵線索，G3 證據的 incremental value 較低。然而，在**文字類異常**（unusual\_vendor、vendor\_spending、quote\_manipulation、conflict\_of\_interest）上，Section E 完全無法提供訊號（所有 ratio 和 z-score 均在正常範圍），G3 AI 證據是受試者唯一的額外資訊來源。
>
> 這也是 RQ2 將 signal\_type 作為調節變數的理論基礎：我們預期 G3 的優勢（若存在）將集中在 text\_dominant 子集上，正是因為 Section E 在該子集上失效，G3 的 incremental value 最大。

---

### 問題 3：G1 控制組的定位不夠精確

**問題**：§3.2 將 G1 描述為「控制組」，但 G1 看到的不只是「原始訂單」——還包括 Section E 偏差特徵。G1 實際上是「人類 + 統計輔助」，不是 naked human baseline。

**為什麼重要**：如果評審以為 G1 是沒有任何輔助的人類，會低估你的 baseline 強度，也會誤解 G2/G3 的 incremental 效果。

**修法**：§3.2 的 G1 行修改為：

| 組 | 看到 AI 嗎 | AI 形式 | 對照 Vaccaro 的設計缺陷 |
|---|---|---|---|
| G1 | ❌ | — | **統計輔助控制組**：看到原始欄位 + Section E 偏差特徵，但無 AI 輸出。三組共享 Section E 作為共同基線，唯一操縱變數是 AI 輸出的有無與格式。 |

---

## 三、前後不一致問題（必修，但不致命）

### 問題 4：§8.4 的 RQ 對應表仍是舊版

**現狀**：

| 區塊 | 主要對應 RQ |
|---|---|
| C1 | RQ2（人類能否抗拒 D² / AI 的誤導不誤判？） |
| C2a + C2b | RQ3（邊界假陰性率，本研究最關鍵的 measurement） |

**問題**：§14 的新 RQ 定義已改變——RQ2 現在是「訊號類型的調節效應」，RQ3 是「推翻 AI 錯誤」。§8.4 的對應表沒有同步更新。

**修法**：

| 區塊 | 主要對應 RQ |
|---|---|
| A | RQ1（整體 accuracy — specificity） |
| B | RQ1（整體 accuracy — sensitivity） |
| C1 | RQ2（normal 子集中 specificity；假陽性陷阱測試 AI 格式是否誘導誤判） |
| C2a | RQ2（numeric\_dominant 子集的 sensitivity） |
| C2b | RQ2（text\_dominant 子集的 sensitivity——G3 預期優勢最大處） |
| AI 答錯的題目（跨 block） | RQ3（推翻 AI 錯誤的能力） |

---

### 問題 5：§0.2 摘要仍用舊版 RQ 措辭

**現狀**：§0.2 寫「(ii) 推翻率（AOR）、(iii) 邊界案例的假陰性率」。

**問題**：(ii) 應改為「訊號類型的調節效應」，(iii) 應改為「推翻 AI 錯誤的能力」。且 AOR 在新框架下嚴格只適用 G2（§14.2 已正確界定），但 §0.2 的語氣暗示 AOR 適用所有組。

**修法**：

> 實驗端：設置 G1（人類 + 統計輔助）、G2（人類 + AI 結論）、G3（人類 + AI 證據）三組受試者，比較三種 AI 輸出格式對 (i) 整體偵測準確率、(ii) 不同訊號類型（數值 vs. 文字）下的格式效應差異、(iii) 人類在 AI 犯錯時的修正能力 的影響。

---

### 問題 6：§14.8 與 §16.1 樣本數描述需統一為實際定案值

**現狀**：§14.8 寫 N = 8–15、§16.1 第 2 點寫「每組 ≥ 30 是統計下限」，前後矛盾且都不是實際數字。

**實際定案**：FYP 時程下，每組招募 **N = 4 人**，三組總計 **12 人**（pilot/proof-of-concept 規模）。

**問題**：4 人/組是非常小的樣本，必須在 §14.8 與 §16.1 統一寫實話，並把分析計畫的論述軸心從「p 值」轉為「效果量 + Bayes Factor + bootstrap CI」。

**修法（§14.8 整節重寫；同時連動更新 §14.4 主分析計畫，捨棄 mixed logit）**：

> ### 14.8 樣本數與統計分析定位
>
> #### 務實樣本數
> - **每組 N = 4 人**，三組總計 **12 人**（FYP 時程下的實際招募定案）
> - 每受試者：32 主題 × ~2 分鐘 + 練習 2 題 + 問卷 ≈ **70–90 分鐘 / 人**
> - **題目層級觀測值**：4 人 × 32 題 = **128 obs / 組**，三組合計 384 obs
>
> #### 為什麼此樣本仍可寫成 FYP 論文
> 1. **完整 pipeline 驗證**：本研究核心貢獻之一是建立並驗證從合成資料 → RAG → LLM 凍結 → UI → 資料分析的端到端框架，N = 4 / 組已足以驗證每個環節都能跑通
> 2. **效果量與 Bayes Factor 為主**：在此樣本下 p 值不再是主軸；報 Cliff's δ、OR、95% bootstrap CI 與 BF₁₀（BF₁₀ > 3 支持有差；BF₁₀ < 1/3 支持沒差且為**有意義的負面結論**，呼應 Vaccaro (2024) 元分析的 null finding）
> 3. **完全捨棄推論型混合模型**：4 個 cluster 估 random-effect variance 會嚴重不穩定（不收斂或 variance estimate 退化到 0），本研究**不**使用 mixed-effects logistic regression / GEE。混合模型保留為後續大樣本研究的主分析工具
> 4. **質性互補**：自由文本理由 + 信任感問卷 + 決策時間補強說服力
>
> #### 統計分析三層次（取代原 §14.4 的 mixed logit 計畫）
>
> **主層 — 描述統計與效果量**（不假設分布、不依賴 p 值）
> - 三組各 32 題正確率：中位數 + IQR + **95% bootstrap CI**（10 000 次重抽）
> - **Per-block 正確率熱力圖**（A / B / C1 / C2a / C2b × G1 / G2 / G3）— 每格逐筆列出 4 人中答對人數
> - **文字 vs. 數值類異常正確率對比** — 直接對應 RQ2 的核心問題：「文字類異常是否最容易被誤判？G3 是否在文字類有最大優勢？」
> - **Cliff's δ**（非參數效果量，對小樣本比 Cohen's d / Hedges' g 穩定）
>
> **補充層 — 非參數檢定 + Bayesian**
> - Mann-Whitney U（兩組對比）/ Kruskal-Wallis（三組）：報 p 與 rank-biserial r，僅作參考
> - **Bayesian proportion test → BF₁₀**：處理 null 結果的主要工具
> - **Fisher's exact test**：RQ3 的「AI 答錯題」子集 G2 vs. G3 二乘二表
>
> **質性層** — 自由文本理由（編碼為「訴諸 Section E ratio」/「訴諸 supplier profile」/「訴諸 purchase note」/「訴諸 AI 結論」等類別）+ 信任問卷 + 決策時間
>
> #### 預期可偵測效應量（誠實版）
> - 主效應：OR ≈ 4 ↔ 正確率 ~80% vs ~50%（**大效應**） — 可能達到 BF₁₀ > 3
> - 交互作用：OR ≈ 6+（**極大效應**） — 12 人下幾乎只能在 text_dominant 子集這種設計上預期最大差異處才有機會偵測
> - **任何中小效應（OR < 2.5）幾乎不可能在 N = 4 / 組下偵測到**；遇 null 直接報 BF₁₀ 並接受結論，不嘗試硬擠 p < 0.05
>
> #### 研究定位
> 本研究明確定位為 **proof-of-concept / pilot study**，**不**主張統計上的決定性結論。論文 Chapter 5 將清楚聲明：
> - 主要貢獻：(a) 設計並驗證證據 vs. 結論的對比實驗框架可行性；(b) 提供初步效果量估計給後續大樣本研究做 power analysis；(c) 公開全部資料、prompt、frozen LLM 輸出供他人 replicate
> - 後續工作：擴大至每組 N ≥ 30，跨產業審計員樣本，再做確認性檢定（含 mixed-effects logistic regression 作為主分析）

**修法（§16.1 第 2 點）**：

> 2. **樣本量與分析模型**：本研究每組僅 4 人（總 12 人），定位為 proof-of-concept / pilot study。此樣本量遠低於傳統大樣本檢定（N ≥ 30 / 組）的下限。受限於 4 個 cluster 估混合效應變異數會不穩定，本研究**捨棄** mixed-effects logistic regression 與 GEE，改以描述統計 + Cliff's δ + 95% bootstrap CI + BF₁₀ 為主分析（§14.4）。只能偵測 OR > 4 級的大效應；中小效應（OR ∈ [1.5, 2.5]）必然會 null，此時 BF₁₀ < 1/3 可作為「pilot 級證據支持無差異」結論。任何「顯著結果」皆需在後續大樣本研究中確認，本研究不主張決定性結論。

---

### 問題 7：模型名稱不一致 — ✅ **已解決**

**現狀更新（2026-04-26）**：實機 `ollama list` 顯示已 pull 的是 `qwen3:8b`（5.2 GB，500a1f067a9f）；Ollama registry 中**沒有** `qwen3:7b` 此 tag（pull 會失敗）。

**處置**：
- `freeze_llm_outputs.py` 的 `ANALYSIS_MODEL` 已改為 `"qwen3:8b"`
- methodology.md 重建時，§4.8 / §12.2 / §14.9 / §15.4 / §16.1 全部用 `qwen3:8b`
- 後續所有操作指令統一使用 `ollama pull qwen3:8b`

**無需再修法**。

---

### 問題 8：§14.3 的 B-approval\_bypass 歸類需註明 Variant（code 已確認）

**現狀**：B-approval\_bypass 歸在 `numeric_dominant`，沒說是 V-A 還是 V-B。

**問題**：根據 §8.2，B 區優先選 Variant A（`policy_violation=1`）。V-A 的主訊號是政策違規（類別型），不是純數值型。需要解釋為什麼歸 numeric_dominant。

**Code 確認**：`prepare_stage3.py` 中 `add_policy_violation()`（line 356–366）將 `policy_violation = 1` 的 3 種觸發條件明確列出：
> 1. **`approver_id` 為空**（缺失簽核者 — Variant A 標誌）
> 2. **金額 ≥ $1,000 且 approver = `A-PROC-01`**（跳過 CTO 階層）
> 3. **金額 ≥ $5,000 且 approver = `A-CTO`**（跳過 CEO 階層）
>
> Stage-3 抽樣邏輯（line 430–433）：B-approval_bypass 優先選 `policy_violation=1` 候選，並以最高 log-D² 為 tie-breaker。

**修法**：加 footnote：

> **腳註：B-approval_bypass 的 Variant 歸類**
>
> B 區的 approval_bypass 題選的是 Variant A，定義為 `policy_violation = 1`，由以下 3 條規則任一觸發（code: `add_policy_violation`，`prepare_stage3.py` line 356–366）：
> (1) `approver_id` 為空；
> (2) 金額 ≥ $1,000 但簽核者僅為 `A-PROC-01`（跳過 CTO 階層）；
> (3) 金額 ≥ $5,000 但簽核者僅為 `A-CTO`（跳過 CEO 階層）。
>
> 雖然 V-A 的核心訊號為類別/規則型（policy 違規），但其 Stage-1 mutation 通常伴隨金額抬升（觸發條件 (2)、(3) 內建金額門檻）以及 Mahalanobis D² 偏離，使數值偏差同時可見。因此本研究在 RQ2 訊號分類中將 B-approval_bypass 歸入 `numeric_dominant`（受試者不需閱讀 purchase_note 也能從欄位偏差察覺）。
>
> 對應地，**C2a 的 approval_bypass** 選的是 **Variant B**：approver_id 完整、policy_violation = 0，但 `approval_lag = 0.05d`（極短）— linear D² 不敏感、log D² 高，屬於需更精細閱讀才能察覺的隱晦數值異常。**B (V-A) vs. C2a (V-B) 構成同一類異常的「強訊號 vs. 弱訊號」對照**，是 RQ2 訊號層級分析的關鍵設計。

---

## 四、方法論問題（defense 會被追問，建議主動揭露）

### 問題 9：RAG 語料庫包含異常訂單——隱式 few-shot 效應

**問題**：466 筆 RAG 語料中包含約 60 筆異常訂單（76 總注入 − 16 被選入實驗/練習題）。這些異常訂單的 purchase\_note 含有 Stage 2 埋入的語義線索。LLM 在 retrieve 到這些異常訂單時，可能間接獲得「什麼是可疑的」隱式知識——等同於 implicit few-shot learning。

**為什麼重要**：你在 experiment\_intent.md 定義 Test A 為「naive LLM」，但 RAG 裡有異常訂單意味著 LLM 不是完全 naive。

**修法**：在 §16.1 加一條限制：

> RAG 語料庫中約 60 筆訂單帶有 Stage 2 注入的異常語義線索（injection\_plan ≠ "none" 但未被選入 32 題實驗集或 2 題練習題）。LLM 可能透過 RAG 檢索間接獲得異常偵測的隱式知識，這與 Test A「naive LLM」的假設存在張力。此效應的方向為正向（使 LLM 表現偏好），因此不會高估「證據 vs. 結論」格式差異的效應量，但可能高估 LLM 整體準確率（Chapter 4 的 LLM-only baseline）。

---

### 問題 10：32 題的 base rate 與 500 筆不同

**問題**：500 筆的異常率 15.2%。但 32 題中有 16 筆異常（B 區 8 + C2a 3 + C2b 5）= **50% 異常率**。受試者如果感知到「一半都是異常」，會調整判斷策略（more liberal criterion），影響 precision 和 specificity 的解讀。

**修法**：在 §8.1 加一段：

> 32 題實驗集的異常率（50%，16/32：B 區 8 + C2a 3 + C2b 5）顯著高於 500 筆母體的異常率（15.2%，76/500）。此為刻意的設計取捨：若維持 15.2% 的 base rate，32 題中僅約 5 筆異常，不足以支撐 per-class 和 per-signal-type 的子集分析。高異常率可能導致受試者採取更寬鬆的判斷標準（response bias），使整體 false positive rate 上升。
>
> 此外，**Block C1 的 6 題正常訂單因 D² 偏高（85–95 百分位），其 Section E 偏差特徵看起來可能可疑**，使受試者主觀感知的「疑似異常率」可能進一步上升至 22 / 32 = **68.75%**（16 真異常 + 6 假陽性陷阱），強化寬鬆判斷傾向。這正是 C1 作為「假陽性陷阱」的設計本意 — 在主觀感知偏差最大的情境下測試三組能否抗拒誤判。
>
> 然而，上述 base rate shift 與感知放大效應對三組的影響是均等的（G1 / G2 / G3 看到的題目完全相同），因此**不影響組間比較的內部效度**，僅限制結果推論至真實 base rate（15.2%）情境的外部效度。

---

### 問題 11：決策時間的收集方式未交代

**問題**：§14.2 列決策時間為二級指標，但沒有說明：
- 怎麼收集（UI timestamp 差值？受試者自報？）
- 離群值處理（某題 > 10 分鐘怎麼辦？）
- 是否扣除非作答時間（中途離開等）

**修法**：在 §14.2 二級指標下方加：

> 決策時間定義為 UI 前端記錄的「題目顯示時間」至「受試者點擊提交」的差值（秒）。若單題時間 > 300 秒（5 分鐘），視為離群值，在分析中以該組中位時間替代（winsorization）。32 題總時間為各題時間加總。分析時取 log 轉換後再做組間比較（Mann-Whitney U），因反應時間分布右偏。

---

## 五、小問題（快速修即可）

### 問題 12：§2.3 的 RQ 表格措辭要與 §14.1 完全同步

§2.3 目前寫的是白話版 + 分析方法的簡表，但 RQ 的英文措辭沒有出現。建議在白話後面加括號引用 §14.1 的正式英文 RQ，或直接將 §14.1 的英文 RQ 搬到 §2.3（因為 RQ 通常在論文前段就要出現完整版）。

---

### 問題 13：§14.6.1 shadow G2 的 sanity check 需量化標準

**現狀**：「實證上 shadow\_g2 與正式 g2\_verdicts 應幾乎一致」。

**修法**：加一句：

> 凍結完成後，計算 shadow\_g2 與 g2\_verdicts 在 32 題上的 agreement rate。若 < 90%（即 > 3 題不一致），須在論文中揭露並討論 temperature=0 下的非確定性來源（如 Ollama 的 batch parallelism 或 KV cache 差異）。若 100% 一致，shadow\_g2 在功能上等價於 g2\_verdicts，但保留作為方法論嚴謹性的交叉驗證。

---

### 問題 14：論文整體語言——中文還是英文？

§9.4 提到「整本論文用中文」，但 methodology.md 本身是中英混寫，§14 的 RQ 全部用英文，reason 欄位也是英文。建議在 §0 或論文 Chapter 3 開頭明確聲明：

> 本論文以中文撰寫。研究問題 (RQ)、技術術語、程式碼片段及 reason 欄位保留英文原文，以確保與國際文獻的可對照性及技術精確性。

---

### 問題 15：§14.9 第 4 種結果情境措辭過時（連動 N=4 定案）

**現狀**：原 §14.9 「四種結果情境」的第 4 種寫「8B 級 local LLM 能力不足」，將 null 結果歸因於模型規模。

**問題**：在 N = 4 / 組的條件下，「全部沒差」幾乎是 default outcome — 此時把 null 全推給「模型規模不足」是站不住腳的歸因（樣本量問題 ≫ 模型問題）。需要把第 4 種情境重寫成更有份量的論述，主動承擔「pilot scope」的定位。

**修法（§14.9 第 4 種結果情境整段重寫）**：

> **情境 4 — 三 RQ 皆未達 BF₁₀ > 3（最可能的結果）**
>
> 在 N = 4 / 組的 pilot 條件下，三 RQ 皆無法達到 BF₁₀ > 3 的「中等支持有差」門檻。本研究的主要貢獻轉為：
>
> 1. **驗證實驗框架的可行性**：完成從合成資料 → RAG → LLM 凍結 → UI → 收受試者的端到端 pipeline，所有環節皆可重現。
> 2. **提供初步效果量估計**：報 OR、Cliff's δ 與 95% bootstrap CI，供後續大樣本研究做 power analysis 與樣本數規劃。
> 3. **提供 pilot 級的 null 證據**：若進一步達到 BF₁₀ < 1/3，則為「AI 輸出格式對協作表現無顯著影響」提供初步證據，呼應 Vaccaro et al. (2024) 元分析的核心發現。
>
> **重要免責聲明**：上述呼應力受限於 N = 4 / 組的 pilot 樣本量，**僅供後續研究參考，不構成對 Vaccaro 結論的確認或反駁**。任何決定性結論皆須等待後續大樣本（每組 N ≥ 30）研究方能成立。

---

## 六、審查總結

| 嚴重程度 | 問題數 | 狀態 | 說明 |
|---|---|---|---|
| 結構性（必修） | 3 | ✏️ 定稿 | Collaboration 定義（Vaccaro 2 段引文 + paraphrase）、Section E vs G3 重疊、G1 定位 |
| 前後不一致（必修） | 5 | 4 ✏️ + 1 ✅ | §8.4 RQ 對應、§0.2 摘要、§14.8 + §16.1 樣本數（**N=4/組，總 12；捨棄 mixed logit**）、模型名稱（**已解決：qwen3:8b**）、B-approval_bypass 歸類（code 確認的 3 條觸發版） |
| 方法論（建議揭露） | 3 | ✏️ 定稿 | RAG 含異常訂單、base rate shift（含 C1 假陽性陷阱感知放大）、決策時間收集 |
| 小問題 | 4 | ✏️ 定稿 | §2.3 措辭、shadow G2 量化、語言聲明、§14.9 第 4 種結果情境改寫 |
| **合計** | **15** | **14 待寫入 + 1 已解決** | |

**狀態說明**：本檔案所列「修法」段落為與作者討論後的**最終定稿文字**，將於重建 `methodology.md` 時逐條搬入對應章節。

**底線判斷**：沒有任何一個問題是致命的。15 個問題中大部分是「寫清楚」的問題，不是「設計有缺陷」的問題。

**三項核心定案**（最終確認版）：

1. **N = 4 / 組（總 12 人）→ 砍掉推論型混合模型**
   分析軸心從「p 值是否 < 0.05」徹底轉為「**Cliff's δ + 95% bootstrap CI + BF₁₀ + 非參數補充**」。論文明確自我定位為 **proof-of-concept / pilot study**。此定位反而保護論文 — 即使所有 RQ 得 null，若 BF₁₀ < 1/3 仍是有意義的「pilot 級證據支持無差異」結論，呼應 Vaccaro (2024) 元分析的 null finding。

2. **不採用 pre-registration**
   FYP 學士層級不要求正式 pre-reg。論文以「分析計畫白紙黑字寫在 methodology.md §14.4 / §14.8 中」+「程式碼版本控制可追溯」作為事後挑指標的反證。Defense 時若被問「怎麼防 p-hacking」，回答「描述統計 + BF 為主，p 值僅作參考，本研究不做多重比較校正以外的推論決定」即可。

3. **§14.9 第 4 種情境（最可能的結果）改寫為主動承擔 pilot 定位**
   不再把 null 推給「8B 模型不夠強」，而是直接承認「N = 4 是樣本量限制」，並把貢獻重寫為 (a) 框架可行性驗證 (b) 初步效果量供後續 power analysis (c) pilot 級 null 證據（**含免責聲明：不構成對 Vaccaro 結論的確認或反駁**）。

---

# Part B — 章節草稿存檔（§1–§12，舊版快照）

## ⚠️ 同步更新對照表（重建 methodology.md 時必須先做）

> **本快照為 32 題重設計之前的舊版**。以下文字大量沿用 OK，但具體數字必須依此表全面更新；最終以 `prepare_stage3.py` 1.x 版的實際輸出為準。

| 舊文字 | 新文字 | 出現位置 / 對應 Part A 問題 |
|---|---|---|
| 15 題實驗集 | **32 題**（A 10 + B 8 + C1 6 + C2a 3 + C2b 5）+ 練習 2 題 | §6 / §8.3 / §8.4 — Part A 問題 4、6 |
| 485 RAG 文件 | **466**（500 − 32 實驗 − 2 練習） | §8.4 / §11.5 |
| `experiment_15qs_*.xlsx` | `experiment_32qs_*.xlsx` | §8.4 / §11.5 |
| `rag_corpus_485_*.jsonl` | `rag_corpus_466_*.jsonl` | §8.4 / §11.5 |
| Qwen3 7B（§7 末段） | **qwen3:8b** | §7 — Part A 問題 7 ✅ |
| `experiment_stratum` 4 值（normal / obvious_anomaly / edge_numeric / edge_text） | **5 值**（A / B / C1 / C2a / C2b）+ 新增 `practice_role` 欄位 | §6.4 層次 4 / §8.3 |
| §8.3 「凍結實驗集（15 題 + 485 RAG）」分層邏輯 | 改用 prepare_stage3.py 1.x 版邏輯（含 `policy_violation`、log-Mahalanobis、χ²(4, 0.99) = 13.28 上限過濾、C2a 取最低 linear-D²、C2b 取最低 `text_signal_score`） | §8.3 — Part A 問題 8 |
| 8 類異常注入規則（§6） | **不變**（仍是 8 類，但 `border_value` 從 C2a 移出，已在 1.x 版實作） | §6.3 / §6.4 |
| `total_amount_usd` ≥ $1,000 / $5,000 → 跳階核准 | 已新增為 `policy_violation = 1` 的觸發條件之一 | Part A 問題 8 — 含 code line 號引用 |

**另外要對齊到 Part A 的章節**：
- §3.1 / §3.2 — 加入 Vaccaro 定義段落 + G1 為「統計輔助控制組」標註（Part A 問題 1、3）
- §7.6 — 新增「Section E 與 G3 AI 證據的互補性」（Part A 問題 2）
- §8.1 — 加入 base rate + C1 感知放大段（Part A 問題 10）
- §14 — 整章重寫，§14.4 主分析改為描述統計 + BF₁₀（Part A 問題 6、11、15）
- §14.10 — pre-registration 章節整章刪除（Part A 三項核心定案 #2）

---

## 資料集建置說明 — 採購稽核模擬實驗

本文件以論文格式記錄用於人機協作實驗的合成採購資料集。每個參數均可追溯至下列三類來源之一：(a) Mouser API 真實市場資料、(b) 有明確引文支撐的建模假設、(c) 不影響 Ground-Truth 標籤的設計選擇。

配套腳本：

- `generate_dataset.py` — Stage 0（Mouser API）+ Stage 1（模擬與異常注入）
- `generate_semantics.py` — Stage 2（DeepSeek 填充語義欄位）
- `prepare_stage3.py` — Stage 3（偏差特徵 + Mahalanobis + ⚠ ~~15/485~~ → **32+2/466** 實驗切割）

### 目錄

1. 場景定義
2. 實體設定
3. 零件清單與 Stage 0 API 錨點
4. Stage 1 蒙地卡羅管線
5. 範例詳解：PO-2024-0001（一筆正常訂單）
6. 異常注入 — PACE 分類法 T
7. Stage 2 — DeepSeek 語義欄位生成
8. Stage 3 — `prepare_stage3.py`
9. 可重現性保證
10. 參數來源摘要
11. 如何閱讀 Excel 資料集
12. 參考文獻

---

### 1. 場景定義

**公司**。 ABC Electronics Ltd. — 一家虛構的香港 30 人 IoT 硬體公司，專為內部研發採購電子零件。

**實驗任務**。 稽核人員逐一審查採購訂單（PO），判斷每筆訂單是「正常」或「異常」。實驗比較三種稽核員條件：

| 組別 | 稽核員看到的資訊 |
|---|---|
| G1 對照組 | 僅原始 PO（⚠ 重建時依 Part A 問題 3 改為「原始 PO + Section E 偏差特徵」） |
| G2 結論型 | 原始 PO + AI 裁決（"suspicious" / "normal"）+ 一句理由 |
| G3 證據型 | 原始 PO + AI 呈現的 4 項結構化可疑特徵 |

**資料集規模**。 一個會計年度（2024-01-01 至 2024-12-31），共 500 筆訂單，其中 424 筆正常，76 筆帶有注入異常，來自八類規則 — 五類直接改編自 PACE PO/ACRA 指標目錄（Westerski et al., 2021），兩類將 PACE 的 ITQ 範疇指標重新對應至 PO 層級，一類（`bank_account_change`）來自 ACFE / IJFMR 當代詐欺類型學。

---

### 2. 實體設定

#### 2.1 工程師（請購人）

```python
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
```

權重總和為 1.00。最忙碌的工程師（R-ENG-01）約發出 90 筆訂單，最少的（R-ENG-08）約 40 筆。此異質性反映文獻觀察：採購詐欺傾向集中於少數重複行為者。

#### 2.2 核准人（門檻制）

```python
APPROVER_PROC = "A-PROC-01"   # total < USD 1,000
APPROVER_CTO  = "A-CTO"       # USD 1,000 ≤ total ≤ 5,000
APPROVER_CEO  = "A-CEO"       # total > USD 5,000
```

總金額決定核准人，規則完全確定性。此設計使 `border_value` 攻擊（第 6 節）得以精確：$999 訂單天然繞過 CTO。

#### 2.3 供應商（25 家正常 + 5 家異常池）

共 30 家供應商：

| ID 範圍 | 名稱格式 | 成立年份 | 標記 |
|---|---|---|---|
| S-001 … S-025 | Supplier NNN Electronics Co. | 2008–2022（TruncNorm 中心 2015）| `is_anomaly_pool = False` |
| S-026 … S-030 | Supplier NNN Trading Ltd. | 2024（當年新成立）| `is_anomaly_pool = True` |

異常池內建兩個紅旗：成立時間過新（當年採購年）與公司型態（貿易商而非製造商）。

#### 2.4 請購人–供應商偏好圖（Markov 風格）

每位工程師預先指定三家習慣性供應商，從正常 25 家不重複抽樣：

```python
def build_preferences(suppliers_df, rng):
    normal = suppliers_df.loc[~suppliers_df["is_anomaly_pool"], "supplier_id"].tolist()
    prefs = {}
    for r in REQUESTERS:
        chosen = rng.choice(normal, size=3, replace=False)
        prefs[r["id"]] = {"primary": chosen[0], "secondary": chosen[1], "tertiary": chosen[2]}
    return prefs

def sample_supplier(requester_id, prefs, rng):
    r = rng.random()
    if   r < 0.65: return prefs[requester_id]["primary"]
    elif r < 0.90: return prefs[requester_id]["secondary"]
    else:          return prefs[requester_id]["tertiary"]
```

(0.65, 0.25, 0.10) 的機率構成退化 Markov 鏈。正常訂單永遠不會路由至 S-026…S-030；任何此類路由因此都是異常注入的鑑識標記。

---

### 3. 零件清單與 Stage 0 API 錨點

#### 3.1 10 個 SKU

```python
COMPONENTS_DEF = [
    {"mouser_pn": "603-CFR-25JB-52-10K",   "sku": "CFR-25JB-52-10K",    "category": "Resistor",  "qty_median": 100, "qty_sigma_log": 0.9},
    {"mouser_pn": "81-GCM21BR71H104KA7L",  "sku": "GCM21BR71H104KA7L",  "category": "Capacitor", "qty_median":  80, "qty_sigma_log": 0.9},
    {"mouser_pn": "511-STM32F103C8T6",     "sku": "STM32F103C8T6",      "category": "IC",        "qty_median":   8, "qty_sigma_log": 0.7},
    {"mouser_pn": "356-ESP32WROOM32EN8R2", "sku": "ESP32-WROOM-32E",    "category": "IC",        "qty_median":  10, "qty_sigma_log": 0.7},
    {"mouser_pn": "358-SC0915",            "sku": "SC0915",             "category": "DevBoard",  "qty_median":   5, "qty_sigma_log": 0.6},
    {"mouser_pn": "2154-101262",           "sku": "Soldered-101262",    "category": "DevBoard",  "qty_median":   8, "qty_sigma_log": 0.6},
    {"mouser_pn": "485-4566",              "sku": "AHT20-4566",         "category": "Sensor",    "qty_median":   5, "qty_sigma_log": 0.7},
    {"mouser_pn": "262-BME280",            "sku": "BME280",             "category": "Sensor",    "qty_median":   8, "qty_sigma_log": 0.7},
    {"mouser_pn": "455-B4B-XH-A",          "sku": "B4B-XH-A",           "category": "Connector", "qty_median":  30, "qty_sigma_log": 0.8},
    {"mouser_pn": "590-588",               "sku": "MG-588",             "category": "PCB",       "qty_median":   3, "qty_sigma_log": 0.6},
]
```

SKU 與數量中位數為設計選擇；價格與前置時間從 Mouser API 擷取。

#### 3.2 Mouser API 呼叫（Stage 0）

```python
def _fetch_exact_pn(mouser_pn: str, api_key: str) -> dict:
    url     = f"https://api.mouser.com/api/v1/search/partnumber?apiKey={api_key}"
    payload = {"SearchByPartRequest": {"mouserPartNumber": mouser_pn,
                                       "partSearchOptions": "exact"}}
    resp = requests.post(url, headers={"Content-Type": "application/json"},
                         json=payload, timeout=20)
    parts = resp.json()["SearchResults"]["Parts"]
    if not parts:
        raise MouserAPIError(f"{mouser_pn} not found")
    return parts[0]
```

每次回應持久化至 `data/mouser_raw_exact.json`，附帶快取指紋：

```json
{
  "_meta": {
    "first_fetched_at": "2026-04-20T01:55:36",
    "last_modified_at": "2026-04-20T01:55:36",
    "note": "Immutable baseline. Do not overwrite unless re-baselining."
  },
  "262-BME280": {
    "LeadTime": "84 Days",
    "PriceBreaks": [
      {"Quantity": 1,   "Price": "$3.21"},
      {"Quantity": 10,  "Price": "$2.95"},
      {"Quantity": 100, "Price": "$2.74"}
    ]
  }
}
```

後續所有執行均從此快取讀取，保證完全重現性。

#### 3.3 價格統計 — 從階梯定價到連續分布

Mouser 價格區間是**數量階梯**：買 100–999 件固定 $0.0987/件；買 ≥ 1000 件則 $0.092。這是階梯函數，不是連續曲線。

模擬不複製階梯定價。取而代之，將 *k* 個公開區間價格視為底層市場價格分布的實證觀測值，配適連續 Log-Normal 分布，供第 8 節多變量異常評分使用。

```python
def _price_stats(price_breaks: list) -> tuple[float, float]:
    prices = [float(re.sub(r"[^\d.]", "", b["Price"])) for b in price_breaks]
    prices = [p for p in prices if p > 0]
    log_p  = [math.log(p) for p in prices]

    geo    = math.exp(sum(log_p) / len(log_p))                       # e^(mean ln p)
    sigma  = (math.log(max(prices)) - math.log(min(prices))) / 4     # 4-sigma 法則
    sigma  = max(0.05, min(0.50, sigma))                             # 截斷
    return round(geo, 4), round(sigma, 3)
```

閉合公式（對於價格區間 *p₁ < … < pₖ*）：

```
µ_price = (1/k) · Σᵢ ln(pᵢ)         [Log-Normal 對數空間均值]
e^µ     = {pᵢ} 的幾何平均            [取樣中心]
σ_price = clamp(0.05, 0.50)( (ln pₖ − ln p₁) / 4 )
```

幾何平均是 Log-Normal 配適 *k* 個觀測值的最大概似中心。「除以四」為工程 4-σ 法則（觀測範圍 ≈ ±2σ 覆蓋 ≈ 95% 的機率質量）。截斷防止 *k=2* 時出現病態值。

#### 3.4 前置時間解析

```python
def _lead_days(product: dict) -> int:
    raw = str(product.get("LeadTime", ""))
    days_m  = re.search(r"(\d+)\s*day",  raw, re.IGNORECASE)
    weeks_m = re.search(r"(\d+)\s*week", raw, re.IGNORECASE)
    range_m = re.search(r"(\d+)\s*-\s*(\d+)\s*week", raw, re.IGNORECASE)
    if range_m: return int(round((int(range_m.group(1)) + int(range_m.group(2))) / 2 * 7))
    if weeks_m: return int(weeks_m.group(1)) * 7
    if days_m:  return int(days_m.group(1))
    if "non-stock" in raw.lower() or "call" in raw.lower(): return 21
    if "stock" in raw.lower(): return 3
    return 14
```

全部 10 個固定 SKU 均回傳 `"NNN Days"` 格式，實際上只有 `days_m` 分支觸發；其餘分支為穩健性保留。

#### 3.5 前置時間變異數

```
σ_lead = max( 2 天, 0.25 · µ_lead )
```

變異係數 0.25 落在穩定電子供應鏈 0.2–0.3 區間的中段（Silver, Pyke & Peterson, 2017, ch. 7）。2 天下限防止短前置時間零件出現退化分布。此 σ 僅影響 `expected_delivery_lag_days` 的正態分布，不進入任何異常標籤。

#### 3.6 零件彙整表（Mouser 快取實際值）

| SKU | 製造商 | µ_price (USD) | σ_price (log) | qty_med | σ_qty (log) | µ_lead (天) | σ_lead |
|---|---|---|---|---|---|---|---|
| CFR-25JB-52-10K     | YAGEO         | 0.0218  | 0.500 | 100 | 0.9 | 126 | 31.5 |
| GCM21BR71H104KA7L   | Murata        | 0.1163  | 0.384 |  80 | 0.9 | 114 | 28.5 |
| STM32F103C8T6       | ST            | 4.0631  | 0.143 |   8 | 0.7 | 210 | 52.5 |
| ESP32-WROOM-32E     | Espressif     | 4.4839  | 0.145 |  10 | 0.7 | 120 | 30.0 |
| SC0915              | Raspberry Pi  | 4.0000  | 0.150 |   5 | 0.6 | 112 | 28.0 |
| Soldered-101262     | Soldered      | 8.8036  | 0.050 |   8 | 0.6 |  38 |  9.5 |
| AHT20-4566          | Adafruit      | 4.5000  | 0.150 |   5 | 0.7 |  90 | 22.5 |
| BME280              | Bosch         | 2.9156  | 0.124 |   8 | 0.7 |  84 | 21.0 |
| B4B-XH-A            | JST           | 0.1027  | 0.163 |  30 | 0.8 | 112 | 28.0 |
| MG-588              | MG Chemicals  | 15.5745 | 0.097 |   3 | 0.6 |  23 |  5.75 |

---

### 4. Stage 1 蒙地卡羅管線

#### 4.1 全域設定

```python
RANDOM_SEED   = 42
N_ORDERS      = 500
START_DATE    = date(2024, 1, 1)
END_DATE      = date(2024, 12, 31)
CURRENCY_DIST = {"USD": 1.00}          # 單一幣種
APPROVAL_LAG_MEAN, APPROVAL_LAG_STD = 2.0, 1.5
APPROVAL_LAG_MIN,  APPROVAL_LAG_MAX  = 0.1, 14.0
```

#### 4.2 Poisson 訂單日期

```
Nₜ ~ Poisson(λ),   λ = N / T = 500 / 366 ≈ 1.366
```

```python
def order_dates(n, rng):
    total  = (END_DATE - START_DATE).days + 1
    lam    = n / total
    counts = rng.poisson(lam, total).astype(int)
    diff = n - int(counts.sum())
    while diff > 0: counts[int(rng.integers(0, total))] += 1; diff -= 1
    while diff < 0:
        nz = np.where(counts > 0)[0]
        counts[int(rng.choice(nz))] -= 1
        diff += 1
    return [START_DATE + timedelta(days=int(t))
            for t, c in enumerate(counts) for _ in range(c)]
```

理由：Poisson 是事件獨立、期望到達率在區間內大致穩定時的標準到達過程模型。

#### 4.3 數量與價格的 Log-Normal 取樣

每筆訂單：

```
quantity   ~ LogNormal( ln(qty_median),   σ_qty )
unit_price ~ LogNormal( ln(price_median), σ_price )
```

```python
def sample_qty(comp, rng):
    return max(1, int(rng.lognormal(np.log(comp["qty_median"]),
                                    comp["qty_sigma_log"])))

def sample_price(comp, rng):
    return float(rng.lognormal(np.log(comp["price_median_usd"]),
                               comp["price_sigma_log"]))
```

**為何用 Log-Normal 而非 Normal？** (i) 採購數量與價格嚴格為正，Normal 在相同離散程度下會對負值賦予不可忽略的機率；(ii) 採購資料右偏（偶有大宗訂單、高端零件），Log-Normal 能捕捉此不對稱性；(iii) 對數空間的 σ 具有清晰的相對變異詮釋：±1σ 對應 ×e^σ 的價格變動（例如 σ = 0.124 ⇒ ±13%）。

#### 4.4 核准延遲與交貨延遲的截斷正態分布

```
approval_lag         ~ TruncNormal(µ=2,  σ=1.5, [0.1, 14])
delivery_lag (SKU k) ~ TruncNormal(µ=µₖ, σ=σₖ, [max(2, µₖ−2σₖ), µₖ+3σₖ])
```

```python
def sample_approval_lag(rng):
    a = (APPROVAL_LAG_MIN - APPROVAL_LAG_MEAN) / APPROVAL_LAG_STD
    b = (APPROVAL_LAG_MAX - APPROVAL_LAG_MEAN) / APPROVAL_LAG_STD
    return float(truncnorm.rvs(a, b, loc=APPROVAL_LAG_MEAN,
                               scale=APPROVAL_LAG_STD, random_state=rng))

def sample_delivery_lag(comp, rng):
    µ, σ = comp["lead_time_median_days"], comp["lead_time_sigma_days"]
    low  = max(2, µ - 2*σ)
    high = µ + 3*σ
    a, b = (low - µ)/σ, (high - µ)/σ
    return int(truncnorm.rvs(a, b, loc=µ, scale=σ, random_state=rng))
```

**為何截斷？** 尾端必須保留給異常注入。若允許自然的 30 天核准延遲，會與 `approval_bypass` 的慢速變體重疊，造成無法分辨的偽陽性；截斷在 14 天消除了此誤差來源。

---

### 5. 範例詳解：PO-2024-0001（一筆正常訂單）

`RANDOM_SEED = 42` 時，第一筆訂單如下：

| 步驟 | 取樣器 | 結果 |
|---|---|---|
| 1 | Poisson 日期 | 2024-01-01 |
| 2 | 加權類別 | requester = R-ENG-02 |
| 3 | Markov 偏好 | supplier = S-001（主要，p=0.65）|
| 4 | SKU 均勻抽樣 | item = BME280 |
| 5 | LogNormal(ln 8, 0.7) | quantity = 10 |
| 6 | LogNormal(ln 2.9156, 0.124) | unit_price = $2.9529 |
| 7 | 確定性規則 | total = $29.53 → approver A-PROC-01 |
| 8 | TruncNormal(2, 1.5, [0.1, 14]) | approval_lag = 1.162 d |
| 9 | TruncNormal(84, 21, [42, 147]) | delivery_lag = 116 d |

---

### 6. 異常注入 — PACE 分類法 T

#### 6.1 八類異常的來源

分類法 T = { t₁, t₂, …, t₈ } 包含兩個脈絡：

**脈絡 A — 直接改編自 PACE 指標（Westerski et al., 2021）。** 五類直接取自 PACE PO 範疇與 ACRA 範疇指標目錄（表 A1）：`item_spending`、`vendor_spending`、`border_value`、`unusual_vendor`、`conflict_of_interest`。另有兩類 — `approval_bypass` 和 `quote_manipulation` — 分別改編自 PACE ITQ 範疇的「快速核准」和「單一投標/遲延得標」，因本模擬公司（30 人 IoT 中小企業）不進行正式 ITQ 招標，故重新對應至採購訂單層級。

**脈絡 B — 稽核實務的營運詐欺類型學。** 第八類 `bank_account_change` 不在 PACE 涵蓋範圍內。對應 ACFE 2024 年報及 IJFMR（2025）哨兵研究所記錄的企業電子郵件入侵（BEC）付款重定向模式。

#### 6.2 兩個角色 — 注入與 Ground Truth

每類異常 *tᵢ* 在本實驗中扮演恰好兩個角色：

1. **注入模板（Stage 1）** — 依照第 6.4 節的突變配方，將 *Nᵢ* 筆隨機選中的訂單改寫為 *tᵢ* 類型。
2. **Ground Truth 標籤（所有下游評估）** — 評估的唯一真值基準。

**分類法不重新實作為偵測器。** 任何以注入規則為基礎的 Stage-3 偵測器都是循環的 — 它評估的正是它被注入的邏輯，必然得到完美偵測，但理由是錯的。Stage 3 只計算數值偏差特徵和 Mahalanobis 距離（詳見第 8 節），兩者均不知道注入規則。

#### 6.3 注入配額

```python
ANOMALY_TARGETS = {
    "item_spending":        13,
    "vendor_spending":       9,
    "border_value":         11,
    "unusual_vendor":       10,
    "approval_bypass":       8,
    "quote_manipulation":    6,
    "bank_account_change":   9,
    "conflict_of_interest": 10,
}   # 合計 = 76 筆 = 500 筆的 15.2%
```

#### 6.4 Ground Truth 的精確定義

Ground Truth 不只是一條布林方程式。完整定義有四個層次，全部來自 `generate_dataset.py` 的注入引擎：

##### 層次 1：二元標籤（主要評估指標）

```python
y_binary = (df["injection_plan"] != "none").astype(int)
# 0 = 正常, 1 = 異常
```

用於計算：Accuracy、F1、Precision、Recall、AOR（異常偵測率）。

##### 層次 2：多類別標籤（混淆矩陣）

```python
y_class = df["injection_plan"]
# 9 個值：{"none", "item_spending", "border_value", "unusual_vendor",
#          "vendor_spending", "approval_bypass", "quote_manipulation",
#          "bank_account_change", "conflict_of_interest"}
```

用於計算：每類召回率（per-rule recall）、繪製 8×2 混淆矩陣。

##### 層次 3：每類精確突變合約（完整真值 — 衍生自 `apply_anomaly()`）

這才是「被改了什麼」的完整記錄。每類的字段突變如下：

**item_spending（t₁）**

```python
mult = float(rng.uniform(2.5, 4.0))          # 隨機倍數
new_p = df.at[idx, "unit_price_usd"] * mult
df.at[idx, "unit_price_usd"]   = round(new_p, 4)
df.at[idx, "total_amount_usd"] = round(df.at[idx, "quantity"] * new_p, 2)
df.at[idx, "approver_id"]      = decide_approver(df.at[idx, "total_amount_usd"])
```

突變字段：`unit_price_usd`（×2.5–4.0）、`total_amount_usd`（重算）、`approver_id`（重算）

**border_value（t₂）** — 前提：`unit_price_usd` ∈ [1.0, 100.0]

```python
up     = df.at[idx, "unit_price_usd"]
target = float(rng.uniform(950, 999) if rng.random() < 0.5
               else rng.uniform(4750, 4999))  # 落在核准門檻正下方
new_qty   = max(1, int(target / up))
new_total = round(new_qty * up, 2)
df.at[idx, "quantity"]         = new_qty
df.at[idx, "total_amount_usd"] = new_total
df.at[idx, "approver_id"]      = decide_approver(new_total)
```

突變字段：`quantity`（調整使 total 落入 [950,999] 或 [4750,4999]）、`total_amount_usd`、`approver_id`

**unusual_vendor（t₃）** — 前提：目前使用 S-001..S-025

```python
pool = suppliers_df.loc[suppliers_df["is_anomaly_pool"], "supplier_id"].tolist()
df.at[idx, "supplier_id"] = str(rng.choice(pool))
```

突變字段：`supplier_id`（改為 S-026..S-030）

**approval_bypass（t₆）** — 有兩種子變體：

```python
if rng.random() < 0.5:
    # 變體 A：缺漏核准人
    df.at[idx, "approver_id"] = ""
    if df.at[idx, "total_amount_usd"] < 1000:
        up = df.at[idx, "unit_price_usd"]
        nq = max(1, int(1500 / up))        # 確保金額夠大才顯著
        df.at[idx, "quantity"]         = nq
        df.at[idx, "total_amount_usd"] = round(nq * up, 2)
else:
    # 變體 B：橡皮圖章（極速核准）
    lag = float(rng.uniform(0.01, 0.09))
    df.at[idx, "approval_lag_days"] = round(lag, 3)
    df.at[idx, "approved_date"]     = (
        pd.Timestamp(df.at[idx, "created_date"])
        + pd.Timedelta(days=lag)).isoformat()
```

突變字段（A）：`approver_id = ""`；可能附帶 `quantity`、`total_amount_usd`
突變字段（B）：`approval_lag_days`（0.01–0.09 天）、`approved_date`

> **⚠ 與 Part A 問題 8 的對齊**：1.x 版 `prepare_stage3.py` 已加入 `policy_violation` 欄位（line 356–366），把 Variant A 細分為 3 條觸發條件（缺核准人 / amount ≥ $1k 跳階 / amount ≥ $5k 跳階）。重建 §6.4 時請將此細節寫入。

**bank_account_change（t₈）**

```python
if df.at[idx, "total_amount_usd"] < 2000:
    up  = df.at[idx, "unit_price_usd"]
    nq  = max(1, int(2500 / up))
    tot = round(nq * up, 2)
    df.at[idx, "quantity"]         = nq
    df.at[idx, "total_amount_usd"] = tot
    df.at[idx, "approver_id"]      = decide_approver(tot)
```

突變字段：`quantity`（調整使 total ≥ 2500）、`total_amount_usd`、`approver_id`

**conflict_of_interest（t₅）** — 前提：目前使用 S-001..S-025

```python
pool = suppliers_df.loc[suppliers_df["is_anomaly_pool"], "supplier_id"].tolist()
df.at[idx, "supplier_id"] = str(rng.choice(pool))
```

突變字段：`supplier_id`（改為 S-026..S-030）

**vendor_spending（t₄）** — 僅標記，不突變任何字段（跨訂單語義模式）

**quote_manipulation（t₇）** — 僅標記，不突變任何字段；Stage 2 在 `purchase_note` 嵌入「僅收到單一報價」的語義

**突變合約彙整表**

| 類別 | 突變字段 | 未突變字段 | 訊號所在 |
|---|---|---|---|
| item_spending | unit_price, total, approver | quantity, supplier, lags | 數值（價格） |
| border_value | quantity, total, approver | unit_price, supplier, lags | 數值（金額區間） |
| unusual_vendor | supplier_id | 全部數值 | 類別 + 文字 |
| vendor_spending | 無 | 全部 | 跨訂單模式 |
| approval_bypass | approver 或 approval_lag | 大部分 | 流程（數值）|
| quote_manipulation | 無 | 全部 | 文字語義 |
| bank_account_change | quantity, total, approver | unit_price, supplier, lags | 數值 + 文字 |
| conflict_of_interest | supplier_id | 全部數值 | 類別 + 文字 |

##### 層次 4：實驗分層（次要分析用）

```python
y_stratum = df["experiment_stratum"]
# ⚠ 舊 4 值：{"normal", "obvious_anomaly", "edge_numeric", "edge_text"}
# 新 5 值：{"A", "B", "C1", "C2a", "C2b"} — 詳見 prepare_stage3.py 1.x
```

用於分析：邊界案例 FN 率（G3 vs G2 在此最關鍵）。

#### 6.5 `injection_seed` 的用途（非 Ground Truth，技術紀錄）

```python
df.at[idx, "injection_seed"] = seed   # 6 位整數
# -1 表示正常訂單
```

`injection_seed` **不是** Ground Truth，常被混淆。用途：給定一筆異常訂單，可重現當時的隨機突變（例如 `item_spending` 中那個 2.5–4.0 之間的具體倍數）。

#### 6.6 注入引擎（完整代碼）

```python
def eligible(orders_df, indicator, used):
    avail = orders_df[~orders_df.index.isin(used)]
    if indicator == "border_value":
        return avail[(avail["unit_price_usd"] >= 1.0) &
                     (avail["unit_price_usd"] <= 100.0)].index.tolist()
    if indicator in ("vendor_spending", "unusual_vendor", "conflict_of_interest"):
        normal = {f"S-{i:03d}" for i in range(1, 26)}
        return avail[avail["supplier_id"].isin(normal)].index.tolist()
    return avail.index.tolist()


def inject_anomalies(orders_df, suppliers_df, rng):
    log, used = [], set()
    for indicator, target in ANOMALY_TARGETS.items():
        pool = eligible(orders_df, indicator, used)
        if len(pool) < target:
            print(f"  WARNING: {indicator} needs {target}, only {len(pool)} eligible.")
            target = len(pool)
        arr = np.array(pool)
        rng.shuffle(arr)
        for idx in arr[:target].tolist():
            seed = int(rng.integers(0, 1_000_000))
            apply_anomaly(orders_df, idx, indicator, suppliers_df, rng)
            orders_df.at[idx, "injection_plan"] = indicator
            orders_df.at[idx, "injection_seed"] = seed
            used.add(idx)
            log.append({"po_id": orders_df.at[idx, "po_id"],
                        "indicator": indicator, "seed": seed})
    return log
```

每筆突變後的訂單收到 `injection_plan = tᵢ.name` 和整數 `injection_seed` 以供逐列重現。

---

### 7. Stage 2 — DeepSeek 語義欄位生成

Stage 1 結束後 `purchase_note` 與 `supplier_profile` 為空。`generate_semantics.py` 對每筆訂單呼叫一次 DeepSeek Chat API。異常訂單附帶一個內部提示（對最終稽核員不可見）：

```python
PACE_HINTS = {
    "item_spending":      "Pricing seems higher than usual; requester argues urgency or premium grade.",
    "vendor_spending":    "Another order to the same supplier this quarter; buyer mentions long-standing relationship.",
    "border_value":       "Total is just under the next approval tier; note hints at careful sizing to avoid escalation.",
    "unusual_vendor":     "Supplier is a recent or unfamiliar trading company with little track record.",
    "approval_bypass":    "Note is terse; no approver mentioned; treated as an expedited transaction.",
    "quote_manipulation": "Mentions a single quote received or a competing quote was withdrawn.",
    "bank_account_change":"Note flags supplier recently updated banking details and requested wire to a different account.",
    "conflict_of_interest":"Profile hints at a personal or prior employment link with the requester.",
}
```

JSON 回應解析後寫回訂單列。每 10 列存檔一次，支援 API 失敗後續跑。另插入兩個空欄 `purchase_note_human`、`supplier_profile_human` 供人工改寫；AI 與人工用語的對比支援一項獨立的探索性子研究。

DeepSeek 刻意選用與下游分析器（**qwen3:8b** ⚠ 舊版寫 Qwen3 7B）不同的模型，以防止同源預填偏誤。

---

### 8. Stage 3 — `prepare_stage3.py`

Stage 3 不執行偵測。它完成三項確定性任務，產出**凍結的實驗工具**；所有下游偵測（Baseline-Stat、G2 LLM 裁決、G3 LLM 證據）在 Stage 4–7 中以這些工件為固定輸入進行。

#### 8.1 任務 A — 偏差特徵（8 個新欄位）

針對每筆訂單，從 `components` 表格連結 SKU 並計算：

| 新欄位 | 公式 | 意義 |
|---|---|---|
| `expected_unit_price_usd` | `components.price_median_usd[sku]` | 該 SKU 的族群中心 |
| `unit_price_ratio` | `unit_price_usd / expected_unit_price_usd` | 相對典型價格的倍數 |
| `expected_quantity` | `components.qty_median[sku]` | 該 SKU 的族群中心 |
| `quantity_ratio` | `quantity / expected_quantity` | 相對典型數量的倍數 |
| `expected_delivery_lag_mean` | `components.lead_time_median_days[sku]` | 交貨 TruncNormal 的 µ |
| `expected_delivery_lag_sigma` | `components.lead_time_sigma_days[sku]` | 交貨 TruncNormal 的 σ |
| `delivery_lag_z` | `(delivery_lag − µ_lead) / σ_lead` | 標準化交貨偏差 |
| `approval_lag_z` | `(approval_lag − 2.0) / 1.5` | 標準化核准偏差 |
| `total_vs_approval_gap` | `total − nearest(1000, 5000)` | 負值 = 剛好低於門檻 |

> **⚠ 與 Part A 問題 2、3 的對齊**：以上偏差特徵 = Section E。重建 methodology.md 時，§7.6 須說明 Section E 與 G3 AI 證據的互補性（數值類重疊、文字類 G3 為唯一訊號），且 §3.2 須將 G1 改為「統計輔助控制組」（看到 Section E 但不看 AI）。

LLM 必須從原始欄位加上 RAG 檢索到的歷史訂單自行推論偏差。若將預算好的 ratio 直接餵給 LLM，等同替它完成推理，破壞實驗純度。

偏差特徵的用途：

1. 研究者人工檢查資料集
2. 論文 Chapter 4 的「Baseline-Stat Detector」（以 ratio 跑 logistic regression 作為對照組）
3. 確認邊界案例確實偏差顯著的 sanity check
4. **以自然語言句子形式呈現給三組受試者作為共同基線（與舊版「only G1 看不到」的描述不同 — 詳 Part A 問題 3）**

#### 8.2 任務 B — Mahalanobis 距離（雙軌：linear + log）

每筆訂單的特徵向量：

```
x = ( unit_price_usd, quantity, approval_lag_days, expected_delivery_lag_days )  ∈ ℝ⁴
```

僅使用 424 筆 `injection_plan == "none"` 的訂單估計：

```
µ̂ = (1/n) · Σ xᵢ
Σ̂ = (1/(n−1)) · Σ (xᵢ − µ̂)(xᵢ − µ̂)ᵀ
```

再對全部 500 筆計算：

```
D²(x) = (x − µ̂)ᵀ · Σ̂⁻¹ · (x − µ̂)
```

在 *x ~ N(µ, Σ)* 的虛無假設下，D² ~ χ²(4)，產生有原則的門檻：

| 顯著水準 | 門檻 | 詮釋 |
|---|---|---|
| α = 0.05 | D² > 9.49 | 前 5% — 「邊界」|
| α = 0.01 | D² > 13.28 | 前 1% — 「異常」|

> **⚠ 1.x 版新增 log-Mahalanobis**：對 *log(x)* 重複以上計算，產生 `mahalanobis_D2_log` 與 `D2_log_percentile`。理由：linear D² 對 `approval_bypass` Variant B（lag = 0.05d）不敏感，log D² 能補捕乘法尺度的離群值。重建 §8.2 時請加入此雙軌設計說明。

D² 的用途：

- 層化 ⚠~~15 題~~ → **32 題**實驗集（第 8.3 節）
- 論文 Chapter 4 的「Baseline-Stat」偵測器（無領域知識的演算法下界）

D² **不**用於：呈現給 G2/G3 受試者或餵給 LLM。UI 永遠不顯示 D² 值或百分位。

#### 8.3 任務 C — 凍結實驗集

> **⚠ 此節舊版完全失效**。1.x 版 `prepare_stage3.py` 使用全新的 A/B/C/C2a/C2b 五層分層 + 練習題：

| 層別 | 數量 | 篩選準則 |
|---|---|---|
| **A** 正常 | 10 | `injection_plan == "none"` 且 D² < χ²(4, 0.95) = 9.49 |
| **B** 明顯異常 | 8 | 8 類各 1 題，每類取**最高訊號**（item_spending / border_value / approval_bypass V-A 取高 D²；文字類取高 `text_signal_score`）|
| **C1** 邊界正常（假陽性陷阱）| 6 | `injection_plan == "none"` 且 D² 百分位 ∈ [85, 95]，且 D² < χ²(4, 0.99) = 13.28 |
| **C2a** 邊界異常 — 數值隱晦 | 3 | item_spending、approval_bypass V-B、bank_account_change（取最低 linear-D²） |
| **C2b** 邊界異常 — 文字隱晦 | 5 | bank_account_change、unusual_vendor、vendor_spending、quote_manipulation、conflict_of_interest（取最低 `text_signal_score`）|
| **練習** | 2 | 1 obvious normal + 1 obvious anomaly（與實驗集不重疊，亦不入 RAG）|
| **合計** | **32 + 2** | |

**納入文字隱藏邊界案例的理由**：t₃、t₄、t₅、t₇（及 t₈ 弱變體）未突變 4 維數值特徵向量，訊號藏在 `supplier_profile` 和 `purchase_note`。這些正是 LLM 證據預期勝過純統計偵測器的案例，對 G3 vs G2 比較最具鑑別力。

#### 8.4 輸出檔案

`prepare_stage3.py` 產出（時間戳記 `<TS>`）：

- `data/stage3/stage3_full_with_truth_<TS>.xlsx/.csv` — 全部 500 筆，含偏差特徵、`mahalanobis_D2`、`mahalanobis_D2_log`、`D2_percentile`、`D2_log_percentile`、`risk_tier`、`policy_violation`、`injection_plan`、`injection_seed`、`experiment_stratum`、`experiment_block`、`practice_role`、`reason`。**僅研究者使用**，不對受試者展示。
- `data/stage3/experiment_32qs_<TS>.xlsx/.csv` ⚠ 舊名 `experiment_15qs` — **32 題**層化訂單，已剝離所有 Ground-Truth、偵測器信號與預算偏差特徵（保留 Section E 作為共同基線）。展示順序額外打亂，防止從列號推斷層別。**UI 使用**。
- `data/stage3/experiment_32qs_<TS>_KEY.xlsx` — 研究者答案鍵：`po_id`、`experiment_stratum`、`experiment_block`、`injection_plan`、`mahalanobis_D2`、`mahalanobis_D2_log`、`D2_percentile`、`D2_log_percentile`、`risk_tier`、`reason`、`policy_violation`。
- `data/stage3/practice_2qs_<TS>.xlsx/.csv` + `*_KEY.xlsx` — 2 練習題（與實驗集嚴格不重疊）。
- `data/stage3/rag_corpus_466_<TS>.jsonl/.csv` ⚠ 舊版 485 — 其餘 **466 筆**（500 − 32 實驗 − 2 練習）序列化為 RAG 文件（自然語言 `text` + 精簡 metadata），已剝離所有敏感欄位。**Stage 4 導入 Chroma**。

**資訊隔離原則**：UI 與 RAG 只保留原始欄位（17 個）+ 語義欄位（4 個）+ Section E 偏差特徵（自然語言句子）= 真正的 naive 環境，LLM 必須透過 RAG 檢索到的 5 筆相似訂單自行推論任何偏差。

---

### 9. 可重現性保證

1. **確定性 RNG**。 `numpy.random.default_rng(42)` 統一種子；`injection_seed` 鎖定逐列異常注入。
2. **凍結市場資料**。 `data/mouser_raw_exact.json` 及其 `_meta` 指紋是價格與前置時間的唯一真實來源。
3. **快取 → 可重生成**。 從乾淨 checkout 執行 `python generate_dataset.py` 可逐位元重現 `dataset_YYYYMMDD_HHMMSS.xlsx`（時間戳記是唯一漂移）。
4. **論文附錄相容性**。 所有參數由 `print_all_parameters()` 在執行時輸出，可直接附於論文附錄作為可驗證的控制台追蹤。

---

### 10. 參數來源摘要

| 參數 | 來源 | 類型 |
|---|---|---|
| 10 個 SKU | 手選，涵蓋各零件類別 | 設計 |
| `price_median_usd` | Mouser API 價格區間的幾何平均 | 真實 |
| `σ_price` | (ln max − ln min)/4，截斷 [0.05, 0.50] | 衍生 |
| `lead_time_median_days` | Mouser `LeadTime` 欄位 | 真實 |
| `σ_lead` | max(2, 0.25·µ) — CV 0.25，Silver et al. (2017) | 假設 |
| `qty_median`, `σ_qty` | 按類別合理性手設 | 設計 |
| `APPROVAL_LAG_*` | 小企業快速核准假設 | 設計 |
| 請購人權重 | 輕微集中，模擬關鍵人員 | 設計 |
| 供應商偏好圖 | 25 家製造商 + 5 家貿易殼 | 設計 |
| Poisson λ = N/T | 標準到達過程 | 理論 |
| 8 類異常 | 5 PACE PO/ACRA + 2 PACE ITQ 重範疇 + 1 ACFE BEC | 文獻混合 |
| Mahalanobis 門檻 9.49 / 13.28 | χ²(4) α = 0.05 / 0.01 | 理論 |
| ⚠~~15 / 485~~ → **32+2 / 466** 實驗切割 | 按注入類別 + D² 百分位層化（A/B/C 五層）| 設計 |

---

### 11. 如何閱讀 Excel 資料集

Stage 1 輸出檔案 `data/dataset_YYYYMMDD_HHMMSS.xlsx` 是主要工件。單一 .xlsx 活頁簿，共五個工作表。

#### 11.1 活頁簿地圖

| # | 工作表 | 列 × 欄 | 一句話說明 |
|---|---|---|---|
| 1 | metadata | 18 × 2 | 執行指紋 — 種子、時間戳記、快取校驗碼 |
| 2 | components | 10 × 15 | 10 個 SKU 及 Mouser 衍生的價格與前置時間 |
| 3 | suppliers | 30 × 6 | 25 家正常供應商 + 5 家異常池供應商 |
| 4 | injections | 76 × 3 | 哪些 PO 被突變、依哪個規則、用哪個種子 |
| 5 | orders | 500 × 21 | 主資料 — 2024 年全部採購訂單 |

#### 11.2 逐表欄位說明

##### metadata — 執行指紋（先看這裡）

| 欄位 | 範例值 | 意義 |
|---|---|---|
| `generated_at` | 20260420_015519 | 本次執行的時間戳記後綴 |
| `random_seed` | 42 | 重現逐位元輸出所用種子 |
| `n_orders` | 500 | orders 工作表列數 |
| `mouser_first_fetched_at` | 2026-04-20T01:55:36 | 凍結 Mouser 基準首次擷取時間 |
| `mouser_last_modified_at` | 2026-04-20T01:55:36 | 基準最後修改時間（應與首次相同，否則使用的是重新基準的快取）|
| `anomaly_targets_*` | 13, 11, 10, … | 實際執行的注入配額 |

**經驗法則**：若 `mouser_first_fetched_at` 不符合論文附錄的時間戳記，數字將無法重現。

##### components — 10 列，每 SKU 一列

| 欄位 | 意義 | 來源 |
|---|---|---|
| `mouser_pn`, `sku`, `category` | 識別碼 | 設計 |
| `price_median_usd` | Log-Normal 的 µ（USD）| Mouser 幾何平均 |
| `price_sigma_log` | 對數空間 σ | Mouser 4-σ 法則，截斷 |
| `qty_median`, `qty_sigma_log` | 數量 Log-Normal 的 µ, σ | 設計 |
| `lead_time_median_days` | 交貨 TruncNormal 的 µ | Mouser LeadTime |
| `lead_time_sigma_days` | σ = max(2, 0.25·µ) | 假設 |
| `ref_url` | Mouser 產品頁 | 可追溯性 |
| `price_source` | 例如 `mouser_partnumber_api:603-CFR-25JB-52-10K` | 稽核軌跡 |

##### suppliers — 30 列，每供應商一列

| 欄位 | 意義 |
|---|---|
| `supplier_id` | S-001 … S-030 |
| `name` | 正常：Supplier NNN Electronics Co.；異常池：Supplier NNN Trading Ltd. |
| `founded_year` | 正常：2008–2022；異常池：2024 |
| `location` | {深圳, 東莞, 上海, 台北, 首爾, 東京, 班加羅爾} 之一 |
| `primary_category` | 供應商名義上的專攻類別 |
| `is_anomaly_pool` | S-001…S-025 為 False，S-026…S-030 為 True ← 定義「異常供應商」的唯一位元 |

##### injections — 76 列，每筆突變訂單一列

| 欄位 | 意義 |
|---|---|
| `po_id` | 哪筆 PO 被觸碰（關聯 `orders.po_id`）|
| `indicator` | 使用哪個規則（item_spending, …, quote_manipulation）|
| `seed` | 用於 `apply_anomaly` 內的 6 位整數種子 |

快速驗證：

```python
df_inj["indicator"].value_counts()
# 應符合第 6.3 節的 ANOMALY_TARGETS
```

##### orders — 500 列，主表

**識別欄位**

| 欄位 | 範例 |
|---|---|
| `po_id` | PO-2024-0001 |
| `batch_generated_at` | 2026-04-20T01:55:36 |

**行為者**

| 欄位 | 範例 | 關聯至 |
|---|---|---|
| `requester_id` | R-ENG-02 | REQUESTERS（硬編碼）|
| `approver_id` | A-PROC-01 / A-CTO / A-CEO / ""（繞過）| 依 total 確定性決定 |
| `supplier_id` | S-001 … S-030 | suppliers 工作表 |

**生命週期時間戳記**

| 欄位 | 意義 |
|---|---|
| `created_date` | 2024-01-01（Poisson 過程）|
| `approval_lag_days` | TruncNormal(2, 1.5, [0.1, 14])|
| `approved_date` | = created_date + approval_lag_days |
| `expected_delivery_lag_days` | TruncNormal(µ_lead, σ_lead) |
| `expected_delivery_date` | = approved_date + expected_delivery_lag_days |

**商業內容**

| 欄位 | 意義 |
|---|---|
| `item_category`, `item_sku`, `item_description` | 來自 components 工作表 |
| `quantity` | LogNormal(ln qty_median, σ_qty) |
| `unit_price_usd` | LogNormal(ln price_median, σ_price) |
| `total_amount_usd` | = quantity × unit_price_usd |
| `currency` | 固定為 USD |

**語義佔位（Stage 2）**

| 欄位 | 意義 |
|---|---|
| `purchase_note` | Stage 1 後為空；Stage 2 由 DeepSeek 填充 |
| `supplier_profile` | Stage 1 後為空；Stage 2 由 DeepSeek 填充 |
| `purchase_note_human` | 人工改寫欄（實驗者手填）|
| `supplier_profile_human` | 人工改寫欄（實驗者手填）|

**Ground-Truth 標籤**

| 欄位 | 意義 |
|---|---|
| `injection_plan` | 正常：`"none"`；異常：8 類名稱之一（詳見第 6.4 節）|
| `injection_seed` | 正常：-1；異常：當列注入所用的逐列種子 |

#### 11.3 用 Python 讀取

```python
import pandas as pd

fp = "code/dataset/data/dataset_20260420_015519.xlsx"

orders     = pd.read_excel(fp, sheet_name="orders")
suppliers  = pd.read_excel(fp, sheet_name="suppliers")
components = pd.read_excel(fp, sheet_name="components")
injections = pd.read_excel(fp, sheet_name="injections")
metadata   = pd.read_excel(fp, sheet_name="metadata")

# 二元分割
normal    = orders[orders["injection_plan"] == "none"]   # 424 列
anomalies = orders[orders["injection_plan"] != "none"]   #  76 列
print(anomalies["injection_plan"].value_counts())

# 每類召回率（實驗後用）
for rule in anomalies["injection_plan"].unique():
    subset = anomalies[anomalies["injection_plan"] == rule]
    # recall = llm_verdict.loc[subset.index].eq("suspicious").mean()
    print(f"{rule:25}  n={len(subset)}")
```

#### 11.4 用 Excel 瀏覽（無需程式碼）

1. 雙擊 `dataset_20260420_015519.xlsx`。
2. 用底部工作表標籤在 5 個工作表間切換。
3. 在 orders 工作表，點選 **資料 → 篩選**，篩選 `injection_plan ≠ none` 查看 76 筆異常。
4. 用**格式化條件 → 色階**套用於 `unit_price_usd` 和 `total_amount_usd` 直觀發現數值異常值。

#### 11.5 配套檔案

| 路徑 | 用途 | 何時使用 |
|---|---|---|
| `data/mouser_raw_exact.json` | 凍結的 Mouser API 回應 | 稽核軌跡；論文中引用價格 |
| `data/stage1/orders_*.csv` | orders 工作表的純文字副本 | git 可差異比對、腳本處理 |
| `data/stage2/orders_stage2_semantics.xlsx` | Stage 2 帶有 `*_human` 欄的 Excel | 手動改寫語義欄 |
| `data/stage3/stage3_full_with_truth_*.xlsx` | 含偏差特徵與 D² 的完整研究者主檔 | 論文分析、Baseline-Stat 偵測器 |
| `data/stage3/experiment_32qs_*.xlsx` ⚠ 舊名 `_15qs` | UI 使用（已清除所有敏感欄位）| 實驗展示 |
| `data/stage3/practice_2qs_*.xlsx` 🆕 | 練習題（不入 RAG）| 受試者熱身 |
| `data/stage3/rag_corpus_466_*.jsonl` ⚠ 舊版 485 | Chroma RAG 語料庫 | Stage 4 向量化 |

---

### 12. 參考文獻

```
Association of Certified Fraud Examiners (2024). Occupational Fraud 2024:
   A Report to the Nations. Austin, TX: ACFE.

IJFMR (2025). Whistle-blower Mechanisms in Operational Departments.
   International Journal of Financial Management Research.

Silver, E.A., Pyke, D.F., & Peterson, R. (2017). Inventory and Production
   Management in Supply Chains, 3rd ed. CRC Press, ch. 7.

Vaccaro, M., Almaatouq, A., & Malone, T. (2024). When combinations of humans
   and AI are useful: A systematic review and meta-analysis. Nature Human
   Behaviour, 8(12), 2293–2303.

Westerski, A., Kanagasabai, R., Shaham, E., Narayanan, A., Wong, J., &
   Singh, M. (2021). Explainable anomaly detection for procurement fraud
   identification — lessons from practical deployments. International
   Transactions in Operational Research, 28(6), 3276–3302.
   Preprint: http://www.adamwesterski.com/files/publications/itor2021/
   explainable_procurement_itor2021_preprint.pdf

Mouser Electronics Search API v1, `search/partnumber` endpoint,
   `partSearchOptions="exact"`.
```
