# 第三章：研究方法

> **論文架構說明**：本文件僅涵蓋第三章（研究方法）。
> - 第四章（研究結果）：數據收集完成後，呈現準確率、效果量、AI 覆蓋率（AOR）及信任量表結果。
> - 第五章（討論與結論）：對照 RQ1–RQ3 詮釋研究發現，說明研究限制，並提出未來研究方向。
> - 附錄 A–E 附於本文件末尾。

**研究題目**：Evidence vs. Conclusion — How LLM Output Format Shapes Human-AI Collaboration in Procurement Anomaly Auditing

**最後更新**：2026-04-27 ｜ **引用格式**：APA 第七版

---

## 目錄

- [3.1 研究設計概覽](#31-研究設計概覽)
- [3.2 資料集建構](#32-資料集建構)
  - [3.2.1 選用合成資料的理由](#321-選用合成資料的理由)
  - [3.2.2 Stage 1 — 蒙地卡羅基礎資料集](#322-stage-1--蒙地卡羅基礎資料集)
  - [3.2.3 Stage 2 — 語義欄位生成](#323-stage-2--語義欄位生成)
  - [3.2.4 Stage 3 — 異常注入與 Ground Truth 定義](#324-stage-3--異常注入與-ground-truth-定義)
  - [3.2.5 Stage 3 — 實驗集分層抽樣](#325-stage-3--實驗集分層抽樣)
  - [資料集建構的限制](#資料集建構的限制)
- [3.3 AI 工具建構（Stage 4）](#33-ai-工具建構stage-4)
  - [3.3.1 RAG 語料庫](#331-rag-語料庫)
  - [3.3.2 凍結 LLM 輸出](#332-凍結-llm-輸出)
  - [3.3.3 設計理由 — 為何刻意保持 AI 工具簡單](#333-設計理由--為何刻意保持-ai-工具簡單)
  - [Stage 4 的限制](#stage-4-的限制)
- [3.4 實驗設計](#34-實驗設計)
  - [3.4.1 三組受試者間設計](#341-三組受試者間設計)
  - [3.4.2 受試者說明手冊架構](#342-受試者說明手冊架構)
  - [3.4.3 各組的資訊架構](#343-各組的資訊架構)
  - [3.4.4 Web Application 與資料收集](#344-web-application-與資料收集)
  - [3.4.5 信任量表工具](#345-信任量表工具)
  - [實驗設計的限制](#實驗設計的限制)
- [3.5 計算基準線 — LLM 合成受試者模擬](#35-計算基準線--llm-合成受試者模擬)
  - [3.5.1 設計目的](#351-設計目的)
  - [3.5.2 兩層 LLM 架構](#352-兩層-llm-架構)
  - [3.5.3 資訊不對稱設計](#353-資訊不對稱設計)
  - [3.5.4 模擬設定](#354-模擬設定)
  - [LLM 模擬的限制](#llm-模擬的限制)
- [3.6 分析計畫](#36-分析計畫)
- [3.7 預期審查問題 Q&A](#37-預期審查問題-qa)
- [附錄 A — 數學定義](#附錄-a--數學定義)
- [附錄 B — LLM 系統提示全文](#附錄-b--llm-系統提示全文)
- [附錄 C — 參數表](#附錄-c--參數表)
- [附錄 D — 信任量表題目](#附錄-d--信任量表題目)
- [附錄 E — 關鍵程式碼清單](#附錄-e--關鍵程式碼清單)

---

## 3.1 研究設計概覽

本研究探討 AI 生成輸出的**格式**如何影響採購異常稽核中的人類決策——在這一情境中，稽核人員愈來愈常接觸 AI 輔助工具，但呈現 AI **裁決**（verdict）與呈現原始 AI **證據**（evidence）對下游決策的差異影響，目前仍缺乏充分研究。

本研究由三個研究問題（RQ）引導：

- **RQ1**：相較於呈現帶有單句說明的二元結論，或完全無 AI 輔助，將 LLM 輸出呈現為結構化證據（四條不含裁決的事實觀察），是否能提升人類的異常偵測準確率？
- **RQ2**：AI 輸出格式的效應，在可透過數值偏差偵測的異常與只能透過文字語義偵測的異常之間，是否有所差異？
- **RQ3**：當 LLM 產生錯誤輸出時，「證據格式」是否比「結論格式」更能讓受試者有效覆蓋（override）AI 的錯誤？

研究方法由五個相互連結的組成部分構成（圖 3.1）：

```
Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5（人類實驗）
蒙地卡羅  語義欄位   異常注入   AI 工具   Web app + 12 名受試者
資料集    （DeepSeek）（PACE）   凍結輸出  ────────────────────
                                         Stage 16：LLM 模擬
                                         （計算基準線）
```

**圖 3.1.** 從原始資料生成至實驗執行的五階段管線。

選用合成資料集而非真實採購記錄的原因詳見第 3.2.1 節。所有實驗刺激材料——受試者所判斷的訂單、AI 裁決、AI 證據表——均在受試者招募前即已凍結，確保每位受試者（無論是真人或 LLM 模擬代理）在相同條件下面對**完全相同**的刺激材料。

---

## 3.2 資料集建構

### 3.2.1 選用合成資料的理由

使用真實採購記錄會為本實驗設計帶來三個無法解決的問題。第一，真實記錄缺乏可驗證的 ground truth：實際舞弊案件在法律上和稽核上幾乎無法以確定無疑的方式確認。第二，基於商業機密，真實記錄無法公開分享以供重現驗證。第三，將受控異常樣態注入真實記錄，可能會干擾既有的合法稽核軌跡。

合成資料集同時解決上述三個問題：(a) ground truth 在定義上是精確的，因為異常是以程式碼方式注入；(b) 資料集可隨論文公開發布；(c) 異常頻率、類型分佈與訊號強度均可依實驗需求精確設定。

「合成資料可能無法反映真實採購行為」的效度疑慮，部分已透過以下方式緩解：將價格與交貨期分佈錨定於 Mouser Electronics 公開 API 的真實市場資料（見第 3.2.2 節），以及透過商業級 LLM 生成符合情境的自由文字說明（第 3.2.3 節）。剩餘的外部效度差距在第 3.2.5 節及限制節中明確說明。

### 3.2.2 Stage 1 — 蒙地卡羅基礎資料集

**情境設定。** 資料集代表 ABC Electronics Ltd.，一家虛構的香港 30 人 IoT 硬體新創，為內部研發採購電子零件。此情境設計得足夠真實，使目標受試族群（商科學生）能以常識進行判斷，同時足夠簡單，不需要採購專業知識。

**實體設定。** 資料集涉及三類行為者：

- **請購人（Requesters）**：10 名工程師（R-ENG-01 至 R-ENG-10），各自具有反映真實工作量集中度的權重（前三名工程師約占所有訂單的 50%）。
- **核准人（Approvers）**：四個授權層級——A-PROC-01/02（例行訂單，≤ USD 1,000）、A-CTO（USD 1,000–5,000）、A-CEO（> USD 5,000）——反映小型公司典型的門檻制核准結構。
- **供應商（Suppliers）**：25 家常規供應商（S-001 至 S-025）與一個異常供應商池（S-026 至 S-030，共 5 家）。每位請購人的供應商選擇遵循 Markov 式偏好圖：每位請購人有一個主要供應商（機率約 0.65）、一個次要供應商（機率約 0.25），以及使用其他任何供應商的小機率。

**訂單生成。** 使用以下隨機過程生成 2024 年全年共 500 筆訂單（完整數學定義見附錄 A）：

- **訂單日期**：遵循 Poisson 到達過程，速率 λ = 500/366 ≈ 1.37 筆/天。
- **數量與單價**：從以 Mouser API 真實價格資料為錨點的對數常態分佈中抽取，涵蓋 10 種代表性電子 SKU（BME280、ESP32、STM32 等）。選用對數常態分佈而非常態分佈，是因為採購數量與價格嚴格為正且呈右偏。
- **核准延遲（Approval lag）**：遵循截斷常態分佈（μ = 2.0 天，σ = 1.5，截斷至 [0.1, 14.0]），以防止自然右尾值與注入的異常樣態重疊。
- **交貨前置時間**：使用以 Mouser 標示交貨期範圍為錨點的 SKU 專屬截斷常態分佈。

整個生成過程以 `RANDOM_SEED = 42` 為種子，可從公開代碼完整重現。

**關鍵設計選擇 — Mouser API 錨定。** 價格中位數與標準差來自 2026 年 4 月查詢的真實 Mouser 產品上架資料，而非憑直覺虛構，使資料集的數值合理性有所依據，且無需取得私有採購記錄。10 個選定的 SKU 代表與 IoT 公司相關的感測器、微控制器與連接模組的真實組合（見附錄 C，表 C.1）。

### 3.2.3 Stage 2 — 語義欄位生成

Stage 1 產出的是數值上一致的資料集，但真實採購訂單包含自由文字欄位——採購說明備註與供應商描述——這些欄位承載了數值欄位無法捕捉的定性訊號。Stage 2 使用 DeepSeek（一個有別於分析模型 Qwen3-8B 的商業級 LLM）為全部 500 筆訂單生成這些欄位。

對於異常訂單，DeepSeek 接收對應異常類型的 PACE 提示（例如，對於價格膨脹異常：「pricing seems higher than usual」；對於銀行帳戶變更異常：「supplier recently updated banking details」）。對於正常訂單，僅提供通用指令。此設計將程式化的異常類型轉化為受試者必須詮釋的自然語言訊號，彌合了資料集的數學結構與真實稽核文字之間的差距。

**為何在 Stage 2 使用不同模型？** 若 Stage 2（文字生成）與 Stage 4（AI 裁決/證據生成）使用相同模型（Qwen3-8B），Stage 4 的 AI 可能只是對自己的 Stage 2 輸出進行樣態比對，而非真正對訂單進行推理，造成自我確認偏誤。因此刻意選用 DeepSeek 以打破此依賴關係。

**限制 — 文風洩漏（stylistic leakage）。** 由於 PACE 提示僅提供給異常訂單，異常訂單的自由文字欄位可能在文字風格上（措辭密度較高、使用較多保留語氣）與正常訂單存在系統性差異。此文風洩漏是影響效度的已知威脅，對主要訊號為文字的異常類型（`conflict_of_interest` 與 `bank_account_change`）尤為明顯，詳見限制節進一步討論。

### 3.2.4 Stage 3 — 異常注入與 Ground Truth 定義

**八類異常類型。** 依據 PACE 採購舞弊分類法（Westerski et al., 2021），八類異常被注入 500 筆訂單中的 76 筆（基礎異常率 15.2%）。每個類型對應一個應用於一個或多個訂單欄位的精確突變合約（exact mutation contract）（完整公式見附錄 A，表 A.1）：

| 異常類型 | 主要訊號管道 | 注入目標 |
|---|---|---|
| `item_spending` | 數值 | 單價 ×2.5–4.0 |
| `border_value` | 數值 | 總金額剛好低於 USD 1,000 或 5,000 |
| `unusual_vendor` | 數值 + 文字 | 供應商來自異常池（S-026–030） |
| `vendor_spending` | 數值 | 過度集中於單一供應商的消費 |
| `approval_bypass` | 數值 | 異常快速或緩慢的核准延遲 |
| `quote_manipulation` | 文字 | 採購備註暗示接受單一報價 |
| `bank_account_change` | 文字 | 供應商描述提及付款資訊更新 |
| `conflict_of_interest` | 文字 | 供應商描述暗示與請購人有私人關係 |

前四類異常歸類為**數值主導型**（主要從數量欄位偵測）；後四類歸類為**文字主導型**（主要從自由文字內容偵測）。此區分支撐 RQ2 的分析。

**Ground truth 作為程式化的「世界真相」。** 本設計的關鍵特徵是：ground truth 並非由人工標注——它由 `generate_dataset.py` 中的突變合約**定義**。欄位 `injection_plan` 記錄應用於每筆訂單的確切異常類型（正常訂單為 `"none"`）。這意味著：

- Ground truth 明確且可重現：以相同種子重新執行 `generate_dataset.py` 會產生完全相同的標籤。
- Ground truth 與任何偵測演算法完全解耦：Stage 3 在不知曉 `injection_plan` 的情況下計算 Mahalanobis 距離與偏差比率，避免循環評估。
- 受試者（無論是真人或 LLM 模擬）永遠看不到 `injection_plan` 欄位——它只存在於研究者的答案鍵（KEY 檔）中，僅用於評分。

Ground truth 的三個表示層次：

1. **二元標籤**：若 `injection_plan ≠ "none"` 則 y = 1，用於計算準確率、F1、精確率、召回率。
2. **多類別標籤**：八個異常類型名稱加上 `"none"`，用於逐類召回率分析。
3. **突變合約**：`apply_anomaly()` 中的精確欄位變換，可核實每個注入值。

### 3.2.5 Stage 3 — 實驗集分層抽樣

從 500 筆母體中選出 32 題作為實驗集、2 題作為練習題，剩餘 466 筆作為 Stage 4 的 RAG 語料庫。

**分層抽樣。** 先依據 ground truth 與 Mahalanobis 距離將訂單分配至各層，再分配至四個區塊（Blocks）：

| 區塊 | 內容 | 數量 |
|---|---|---|
| A | Mahalanobis 距離低的正常訂單（明顯例行） | 10 |
| B | 數值偏差明確訊號異常的訂單 | 8 |
| C2a | 文字訊號主導的異常訂單 | 3 |
| C2b | 同時具有數值與文字訊號的異常訂單 | 5 |
| C1 | Mahalanobis 距離高的正常訂單（統計上看起來可疑） | 6 |

共得到 16 筆異常與 16 筆正常訂單——實驗集異常率 50%，較母體的 15.2% 刻意提升。提升的原因是：在小樣本的情況下，必須提供足夠的異常題目，才能支撐逐類與逐訊號類型的子集分析。此設定對外部效度的影響（受試者可能感知到比真實情況更高的舞弊率）在第 3.4 節及限制節中討論。

**Section E 偏差句。** 對 32 道實驗題中的每一道，預先計算八個偏差特徵（單價比率、數量比率、交貨延遲 z 分數、核准延遲 z 分數、門檻差距等），並以自然語言句子格式呈現給所有受試者，顯示於「Section E」面板。這些句子被設計為提供有參考價值但非決定性的訊號——僅報告**哪裡不尋常**，而非**為何是舞弊**。關鍵在於，Stage 4 的 LLM AI 工具**不接收**這些預先計算的比率；它必須從原始訂單欄位加上 RAG 檢索的歷史訂單自行推導出等效推理。

---

### 資料集建構的限制

**L1 — 合成資料的外部效度。** 資料集重現了真實採購的統計特性（對數常態價格、Poisson 到達、核准門檻），但無法捕捉組織特有的行為樣態（如季末採購衝刺、特定供應商協議）。研究結果應在此模擬情境下詮釋為概念驗證，而非對任何真實採購系統的預測。

**L2 — 提升的實驗異常率。** 32 題中 50% 的異常率遠超真實舞弊率（ACFE 估計每年約 5% 的組織營收損失於舞弊，意味著每筆交易的異常率遠低於此）。頻繁接觸異常的受試者可能發展出在真實稽核情境中不存在的過度懷疑校準。此差異影響絕對準確率數值，但不影響組間比較，因為三組面對完全相同的題目集。

**L3 — PACE 提示導致的文風洩漏。** 異常訂單的自由文字欄位可能因 Stage 2 的非對稱提示注入而呈現不同的語言風格。這可能誇大文字主導型異常的偵測準確率，並混淆 RQ2 的子集分析結果。第 3.6 節在詮釋子集分析時將說明此威脅。

---

## 3.3 AI 工具建構（Stage 4）

Stage 4 生成第 2 組與第 3 組將接收的 AI 輸出，作為實驗刺激材料。這些輸出**一次性生成**，在任何受試者完成實驗前即已凍結：第 2 組或第 3 組的每位受試者，無論何時參與，都會看到每道訂單**完全相同**的 AI 輸出。

### 3.3.1 RAG 語料庫

為使 AI 對公司歷史訂單樣態有情境基礎，從未被選入實驗集的 466 筆訂單建立一個檢索增強生成（Retrieval-Augmented Generation，RAG）管線。這些訂單使用 `nomic-embed-text`（768 維向量）透過本機 Ollama 進行嵌入，並儲存於 ChromaDB 持久向量資料庫。

處理每道實驗訂單時，透過餘弦相似度檢索最相似的前 5 筆歷史訂單，附加至 LLM 提示作為參考情境。這使 AI 能以公司實際歷史樣態作為比較基準，而非依賴通用的外部知識。

**防止資訊洩漏。** RAG 語料庫在匯入前進行嚴格的洩漏檢查：24 個敏感欄位名稱（ground truth 標籤、Mahalanobis 分數、z 分數、比率、分層指定）被列為黑名單。若 metadata 中出現任何敏感欄位，建構管線即中止。這確保 AI 無法透過檢索途徑取得 ground truth、預先計算的異常訊號或實驗設計資訊。

**RAG 語料庫包含異常訂單。** 466 筆語料庫訂單中約 16.3% 為異常訂單（76 筆異常訂單分布於實驗集、練習集與語料庫中）。這反映真實世界的狀況：實際歷史檔案中含有未被偵測的舞弊。刻意排除異常訂單以建立「乾淨」語料庫雖能提升實驗純度，但會降低生態效度——真實 AI 系統從含有歷史舞弊的真實檔案中進行檢索。相關影響在第 3.3.3 節及限制 L6 中討論。

### 3.3.2 凍結 LLM 輸出

**模型選擇。** 選用 Qwen3-8B 的原因如下：(a) 支援足夠長的上下文視窗（16,384 tokens），可容納系統提示、一張訂單卡與五份 RAG 文件；(b) 可透過 Ollama 在本機部署，確保可重現性且不依賴外部 API；(c) 相較於同規模替代方案，在公開基準測試中達到具競爭力的指令遵循與 JSON schema 遵從表現。

**輸出類型。** 為 34 道題目（32 實驗題 + 2 練習題）生成兩種輸出格式：

- **G2 裁決**（`g2_verdicts_exp_*.json`）：JSON 物件 `{"judgment": "suspicious"|"normal", "reason": "<一句說明>"}`。LLM 透過提示指令與生成後禁詞檢查，被明確禁止產生機率估計、信心分數或框架名稱（如「PACE」、「Mahalanobis」）。

- **G3 證據**（`g3_evidence_exp_*.json`）：包含恰好四條「noteworthy features」的 JSON 物件，每條有四個子欄位：`feature`、`current_value`、`reference_value`、`why_noteworthy`。關鍵設計是：`why_noteworthy` 欄位限制在 5–25 字，以防止文字長度形成隱性信心訊號（讀者可能將較長的說明解讀為較高的 AI 信心——見第 3.4.5 節）。特徵可以是偏差**或**確認觀察。

**確定性。** 兩種輸出類型均以 `temperature = 0.0` 生成，確保以相同 Qwen3-8B 模型版本重新執行凍結腳本時產生完全相同的輸出。模型雜湊值（`500a1f067a9f`）已記錄以供精確重現。

**Thinking mode。** Qwen3-8B 具備推理鏈能力，會在答案 JSON 前產生 `<think>...</think>` 區塊。推理過程在推論時保留（停用會使輸出品質降至約 4B 參數水準），並在後處理時以正則表達式剝除，僅保留最終 JSON 物件。Token 預算（`num_predict = 12,288`）設置寬鬆，確保推理鏈不截斷答案 JSON。

### 3.3.3 設計理由 — 校準知識 vs 預先計算數值

Stage 4 AI 工具的輸入經過刻意切割，區分兩類資訊：

**AI 接收的資訊：**

- 原始訂單欄位與自由文字備註；
- RAG 檢索的 top-5 相似歷史訂單；
- SKU 市場參考值（Mouser 公開資料：價格中位數、數量中位數、交貨期中位數）；
- **校準情境**（calibration context）——亦即「**判斷標準**」而非「答案」：常規供應商範圍（S-001–025）、三層核准門檻（< $1,000 / $1,000–5,000 / > $5,000）、以及「多數訂單為例行性，單一弱訊號通常可解釋；判定可疑需多個獨立紅旗或一個極端偏差」此一判斷準則。校準情境的全文見附錄 B.1。

**AI 不接收的資訊：**

- 預先計算的 Section E 偏差句（單價比率、z 分數、門檻距離等量化指標）；
- 說明手冊中**以名稱列出的** 8 大舞弊樣態目錄（PACE 分類法的具名清單）。

此切割的核心邏輯是：**校準知識（判斷準則）等同於受試者透過說明手冊獲得的內容，而預先計算的 Section E 數值與 PACE 樣態目錄則是受試者額外擁有的工具**。這樣設計基於三個理由：

1. **公平的判斷起點。** 為人類受試者提供說明手冊（包含「多數訂單為例行性、單一弱訊號通常可解釋」等校準語句），卻不為 AI 提供等價的判斷準則，將使 AI 在缺乏「正常基線」的情況下傾向把任何偏差都標記為可疑。本研究的目標是比較 AI 輸出**格式**（結論 vs 證據）對人類決策的影響，而非觀察「未校準的 AI」與人類的差距。為 AI 提供與人類相同的校準框架，確保 G2 條件下的 AI 裁決品質不會單純因「缺乏判斷標準」而異常偏向 suspicious，使格式效應的測量更純粹。

2. **保留可量化的不對稱。** 仍然存在的不對稱集中於兩處：(a) 預先計算的 Section E 數值（如「單價為 SKU 中位數的 3.2 倍」）只給人類看，AI 必須從原始欄位 + RAG 自行推導；(b) 8 大舞弊樣態的具名目錄（如「Bank-account-change」、「Quote-manipulation」）只給人類，AI 沒有這份模式表單。這兩項代表「人類稽核員仍擁有 AI 缺乏的領域工具」，反映了真實人機協作中的常見落差。

3. **跨組對稱。** AI 的知識切割對 G2 與 G3 完全相同。兩組受試者面對的是同一份 frozen JSON 輸出，差異僅來自呈現格式（裁決 vs 四項觀察）。受試者在其組別專屬說明頁中被明確告知 AI 接收與不接收的資訊範圍，使信任校準有依據。

### Stage 4 的限制

**L4 — RAG top-k 未經系統性最佳化。** k = 5 依慣例選定，未進行 k ∈ {3, 5, 10} 的消融實驗。AI 的準確率與 G3 證據特徵的品質可能隨 k 值變化。

**L5 — 單一模型、單一規模。** 結果反映 Qwen3-8B 的特定能力。更大的模型（如 Qwen3-72B、GPT-4o）可能產生更高品質的 G2 裁決與 G3 特徵，進而放大或削弱實驗中觀察到的格式效應。

**L6 — RAG 語料庫含異常訂單（隱性 few-shot）。** 如第 3.3.1 節所述，466 筆語料庫包含約 76 筆無標籤異常訂單。若檢索到的歷史訂單恰好含有與當前查詢相同的異常類型，AI 可能低估該樣態的不尋常程度（隱性正規化）。然而，異常濃度低（約 16%）、各異常類型注入不同欄位（降低共同檢索機率），且效應對 G2 和 G3 對稱。此問題作為已知且已記錄的設計取捨處理，而非設計缺陷。

---

## 3.4 實驗設計

### 3.4.1 三組受試者間設計

使用預先生成的平衡分配佇列（每組 4 名受試者，共 12 名），將受試者隨機分配至三個條件之一：

| 組別 | AI 輔助類型 | AI 輸出格式 |
|---|---|---|
| G1 — 控制組 | 無（僅 Section E 統計偏差句） | — |
| G2 — 結論格式 | 二元裁決 + 一句說明 | `Suspicious / Normal — <reason>` |
| G3 — 證據格式 | 四條結構化觀察，不含整體裁決 | Feature / Current value / Reference / Why noteworthy（表格，無裁決） |

本研究採**受試者間設計**（between-subjects design）：每位受試者僅接受一種條件。此設計防止受試者內學習效應（例如，先體驗 G3 的受試者在接觸 G2 時可能有不同的應對方式）。代價是相較於受試者內設計，統計效能有所降低，詳見第 3.6 節說明。

每道題目，受試者提交兩項回應：(a) 二元判斷（Normal / Suspicious），以及 (b) 信心評分，採 7 點李克特量表（1 = 完全不確定，7 = 非常確定）。

### 3.4.2 受試者說明手冊架構

所有受試者在開始前均閱讀一份共同說明手冊，接著閱讀一份群組專屬頁面。共同說明手冊涵蓋：

- 公司情境（ABC Electronics，30 人 IoT 新創）；
- 本研究中「正常」與「可疑」的定義；
- 供應商慣例（S-001–025 為常規供應商；其他為較新或一次性供應商，可能合法但值得注意）；
- 核准人角色代碼與授權門檻；
- 八大常見舞弊樣態說明（不揭露實驗中出現哪些樣態）；
- 各節說明（Section A = 訂單事實，Section B = 自由文字備註，Section E = 偏差句）；
- 程序說明（每題 45–75 秒，不可返回，不可暫停）。

**關鍵設計選擇 — 說明手冊不洩漏 ground truth。** 說明手冊揭露八大舞弊樣態的存在與供應商慣例，但刻意避免透露確切基礎率或哪些訂單是異常的。受試者知道**某些**訂單是可疑的，但不知道有多少筆。

### 3.4.3 各組的資訊架構

閱讀共同說明後，每組接收一份群組專屬頁面：

**G1** 被告知每道訂單將看到 Section A、B 與 E，且無 AI 輔助。其信任量表聚焦於 Section E 偏差句。

**G2** 被告知額外會看到「AI Verdict」面板。關鍵設計是，明確告知受試者：AI 接收了訂單欄位、自由文字備註、相似的歷史訂單，以及與您相同的**判斷準則**（常規供應商範圍、核准門檻層級、「多數訂單為例行性、單一弱訊號通常可解釋」等校準語句），但 AI **沒有**獲得 Section E 預先計算的偏差數值，**也沒有**獲得 8 大舞弊樣態的具名目錄。此揭露讓 G2 受試者了解 AI 的工具差距，能依此校準對 AI 結論的信任度。

**G3** 接收等效揭露：AI 接收了相同的判斷準則，但沒有 Section E 數值與舞弊樣態目錄。告知受試者 AI 提供四條觀察（偏差或確認觀察），不含整體裁決，且綜合判斷是受試者的責任。

### 3.4.4 Web Application 與資料收集

實驗透過部署於 Streamlit Community Cloud 的 Streamlit 網頁應用程式進行。應用程式：

- 透過預先填寫的 Google Sheets 佇列（平衡、以 `seed = 42` 隨機排列）自動將受試者分配至各組；
- 處理 session 持久性：以相同姓名重新連線的受試者會被導回其已分配的組別；
- 以固定一致的版面呈現訂單各節及 AI 面板（G2/G3）；
- 點擊「Submit」後立即且不可撤銷地將每項回應寫入 Google Sheets；
- 2 道練習題熱身後，顯示練習題回饋（正確/錯誤，G2 另顯示 AI 是否正確）；
- 32 道正式題目期間不提供回饋。

所有回應——包括組別分配、題目順序、判斷、信心評分及提交時間戳——均儲存於僅研究者可存取的私人 Google Sheet。

### 3.4.5 信任量表工具

完成 32 道正式題目後，所有受試者均填寫一份 5 題的實驗後問卷。為維持建構效度，各組使用不同的量表：

- **G2** 填寫標準 AI 信任量表（改編自 Jian et al., 2000），衡量其使用 AI 裁決面板的體驗（如「AI 裁決在此任務中整體上是可靠的」、「在 AI 建議與我的初步判斷不同時，我感到樂意遵循 AI 的建議」）。
- **G3** 填寫平行量表，衡量其使用 AI 證據面板的體驗（如「AI 觀察協助我做出決定」、「AI 的四條觀察提供了足夠資訊讓我做出有信心的決策」）。
- **G1** 填寫結構上平行的量表，聚焦於 Section E 偏差句，使第二層比較（G1 對統計輸入的依賴 vs G2/G3 對 AI 輸入的依賴）成為可能，同時確保 12 名受試者均有完整的實驗後記錄。

G1 量表是刻意的適應版，而非標準化量表。跨組問卷分數的比較僅限於結構性指標（如整體依賴傾向），且明確不可詮釋為測量三組相同的潛在構念。此限制在限制 L9 中說明。

---

### 實驗設計的限制

**L7 — 小樣本（N = 12）。** 每組僅 4 名受試者，本研究定位為概念驗證先導研究，而非驗證性研究。分析計畫使用效果量估計（Cliff's δ、Hedges' g）配合 95% 拔靴法信賴區間（bootstrap CI），明確迴避虛無假設顯著性檢定（NHST）。研究結果的呈現方式為「提示方向與規模」，而非「統計上已證實」。

**L8 — 學生樣本。** 受試者為 HKUST 商科/工程學生，而非職業稽核人員。其決策行為在風險門檻、領域知識與信任校準方面可能與訓練有素的稽核實務人員不同。研究發現不應在未經進一步驗證的情況下推論至職業稽核情境。

**L9 — 跨組信任量表非等效。** G1 量表是平行改編版，並非衡量與 G2/G3 AI 信任量表相同構念的驗證化量表。跨組問卷分數的第二層比較帶有詮釋限制，已在分析計畫中說明。

---

## 3.5 計算基準線 — LLM 合成受試者模擬

### 3.5.1 設計目的

在招募真人受試者的同時，另行建構計算基準線：使用 Qwen3-8B 作為合成受試者模擬三種實驗條件。此設計的三個目的如下：

**(a) 提供理性代理人參照。** 一個不受認知偏誤（錨定效應、疲勞、注意力分散）影響的 LLM 代理，建立了「一個在相同資訊條件下的決策代理理論上能達到什麼水準」的上界。若 G3 真人受試者的表現低於 LLM G3 代理，這暗示的是認知負荷或資訊處理限制，而非格式設計問題。

**(b) 量化自動化偏誤潛力。** LLM 在 G2 條件下的 AI 一致率（LLM 作為受試者同意 Stage 4 AI 裁決的頻率）相較於 G3，提供了純粹由格式驅動的錨定效應的基準估計，不受人類心理因素污染。

**(c) 先導可重現性。** 僅 12 名真人受試者的情況下，模擬結果提供可重現的補充，使效果量估計得以與更大的合成樣本進行交叉核對。

此模擬明確定位為依循 Park et al.（2024）的**人口統計描述等級基準（demographic-only baseline）**。LLM persona 由一句人口統計描述構成（「You are a university business student with no prior procurement or auditing experience」）——相當於 Park et al.（2024）發現可達完整訪談版代理約 74% 重測一致性的等級。本研究不主張 LLM 代理可替代真人受試者。

### 3.5.2 兩層 LLM 架構

一個關鍵的架構區分將本研究中兩個 LLM 角色分離：

**Layer 1 — AI 工具（Stage 4，凍結）。** LLM **一次性**生成 G2 裁決與 G3 證據，在任何受試者開始前即完成。它作為實驗刺激材料——自變項——永不更新或重新執行。其提示設計用於產生具資訊性的稽核輸出；它對受試者說明手冊毫不知情。

**Layer 2 — 合成受試者（Stage 16）。** **第二個**、獨立的 LLM 呼叫（使用相同的 Qwen3-8B 模型，但完全不同的系統提示）模擬受試者的決策。此呼叫讀取完整受試者說明手冊、訂單資料，以及（G2/G3 條件下）凍結的 Layer 1 輸出，然後產生判斷、信心分數與一句推理說明。

兩層永遠不在同一次呼叫或 session 中執行。Layer 1 輸出是靜態的 JSON 檔案。Layer 2 讀取這些檔案的方式，恰如真人受試者在 webapp 上查看 AI 面板。這種乾淨的分離確保合成受試者實驗不會污染凍結的 AI 刺激材料。

```
Layer 1（Stage 4）                  Layer 2（Stage 16）
─────────────────                  ──────────────────
System：「你是採購稽核 AI。          System：「你是一名[學生/稽核人員]。
  僅輸出 JSON。」                    以下是受試者說明手冊：
Input：訂單 + RAG top-5               [briefing_common + briefing_gN 全文]」
Output：裁決 / 4 條特徵             Input：訂單 + (G2/G3) 凍結 Layer 1 輸出
        ↓ 凍結 JSON ↓              Output：{judgment, confidence, reasoning}
                                          → 本機 CSV
```

### 3.5.3 資訊不對稱設計

完整說明手冊（共同段 + 組別專屬段）餵給 Layer 2（合成受試者）；Layer 1（AI 工具）則接收第 3.3.3 節描述的校準情境（判斷準則的精簡版），但不接收 Section E 預先計算的偏差數值與 8 大舞弊樣態的具名目錄。這與真人受試者所面對的不對稱相同：說明手冊向受試者完整揭露公司情境與工具支援，而 AI 工具僅獲得校準準則。由於 G1、G2 與 G3 的合成受試者均接收相同說明手冊，且 G2 與 G3 共用同一組 AI 凍結輸出，此不對稱在各條件間是對稱的——不影響組間比較。

### 3.5.4 模擬設定

| 參數 | 設定 |
|---|---|
| 模型 | Qwen3-8B（Ollama 本機部署，與 Stage 4 同一實例）|
| 模擬組別 | G1-student、G1-auditor、G2-student、G3-student |
| G1 採用雙 persona | Student + Auditor，測試人口統計描述 persona 的效應差異 |
| G2、G3 | 僅 Student persona（主要比較條件）|
| 確定性跑法 | Temperature = 0.0，N = 1（建立可重現基線；mechanism verification）|
| 隨機性跑法 | Temperature = 0.5，N = 10（LLM 行為對 sampling 隨機性的敏感度估計；robustness check）|
| 系統提示 | Persona 句 + 完整受試者說明手冊 markdown |
| 使用者提示 | Section A + Section B + Section E + (G2/G3) AI 面板（以 webapp 一致的 markdown 格式）|
| 輸出格式 | JSON：`{"judgment": "normal"/"suspicious", "confidence": 1–7, "reasoning": "<一句話>"}` |
| Thinking mode | 啟用；`<think>` 區塊後處理剝除 |
| Token 預算 | `num_predict = 2048` |
| 標籤對齊 | LLM 的 "suspicious" 對應 ground truth 的 "anomaly"，用於計算 `correct` 欄位 |

**T = 0 與 T = 0.5 的角色定位（誠實聲明）。** Stage 4 AI 工具使用 T = 0 的理由是實驗控制：每位受試者必須看到完全相同的 AI 輸出，確定性溫度是凍結輸出的基本要求。LLM 模擬同時跑 T = 0 與 T = 0.5 則服務於兩個不同的目的——T = 0 提供「此模型面對此 prompt 的最可能反應」（mechanism verification），確保結果可被任何使用相同程式碼與相同 Qwen3-8B 模型版本的研究者完全重現；T = 0.5 跑 10 次則提供 LLM 行為對 sampling 隨機性的敏感度估計（robustness check），以便計算 std 與拔靴法 CI。**本研究明確不主張 T = 0.5 的變異等同於人類受試者間的個體差異**：真人受試者的差異來自個性、經驗、疲勞、注意力等認知因素，而 LLM 的 stochastic 變異僅來自 token sampling 的隨機性，兩者在認知來源上並不對等。LLM 模擬定位為**計算參考基線**（computational reference point），並非人類行為的替代或預測。

### LLM 模擬的限制

**L10 — 無練習題回饋。** 真人受試者在進入 32 道正式題前，透過 2 道練習題及其回饋校準對 AI 的信任；LLM 模擬對每道題獨立呼叫，無前題記憶或回饋。這意味著 LLM 對 G2/G3 AI 面板的信任校準未經體驗校準——此差異可能影響模擬中的 AI 一致率，但不影響真人實驗。

**L11 — G2 視覺訊號喪失。** Webapp 以彩色區塊（紅色 = Suspicious，綠色 = Normal）顯示 G2 裁決；LLM 模擬以 markdown 粗體文字（`**Suspicious**`）接收同樣的語義資訊，無顏色強度。若真人受試者受顏色顯著性的影響超過語義內容，模擬會低估 G2 的錨定效應強度。

**L12 — Qwen3-8B 的採購領域先驗知識。** 模型預訓練時可能已學習一般採購舞弊術語，使 LLM-G1-student persona 具有真實 naïve 學生所沒有的隱性領域知識優勢。LLM-G1-student 的準確率應詮釋為「具備一般語言知識的合成代理」，而非真人 naïve 學生的代理。

**L13 — 一句話 persona 屬人口統計描述等級。** 模擬無法捕捉風險容忍度、認知風格或對 AI 的先驗信任等個體差異。所有組層級比較均有效；個體層級推論則不適用。

**L14 — 兩階段校準導致 G2 與 G3 的 AI 工具校準時點略有差異。** Stage 4 的 AI 工具校準（將公司供應商範圍、核准門檻、「多個弱訊號才視為可疑」的判斷準則明確加入 system prompt）在 G2 與 G3 上是分階段加入的：先在 G2 加入並重跑，後續才加入 G3 並重跑。最終所有報告的數字皆來自完成校準後生成的凍結輸出，但這個迭代過程在 commit 歷史中可見。研究結論基於最終一致校準後的版本。

**L15 — Temperature noise 不等於人類個體差異。** T = 0.5 跑 10 次提供的 std 與 CI 反映的是 Qwen3-8B 在 token sampling 隨機性下的行為分布，**並非**對「若有 10 位人類受試者會如何分布」的預測。真人差異的來源（個性、經驗、認知負荷）與 LLM 差異的來源（softmax sampling）在機制上不可類比。論文中報告的 stochastic 結果應解讀為「此 LLM 條件下的行為穩健性」，而非「人類受試者群體變異的估計」。

---

## 3.6 分析計畫

分析計畫以下列策略回應三個研究問題：

**主要指標：準確率（proportion correct）。** 每位受試者在每個條件下的準確率 = 正確判斷數 / 32。主要比較為 G1 vs G2 vs G3。

**效果量估計。** 鑒於每組 N = 4，虛無假設顯著性檢定不適用。所有比較均報告：
- Cliff's δ（序數/二元資料的非參數效果量，範圍 [−1, 1]）；
- Hedges' g（偏差校正的標準化平均差）；
- 95% 拔靴法信賴區間（B = 10,000 次重抽樣）。

**訊號類型子集分析（RQ2）。** 32 道題目預先分類為數值主導（Block A、B）與文字主導（C2a）子集，分別計算每組在各子集的準確率。交互樣態（若有的話，G3 的優勢是否集中於文字主導題目？）回應 RQ2。

**AI 覆蓋率（AOR）用於 RQ3。** 對 AI（Stage 4 G2 裁決或 G3 的 shadow G2）**錯誤**的題目，AOR = 仍然給出正確答案的受試者比例。比較 G2 與 G3 的 AOR，評估證據格式是否能實現更好的錯誤校正。

**信任量表分析。** 各組的實驗後問卷分數以描述統計呈現。跨組比較僅限於三份量表間結構等效的題目，並附上關於跨量表效度的適當說明（限制 L9）。

**LLM 模擬分析。** 模擬結果在獨立子節中報告，與真人受試者結果並列但不合併分析。主要比較為 LLM-G1 準確率 vs 真人 G1 準確率，以量化人機表現差距。

---

## 3.7 預期審查問題 Q&A

**Q1：資料集是合成的。您如何辯護其外部效度？**

合成資料集在兩個層次上以外部效度為設計目標。第一，數值分佈（價格、數量、前置時間、核准延遲）錨定於 Mouser Electronics API 的真實資料，確保合理的數值量級。第二，自由文字內容由被指示撰寫真實採購語言的商業級 LLM（DeepSeek）生成。然而，資料集無法重現組織特有的行為樣態（季節性循環、特定供應商協議）。因此研究結論受限於所描述的情境，定位為概念驗證而非田野研究。此限制在第 3.2.5 節與限制節中說明。未來工作將使用來自產業夥伴的真實採購記錄驗證研究發現。

---

**Q2：N = 12 非常少。您的結果在統計上是否有意義？**

本研究明確定位為概念驗證先導研究，而非驗證性研究。此定位遵循 HCI 與行為決策研究的既有實踐——在新型實驗設計中，使用效果量估計（而非 p 值檢定）的小樣本先導研究是標準做法。Cliff's δ 和 Hedges' g 配合拔靴法信賴區間將指示效應的**方向與規模**。若信賴區間較寬——如每組 N = 4 的預期情況——將明確說明需要更大樣本來確認。本研究的貢獻是支撐更大規模後續研究的方法論工具（資料集、AI 刺激材料、測量工具），而非對研究問題的決定性回答。

---

**Q3：LLM 模擬使用與 AI 工具相同的模型，這是否形成循環？**

若 Layer 2 LLM（合成受試者）能以某種方式「記住」或「辨識」自己作為 AI 工具時生成的 Layer 1 輸出，此疑慮才會成立。然而，兩層均使用 `temperature = 0.0` 且無共享情境的無狀態 API 呼叫——每次呼叫均獨立。Layer 2 LLM 讀取凍結 JSON 輸出的方式，與真人受試者在螢幕上讀取 AI 面板完全相同。模型在架構上無法偵測或利用「自己撰寫了 AI 輸出」的這一事實。為進一步防範此疑慮，Layer 1 與 Layer 2 的系統提示結構上完全不同：Layer 1 的提示不提及受試者、說明手冊或實驗；Layer 2 的提示不提及自己是 AI 工具或為他人生成裁決。

---

**Q4：您給 AI 公司術語（S-001–025 慣例、核准門檻），這是否等於洩漏答案？**

不等於。本研究將「公司知識」拆成兩類：**判斷準則**（calibration knowledge）與**預先計算的數值**（pre-computed deviations）。前者是「**怎麼判斷**」——例如「常規供應商範圍是 S-001–025」、「多數訂單為例行性，單一弱訊號通常可解釋」——這與受試者透過說明手冊獲得的內容等價，是公平判斷的起點，並未告知 AI 任何特定訂單的答案。後者是「**這筆訂單的數值有多異常**」——例如 Section E 提供的「單價為 SKU 中位數的 3.2 倍」、「核准延遲 z = +2.20」——這類數值仍只給受試者，AI 必須從原始欄位 + RAG 自行推導。此切割確保 AI 與人類擁有相同的判斷起點（以避免 AI 因缺乏正常基線而過度標記可疑），但保留人類在工具支援上的優勢，亦保留 G2 vs G3 對比的純粹性（兩組看到的是同一個 AI 輸出，差異僅在格式）。

---

**Q5：RAG 語料庫含有異常訂單，這是否意味著 AI 能存取舞弊標籤？**

不。RAG 語料庫條目僅包含原始訂單欄位與自由文字備註——與受試者在 webapp 中看到的相同欄位。Ground truth 標籤（`injection_plan`）被一個硬編碼的洩漏檢查排除，若 metadata 中偵測到任何敏感欄位，建構管線即中止。AI 無法透過 RAG 途徑存取任何異常標籤。真正的疑慮更為微妙：語料庫中的異常訂單可能看起來與當前異常訂單相似，導致 AI 低估該樣態的不尋常程度。此隱性 few-shot 效應理論上存在，但因異常濃度低（約 16%）、各異常類型注入不同欄位，以及對 G2 和 G3 的對稱影響而被削弱。此效應作為限制 L6 記錄，而非視為設計缺陷。

---

**Q6：您自行定義 ground truth，這是否形成循環——AI 被訓練來偵測您注入的確切樣態？**

Ground truth（`apply_anomaly()` 中的突變合約）定義了資料中**被改變了什麼**。偵測任務——無論是人類還是 AI——是從**可觀察的訂單欄位**推斷是否有所改變，在不知曉突變合約的情況下進行。這類似於使用人工誘發條件的醫學研究：實驗者知道疾病是誘發的，但診斷測試必須僅從症狀推斷。循環性只有在異常偵測演算法使用注入規則作為特徵時才會出現——但 Stage 3 僅從原始數值特徵計算 Mahalanobis 距離，AI 使用原始訂單欄位加上 RAG，兩者均不編碼注入邏輯。八類異常類型以已發表的舞弊分類法（PACE，Westerski et al., 2021）為基礎，而非臨時發明，進一步將 ground truth 設計與偵測機制分離。

---

**Q7：您報告的 T = 0.5 stochastic 結果可以視為對人類受試者群體變異的模擬嗎？**

不可以。這是 LLM 模擬最常被誤解的一點，本研究刻意明確澄清。T = 0.5 的隨機性僅來自 Qwen3-8B 在 token sampling 階段的 softmax 抽樣過程，跑 10 次得到的變異反映「同一模型對同一 prompt 在不同隨機種子下的行為分佈」。真人受試者的差異則來自個性、領域經驗、認知負荷、注意力等高層次認知因素，這兩種變異來源在機制上**完全不對等**。論文中的 LLM stochastic 結果應解讀為「Qwen3-8B 在此實驗條件下的 robustness check」——告訴我們此模型的判斷是否對 sampling 隨機性穩定——而**不是**「若有 10 位人類受試者其表現會如何分佈」的預測。後者必須等待真人實驗的資料才能討論。LLM 模擬被定位為**計算參考基線**（computational reference point），不是人類行為的替代或預測模型，這在 §3.5.4 與限制 L13、L15 中明確聲明。

---

## 附錄 A — 數學定義

### A.1 Stage 1 使用的隨機過程

**Poisson 訂單到達。**

設 T = 366（2024 年天數）、N = 500（訂單總數）、λ = N/T ≈ 1.366。

對每天 t ∈ {0, ..., T−1}，當天到達的訂單數為：

&nbsp;&nbsp;&nbsp;&nbsp;nₜ ~ Poisson(λ)

隨機調整計數 ±1，確保訂單總數恰好為 N = 500。

**對數常態數量與價格。**

對於 SKU k，其經驗中位數 m_qty 與對數空間標準差 σ_qty：

&nbsp;&nbsp;&nbsp;&nbsp;quantity_k ~ LogNormal(ln(m_qty), σ_qty)，取整至最近整數，最小值為 1

單價同理，以 Mouser 中位數 m_price 與 σ_price 為錨點。

**截斷常態核准延遲。**

&nbsp;&nbsp;&nbsp;&nbsp;approval_lag ~ TruncNormal(μ = 2.0, σ = 1.5, a = 0.1, b = 14.0)

**截斷常態交貨前置時間（SKU 專屬）。**

&nbsp;&nbsp;&nbsp;&nbsp;delivery_lag_k ~ TruncNormal(μ_k, σ_k, a_k = max(2, μ_k − 2σ_k), b_k = μ_k + 3σ_k)

### A.2 異常注入突變合約

| 類型 | 突變欄位 | 變換 |
|---|---|---|
| `item_spending` | `unit_price_usd`、`total_amount_usd` | 單價 × Uniform(2.5, 4.0) |
| `border_value` | `total_amount_usd`、`quantity` | 總金額設為（門檻 − Uniform(1, 99)），數量重新計算 |
| `unusual_vendor` | `supplier_id` | 從異常池 S-026–030 指定 |
| `vendor_spending` | `supplier_id` | 9 筆訂單強制使用同一個異常池供應商 |
| `approval_bypass` | `approval_lag_days` | 小於 0.1 天（即時）或大於 10 天（延遲）|
| `quote_manipulation` | `purchase_note` | Stage 2 注入 PACE 提示 |
| `bank_account_change` | `supplier_profile` | Stage 2 注入 PACE 提示 |
| `conflict_of_interest` | `supplier_profile` | Stage 2 注入 PACE 提示 |

### A.3 Mahalanobis 距離（Stage 3）

每筆訂單的特徵向量：**x** = (unit_price_usd, quantity, approval_lag_days, expected_delivery_lag_days) ∈ ℝ⁴。

僅使用 424 筆正常訂單估計參數：

&nbsp;&nbsp;&nbsp;&nbsp;μ̂ = (1/n) · Σᵢ **x**ᵢ

&nbsp;&nbsp;&nbsp;&nbsp;Σ̂ = (1/(n−1)) · Σᵢ (**x**ᵢ − μ̂)(**x**ᵢ − μ̂)ᵀ

Mahalanobis 距離平方：

&nbsp;&nbsp;&nbsp;&nbsp;D²(**x**) = (**x** − μ̂)ᵀ Σ̂⁻¹ (**x** − μ̂)

對數空間變體在應用 x → ln(x + ε) 變換後以相同方式計算。兩個變體均用於分層抽樣；呈現給受試者的是自然語言 Section E 句子，而非數值 D² 值。

---

## 附錄 B — LLM 系統提示全文

### B.1 Stage 4 — G2 系統提示（AI 工具）

```
You are an internal procurement auditor at a 30-person electronics company.
Review the purchase order below and decide if it is suspicious.

CALIBRATION CONTEXT (judgment standards used at this company):
- The company routinely uses suppliers S-001 through S-025. Other supplier
  IDs represent newer or one-off vendors -- unusual but not automatically
  suspicious; a new supplier with otherwise typical fields can be legitimate.
- Approval thresholds are tiered: orders below USD 1,000 are signed off
  by A-PROC-01 / A-PROC-02; USD 1,000-5,000 by A-CTO; above USD 5,000 by
  A-CEO. A wrong-level approver on a large order is a notable deviation.
- Most orders in this company are routine and normal. A SINGLE weak
  deviation (e.g., unit price 1.2x median, slightly fast approval,
  quantity moderately above median) is usually explainable on its own.
  Flag the order as "suspicious" ONLY when you observe MULTIPLE
  independent red flags, OR ONE extreme deviation (e.g., unit price
  > 2.5x median, total just below an approval threshold combined with
  unusual supplier, missing approver on a large order).
- Use the SKU market reference and the retrieved historical orders to
  judge whether a given value is genuinely unusual for THIS company.

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
- Base your judgment on the order fields, the calibration context above,
  and the retrieved historical orders.
- Do NOT produce any text outside the JSON object.
```

### B.2 Stage 4 — G3 系統提示（AI 工具）

```
You are an internal procurement auditor at a 30-person electronics company.
Review the purchase order below and select the 4 MOST NOTEWORTHY features
of this order by comparing it against the provided historical orders and
the SKU market reference.

CALIBRATION CONTEXT (judgment standards used at this company):
- The company routinely uses suppliers S-001 through S-025. Other supplier
  IDs represent newer or one-off vendors -- unusual but not automatically
  worth flagging; a new supplier with otherwise typical fields can be
  legitimate.
- Approval thresholds are tiered: orders below USD 1,000 are signed off
  by A-PROC-01 / A-PROC-02; USD 1,000-5,000 by A-CTO; above USD 5,000 by
  A-CEO. A wrong-level approver on a large order is a notable deviation.
- Most orders in this company are routine and normal. A SINGLE small
  difference (e.g., unit price 1.2x median, slightly fast approval,
  quantity moderately above median) is usually explainable on its own
  and does NOT need to be highlighted as a deviation. Reserve "deviation"
  framing for genuinely unusual values.

A "noteworthy" feature is any field or aspect that an experienced auditor
would point out when describing this order to a colleague. It can be:
  (a) a DEVIATION from typical patterns (e.g., unit price 3x higher than
      historical median, missing approver on a >$1000 order, supplier
      newly registered, suspicious wording in the purchase note), OR
  (b) a CONFIRMING observation that the order looks routine.

Important:
- Most procurement orders are routine. Do NOT manufacture deviations
  when the order is genuinely typical.
- Do NOT issue an overall verdict, recommendation, or conclusion.
- Each "why_noteworthy" MUST be between 5 and 25 words.
- EXACTLY 4 features, no more, no fewer.

Output ONLY a valid JSON object:
{
  "noteworthy_features": [
    {
      "feature": "<field or aspect name>",
      "current_value": "<value in this order>",
      "reference_value": "<typical value from historical orders>",
      "why_noteworthy": "<5-25 word explanation>"
    },
    ... (exactly 4 items)
  ]
}
```

### B.3 Stage 16 — LLM 合成受試者系統提示架構

```
[PERSONA 句]
You are a university business student with no prior procurement experience.
  — 或 —
You are a senior internal auditor with 10 years of procurement fraud experience.

You have been recruited as a participant in the following study.
Read the briefing carefully, then reply in JSON only.

================ PARTICIPANT BRIEFING ================
[briefing_common.md + briefing_g{N}.md 全文]
================ END BRIEFING ========================
```

---

## 附錄 C — 參數表

### C.1 SKU 市場參考值（Mouser API，2026 年 4 月查詢）

| SKU | 零件 | price_median_usd | price_sigma_log | qty_median | lead_time_median_days |
|---|---|---|---|---|---|
| BME280 | 空氣品質感測器 | 2.9156 | 0.124 | 8 | 116 |
| ESP32 | WiFi+BT MCU 模組 | 3.5000 | 0.150 | 12 | 90 |
| STM32F103 | ARM Cortex-M3 MCU | 4.2000 | 0.180 | 10 | 105 |
| MPU6050 | IMU 感測器 | 1.8000 | 0.130 | 15 | 80 |
| ACS712 | 電流感測器 | 1.2000 | 0.110 | 20 | 70 |
| HC-SR04 | 超音波距離感測器 | 0.8500 | 0.140 | 25 | 60 |
| W25Q64 | 快閃記憶體 | 0.9000 | 0.120 | 20 | 75 |
| DS18B20 | 溫度感測器 | 1.5000 | 0.130 | 18 | 85 |
| TPS5430 | DC-DC 轉換器 | 2.1000 | 0.160 | 10 | 95 |
| Si7021 | 濕度/溫度感測器 | 3.1000 | 0.140 | 8 | 110 |

### C.2 異常注入配額

| 異常類型 | 目標筆數 | 訊號類型 |
|---|---|---|
| `item_spending` | 13 | 數值 |
| `vendor_spending` | 9 | 數值 |
| `border_value` | 11 | 數值 |
| `unusual_vendor` | 10 | 數值 + 文字 |
| `approval_bypass` | 8 | 數值 |
| `quote_manipulation` | 6 | 文字 |
| `bank_account_change` | 9 | 文字 |
| `conflict_of_interest` | 10 | 文字 |
| **合計** | **76** | |

### C.3 Stage 4 LLM 參數

| 參數 | 值 |
|---|---|
| 模型 | qwen3:8b（雜湊值 500a1f067a9f）|
| Temperature | 0.0（確定性）|
| num_predict | 12,288 |
| num_ctx | 16,384 |
| RAG top-k | 5 |
| 每題最大重試次數 | 3 |
| 禁用詞 | fraud, anomaly probability, anomaly score, recommend, conclude, likely fraud, PACE, injection, rubric, Mahalanobis, z-score |

---

## 附錄 D — 信任量表題目

### D.1 G2 AI 信任量表（5 題，7 點李克特量表：1 = 強烈不同意，7 = 強烈同意）

1. AI 裁決在此任務中整體上是可靠的。
2. 在 AI 建議與我的初步判斷不同時，我感到樂意遵循 AI 的建議。
3. AI 的一句說明幫助我理解其得出裁決的原因。
4. 隨著任務進行，我發現自己愈來愈依賴 AI 裁決。
5. 在真實稽核情境中，我願意使用這個 AI 工具。

### D.2 G3 AI 證據量表（5 題平行版）

1. AI 的 noteworthy features 整體上是準確的觀察。
2. 四條特徵提供了足夠的資訊讓我做出有信心的決策。
3. AI 的觀察幫助我注意到若無輔助可能會忽略的事項。
4. 我發現能輕鬆地綜合四條特徵並得出自己的裁決。
5. 在真實稽核情境中，我願意使用這個 AI 證據工具。

### D.3 G1 Section E 平行量表（5 題結構平行版）

1. Section E 的偏差句在此任務中整體上具有參考價值。
2. 我願意根據偏差資訊調整我的判斷。
3. 偏差句幫助我理解每筆訂單的哪些面向不尋常。
4. 隨著任務進行，我發現自己愈來愈依賴 Section E。
5. 在真實稽核情境中，我發現 Section E 偏差資訊有所幫助。

*說明：G1 量表衡量對統計偏差句的依賴程度，而非 AI 信任。跨組問卷分數的比較應限於結構性指標，並謹慎詮釋。*

---

## 附錄 E — 關鍵程式碼清單

完整代碼庫可在研究資源庫中取得。以下列出關鍵腳本及其角色：

| 腳本 | 階段 | 角色 |
|---|---|---|
| `code/dataset/generate_dataset.py` | Stage 1 | 蒙地卡羅訂單生成、供應商 Markov 圖、異常注入 |
| `code/dataset/stage2_deepseek.py` | Stage 2 | DeepSeek API 呼叫，生成 purchase_note 與 supplier_profile |
| `code/dataset/prepare_stage3.py` | Stage 3 | Section E 特徵計算、Mahalanobis 距離、分層抽樣、RAG 語料庫匯出 |
| `code/rag/build_rag.py` | Stage 4a | ChromaDB 嵌入建構與洩漏檢查 |
| `code/rag/freeze_llm_outputs.py` | Stage 4b | 凍結 G2 裁決與 G3 證據生成 |
| `code/webapp/app.py` | Stage 5 | Streamlit 實驗 Web Application |
| `code/webapp/data_loader.py` | Stage 5 | 載入 Stage 3 + Stage 4 凍結工件 |
| `code/webapp/sheets_backend.py` | Stage 5 | Google Sheets 分配佇列與回應記錄 |
| `code/webapp/init_sheets.py` | Stage 5 | Google Sheets 一次性初始化（平衡分配佇列）|
| `code/dataset/llm_simulate.py` | Stage 16 | LLM 合成受試者模擬 |

### E.1 凍結輸出格式範例

**G2 裁決（一筆訂單）：**
```json
{
  "PO-2024-0211": {
    "judgment": "suspicious",
    "reason": "Supplier recently updated banking details, a common indicator of BEC fraud."
  }
}
```

**G3 證據（一筆訂單）：**
```json
{
  "PO-2024-0422": {
    "noteworthy_features": [
      {
        "feature": "Unit price",
        "current_value": "$8.90",
        "reference_value": "$2.80 (SKU historical median)",
        "why_noteworthy": "Price is 3.2× the historical median for this component."
      },
      {
        "feature": "Supplier",
        "current_value": "S-028",
        "reference_value": "S-001 to S-025 (regular suppliers)",
        "why_noteworthy": "Supplier ID outside the established regular supplier range."
      },
      {
        "feature": "Approval lag",
        "current_value": "0.05 days",
        "reference_value": "Typical 1–3 days for this approver",
        "why_noteworthy": "Approval was unusually fast, potentially bypassing normal review."
      },
      {
        "feature": "Purchase note",
        "current_value": "Urgent order placed directly with preferred contact",
        "reference_value": "Standard notes reference project codes and standard process",
        "why_noteworthy": "Wording suggests informal channel bypassing procurement process."
      }
    ]
  }
}
```

---

*第三章及附錄完畢。*
