# Methodology — Evidence vs. Conclusion: How LLM Output Format Shapes Human-AI Collaboration in Procurement Anomaly Auditing

**版本**：v1.0
**最後更新**：2026-04-27
**論文語言**：中文撰寫；研究問題 (RQ)、技術術語、程式碼片段、reason 欄位保留英文原文

---

## 目錄

0. 摘要與研究問題
1. 場景定義
2. 實體設定
3. 實驗組別與人機協作定義
4. 零件清單與 Stage 0 (Mouser API)
5. Stage 1 蒙地卡羅管線
6. 範例詳解：PO-2024-0001
7. 異常注入 — PACE 分類法 T
8. Stage 2 — DeepSeek 語義欄位生成
9. Stage 3 — 偏差特徵、Mahalanobis、實驗分層
10. Stage 4 — RAG 建立與 LLM 輸出凍結
11. 可重現性保證
12. 參數來源摘要
13. 如何閱讀 Excel 資料集
14. 實驗分析計畫
15. 限制與威脅
16. 參考文獻

---

## 0. 摘要與研究問題

### 0.1 研究問題（RQ — 正式英文版）

- **RQ1**: Does presenting LLM output as structured evidence (four factual observations without a verdict) yield higher human anomaly detection accuracy than presenting a binary conclusion with a one-sentence rationale, or no AI assistance?

- **RQ2**: Does the effect of AI output format vary between anomalies detectable through numerical deviation versus those detectable only through textual semantics?

- **RQ3**: When the LLM produces an incorrect output, does the evidence format enable participants to override AI errors more effectively than the conclusion format?

### 0.2 摘要

本研究探討大型語言模型 (LLM) 輸出格式對人機協作之採購異常稽核表現的影響。資料端：以 Mouser API 真實市場資料為錨，依 PACE (Westerski et al., 2021) 八類採購異常指標生成含 500 筆訂單（76 異常 + 424 正常）的合成資料集，並依分層抽樣框架挑出 32 題實驗集 + 2 題練習題，其餘 466 筆作為 LLM 的 RAG 歷史檢索語料庫。

實驗端：設置 G1（人類 + 統計輔助）、G2（人類 + AI 結論）、G3（人類 + AI 證據）三組受試者，比較三種 AI 輸出格式對 (i) 整體偵測準確率、(ii) 不同訊號類型（數值 vs. 文字）下的格式效應差異、(iii) 人類在 AI 犯錯時的修正能力 的影響。每組招募 N = 4 人，總計 12 人，定位為 proof-of-concept / pilot study。分析以描述統計、Cliff's δ、Hedges' g 與 95% bootstrap CI 為主軸；本研究不依賴大樣本推論統計，所有結果以效果量及其信賴區間呈現。

### 0.3 語言設計聲明

**論文撰寫**：本論文以中文撰寫；研究問題 (RQ)、技術術語、程式碼片段、reason 欄位保留英文原文。

**資料與 prompt 語言**：所有訂單欄位（`purchase_note`、`supplier_profile`、Section E 自然語言句子等）、LLM system / user prompts、G2 / G3 凍結輸出與 RAG 檢索內容 **全程使用英文**。受試者（HKUST 工管 / 商科學生）對英文採購文件閱讀無障礙。AI 輸出統一使用英文之目的：(a) 確保 prompt 跨模型可比性，避免中譯英 / 英譯中的語意漂移污染格式效應；(b) 對齊 Mouser API 與國際電子採購文件的常見語言慣例；(c) 簡化未來與更大模型（如 GPT-4o、Claude）的對照實驗。

---

## 1. 場景定義

**公司**：ABC Electronics Ltd. — 一家虛構的香港 30 人 IoT 硬體新創，專為內部研發採購電子零件。

**實驗任務**：稽核人員逐一審查採購訂單 (PO)，判斷每筆訂單為「正常」或「異常」。實驗比較三種稽核員條件下的判斷品質與決策時間（詳 §3）。

**資料集規模**：一個會計年度（2024-01-01 至 2024-12-31），共 500 筆訂單，其中 424 筆正常、76 筆帶有注入異常，來自八類規則：五類直接改編自 PACE PO/ACRA 指標目錄（Westerski et al., 2021），兩類將 PACE 的 ITQ 範疇指標重新對應至 PO 層級，一類（`bank_account_change`）來自 ACFE 與 IJFMR 的當代詐欺類型學。

---

## 2. 實體設定

### 2.1 工程師（請購人）

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

### 2.2 核准人（門檻制）

```python
APPROVER_PROC = "A-PROC-01"   # total < USD 1,000
APPROVER_CTO  = "A-CTO"       # USD 1,000 ≤ total ≤ 5,000
APPROVER_CEO  = "A-CEO"       # total > USD 5,000
```

總金額決定核准人，規則完全確定性。此設計使 `border_value` 攻擊（§7）得以精確：$999 訂單天然繞過 CTO。

### 2.3 供應商（25 家正常 + 5 家異常池）

| ID 範圍 | 名稱格式 | 成立年份 | 標記 |
|---|---|---|---|
| S-001 … S-025 | Supplier NNN Electronics Co. | 2008–2022（TruncNorm 中心 2015）| `is_anomaly_pool = False` |
| S-026 … S-030 | Supplier NNN Trading Ltd. | 2024（當年新成立）| `is_anomaly_pool = True` |

異常池內建兩個紅旗：成立時間過新（採購當年新成立）與公司型態（貿易商而非製造商）。

### 2.4 請購人 — 供應商偏好圖（Markov 風格）

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

(0.65, 0.25, 0.10) 的機率構成退化 Markov 鏈。**正常訂單永遠不會路由至 S-026…S-030**；任何此類路由因此都是異常注入的鑑識標記。

---

## 3. 實驗組別與人機協作定義

### 3.1 「人機協作」(Human-AI Collaboration) 操作定義

本研究依 Vaccaro, Almaatouq & Malone (2024) 在 *Nature Human Behaviour* 8(12), 2293–2303 的元分析操作框架界定 human-AI collaboration。Vaccaro 將其元分析的合格標準定為：

> "the paper needed to present an original experiment that evaluated some instance in which **a human and an AI system worked together to perform a task**." (§4.1.1 Eligibility Criteria)

在此寬定義下，Vaccaro 將不同協作型態（AI 解釋有無、AI 信心分數有無、人機分工方式等）視為 11 項 moderator 變數而非排除條件。其中第 (8) AI explanation 與第 (9) AI confidence 兩項 moderator 直接對應本研究的核心操弄變數：

- **G2（結論式：suspicious / normal + 一句理由）**：對應 (8) + (9) 的傳統實作 — 給結論並附簡短解釋。
- **G3（證據式：4 條結構化線索，無結論）**：本研究獨創的格式變體，將「解釋」從附屬資訊提升為主體輸出。

Vaccaro 的 300+ 效果量元分析發現 (8) 與 (9) 的有無對協作表現皆無顯著影響，並建議研究者降低對此議題的投入。本研究的學術價值正在於正面挑戰此 null finding — 透過全新的「結論式 vs. 證據式」格式對比，測試是否存在 Vaccaro 元分析未涵蓋的子型差異。

關於本研究的單向設計（人類接收凍結的 AI 輸出後做最終判斷，AI 不依人類反饋即時調整），Vaccaro 明確指出：

> "**Most (>95%) of the human-AI systems in our data set involved humans making the final decisions after receiving input from the AI algorithms.**" (Discussion)

**因此本研究 G2 / G3 正屬 Vaccaro 元分析中佔 95% 以上的代表性型態，其結論可直接與該文獻對照**。本研究範圍不包含雙向對話、AI 自主執行、AI 即時根據人類反饋學習等型態（後者列為未來工作方向）。部分文獻（如 Bansal et al., 2021）將此類設計另稱為 "AI-assisted decision-making"，兩個術語在本研究領域可互換使用。

### 3.2 三組受試者對照

| 組別 | 看到 AI 嗎 | AI 形式 | 對應 Vaccaro 的 moderator |
|---|---|---|---|
| **G1** 對照 | ❌ | — | **統計輔助控制組**：看到原始欄位 + Section E 偏差特徵（§9.2），但無 AI 輸出。 |
| **G2** 結論型 | ✅ | suspicious / normal + 一句理由 | 對應 (8) AI explanation + (9) AI confidence 的傳統實作 |
| **G3** 證據型 | ✅ | 4 條結構化可疑特徵（無結論）| 對應將 (8) 提升為主體、(9) 完全移除的新型實作 |

**三組共享 Section E 作為共同基線**，唯一操縱變數是 AI 輸出的有無與格式。G1 並非「赤手空拳」的人類 baseline，而是「人類 + 統計輔助」控制組。此設計使 G2 / G3 vs. G1 的差異純粹歸因於 AI 輸出，而非 AI 輸出疊加於 Section E 的綜合效應。

### 3.3 為什麼如此設計

| 文獻痛點 | 本研究的對應做法 |
|---|---|
| PACE 無法處理語義（Westerski et al., 2021）| Stage 2 用 LLM 生成語義欄位；G3 證據包含語義線索 |
| 黑盒 ML 給抽象分數（如 `0.82`）| G3 不給任何分數，只給可比較的數值（`$8.90` vs `$2.80`）|
| SHAP / LIME 解釋仍然無效 | 不用歸因分數；直接用「價格高 3.2 倍」此類人類可執行的陳述 |
| Vaccaro：解釋有無不顯著 | 那是傳統 XAI；本研究的「證據」不是解釋，而是重新設計任務分工（AI 只提供特徵，人類做判斷）|
| 自動化偏誤 | G3 移除結論，強制人類必須自己綜合證據 → 認知強制機能 |

### 3.4 實驗後信任量表（G2 / G3 only）

第 2、3 組（G2、G3）在完成所有 32 道正式題後，填寫一份 5 題的人機信任量表，改編自 Jian, Bisantz & Drury (2000)「Checklist for Trust between People and Automation」實證驗證的 12-item 信任量表。Q1 / Q2 / Q4 改編自原量表的 reliability / dependability / security 三個面向；Q3 與 Q5 為本研究新增，分別針對 RQ2 的「證據型 vs. 結論型 AI 輸出之清晰度感知差異」與 RQ3 的「自動化偏誤主觀知覺」設計。

第 1 組（G1，無 AI 條件）**不填寫此量表** — 五題皆涉及 AI 輸出感知，對 G1 無對應實驗操縱。

**評分**：每題使用 7-point Likert（1 = Strongly disagree, 7 = Strongly agree）。App 顯示英文版作為正式 instrument；中譯僅作為論文敘述參考，不向受試者呈現。

| # | Question (English — used in app) | 中譯（僅供參考）| Construct | Source |
|---|---|---|---|---|
| Q1 | I can trust the information provided by the AI system. | 我相信這個 AI 系統提供的資訊是可靠的。| Trust — reliability | Adapted from "I can trust the system" (Jian et al., 2000, item 11) |
| Q2 | The AI system's output is dependable enough for me to rely on when making my decision. | 我對這個 AI 系統的輸出感到放心，足以依賴它協助我做決定。| Trust — dependability | Adapted from "The system is dependable" (Jian et al., 2000, item 9) |
| Q3 | The information the AI presented made it clear to me why this order was noteworthy. | AI 呈現的資訊讓我清楚理解為什麼這份訂單值得注意。| Clarity / explanation quality | **New** — RQ2-specific; distinguishes evidence-form (G3) vs. verdict-form (G2) AI output |
| Q4 | The AI provided substantive help to my final judgment. | AI 提供的資訊對我的最終判斷有實質幫助。| Perceived usefulness | Adapted from "The system provides security" (Jian et al., 2000, item 7) |
| Q5 | After seeing the AI's output, I still feel I made the final decision myself rather than simply following the AI. | 看完 AI 的輸出後，我仍然感覺是由我自己做出最終決定，而不是跟著 AI 走。| Perceived autonomy / automation-bias awareness | **New** — RQ3-specific; direct subjective measure of automation-bias resistance |

#### 3.4.1 在分析中的角色

- 作為 RQ2、RQ3 的次級主觀 DV：例如「G3 的 Q3 平均分數是否顯著高於 G2」可作為「證據型輸出較易理解」的主觀證據；「G3 的 Q5 平均分數是否高於 G2」可作為「證據型輸出較不誘發自動化偏誤」的主觀證據。
- 因 G1 無資料，所有題目的組間比較限於 **G2 vs. G3**。
- 統計檢定：Mann–Whitney U test（非常態小樣本）+ Cliff's δ 報效應大小，與 §14.4 主分析方法一致。

#### 3.4.2 量表簡化的取捨

完整 Jian et al. (2000) 12-item scale 對 N=8 樣本（G2+G3）會嚴重不穩定（每題 SD 估計皆不可靠，內部一致性 α 估計亦無意義）。本研究選擇 5 題簡化版的取捨：

- 保留原量表的兩個核心信任面向（reliability + dependability）
- 加入 RQ-specific 的 Q3 / Q5，直接測量本研究的核心操縱效應
- 以「實質幫助」（usefulness）替代原量表中與本場景關聯較弱的 "provides security" 措辭
- 捨棄原量表的負向題（"deceptive"、"underhanded"、"suspicious"、"wary"、"harmful"），因為對 procurement audit 場景過於對抗性，且 8 樣本下無法穩健估計反向計分後的內部一致性

完整版量表的應用留待後續大樣本驗證研究。

---

## 4. 零件清單與 Stage 0 (Mouser API)

### 4.1 10 個 SKU

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

### 4.2 Mouser API 呼叫

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

每次回應持久化至 `data/mouser_raw_exact.json`，附帶快取指紋（`_meta.first_fetched_at` 與 `last_modified_at`）。後續所有執行均從此快取讀取，保證完全重現性。

### 4.3 價格統計 — 從階梯定價到連續分布

Mouser 價格區間是數量階梯（買 100–999 件固定 $0.0987/件；買 ≥ 1000 件則 $0.092），不是連續曲線。模擬不複製階梯定價，而是將 *k* 個公開區間價格視為底層市場價格分布的實證觀測值，配適連續 Log-Normal 分布：

```python
def _price_stats(price_breaks: list) -> tuple[float, float]:
    prices = [float(re.sub(r"[^\d.]", "", b["Price"])) for b in price_breaks]
    log_p  = [math.log(p) for p in prices if p > 0]
    geo    = math.exp(sum(log_p) / len(log_p))                       # e^(mean ln p)
    sigma  = (math.log(max(prices)) - math.log(min(prices))) / 4     # 4-sigma 法則
    sigma  = max(0.05, min(0.50, sigma))                             # 截斷
    return round(geo, 4), round(sigma, 3)
```

閉合公式（對價格區間 *p₁ < … < pₖ*）：

```
µ_price = (1/k) · Σᵢ ln(pᵢ)            [Log-Normal 對數空間均值]
e^µ     = {pᵢ} 的幾何平均                [取樣中心]
σ_price = clamp(0.05, 0.50)( (ln pₖ − ln p₁) / 4 )
```

幾何平均是 Log-Normal 配適 *k* 個觀測值的最大概似中心。「除以四」為工程 4-σ 法則（觀測範圍 ≈ ±2σ 覆蓋 ≈ 95% 機率質量）。截斷防止 *k=2* 時出現病態值。

### 4.4 前置時間解析

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

10 個固定 SKU 均回傳 `"NNN Days"` 格式，實際上只有 `days_m` 分支觸發；其餘分支為穩健性保留。

### 4.5 前置時間變異數

```
σ_lead = max( 2 天, 0.25 · µ_lead )
```

變異係數 0.25 落在穩定電子供應鏈 0.2–0.3 區間的中段（Silver, Pyke & Peterson, 2017, ch. 7）。2 天下限防止短前置時間零件出現退化分布。此 σ 僅影響 `expected_delivery_lag_days` 的正態分布，不進入任何異常標籤。

### 4.6 零件彙整表（Mouser 快取實際值）

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

## 5. Stage 1 蒙地卡羅管線

### 5.1 全域設定

```python
RANDOM_SEED   = 42
N_ORDERS      = 500
START_DATE    = date(2024, 1, 1)
END_DATE      = date(2024, 12, 31)
CURRENCY_DIST = {"USD": 1.00}              # 單一幣種
APPROVAL_LAG_MEAN, APPROVAL_LAG_STD = 2.0, 1.5
APPROVAL_LAG_MIN,  APPROVAL_LAG_MAX  = 0.1, 14.0
```

### 5.2 Poisson 訂單日期

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

### 5.3 數量與價格的 Log-Normal 取樣

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

**為何用 Log-Normal 而非 Normal**：(i) 採購數量與價格嚴格為正，Normal 在相同離散程度下會對負值賦予不可忽略的機率；(ii) 採購資料右偏（偶有大宗訂單、高端零件），Log-Normal 能捕捉此不對稱性；(iii) 對數空間的 σ 具有清晰的相對變異詮釋：±1σ 對應 ×e^σ 的價格變動（例如 σ = 0.124 ⇒ ±13%）。

### 5.4 核准延遲與交貨延遲的截斷正態分布

```
approval_lag         ~ TruncNormal(µ=2,  σ=1.5, [0.1, 14])
delivery_lag (SKU k) ~ TruncNormal(µ=µₖ, σ=σₖ, [max(2, µₖ−2σₖ), µₖ+3σₖ])
```

**為何截斷**：尾端必須保留給異常注入。若允許自然的 30 天核准延遲，會與 `approval_bypass` 的慢速變體重疊，造成無法分辨的偽陽性；截斷在 14 天消除了此誤差來源。

---

## 6. 範例詳解：PO-2024-0001

`RANDOM_SEED = 42` 時，第一筆訂單如下：

| 步驟 | 取樣器 | 結果 |
|---|---|---|
| 1 | Poisson 日期 | 2024-01-01 |
| 2 | 加權類別 | requester = R-ENG-02 |
| 3 | Markov 偏好 | supplier = S-001（主要，p = 0.65）|
| 4 | SKU 均勻抽樣 | item = BME280 |
| 5 | LogNormal(ln 8, 0.7) | quantity = 10 |
| 6 | LogNormal(ln 2.9156, 0.124) | unit_price = $2.9529 |
| 7 | 確定性規則 | total = $29.53 → approver A-PROC-01 |
| 8 | TruncNormal(2, 1.5, [0.1, 14]) | approval_lag = 1.162 d |
| 9 | TruncNormal(84, 21, [42, 147]) | delivery_lag = 116 d |

---

## 7. 異常注入 — PACE 分類法 T

### 7.1 八類異常的來源

分類法 T = { t₁, …, t₈ } 包含兩個脈絡：

**脈絡 A — 直接改編自 PACE 指標**（Westerski et al., 2021）。五類直接取自 PACE PO 範疇與 ACRA 範疇指標目錄（表 A1）：`item_spending`、`vendor_spending`、`border_value`、`unusual_vendor`、`conflict_of_interest`。另有兩類 — `approval_bypass` 與 `quote_manipulation` — 分別改編自 PACE ITQ 範疇的「快速核准」與「單一投標 / 遲延得標」，因本模擬公司（30 人 IoT 中小企業）不進行正式 ITQ 招標，故重新對應至採購訂單層級。

**脈絡 B — 稽核實務的營運詐欺類型學**。第八類 `bank_account_change` 不在 PACE 涵蓋範圍內。對應 ACFE 2024 年報及 IJFMR (2025) 哨兵研究所記錄的企業電子郵件入侵 (BEC) 付款重定向模式。

### 7.2 兩個角色 — 注入與 Ground Truth

每類異常 *tᵢ* 在本實驗中扮演恰好兩個角色：

1. **注入模板（Stage 1）**：依照第 7.4 節的突變配方，將 *Nᵢ* 筆隨機選中的訂單改寫為 *tᵢ* 類型。
2. **Ground Truth 標籤（所有下游評估）**：評估的唯一真值基準。

**分類法不重新實作為偵測器**。任何以注入規則為基礎的偵測器都是循環的 — 它評估的正是它被注入的邏輯，必然得到完美偵測但理由是錯的。Stage 3 只計算數值偏差特徵和 Mahalanobis 距離（§9），兩者均不知道注入規則。

### 7.3 注入配額

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

### 7.4 Ground Truth 的精確定義

#### 層次 1：二元標籤

```python
y_binary = (df["injection_plan"] != "none").astype(int)   # 0=正常, 1=異常
```

用於計算 Accuracy、F1、Precision、Recall。

#### 層次 2：多類別標籤

```python
y_class = df["injection_plan"]
# 9 個值：{"none", "item_spending", "border_value", "unusual_vendor",
#          "vendor_spending", "approval_bypass", "quote_manipulation",
#          "bank_account_change", "conflict_of_interest"}
```

用於每類召回率與 8×2 混淆矩陣。

#### 層次 3：每類精確突變合約（衍生自 `apply_anomaly()`）

**item_spending (t₁)**

```python
mult = float(rng.uniform(2.5, 4.0))
new_p = df.at[idx, "unit_price_usd"] * mult
df.at[idx, "unit_price_usd"]   = round(new_p, 4)
df.at[idx, "total_amount_usd"] = round(df.at[idx, "quantity"] * new_p, 2)
df.at[idx, "approver_id"]      = decide_approver(df.at[idx, "total_amount_usd"])
```

突變字段：`unit_price_usd`（×2.5–4.0）、`total_amount_usd`、`approver_id`。

**border_value (t₂)** — 前提：`unit_price_usd` ∈ [1.0, 100.0]

```python
up     = df.at[idx, "unit_price_usd"]
target = float(rng.uniform(950, 999) if rng.random() < 0.5
               else rng.uniform(4750, 4999))
new_qty = max(1, int(target / up))
df.at[idx, "quantity"]         = new_qty
df.at[idx, "total_amount_usd"] = round(new_qty * up, 2)
df.at[idx, "approver_id"]      = decide_approver(df.at[idx, "total_amount_usd"])
```

突變字段：`quantity`（調整使 total 落入 [950, 999] 或 [4750, 4999]）、`total_amount_usd`、`approver_id`。

**unusual_vendor (t₃) / conflict_of_interest (t₅)** — 前提：目前使用 S-001..S-025

```python
pool = suppliers_df.loc[suppliers_df["is_anomaly_pool"], "supplier_id"].tolist()
df.at[idx, "supplier_id"] = str(rng.choice(pool))
```

突變字段：`supplier_id`（改為 S-026..S-030）。兩者突變相同，差異在於 Stage 2 的 `purchase_note` 與 `supplier_profile` 語義線索（前者強調「不熟悉的貿易公司」，後者強調「與請購人的個人關聯」）。

**approval_bypass (t₆)** — 兩個子變體：

```python
if rng.random() < 0.5:
    # Variant A：缺漏核准人 / 跳階核准
    df.at[idx, "approver_id"] = ""
    if df.at[idx, "total_amount_usd"] < 1000:
        up = df.at[idx, "unit_price_usd"]
        nq = max(1, int(1500 / up))
        df.at[idx, "quantity"]         = nq
        df.at[idx, "total_amount_usd"] = round(nq * up, 2)
else:
    # Variant B：橡皮圖章（極速核准）
    lag = float(rng.uniform(0.01, 0.09))
    df.at[idx, "approval_lag_days"] = round(lag, 3)
    df.at[idx, "approved_date"]     = (
        pd.Timestamp(df.at[idx, "created_date"])
        + pd.Timedelta(days=lag)).isoformat()
```

突變字段（A）：`approver_id = ""`；可能附帶 `quantity`、`total_amount_usd`。
突變字段（B）：`approval_lag_days`（0.01–0.09 天）、`approved_date`。

`prepare_stage3.py` 中的 `add_policy_violation()` 進一步將 Variant A 的觸發條件細分為 3 條規則（任一觸發即 `policy_violation = 1`）：

1. `approver_id` 為空（缺失簽核者）；
2. 金額 ≥ $1,000 但 approver = `A-PROC-01`（跳過 CTO 階層）；
3. 金額 ≥ $5,000 但 approver = `A-CTO`（跳過 CEO 階層）。

**bank_account_change (t₈)**

```python
if df.at[idx, "total_amount_usd"] < 2000:
    up  = df.at[idx, "unit_price_usd"]
    nq  = max(1, int(2500 / up))
    df.at[idx, "quantity"]         = nq
    df.at[idx, "total_amount_usd"] = round(nq * up, 2)
    df.at[idx, "approver_id"]      = decide_approver(df.at[idx, "total_amount_usd"])
```

突變字段：`quantity`（調整使 total ≥ 2500）、`total_amount_usd`、`approver_id`。Stage 2 的 `purchase_note` 含「供應商最近更新銀行帳戶並要求轉至新帳戶」的語義。

**vendor_spending (t₄)** 與 **quote_manipulation (t₇)** — 不突變任何字段，僅標記。前者是跨訂單模式（同供應商於同季多次下單），後者由 Stage 2 在 `purchase_note` 嵌入「僅收到單一報價」的語義。

#### 突變合約彙整表（5 欄含真實意義）

下表為本研究 Ground Truth 分類法 T = { t₁, …, t₈ } 的完整定義 — 第三欄將「程式碼層的 mutation 配方」連結至現實採購詐欺類型，第四欄列出本研究在 Stage 1 中對應該類型所做的具體合成資料突變，第五欄標記訊號通道（影響 RQ2 子集分類，§14.3）。

| t | 類別 | 真實世界意義（fraud schema）| 突變字段（Stage 1 合成）| 訊號所在 |
|---|---|---|---|---|
| **t₁** | item_spending | **單價舞弊 / 回扣**：請購人與供應商串通抬高單價，差額作為回扣回流。對應 ACFE 2024《Report to the Nations》之 *corrupt purchasing scheme* 與 PACE PO 範疇 spending 指標。 | `unit_price` × U(2.5, 4.0)；連動 `total`、`approver` 重評估 | 數值（價格）|
| **t₂** | border_value | **門檻拆單 / 規避審批**：故意將總金額壓低於下一個審批門檻（如 $999、$4,999），跳過 CTO / CEO 審查。對應 PACE 之 *threshold avoidance / split bill* 指標。 | `quantity` 調整使 `total` ∈ [950, 999] ∪ [4750, 4999]；連動 `approver` | 數值（金額區間）|
| **t₃** | unusual_vendor | **空殼 / 紙面公司**：訂單路由至新註冊（≤ 1 年）、無實際營運紀錄的貿易公司，常見於洗錢、假發票、回扣中介。對應 PACE 之 *unfamiliar vendor* 指標與 ACFE *shell company* 模式。 | `supplier_id` → S-026..S-030（2024 新成立貿易商池）；其餘數值不變 | 類別 + 文字（supplier_profile）|
| **t₄** | vendor_spending | **單一來源依賴**：同一供應商於同季出現不成比例多次訂單，可能反映利益衝突、競爭排他、或內部偏袒。對應 PACE 之 *concentration risk* 指標。 | 不突變任何字段；僅在 `injection_plan` 標記為跨訂單模式 | 跨訂單統計 |
| **t₅** | conflict_of_interest | **內部利益衝突**：請購人與供應商之間有個人或前職關係（前同事、親屬、合資方），透過該偏好造成不公平採購。對應 ACFE *conflict of interest scheme*。 | `supplier_id` → S-026..S-030；Stage 2 在 `supplier_profile` 嵌入個人關聯語義 | 類別 + 文字（profile）|
| **t₆** | approval_bypass | **流程規避**：(V-A) 簽核者缺漏或越級（如 $5,000 案件僅 PROC-01 簽核，未升至 CTO / CEO）；(V-B) 橡皮圖章式秒批（lag < 0.1 天）。對應 PACE 之 *fast approval / policy violation* 指標。 | V-A：`approver_id`=""、可能拉抬金額觸發越級；V-B：`approval_lag` ∈ [0.01, 0.09] d、連動 `approved_date` | 規則 + 數值（V-A）/ 數值（V-B）|
| **t₇** | quote_manipulation | **競標舞弊**：偽造或抑制競爭供應商投標，製造「僅收到單一報價」假象，使指定供應商穩贏。對應 PACE ITQ 範疇之 *single quote / withdrawn bid* 指標（本研究對應至 PO 層級）。 | 不突變任何數值字段；Stage 2 在 `purchase_note` 嵌入「only one quote received / competitor withdrew」語義 | 文字語義（purchase_note）|
| **t₈** | bank_account_change | **BEC（Business Email Compromise）付款重定向**：詐騙者冒充供應商寄送「銀行帳戶已更新」郵件，誘騙公司將下次款項匯至詐騙帳戶。對應 ACFE 2024 與 IJFMR 2025 哨兵研究之當代最高發案類別。 | `quantity` 調整使 `total` ≥ $2,500（觸發 approver 階層）；Stage 2 在 `purchase_note` 嵌入銀行帳戶變更紅旗 | 數值 + 文字 |

**讀法注意**：
- 第三欄為**現實詐欺意義**；第四欄為**本研究操作化的合成方式**。兩者不必完全等價（如真實 BEC 不會強制拉抬 quantity，但本研究刻意如此設計以使 t₈ 同時帶有數值訊號，便於 §14.3 的訊號類型分類分析）。
- t₃ 與 t₅ 共享相同的 `supplier_id` 突變但 Stage 2 的語義線索不同：t₃ 強調「不熟悉的新貿易公司」，t₅ 強調「與請購人的個人關聯」。兩類在 Block B 中各佔一題，作為「相同類別訊號 + 不同語義差異」的對照。
- `injection_plan` 欄位記錄該訂單被注入的 t 類別，作為 Ground Truth 的多類別標籤（§7.4 層次 2）。

#### 層次 4：實驗分層

```python
y_stratum = df["experiment_stratum"]
# 5 個值：{"A", "B", "C1", "C2a", "C2b"}
y_block   = df["experiment_block"]
# block 名稱：normal_obvious / anomaly_obvious / edge_normal_high_D2 /
#            edge_anomaly_low_D2_numeric / edge_anomaly_low_D2_text
```

詳見 §9.4。

### 7.5 `injection_seed` 的用途（非 Ground Truth）

```python
df.at[idx, "injection_seed"] = seed   # 6 位整數；正常訂單為 -1
```

`injection_seed` 不是 Ground Truth，常被混淆。用途：給定一筆異常訂單，可重現當時的隨機突變（例如 `item_spending` 中那個 2.5–4.0 之間的具體倍數）。

### 7.6 Section E 與 G3 AI 證據的互補性

Section E（§9.2）提供的是 SKU 層級的單變量統計偏差（例如「單價是中位數的 N 倍」），其訊號範圍嚴格限於數值欄位。G3 AI 證據則提供跨欄位語義推理的產物（例如結合 `supplier_profile` 中「2024 新成立貿易公司」與 `purchase_note` 中「僅收到單一報價」的交叉分析）。

兩者的重疊主要發生在**數值類異常**（`item_spending`、`border_value`）上 — 此時 Section E 的 ratio 已足以提供關鍵線索，G3 證據的 incremental value 較低。然而，在**文字類異常**（`unusual_vendor`、`vendor_spending`、`quote_manipulation`、`conflict_of_interest`）上，Section E 完全無法提供訊號（所有 ratio 與 z-score 均在正常範圍），G3 AI 證據是受試者唯一的額外資訊來源。

這也是 RQ2 將 signal_type 作為調節變數的理論基礎：本研究預期 G3 的優勢（若存在）將集中在 text_dominant 子集上，正是因為 Section E 在該子集上失效，G3 的 incremental value 最大。

### 7.7 注入引擎（完整代碼）

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
            target = len(pool)
        arr = np.array(pool); rng.shuffle(arr)
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

每筆突變後的訂單收到 `injection_plan = tᵢ.name` 與整數 `injection_seed`，以供逐列重現。

---

## 8. Stage 2 — DeepSeek 語義欄位生成

Stage 1 結束後 `purchase_note` 與 `supplier_profile` 為空。`generate_semantics.py` 對每筆訂單呼叫一次 DeepSeek Chat API。異常訂單附帶內部提示（對最終稽核員不可見）：

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

JSON 回應解析後寫回訂單列。每 10 列存檔一次，支援 API 失敗後續跑。另插入兩個空欄 `purchase_note_human`、`supplier_profile_human` 供人工改寫；AI 與人工用語的對比支援獨立的探索性子研究。

**模型分離設計**：Stage 2 刻意選用 DeepSeek（與下游分析器 Qwen3-8B 不同的模型），以防止同源預填偏誤。若 Stage 2 與 Stage 4 使用同一模型，G2 / G3 的判斷可能僅是 LLM 對自己 Stage 2 輸出的「自我確認」，而非真實的稽核推理。

---

## 9. Stage 3 — 偏差特徵、Mahalanobis、實驗分層

Stage 3 不執行偵測。它完成四項確定性任務，產出**凍結的實驗工具**；所有下游偵測（Baseline-Stat、G2 LLM 裁決、G3 LLM 證據）在 Stage 4 中以這些工件為固定輸入進行。

### 9.1 Base Rate 設計與外部效度限制

500 筆母體的異常率 = 76 / 500 = **15.2%**，接近真實採購環境。

但 32 題實驗集刻意將異常率提升至 **50%**（16 / 32：B 區 8 + C2a 3 + C2b 5）。此為刻意的設計取捨：若維持 15.2% 的 base rate，32 題中僅約 5 筆異常，不足以支撐 per-class 與 per-signal-type 的子集分析。

**主觀感知異常率的理論上限**：Block C1 的 6 題正常訂單因 D² 偏高（85–95 百分位），其 Section E 偏差特徵看起來可能可疑。若假設受試者將所有 C1 題（6 題高 D² 正常單）皆誤判為異常，則感知異常率理論上最高可達 (16 + 6) / 32 = **68.75%**。實際感知偏差程度需待實驗後問卷與行為資料驗證。

此 base rate shift 與感知放大效應對三組的影響均等（G1 / G2 / G3 看到的題目完全相同），因此**不影響組間比較的內部效度**，僅限制結果推論至真實 base rate（15.2%）情境的外部效度。

### 9.2 偏差特徵（Section E：8 個新欄位）

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

**這些是純數值轉換，不是規則**。Section E 在 UI 中以**自然語言句子**呈現給三組受試者，例如：

> *Unit price: $8.90 vs. SKU historical median $2.80 → 3.2× higher*
> *Approval lag: 0.05 days vs. typical 2.0 days → 40× faster*

LLM **不**直接看到 ratio 數值；LLM 須從原始欄位加上 RAG 檢索到的歷史訂單自行推論偏差（若將預算好的 ratio 直接餵給 LLM，等同替它完成推理，破壞實驗純度）。

### 9.3 Mahalanobis 距離（雙軌：linear + log）

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

**Log-Mahalanobis 雙軌**：對 *log(x)* 重複以上計算，產生 `mahalanobis_D2_log` 與 `D2_log_percentile`。理由：linear D² 對 `approval_bypass` Variant B（lag = 0.05d）不敏感，log D² 能補捕乘法尺度的離群值。

D² 的用途：

- 層化 32 題實驗集（§9.4）
- 論文 Chapter 4 的「Baseline-Stat」偵測器（無領域知識的演算法下界）

**D² 不用於**：呈現給 G2 / G3 受試者或餵給 LLM。UI 永遠不顯示 D² 值或百分位。

### 9.4 凍結實驗集（32 題 + 2 練習）

層化抽樣，seed = 42，完全確定性：

| 層別 | 數量 | 篩選準則 |
|---|---|---|
| **A** 正常 | 10 | `injection_plan == "none"`、`policy_violation == 0`，且 `mahalanobis_D2 < median(全部 500 筆 D²)`（≈ 3.36，χ²(4) 中位數理論值）且 `mahalanobis_D2_log < median(全部 500 筆 log-D²)` |
| **B** 明顯異常 | 8 | 8 類各 1 題；數值類取最高 D²，類別/文字類取最高 `text_signal_score` |
| **C1** 邊界正常（假陽性陷阱）| 6 | `injection_plan == "none"` 且 D² 百分位 ∈ [85, 95]，且 D² < χ²(4, 0.99) = 13.28 |
| **C2a** 邊界異常 — 數值隱晦 | 3 | `item_spending`、`approval_bypass` Variant B、`bank_account_change`（取最低 linear-D²）|
| **C2b** 邊界異常 — 文字隱晦 | 5 | `unusual_vendor`、`vendor_spending`、`quote_manipulation`、`conflict_of_interest`、`bank_account_change` 弱版（取最低 `text_signal_score`）|
| **練習** | 2 | 1 obvious normal + 1 obvious anomaly（與實驗集不重疊，亦不入 RAG）|
| **合計** | **32 + 2** | |

**B vs. C 的核心對比**：每類異常出現兩次 — B 區為「明顯版」（高 D² 或高 text_signal），C2 區為「隱晦版」（低 D² / 低 text_signal）。例如 `approval_bypass` 在 B 區為 Variant A（`policy_violation = 1`，高訊號），在 C2a 為 Variant B（`approval_lag = 0.05d`，linear D² 低、log D² 高）。此設計直接對應 RQ2：在訊號弱化情境下，AI 輸出格式的差異是否被放大？

**納入文字隱晦邊界案例（C2b）的理由**：t₃、t₄、t₅、t₇ 與 t₈ 弱變體未突變 4 維數值特徵向量，訊號藏在 `supplier_profile` 與 `purchase_note`。這些正是 LLM 證據預期勝過純統計偵測器的案例，對 G3 vs. G2 比較最具鑑別力。

### 9.5 輸出檔案

`prepare_stage3.py` 產出（時間戳記 `<TS>`）：

| 檔案 | 內容 | 使用者 |
|---|---|---|
| `data/stage3/stage3_full_with_truth_<TS>.xlsx/.csv` | 全部 500 筆，含 Section E、`mahalanobis_D2`、`mahalanobis_D2_log`、`D2_percentile`、`D2_log_percentile`、`risk_tier`、`policy_violation`、`injection_plan`、`injection_seed`、`experiment_stratum`、`experiment_block`、`practice_role`、`reason` | 研究者主檔 |
| `data/stage3/experiment_32qs_<TS>.xlsx/.csv` | 32 題層化訂單，已剝離所有 Ground-Truth、偵測器信號與預算偏差數值（保留 Section E 自然語言句子）；展示順序額外打亂 | UI 使用 |
| `data/stage3/experiment_32qs_<TS>_KEY.xlsx` | 答案鍵：`po_id`、`experiment_stratum`、`experiment_block`、`injection_plan`、`mahalanobis_D2`、`mahalanobis_D2_log`、`reason`、`policy_violation` | 研究者評分 |
| `data/stage3/practice_2qs_<TS>.xlsx/.csv` + `*_KEY.xlsx` | 2 練習題（嚴格不入實驗集與 RAG）| 受試者熱身 |
| `data/stage3/rag_corpus_466_<TS>.jsonl/.csv` | 其餘 466 筆（500 − 32 − 2）序列化為 RAG 文件（自然語言 `text` + 精簡 metadata），已剝離所有敏感欄位 | Stage 4 Chroma 導入 |

**資訊隔離原則**：UI 與 RAG 只保留原始欄位 (17) + 語義欄位 (4) + Section E 自然語言句子。LLM 必須透過 RAG 檢索到的 5 筆相似訂單自行推論任何偏差，不獲得任何預先計算的 ratio 或 D² 值。

---

## 10. Stage 4 — RAG 建立與 LLM 輸出凍結

### 10.1 RAG 建立（`build_rag.py`）

使用 ChromaDB + Ollama embeddings：

```python
EMBED_MODEL = "nomic-embed-text"   # 768 維，本地 Ollama
COLLECTION  = "po_history"
SOURCE      = "data/stage3/rag_corpus_466_<TS>.jsonl"
```

執行前進行 leakage check：嚴格驗證 metadata 不含敏感欄位（24 個欄位的黑名單，鏡像 `prepare_stage3.py` 的 `TRUTH_COLS + DETECTOR_COLS + DERIVED_COLS`）。任何洩漏即中止建構。

### 10.2 LLM 模型選擇 — Qwen3-8B

本研究選用 Qwen3-8B（透過 Ollama 本地部署）有 3 個理由：

1. **規模平衡**：8B 在推理能力與本地推論可行性間取得平衡，無外部 API 依賴可確保跨年代再現性（不會因 API 改版而結果漂移）；
2. **公開評測表現**：基於公開評測（如 OpenCompass 2025、HuggingFace Open LLM Leaderboard），Qwen3-8B 在指令遵循、結構化 JSON 輸出與長上下文推理任務的表現與 Llama 3-8B、Gemma2-9B 等同級對手相當或略優，符合本研究 G2 / G3 需要嚴格 JSON schema 遵循與多欄位推理的場景需求；
3. **開放權重 + 本地部署**：任何研究者皆可從 `ollama pull qwen3:8b` 重新跑出**完全相同**的 G2 / G3 凍結輸出（Q4 量化版，模型 hash `500a1f067a9f`），且本地部署符合企業稽核情境的資料隱私要求。

### 10.3 凍結 LLM 輸出（`freeze_llm_outputs.py`）

對 32 題實驗集 + 2 練習題凍結三類輸出：

| 輸出檔 | 內容 | 用途 |
|---|---|---|
| `g2_verdicts_<TS>.json` | 每題 1 個 `{judgment, reason}` 物件 | G2 組看到 |
| `g3_evidence_<TS>.json` | 每題 4 條 `{feature, current_value, reference_value, why_noteworthy}` 物件（v2 schema，§10.5）| G3 組看到 |
| `shadow_g2_for_g3_<TS>.json` | 與 g2_verdicts 同 prompt 結構，但伴隨 G3 結束時用同一 LLM session 產出 | RQ3 中作為 G3 組的「AI 錯誤」基準 |

#### Ollama API 參數

| 參數 | 值 | 說明 |
|---|---|---|
| `model` | `qwen3:8b` | |
| `temperature` | 0.0 | 確定性輸出 |
| `thinking mode` | **enabled** | Qwen3 的 `<think>...</think>` 推理塊保留 |
| `num_predict` | 8192 | 含 thinking 的足夠 token 預算 |
| `num_ctx` | 16384 | 含 RAG 5 筆 + system + user prompt 的足夠上下文 |
| `timeout` | 900s | 含 thinking 推理的足夠時間 |
| RAG `top_k` | 5 | 每題檢索 5 筆相似歷史訂單 |

`strip_thinking()` 函式於後處理時剝除 `<think>...</think>` 區塊，僅保留最終 JSON 物件交給下游。

#### 失敗 fallback 機制

若某題 G2 / G3 / shadow_g2 retry 3 次仍失敗，腳本會：

1. 寫入中性 fallback 內容到對應 JSON：
   - G2 / shadow_g2：`{"judgment": "normal", "reason": "AI inference unavailable...", "_fallback": true}`
   - G3：4 條 `(unavailable)` 佔位 evidence + `_fallback: true`
2. 在 `generation_log_<TS>.json` 留下 `g2_fallback_used: true` 與原始錯誤訊息；
3. acceptance 階段印出 `WARN: G3 fallback used for X/32` 警示。

### 10.4 G2 prompt 設計

```
SYSTEM:
You are a procurement audit assistant. Given an order and 5 similar
historical orders, decide if the order is "suspicious" or "normal" and
provide a one-sentence rationale. Output ONLY the required JSON object.

USER:
[Current order: 17 raw fields + 4 semantic fields]
[5 RAG-retrieved historical orders, each: 17 raw + 4 semantic fields]

Think step by step inside a <think>...</think> block, then output:
{"judgment": "suspicious"|"normal", "reason": "..."}
```

### 10.5 G3 prompt 設計

#### 10.5.1 設計演進（v1 → v2）

G3 的 prompt 經歷一次重要修訂。**v1 版**（首批凍結輸出於 2026-04-26）要求 LLM「identify the FOUR most suspicious factual observations」並輸出 `suspicious_features` / `why_suspicious` 欄位。在實測中此設計暴露兩個問題：

1. **強迫 LLM 對正常訂單捏造可疑點**：對 A 區 10 題 / C1 區 6 題（皆為正常訂單），LLM 須在毫無真實異常時硬擠 4 條「偏離」描述（例如「quantity 10 vs 中位數 8、高 25%」這種無實務意義的微小偏差）。極端情況下，模型在 thinking 鏈中死轉，token 預算耗盡而無法吐出 JSON（PO-2024-0422 練習題即為此）。
2. **語意悖反原始設計意圖**：G3 的設計目標是「提供中立證據讓人類自己下結論」（§3.2）。但 v1 prompt 強制標籤為 `suspicious_features` 等於把每條觀察都塗上了「此處有問題」的有色濾鏡，這已經是隱式結論，違背原意。

#### 10.5.2 v2 版設計（2026-04-27 起，正式採用）

v2 將 G3 重新定位為「中立 noteworthy 觀察」，明示允許兩類觀察並存：

- **(a) 偏離型**：current_value 顯著偏離歷史 / 市場參考值（例如 `unit_price $0.2878 vs market median $0.1163, 2.5× higher`）
- **(b) 確認型**：current_value 與歷史 / 市場參考值一致或在合理範圍內（例如 `quantity 10 matches historical median for this SKU`）

LLM 自行決定 4 條中各有幾條偏離 / 幾條確認，**禁止為了湊滿 4 條而捏造偏離**。

```text
SYSTEM (v2, 摘要):
You are an internal procurement auditor at a 30-person electronics company.
Select the 4 MOST NOTEWORTHY features of this order.
A noteworthy feature can be EITHER (a) a deviation from typical patterns,
OR (b) a confirming observation that the order looks routine.
Most procurement orders are routine. Do NOT manufacture deviations.
Do NOT issue an overall verdict, recommendation, or conclusion.

JSON schema:
{"noteworthy_features": [
  {"feature": "...", "current_value": "...",
   "reference_value": "...", "why_noteworthy": "<5-25 words>"},
  ... × exactly 4
]}
```

USER 模板與 G2 共用（§10.4）。

#### 10.5.3 防混淆設計：每條 `why_noteworthy` 限 5–25 words

V2 引入硬性長度約束：每條 `why_noteworthy` 必須在 5–25 words 之間，由 `validate_g3()` 在驗證階段檢查。**設計理由**：v1 G2 凍結輸出顯示 suspicious 平均 reason 長 24.7w / normal 19.5w，存在 ~5w 系統性差異（§15.8）。雖然 G3 並無 verdict，但若 4 條 `why_noteworthy` 中部分顯著較長、部分較短，受試者仍可能將文字長度誤讀為「AI 對該特徵的信心高低」 — 這是另一種隱式 confidence signal。固定長度區間使 4 條視覺均勻，迫使受試者基於內容而非長度判斷。

#### 10.5.4 對 RQ2 與 RQ3 的影響

v1 → v2 的轉換改變了 G3 vs G2 的對比語意：

- **v1 對比**：「AI 寫成可疑列表」vs「AI 寫成結論加一句理由」 — 兩者皆帶可疑取向，僅形式不同
- **v2 對比**：「AI 提供中立觀察清單」vs「AI 提供傾向結論加一句理由」 — 形式 + 取向皆不同

v2 對比更貼近現實的「人 + AI 證據型助手 vs 人 + AI 結論型助手」分歧。對 RQ2（訊號類型調節）與 RQ3（人類推翻 AI 錯誤）的假設方向不變，但效應大小可能放大（v2 的 G3 更接近「真正的證據」設計）。

**已凍結之 v1 輸出**（`g3_evidence_exp_20260426_224057.json`）保留於 repo 作為演進紀錄，但**不用於正式分析**。所有正式分析使用 v2 重跑後產出的 `g3_evidence_exp_<新 TS>.json`。

### 10.6 Shadow G2

於 G3 結束後，用同一 Ollama session 對同一題重新跑一次 G2 prompt，產出 `shadow_g2_for_g3`。理由：RQ3 需要定義「AI 在哪些題上答錯」作為人類推翻能力的基準。對 G2 組可直接用 `g2_verdicts`；對 G3 組需要一個對應的「假設 G3 受試者看到的 AI 結論會是什麼」基準，這即 shadow G2。

#### 10.6.1 Sanity check 實際結果（v1 32 題）

凍結完成後計算 shadow G2 與正式 g2_verdicts 在 32 題上的 agreement rate：

- **實際 agreement = 28/32 = 87.5%**（4 題不一致）
- 4 題不一致全部發生在 `g2 = suspicious / shadow = normal` 方向：

  | PO | Truth | g2 | shadow | 誰對 |
  |---|---|---|---|---|
  | PO-2024-0375 | normal | suspicious | normal | shadow ✅ |
  | PO-2024-0298 | normal | suspicious | normal | shadow ✅ |
  | PO-2024-0174 | anomaly | suspicious | normal | g2 ✅ |
  | PO-2024-0418 | anomaly | suspicious | normal | shadow miss ❌ |

  Shadow 比 g2 略不警覺（TN +2、FN +2、整體精度相同 56.25%）。

#### 10.6.2 操作判定：以 g2_verdicts 為 RQ3 共同基準

雖然 87.5% < 100%，本研究選擇以 g2_verdicts 作為 G2 與 G3 兩組共同的「AI 錯誤基準」進行 RQ3 分析。理由：

1. **跨組一致性優先**：若 G2 用 g2_verdicts、G3 用 shadow_g2，兩組受比較的 AI 錯誤集合不同，RQ3 的「G3 推翻 AI 錯誤」相對於「G2 推翻 AI 錯誤」就喪失可比性。
2. **shadow_g2 並非「假設 G3 看到的結論」**：shadow_g2 是用 G2 prompt 在 G3 之後再跑一次 — 形式上與 g2_verdicts 等價，理論上應 100% 一致；87.5% 是實作層的非確定性（同一 prompt 同一 model temperature=0 仍輸出不同）。換言之，shadow_g2 是 g2_verdicts 的雜訊複本，不是獨立信號。
3. **shadow_g2 的真正用途**：作為 LLM 確定性極限的方法論證據檔，**而非 RQ3 的計算輸入**。

#### 10.6.3 87.5% 不一致的方法論揭露

非確定性原因為何 temperature = 0 仍出現 87.5% agreement？推測為：

- **System prompt 上下文不同**：G2 和 shadow_g2 雖然 prompt 內容相同，但 G3 在兩者之間執行（用了 G3 system prompt），影響了 Ollama 內部 KV cache 與 token sampling 路徑。
- **批次平行性**：Ollama 在多個請求間的 GPU 排程順序可能造成微差。

本研究於 Chapter 4 將完整列出 4 題不一致的細節，作為「即使 frozen LLM 設計，相同 prompt 仍可能輸出 87.5% 一致而非 100%」的方法論誠實揭露。對未來研究的建議：若要追求 100% 確定性，應使用單一 batch、停用 background prefetch、或改用支援固定 RNG 的 sampler。

---

## 11. 可重現性保證

1. **確定性 RNG**：`numpy.random.default_rng(42)` 統一種子；`injection_seed` 鎖定逐列異常注入。
2. **凍結市場資料**：`data/mouser_raw_exact.json` 及其 `_meta` 指紋是價格與前置時間的唯一真實來源。
3. **凍結 LLM 輸出**：`g2_verdicts_<TS>.json` / `g3_evidence_<TS>.json` / `shadow_g2_*.json` 一旦產生即不再呼叫 Ollama。所有受試者看到完全相同的 AI 輸出。
4. **凍結 RAG**：Chroma collection `po_history` 一旦建構（466 文件、`nomic-embed-text` embeddings）即視為靜態知識庫。
5. **論文附錄相容性**：所有參數由 `print_all_parameters()` 在執行時輸出，可直接附於論文附錄作為可驗證的控制台追蹤。

從乾淨 checkout 執行：

```bash
python generate_dataset.py        # Stage 0+1
python generate_semantics.py      # Stage 2
python prepare_stage3.py          # Stage 3
cd ../rag
python build_rag.py --reset       # Stage 4a
python freeze_llm_outputs.py --label exp     # Stage 4b (experiment)
python freeze_llm_outputs.py --label practice # Stage 4b (practice)
```

可逐位元重現所有 Stage 1–4 工件（檔名時間戳記是唯一漂移）。

---

## 12. 參數來源摘要

| 參數 | 來源 | 類型 |
|---|---|---|
| 10 個 SKU | 手選，涵蓋各零件類別 | 設計 |
| `price_median_usd` | Mouser API 價格區間的幾何平均 | 真實 |
| `σ_price` | (ln max − ln min) / 4，截斷 [0.05, 0.50] | 衍生 |
| `lead_time_median_days` | Mouser `LeadTime` 欄位 | 真實 |
| `σ_lead` | max(2, 0.25 · µ) — CV 0.25，Silver et al. (2017) | 假設 |
| `qty_median`, `σ_qty` | 按類別合理性手設 | 設計 |
| `APPROVAL_LAG_*` | 小企業快速核准假設 | 設計 |
| 請購人權重 | 輕微集中，模擬關鍵人員 | 設計 |
| 供應商偏好圖 | 25 家製造商 + 5 家貿易殼 | 設計 |
| Poisson λ = N / T | 標準到達過程 | 理論 |
| 8 類異常 | 5 PACE PO/ACRA + 2 PACE ITQ 重範疇 + 1 ACFE BEC | 文獻混合 |
| Mahalanobis 門檻 9.49 / 13.28 | χ²(4) α = 0.05 / 0.01 | 理論 |
| 32+2 / 466 實驗切割 | 按注入類別 + D² 百分位的 5 層分層 | 設計 |
| Qwen3-8B (Q4 量化) | Ollama 本地，模型 hash `500a1f067a9f` | 工具選擇 |

---

## 13. 如何閱讀 Excel 資料集

Stage 1 輸出檔 `data/dataset_YYYYMMDD_HHMMSS.xlsx` 是主要工件，單一 .xlsx 活頁簿，共 5 個工作表。

### 13.1 活頁簿地圖

| # | 工作表 | 列 × 欄 | 一句話說明 |
|---|---|---|---|
| 1 | metadata | 18 × 2 | 執行指紋 |
| 2 | components | 10 × 15 | 10 個 SKU 及 Mouser 衍生價格、前置時間 |
| 3 | suppliers | 30 × 6 | 25 家正常 + 5 家異常池 |
| 4 | injections | 76 × 3 | 哪些 PO 被突變、依哪個規則、用哪個種子 |
| 5 | orders | 500 × 21 | 主資料 |

### 13.2 用 Python 讀取

```python
import pandas as pd

fp = "code/dataset/data/dataset_20260420_015519.xlsx"

orders     = pd.read_excel(fp, sheet_name="orders")
suppliers  = pd.read_excel(fp, sheet_name="suppliers")
components = pd.read_excel(fp, sheet_name="components")
injections = pd.read_excel(fp, sheet_name="injections")

normal    = orders[orders["injection_plan"] == "none"]   # 424 列
anomalies = orders[orders["injection_plan"] != "none"]   #  76 列
```

### 13.3 配套檔案

| 路徑 | 用途 |
|---|---|
| `data/mouser_raw_exact.json` | 凍結的 Mouser API 回應（稽核軌跡）|
| `data/stage1/orders_*.csv` | orders 工作表的純文字副本 |
| `data/stage2/orders_stage2_semantics.xlsx` | Stage 2 帶有 `*_human` 欄的 Excel |
| `data/stage3/stage3_full_with_truth_*.xlsx` | 含 Section E 與 D² 的研究者主檔 |
| `data/stage3/experiment_32qs_*.xlsx` | UI 使用（已清除敏感欄位）|
| `data/stage3/practice_2qs_*.xlsx` | 練習題（不入 RAG）|
| `data/stage3/rag_corpus_466_*.jsonl` | Chroma RAG 語料庫 |
| `data/stage4/g2_verdicts_*.json` | 凍結 G2 輸出 |
| `data/stage4/g3_evidence_*.json` | 凍結 G3 輸出 |
| `data/stage4/shadow_g2_for_g3_*.json` | 凍結 Shadow G2 輸出 |
| `data/chroma/` | Chroma 向量庫 |

---

## 14. 實驗分析計畫

### 14.1 RQ 正式版

- **RQ1**: Does presenting LLM output as structured evidence (four factual observations without a verdict) yield higher human anomaly detection accuracy than presenting a binary conclusion with a one-sentence rationale, or no AI assistance?

- **RQ2**: Does the effect of AI output format vary between anomalies detectable through numerical deviation versus those detectable only through textual semantics?

- **RQ3**: When the LLM produces an incorrect output, does the evidence format enable participants to override AI errors more effectively than the conclusion format?

### 14.2 評估指標

#### 主指標（accuracy 系列）

- **整體正確率** (Accuracy)：每受試者 32 題答對比例
- **Sensitivity / Recall**：在 16 真異常題中答對的比例
- **Specificity**：在 16 真正常題中答對的比例
- **F1 分數**：2 · (P · R) / (P + R)
- **Per-class recall**：每類異常（8 類）+ 每 block（A / B / C1 / C2a / C2b）的答對比例
- **Appropriate Override Rate (AOR)**：僅適用於 G2 / G3 — 在 AI 答錯的題目中，人類給出正確判斷的比例（RQ3 主指標）

#### 二級指標

- **決策時間**：定義為 UI 前端記錄的「題目顯示時間」至「受試者點擊提交」的差值（秒）。
  - **離群值處理**：以 300 秒為閾值，超過者**標記為 outlier**；主要分析保留所有資料，**額外報告排除 outlier 後的組中位數**作為穩健性檢查（不採 winsorization，避免在小樣本下扭曲組內變異）。若某組 outlier > 20%，於討論中說明對結果的潛在影響。
  - **分布處理**：分析時取 log 轉換後再做組間比較（反應時間分布右偏）。
- **信任問卷**：實驗後 5-point Likert：「我對這次的判斷有多少把握？」、「我多少程度依賴了 AI 的輸出？」（僅 G2 / G3）
- **自由文本理由編碼**：每題受試者填寫一句理由，事後編碼為「訴諸 Section E ratio」/「訴諸 supplier_profile」/「訴諸 purchase_note」/「訴諸 AI 結論」/「直覺」等類別

### 14.3 訊號類型分類（RQ2）

| 子集 | 內容 | 訊號類型 |
|---|---|---|
| `numeric_dominant` | B-item_spending、B-border_value、B-approval_bypass*、B-bank_account_change（強版）††、C2a 全部 | 數值 |
| `text_dominant` | B-unusual_vendor、B-vendor_spending、B-quote_manipulation、B-conflict_of_interest、C2b 中除 bank_account_change 外的 4 題† | 文字 |
| `dual_signal` | C2b 中的 `bank_account_change` 弱版（PO-2024-0211）†† | 文字 + 殘留數值 |
| `normal` | A 全 10 + C1 全 6 | — |

**通則註腳**：同一異常類別可能因強度不同而落入不同 `signal_type`。例如 `bank_account_change` 在 B 區因 quantity 大幅拉抬使 D² 顯著偏高，歸為 `numeric_dominant`；在 C2b 區則為弱版（PO-2024-0211），主要訊號藏於 `purchase_note`。此為「強訊號 vs. 弱訊號」對照設計的副產物，不影響分析有效性。

**B-approval_bypass 註腳 (\*)**：B 區的 `approval_bypass` 題選的是 Variant A，定義為 `policy_violation = 1`，由以下 3 條規則任一觸發（code: `add_policy_violation`，`prepare_stage3.py` line 356–366）：(1) `approver_id` 為空；(2) 金額 ≥ $1,000 但簽核者僅為 `A-PROC-01`；(3) 金額 ≥ $5,000 但簽核者僅為 `A-CTO`。雖然 V-A 的核心訊號為類別/規則型（policy 違規），但其 Stage-1 mutation 通常伴隨金額抬升以及 Mahalanobis D² 偏離，使數值偏差同時可見。因此本研究在 RQ2 訊號分類中將 B-approval_bypass 歸入 `numeric_dominant`。對應地，C2a 的 `approval_bypass` 選的是 Variant B（`approval_lag = 0.05d`），linear D² 不敏感、log D² 高，屬於需更精細閱讀才能察覺的隱晦數值異常。**B (V-A) vs. C2a (V-B) 構成同一類異常的「強訊號 vs. 弱訊號」對照**，是 RQ2 訊號層級分析的關鍵設計。

**C2b 註腳 (†)**：`text_dominant` 子集刻意排除 C2b 中的 `bank_account_change` 弱版（PO-2024-0211），原因見下方第三註腳。

**bank_account_change 跨子集註腳 (††)**：本研究 `bank_account_change` 類別共出現兩題：B 區強版歸入 `numeric_dominant`，C2b 區弱版（PO-2024-0211）歸入 `dual_signal`。**同一異常類別跨兩個子集是設計上的有意安排**，目的是建立同類別內的「強訊號 vs. 弱訊號」對照（與 §14.3 通則註腳一致）。具體分類依據：`bank_account_change` 在 Stage 1 mutation 時為使 total ≥ $2,500（觸發 approver 階層變動），對 quantity 進行了拉抬。即使在 C2b 中已挑選該類 D² 最低的候選，PO-2024-0211 的 D² 仍高於其他純文字類異常（具體百分位於 Chapter 4 公開揭露）。為避免污染 `text_dominant` 子集的純度，本研究將其單獨置於 `dual_signal` 類別，**在彙總統計（如 text_dominant 子集的 G3 vs. G2 對比）時不併入該子集**，但在個別題目層級分析中保留。

### 14.4 統計分析三層次

本研究 N = 4 / 組（總 12 人）為 pilot 規模。4 個 cluster 估混合效應變異數會嚴重不穩定（不收斂或退化到 0），因此本研究**完全捨棄** mixed-effects logistic regression 與 GEE，亦**不採用** Bayes Factor（其 prior 選擇對小樣本 BF 數值影響極大，FYP 範圍內難以充分論證）。分析以效果量及其信賴區間為主軸：

#### 主層 — 描述統計與效果量（不假設分布、不依賴 p 值）

- **三組各 32 題正確率**：中位數 + IQR + **95% bootstrap CI**（10 000 次重抽）
- **Per-block 正確率熱力圖**（A / B / C1 / C2a / C2b × G1 / G2 / G3） — 每格逐筆列出 4 人中答對人數
- **文字 vs. 數值類異常正確率對比** — 直接對應 RQ2 的核心問題：「文字類異常是否最容易被誤判？G3 是否在文字類有最大優勢？」
- **效果量**：
  - **Cliff's δ**（非參數，逐題二元正確率）：基準（Romano et al., 2006）：絕對值 < 0.11 微不足道、0.11–0.28 小、0.28–0.43 中、> 0.43 大。（**註**：此為 Romano et al. 對教育研究序位資料的經驗建議，非通用標準；本研究僅用於跨組相對比較，不作為決定性閾值。）
  - **Hedges' g**（小樣本修正的 Cohen's d，用於受試者層級總正確率與決策時間）：基準（Cohen, 1988）：0.2 / 0.5 / 0.8 = 小 / 中 / 大。

#### 補充層 — 非參數檢定

- **Mann-Whitney U**（兩組對比）/ **Kruskal-Wallis**（三組）：報 p 值與 rank-biserial r，僅作補充參考
- **Fisher's exact test**：RQ3 的「AI 答錯題」子集 G2 vs. G3 二乘二表

#### 質性層

- 自由文本理由（編碼類別）+ 信任問卷 + 決策時間
- 結合主層的效果量，輔助詮釋為何某組正確率較高（是真理解、隨機猜對、還是依賴 AI）

### 14.5 樣本數與統計分析定位

#### 務實樣本數

- **每組 N = 4 人**，三組總計 **12 人**（FYP 時程下的實際招募定案）
- 每受試者：32 主題 × ~2 分鐘 + 練習 2 題 + 問卷 ≈ **70–90 分鐘 / 人**
- **題目層級觀測值**：4 人 × 32 題 = **128 obs / 組**，三組合計 384 obs

#### 為什麼此樣本仍可寫成 FYP 論文

1. **完整 pipeline 驗證**：本研究核心貢獻之一是建立並驗證從合成資料 → RAG → LLM 凍結 → UI → 資料分析的端到端框架，N = 4 / 組已足以驗證每個環節都能跑通；
2. **效果量 + bootstrap CI 為主**：報 Cliff's δ、Hedges' g、95% bootstrap CI；不依賴 p 值是否 < 0.05；
3. **質性互補**：自由文本理由 + 信任問卷 + 決策時間補強說服力。

#### 預期可偵測效應量（誠實版）

- 主效應：Cliff's δ ≈ 0.43+（**大效應**） — 對應正確率 ~80% vs. ~50%
- 交互作用：text_dominant 子集中 G3 vs. G2 的差異須達 δ ≈ 0.5+ 才有 95% bootstrap CI 不跨 0
- **任何中小效應（δ < 0.28）的 95% CI 必然跨 0**；遇此狀況直接報效果量並接受結論，不嘗試硬擠 p < 0.05

#### 研究定位

本研究明確定位為 **proof-of-concept / pilot study**，**不**主張統計上的決定性結論。主要貢獻：

(a) 設計並驗證證據 vs. 結論的對比實驗框架可行性；
(b) 提供初步效果量估計給後續大樣本研究做 power analysis；
(c) 公開全部資料、prompt、frozen LLM 輸出供他人 replicate；
(d) 後續工作：擴大至每組 N ≥ 30，跨產業審計員樣本，再做確認性檢定（含 mixed-effects logistic regression 作為主分析）。

### 14.6 四種結果情境的論文寫法

**情境 1：G3 > G2 > G1（任一兩組對比效果量 95% CI 完全在 0 的同一側）**
證據設計本身勝出。**在 pilot 樣本（N = 4 / 組）下，本研究將此結果定位為對「證據式格式優於結論式」假設的初步支持，呼應 Vaccaro (2024) 元分析中 explanation 無效的反例方向；待大樣本（每組 N ≥ 30）確認後方可視為穩健結論**。

**情境 2：整體沒差，但 C2b 文字類 G3 > G2**
證據設計在特定條件下有效，須搭配適當的異常類型；對應 RQ2 訊號類型調節效應。**同樣受限於 pilot 樣本量，本研究將此結果定位為交互作用假設的初步證據，需後續大樣本驗證子集差異是否穩健。**

**情境 3：G2 < G1（AI 反而拖累）**
結論型 AI 引發自動化偏誤；方向上呼應 Vaccaro 元分析中 g = −0.23 的發現。**Pilot 樣本下此方向若出現，建議解讀為「警示訊號」而非確證；確認 G2 確實系統性地拖累人類判斷需要更大樣本與更多異常類型重複驗證。**

**情境 4：三 RQ 的效果量 95% bootstrap CI 均包含 0（無統計上顯著差異；最可能的結果）**
在 N = 4 / 組的 pilot 條件下，三 RQ 皆無法達到 effect size 顯著差異門檻。本研究的主要貢獻轉為：

- **(a) 框架可行性驗證**：證明完整 pipeline（從合成資料 → RAG → LLM 凍結 → UI → 受試者收資料）可端到端跑通；
- **(b) 效果量初值**：提供 Cliff's δ 與 Hedges' g 的點估計與 95% CI 給後續大樣本研究做 power analysis 與樣本數規劃；
- **(c) Pilot 級 null 訊號**：若效果量極小（δ 絕對值 < 0.11）且 95% CI 緊貼 0，可作為「AI 輸出格式對協作表現無顯著影響」的初步證據，呼應 Vaccaro et al. (2024) 的核心發現。

**重要免責聲明**：上述呼應力受限於 N = 4 / 組的 pilot 樣本量，**僅供後續研究參考，不構成對 Vaccaro 結論的確認或反駁**。

---

## 15. 限制與威脅

### 15.1 樣本量與分析模型

本研究每組僅 4 人（總 12 人），定位為 proof-of-concept / pilot study。此樣本量遠低於傳統大樣本檢定（N ≥ 30 / 組）的下限。受限於 4 個 cluster 估混合效應變異數會不穩定，本研究捨棄 mixed-effects logistic regression 與 GEE，亦不使用 Bayes Factor（prior 選擇對小樣本影響大），改以描述統計 + Cliff's δ + Hedges' g + 95% bootstrap CI 為主分析（§14.4）。只能偵測大效應；中小效應的 95% CI 必然跨 0，此時直接報效果量並接受結論。任何「顯著結果」皆需在後續大樣本研究中確認，本研究不主張決定性結論。

### 15.2 RAG 語料庫含異常訂單 — 隱式 few-shot 效應

466 筆 RAG 語料中包含約 60 筆異常訂單（76 總注入 − 16 被選入實驗集 − 0 被選入練習題）。這些異常訂單的 `purchase_note` 含有 Stage 2 注入的語義線索。LLM 在 retrieve 到這些異常訂單時，可能間接獲得「什麼是可疑的」隱式知識 — 等同於 implicit few-shot learning。

此效應的方向為正向（使 LLM 整體準確率偏好），但對「證據 vs. 結論」格式差異的影響方向不明確：若 G3 的證據格式更依賴 RAG 中的文字線索，則 G3 可能被 RAG 污染得相對更嚴重。本研究將此列為已知威脅，於 Chapter 4 LLM-only baseline 評估時謹慎詮釋絕對準確率，並在組間比較時聚焦於相對差異（差異本身對污染相對穩健，因為三組的 LLM 輸出均來自相同 RAG）。**本研究未進行事後污染程度量化（如實驗題與 RAG 檢索 top-5 結果的 cosine similarity 分析、或重複跑「無異常 RAG」對照組以隔離 few-shot 效應），列為後續工作。**

### 15.3 Base rate 外部效度

32 題實驗集的異常率 50% 顯著高於 500 筆母體的 15.2%（§9.1）。此 base rate shift 對組間比較內部效度無影響（三組看到相同題目），但限制結果推論至真實 base rate 情境的外部效度。實際採購系統部署時，受試者可能採用更保守的判斷標準，此推論需後續驗證研究確認。

### 15.4 PO-2024-0211 caveat（Block C2b 之 bank_account_change）

C2b 中的 `bank_account_change` 弱版（PO-2024-0211）依舊保留了 Stage 1 的 quantity 拉抬（使 total ≥ 2500 觸發 approver 階層變動）。雖然已是該類中 D² 最低的候選，其 D² 仍可能高於其他純文字類異常。本研究於 Chapter 4 將揭露此特定題目的 D² 百分位，避免讀者誤解 C2b「全部」為純文字訊號。

### 15.5 模型規模與單一 LLM 假設

本研究僅使用 Qwen3-8B（Ollama Q4 量化版）。更大的模型（如 Qwen3-72B、GPT-4 級別）可能產出更高品質的 G2 / G3 輸出，使結論不適用於更大模型。然而，選擇 8B 也有正面意義：(a) 接近實際企業可負擔本地部署的規模；(b) 開放權重確保研究者可逐位元 replicate。後續工作將擴大至多模型對照（不同規模、不同訓練語料）。

### 15.6 受試者背景

FYP 階段的受試者預期為 HKUST 工管 / 商科學生，非真實採購審計員。其判斷可能不反映職業審計員的決策模式。後續工作將招募具實際採購經驗的審計員作為驗證樣本。

### 15.7 Stage 2 PACE_HINTS 不對稱導致的文風洩漏（stylistic leakage）

Stage 2 用 DeepSeek 為每筆訂單生成 `purchase_note` 與 `supplier_profile` 時，**僅對異常訂單注入 PACE_HINTS**（例如「pricing seems higher than usual」、「supplier recently updated banking details」），對正常訂單僅給中性指令而無 hint。此設計意圖為將 ground-truth 異常類型轉化為文字線索，但副作用是異常訂單的 `purchase_note` 在語氣、用詞密度、句法緊張度上可能與正常訂單存在系統性差異 — 即所謂「文風洩漏」（stylistic leakage）。

**實務後果**：受試者（特別是英語敏感度高者）可能透過文風差異而非內容判斷異常，使 `text_dominant` 子集的 G3 vs. G2 對比夾雜「LLM 是否寫得夠中性」的混淆變數。

**為何不重跑 Stage 2**：500 筆訂單重新呼叫 DeepSeek API 成本過高（時間與 quota），且重新生成會破壞 v1 frozen output 的可重現性。本研究將此列為已知威脅，於 Chapter 4 結果詮釋時注意 — 若 G3 在 text_dominant 子集上顯著優於 G2，需考慮文風線索是否為部分原因。後續工作建議：(a) 對所有訂單使用對稱 prompt（hint 注入無論異常與否）、(b) 用第二個 LLM 對 purchase_note 做 paraphrase 改寫使三組輸入文風均勻。

### 15.8 G2 reason 長度作為隱式 confidence signal

對 v1 凍結的 32 題 G2 輸出進行長度統計：

- `suspicious` 類 (n=30)：平均 24.7w / 中位 23.5w / 範圍 [18, 40]
- `normal` 類 (n=2)：平均 19.5w / 中位 19.5w / 範圍 [18, 21]

兩類存在約 5w 系統性長度差異。雖然兩類最短皆為 18w（範圍下界重疊），但若受試者在 32 題中累積經驗，可能將「reason 長 → AI 在強調可疑點 → AI 信心高」、「reason 短 → AI 在敷衍正常結論 → AI 信心低」這類隱式 confidence signal 內化進判斷。此違反 §3.1 設計原則「不向受試者暴露 AI confidence 量化資訊」。

**為何不重跑 G2**：(a) 重跑將打破已凍結的 32 題 G2 輸出；(b) 87.5% FPR 是有意保留的論文發現（§10.4），重跑可能改變 verdict 分布；(c) `normal` 樣本只有 2 筆，統計力不足以穩健推論該長度差異是否為系統現象 — 也許其實是隨機 noise。本研究將此列為已知威脅。

**v2 G3 防範同類問題**：v2 G3 prompt 引入硬性長度約束 — 每條 `why_noteworthy` 限 5–25 words（§10.5.3），由 `validate_g3()` 檢查，使 4 條觀察視覺均勻，從源頭杜絕 G3 也出現此類洩漏。

### 15.9 Section E 自然語言句子的方向性措辭

Section E 自然語言句子使用如「Unit price $8.90 vs SKU historical median $2.80 → 3.2× higher」等措辭。「higher」 / 「lower」 / 「longer」帶有方向暗示，但本身並未斷定該偏離方向是「異常」（高價可能是急單溢價、premium 規格、合理採購）。三組受試者（G1 / G2 / G3）共同接收 Section E 顯示，此措辭差異對 between-group 比較的內部效度無影響。但對 Section E 在「協助人類解讀」上的解釋力，應考慮此措辭可能輕微抬升受試者對偏離特徵的疑慮警覺度。

**處理方案**：列為 nice-to-have，不立即重新生成 Section E。後續版本可改用方向中性的純比例描述（如 `Unit price $8.90 vs median $2.80 (ratio: 3.18)` 不加 higher / lower 標籤），由受試者自行判斷該比率代表什麼意義。

### 15.10 RAG top-K = 5 未經系統優化

凍結 LLM 輸出時，`build_rag.py` 與 `freeze_llm_outputs.py` 統一使用 RAG top-K = 5（檢索 5 筆最相似歷史訂單作為 LLM 輸入上下文）。此 K 值為直觀經驗值，未經系統測試：

- **K 過小**（例如 K = 1–2）：LLM 缺乏足夠歷史比較基準，可能偏向僅依賴 SKU 市場參考值或先驗判斷。
- **K 過大**（例如 K = 10）：top-10 中可能含更多異常訂單（RAG 語料中的 60 筆異常，§15.2），間接放大隱式 few-shot 效應。

**為何不立即優化**：選定不同 K 值將需要重跑全部 32 題 G2 + G3，每次需 30–60 分鐘，且對結論方向的影響不明（K 對 LLM 判斷的敏感性本身就是一個未知數）。本研究固定 K = 5 作為中庸選擇並列為已知威脅。後續工作建議：對 K ∈ {3, 5, 7, 10} 各跑一遍實驗，比較 LLM accuracy / FPR / 證據品質的變化曲線，作為 RAG 設計的方法論貢獻。

---

## 16. 參考文獻

```
Association of Certified Fraud Examiners (2024). Occupational Fraud 2024:
   A Report to the Nations. Austin, TX: ACFE.

Bansal, G., Wu, T., Zhou, J., Fok, R., Nushi, B., Kamar, E., Ribeiro, M. T.,
   & Weld, D. S. (2021). Does the whole exceed its parts? The effect of AI
   explanations on complementary team performance. CHI '21, 1–16.

Cohen, J. (1988). Statistical Power Analysis for the Behavioral Sciences,
   2nd ed. Lawrence Erlbaum Associates.

IJFMR (2025). Whistle-blower Mechanisms in Operational Departments.
   International Journal of Financial Management Research.

Jian, J.-Y., Bisantz, A. M., & Drury, C. G. (2000). Foundations for an
   empirically determined scale of trust in automated systems.
   International Journal of Cognitive Ergonomics, 4(1), 53–71.

Romano, J., Kromrey, J. D., Coraggio, J., & Skowronek, J. (2006).
   Appropriate statistics for ordinal level data: Should we really be using
   t-test and Cohen's d for evaluating group differences on the NSSE and
   other surveys? Annual meeting of the Florida Association of
   Institutional Research, 1–33.

Silver, E. A., Pyke, D. F., & Peterson, R. (2017). Inventory and Production
   Management in Supply Chains, 3rd ed. CRC Press, ch. 7.

Vaccaro, M., Almaatouq, A., & Malone, T. (2024). When combinations of
   humans and AI are useful: A systematic review and meta-analysis.
   Nature Human Behaviour, 8(12), 2293–2303.

Westerski, A., Kanagasabai, R., Shaham, E., Narayanan, A., Wong, J., &
   Singh, M. (2021). Explainable anomaly detection for procurement fraud
   identification — lessons from practical deployments. International
   Transactions in Operational Research, 28(6), 3276–3302.
   Preprint: http://www.adamwesterski.com/files/publications/itor2021/
   explainable_procurement_itor2021_preprint.pdf

Mouser Electronics Search API v1, `search/partnumber` endpoint,
   `partSearchOptions="exact"`.
```
