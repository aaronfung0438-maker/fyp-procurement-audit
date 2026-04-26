# Dataset Pipeline 說明文件
**ABC Electronics Ltd. 採購異常偵測 FYP**

---

## 一、現有腳本

| 腳本 | 職責 |
|------|------|
| `generate_dataset.py`   | Stage 0+1：Mouser API → Monte Carlo → 500 筆訂單（Excel + CSV） |
| `generate_semantics.py` | Stage 2：DeepSeek `deepseek-chat` 補 `purchase_note`、`supplier_profile` |

### 執行方式

```powershell
cd "C:\Users\aaron\Desktop\HKUST\IEDA FYP\code"
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt   # 含 requests、python-dotenv
python dataset\generate_dataset.py
```

### API 金鑰（`.env`，建議）

專案內可放置 `dataset/.env`（僅本機使用，勿提交公開儲存庫）。腳本會在啟動時嘗試 **`load_dotenv(dataset/.env)`**（需已 `pip install python-dotenv`），然後用 **`os.getenv("MOUSER_API_KEY", …)`** 讀金鑰；若未安裝 `python-dotenv`，請改用下列方式之一設定環境變數。

- 若你在 PowerShell 先設好變數再執行，可不依賴 `.env` 檔：
  ```powershell
  $env:MOUSER_API_KEY = "你的金鑰"
  python dataset\generate_dataset.py
  ```
- 若將專案推到 GitHub，請**勿**把含真實金鑰的 `.env` 一併提交；在儲存庫根目錄的 `.gitignore` 加入一行 `**/.env` 或 `code/dataset/.env`。

### 執行時會印出的參數總覽

Stage 0（載入或抓取 Mouser）結束後，腳本會呼叫 **`print_all_parameters()`**，在終端機列出：

- 全域：`RANDOM_SEED`、`N_ORDERS`、日期區間、Poisson 的 λ  
- 審批延遲：Truncated Normal 的 μ、σ、上下界  
- 審批門檻、幣別（目前僅 USD）  
- 各工程師權重、8 類異常注入筆數  
- **每顆零件一列**：`price_median_usd`、`μ_price = ln(price_median)`、`price_sigma_log`、`qty_median`、`qty_sigma_log`、`lead_time_median_days`、`lead_time_sigma_days`  

論文寫「模擬設定」時可直接從這段輸出抄表或附錄。

首次執行：打 Mouser API，結果快取到 `data/mouser_raw_exact.json`。  
再次執行：直接讀快取，不重打 API，直接跑模擬。

---

## 二、Pipeline 全貌

```
generate_dataset.py
│
├── Stage 0  Mouser Search API (/search/partnumber, exact match)
│            ↓  mouser_raw_exact.json  (快取，論文附錄用)
│
├── Stage 1  Monte Carlo 模擬 (RANDOM_SEED = 42)
│            ├── Poisson Process      → 下單日期
│            ├── Log-Normal           → 單價、數量
│            ├── Truncated Normal     → 審批天數、交貨天數
│            ├── Markov-style         → 工程師→供應商偏好
│            └── Importance Sampling  → 76 筆異常強制注入
│            ↓
├── Stage 2  generate_semantics.py (待建)
│            deepseek-chat 填入 purchase_note / supplier_profile
│            （Stage 1 已有 Mouser 的 item_description，不需 LLM 重寫）
│            ↓ 你人工改寫語義欄位（可選）
│
└── Stage 3  prepare_stage3.py (已完成)
             偏差特徵 (unit_price_ratio 等 8 欄) + Mahalanobis D²
             + 切成 15 題實驗樣本 / 485 筆 RAG 語料
             → Stage 4 嵌入 Chroma、Qwen3 7B 凍結 G2/G3 輸出
```

---

## 三、輸出檔案

| 檔案 | 說明 |
|------|------|
| `data/mouser_raw_exact.json` | Mouser API 完整回應（論文附錄） |
| `data/dataset_<時間戳>.xlsx` | 5 個 sheet：orders / suppliers / components / injections / metadata |
| `data/orders_<時間戳>.csv` | 純 orders 表，方便 Python 讀取 |

### Excel 5 個 Sheet 說明

| Sheet | 內容 |
|-------|------|
| `orders` | 500 筆採購單（21 欄，含 `batch_generated_at`） |
| `suppliers` | 30 家供應商（25 正常 + 5 異常池） |
| `components` | 10 種零件（含 Mouser 抓回的真實價格） |
| `injections` | 76 筆異常注入紀錄（po_id / indicator / seed） |
| `metadata` | 設定快照（seed、日期、異常數量等） |

### `orders_<時間戳>.csv` 欄位與程式對照

| 欄位 | 產生位置／邏輯 | 說明 |
|:---|:---|:---|
| `po_id` | `generate_orders()`，`f"PO-2024-{i+1:04d}"` | 採購單號，依產生順序遞增 |
| `batch_generated_at` | `generate_orders()` 開頭一次 `datetime.now().isoformat()` | **整批資料集**產生時間，500 筆共用，用於版本追蹤（不是單筆訂單建立時間；單筆日期見 `created_date`） |
| `requester_id` | `rng.choice(req_ids, p=req_weights)` | 8 位工程師之一 |
| `approver_id` | `decide_approver(total_amount_usd)` | 依金額門檻；`approval_bypass` 變體 A 可能改為**空字串**（表示未指派核准人） |
| `supplier_id` | `sample_supplier()`（Markov 偏好 0.65 / 0.25 / 0.10） | 異常可能改為 S-026～S-030 |
| `created_date` | `order_dates()`（Poisson + 微調總數 = 500） | 訂單建立日 |
| `approval_lag_days` | `sample_approval_lag()`，Truncated Normal | μ=2、σ=1.5、範圍 [0.1, 14] |
| `approved_date` | `created_date` + `approval_lag_days` | |
| `expected_delivery_lag_days` | `sample_delivery_lag()`，Truncated Normal | μ = 該零件 `lead_time_median_days`（見下） |
| `expected_delivery_date` | `approved_date` + 交貨延遲天數 | |
| `item_category` | `COMPONENTS_DEF["category"]` | |
| `item_sku` | `COMPONENTS_DEF["sku"]` | |
| `item_description` | Mouser `Description`（經 `stage0_fetch` 寫入 `comp["name"]`） | **真實 API 文字**，非 Stage 2 生成 |
| `quantity` | `sample_qty()`，Log-Normal | 幾何中心 `qty_median`，σ=`qty_sigma_log`，至少 1 |
| `unit_price_usd` | `sample_price()`，Log-Normal | 中心 `price_median_usd`，σ=`price_sigma_log`；`item_spending` 可乘 2.5～4 倍 |
| `total_amount_usd` | `quantity * unit_price_usd`（四捨五入 2 位） | 門檻與異常會一併改寫 |
| `currency` | `sample_currency()` | **僅 USD**（`CURRENCY_DIST = {"USD": 1.0}`），無多幣別假設 |
| `purchase_note` | Stage 1 為空字串 `""` | 預留 Stage 2 LLM |
| `supplier_profile` | Stage 1 為空字串 `""` | 預留 Stage 2 LLM |
| `injection_plan` | 預設 `"none"`；`inject_anomalies()` 寫入指標名 | |
| `injection_seed` | 注入時 `rng.integers(0, 1_000_000)`；未注入為 `-1` | |

**交期（lead time）來源**：目前 10 顆零件在快取 `mouser_raw_exact.json` 中，`LeadTime` 皆為 **`"NNN Days"`** 格式；`_lead_days()` 用正則 `(\d+)\s*day` 直接解析整數天數，**未使用**「In Stock / Non-Stock / Call」等後備分支（該分支僅在 API 回傳非數字格式時才會用到）。

**僅標記、不改欄位的異常**：`vendor_spending`、`quote_manipulation` 在 Stage 1 只設定 `injection_plan`／`injection_seed`，欄位數值與正常單相同；其異常訊號僅存在於語義欄位或跨訂單分布之中，是 Stage 3 用來挑選「文字隱藏型」邊界案例的依據。

---

## 四、10 種零件（Mouser 真實資料）

| Mouser PN | SKU | 類別 | 廠商 | 用途說明 |
|-----------|-----|------|------|----------|
| 603-CFR-25JB-52-10K | CFR-25JB-52-10K | Resistor | YAGEO | 10kΩ 碳膜電阻，電路板上最基礎的被動元件，單價極低、下單量大，是資料集中「低單價高數量」的代表性品項 |
| 81-GCM21BR71H104KA7L | GCM21BR71H104KA7L | Capacitor | Murata | 100nF 積層陶瓷電容，廣泛用於電源濾波，與電阻同屬低價被動元件，提供資料集中第二種低價品類 |
| 511-STM32F103C8T6 | STM32F103C8T6 | IC | STMicroelectronics | ARM Cortex-M3 32 位元微控制器，IoT 裝置核心晶片，單價中高（約 $3–5），是資料集中「中價 IC」的代表，也是最易引發 `item_spending` 異常的品項 |
| 356-ESP32WRM32EN8R2 | ESP32-WROOM-32E-N8R2 | IC | Espressif | ESP32 Wi-Fi + 藍牙模組（8MB Flash），ABC Electronics 主力 IoT 產品的核心模組，採購頻率高，是供應商集中消費分析的關鍵品項 |
| 358-SC0915 | SC0915 | DevBoard | Raspberry Pi | Raspberry Pi Pico 開發板，用於原型測試，價格固定（全球統一零售約 $4），是資料集中「低 sigma、穩定價格」的基準品項 |
| 392-101262 | Soldered-101262 | Sensor | Soldered | DHT22 相容溫濕度感測器模組，已附接腳，適合快速部署，代表採購人員偶爾選用非主流品牌的行為，可觸發 `unusual_vendor` 分析 |
| 485-4566 | AHT20-4566 | Sensor | Adafruit | Adafruit AHT20 溫濕度 breakout 板（含 STEMMA QT 連接器），單價較高但功能完整，代表資料集中「品牌溢價」的感測器採購 |
| 262-BME280 | BME280 | Sensor | Bosch | Bosch BME280 氣壓、溫度、濕度三合一感測器裸晶片，需要焊接，是資料集中「中高價、小批量」的感測器代表，對 `border_value` 異常敏感 |
| 306-B4BXHAMLFSNP | B4B-XH-A | Connector | JST | JST XH 2.54mm 4Pin 連接器（無鉛、錫鍍），用於感測器與主板連線，下單量大、單價低，與電阻/電容同屬「消耗性配件」品類 |
| 590-588 | MG-588 | PCB | MG Chemicals | MG Chemicals 6×9 吋單面銅板，用於手工打樣，單價最高（約 $12–15）但下單量極小（通常 1–3 片），在資料集中是「高單價低數量」的極端代表，容易在 Mahalanobis 分析中與正常模式產生距離 |

---

### 價格參數計算方式

`price_median_usd`（Log-Normal 中心值）= 所有 Mouser 價格梯的**幾何平均**
→ 用途：作為 Monte Carlo 抽樣的「中位數錨點」；幾何平均比算術平均更適合右偏的價格分佈，因為它對應 Log-Normal 的中位數參數 e^μ

`price_sigma_log`（Log-Normal 離散度）= (ln 最高價格梯 − ln 最低價格梯) / 4，再**夾在 [0.05, 0.50]**  
→ 除以 4 是「4-sigma」經驗：用價格梯的 ln 範圍反推 ln 空間的 σ。  
→ **下限 0.05**：避免價格梯極少時 σ 趨近 0、抽樣失去變異。  
→ **上限 0.50**：價格梯只有兩點時，原始公式會把 σ 估得過大，夾上限可避免單價模擬飄到不切實際。

**為什麼 σ 的公式裡是 ln，不是 e^？**  
σ 描述的是 **ln(單價)** 這個 Normal 變數的標準差，所以範圍用 **ln(最高) − ln(最低)**。`e^` 只在抽樣後把 **ln 空間的樣本** 轉回 **美元單價** 時使用（`rng.lognormal` 內部等價於先抽 Normal 再 `exp`）。

---

## 五、統計方法詳解

### 5.1 Monte Carlo 概念

Monte Carlo 是「用大量隨機抽樣逼近真實分佈」的方法。
這個腳本用它來：**為每筆採購單的每個欄位，從對應的機率分佈抽一個值**，重複 500 次，得到 500 筆不同但統計上合理的訂單。

```
第 i 筆訂單 = {
    created_date       ← 從 Poisson 過程抽
    requester_id       ← 從活躍度權重抽
    supplier_id        ← 從 Markov 偏好抽
    quantity           ← 從 Log-Normal(qty_median, sigma) 抽
    unit_price_usd     ← 從 Log-Normal(price_median, sigma) 抽
    approval_lag_days  ← 從 Truncated Normal(2, 1.5) 抽
    delivery_lag_days  ← 從 Truncated Normal(lead_time, sigma) 抽
}
```

每次抽都是獨立的，所以每筆訂單都不同，但整體分佈符合現實。

### 5.2 各欄位用哪種分佈

| 欄位 | 分佈 | 參數 | 理由 |
|------|------|------|------|
| `created_date` | Poisson Process | λ = 500/366 | 採購到達是隨機事件，Poisson 是標準模型 |
| `quantity` | Log-Normal | μ = ln(qty_median), σ = qty_sigma_log | 數量右偏：大多買少量，偶爾大批 |
| `unit_price_usd` | Log-Normal | μ = ln(price_median), σ = price_sigma_log | 價格分佈同樣右偏 |
| `approval_lag_days` | Truncated Normal | μ=2, σ=1.5, [0.1, 14] | 有下限（不能是負數），上限 14 天強制防止自然極端值污染異常偵測 |
| `expected_delivery_lag_days` | Truncated Normal | μ=lead_time, σ=lead_time×0.25 | 同上 |
| `supplier_id` | Categorical (Markov) | 0.65/0.25/0.10 | 工程師習慣找熟悉的供應商 |
| `currency` | 常數 | 100% USD | 僅美元，避免無文獻支撐的多幣別比例 |

---

### 5.3 Log-Normal 的本質：就是「先取 log，再用 Normal」

#### 為什麼要先取 log？

電阻單價 $0.022、電容 $0.116、MCU $4.06——這些數字跨越了幾個數量級，直接用 Normal 分佈有兩個問題：

**問題一：Normal 會抽出負數**
```
unit_price ~ Normal(0.022, 0.01)
有機率抽出 -0.003 → 負數單價，完全無意義
```

**問題二：Normal 的「距離感」不對**
```
Normal 認為：$0.022 和 $0.032 的差距 = $1.00 和 $1.01 的差距（都差 $0.01）
現實中：電阻從 $0.022 漲到 $0.032 是漲了 45%，非常大
        MCU 從 $4.06 漲到 $4.07 是漲了 0.25%，幾乎沒差

→ 價格的差異應該用「比例」衡量，不是「絕對值」
```

#### 解決方案：先取 ln，讓小數字變成正常大小的數字

```
原始價格         取 ln 之後
───────────      ─────────────
$0.011    →      ln(0.011) = -4.51
$0.022    →      ln(0.022) = -3.82   ← 現在這些數字
$0.116    →      ln(0.116) = -2.15     都在同一個數量級
$4.06     →      ln(4.06)  =  1.40     可以直接用 Normal 處理
$55.0     →      ln(55.0)  =  4.01
```

ln 之後的數字，用 Normal 分佈完全沒問題：
- 不會出現負數（因為 ln 是 Normal，取 exp 之後必定 > 0）
- 比例差異被正確反映（乘以 2 倍 = 加 ln 2，在 ln 空間是等距的）

#### Log-Normal 的完整流程（以 Mouser 電阻為例）

```
Step 1  從 Mouser 拿到幾何平均價格
        geo_mean = $0.0218

Step 2  計算 Log-Normal 的 μ 參數
        μ = ln(0.0218) = -3.826

Step 3  計算 σ 參數（4-sigma 法則，在 **ln 空間**）
        最高價 $0.10，最低價 $0.011
        σ_raw = (ln(0.10) - ln(0.011)) / 4
              = (-2.303 - (-4.510)) / 4
              = 0.552
        程式再 clamp：σ = min(max(σ_raw, 0.05), 0.50)
        → 本例若無 clamp 為 0.552；若超過 0.50 則以 0.50 進入抽樣

Step 4  Monte Carlo 抽樣（概念）
        z ~ Normal(μ = ln(0.0218), σ)   # z 在「ln(美元)」空間
        price = exp(z)                  # e^ 只在「轉回美元」這一步

Step 5  numpy 一行等價寫法
        price = rng.lognormal(mean=ln(0.0218), sigma=σ)
        （內部等同 Step 4：Normal 再 exp）
```

#### 一張圖看懂 Normal vs Log-Normal

```
Normal(μ=0.022, σ=0.01)          LogNormal(μ=ln(0.022), σ=0.552)
        ████                              ████
      ████████                          ████████
    ████████████                      ████████████████
  ████████████████                  ██████████████████████████
──┼──────────────────────        ──┼──────────────────────────────
 -0.01  0.022  0.06  (USD)        0   0.011  0.022    0.10   (USD)
  ↑                                ↑
  會抽出負數！                     永遠是正數，形狀右偏
```

---

### 5.4 Truncated Normal：Normal 加上剪裁

審批天數用 Normal(μ=2, σ=1.5) 的問題：
```
Normal(-∞, +∞) 理論上可以抽出 -5 天（負數）或 50 天（不合理的長）

解法：截斷
    低於 0.1 天 → 丟掉重抽（不可能比 6 小時更快審批）
    高於 14 天  → 丟掉重抽（超過 14 天的由異常注入負責，正常流程不應出現）

結果 → Truncated Normal(μ=2, σ=1.5, min=0.1, max=14)
      只保留 [0.1, 14] 範圍內的值，形狀仍然是鐘形
```

為什麼截斷上限很重要：
```
若不截斷，Exponential 或 Normal 偶爾會自然產生 20 天、30 天的審批天數
這些「自然極端值」混入正常訂單，會污染 Mahalanobis 的基準 μ 和 Σ
導致真正注入的異常（秒批 0.01 天）反而顯得不突出
→ Truncated Normal 的上限 = 給 Mahalanobis 一個乾淨的正常範圍
```

---

### 5.5 Poisson Process 的數學

```
每天下單數 ~ Poisson(λ)，λ = 500 / 366 ≈ 1.366 筆/天

E[每天下單數] = λ = 1.366
Var[每天下單數] = λ = 1.366   ← Poisson 的特性：均值 = 變異數

全年 Σ counts = 500（腳本做微調確保恰好 500 筆）
```

Poisson 用在下單日期的原因：採購申請的到達是「獨立隨機事件」，每天不固定，有時 0 筆、有時 3 筆，符合 Poisson 的假設。

---

## 六、Mahalanobis Distance（Stage 3 用）

> **這部分是 Stage 3 `prepare_stage3.py` 的工作，Stage 1 不計算，但設計資料集時已為它預留欄位。**

### 6.1 為什麼需要 Mahalanobis Distance？

Stage 1 注入的是**結構性異常**（改數字），但還有一類「邊界案例」：
數字本身不是極端值，而是**幾個特徵的組合**看起來可疑。

普通的 Z-score 只看單個變數。Mahalanobis Distance 看**4 個變數的聯合分佈**，並且考慮變數之間的相關性（例如高價格的零件通常交期也長——如果兩者不一致就很可疑）。

### 6.2 4 維特徵向量

Stage 3 會對每筆訂單計算：

```
x = [unit_price_usd,
     quantity,
     approval_lag_days,
     expected_delivery_lag_days]
```

### 6.3 計算公式

```
D²(x) = (x − μ)ᵀ Σ⁻¹ (x − μ)

μ  = 從 424 筆「正常訂單」(injection_plan="none") 計算的均值向量
Σ  = 從正常訂單計算的 4×4 共變異矩陣
```

D²(x) 服從 χ²(4) 分佈（4 自由度），所以：
- D²(x) > χ²(4, 0.95) = 9.49  → 邊界案例（top 5%）
- D²(x) > χ²(4, 0.99) = 13.28 → 異常案例（top 1%）

### 6.4 為什麼用正常訂單估計 μ 和 Σ，不是用全部 500 筆？

用全部 500 筆的話，76 筆異常的極端值會把均值拉偏、把共變異矩陣撐大，導致異常訂單的 D² 被「稀釋」，反而看起來不那麼異常。只用 424 筆正常訂單估計，才能讓異常訂單的距離計算有意義。

### 6.5 與 Monte Carlo 的關係

```
Monte Carlo 生成 500 筆訂單（含正態的隨機性）
                ↓
Stage 3 從其中 424 筆正常訂單估計 μ、Σ
                ↓
對所有 500 筆計算 D²(x)
                ↓
D² 超過 χ² 門檻 → 標記為「數學邊界案例」
```

這樣的設計避免了「循環定義」：μ 和 Σ 的錨點來自 Mouser 真實價格（price_median_usd）決定的 Log-Normal 分佈，而不是從生成的資料本身自我定義。

---

## 七、500 筆的組成

```
424 筆  injection_plan = "none"  （正常訂單）
 76 筆  異常訂單，分 8 種：
         item_spending        13  單價 2.5x ~ 4x 偏高
         border_value         11  總金額刻意壓在審批門檻下（$950-999 / $4750-4999）
         conflict_of_interest 10  使用異常池供應商（2024 年成立）
         unusual_vendor       10  突然換用不熟悉的新供應商
         bank_account_change   9  金額拉高 > $2000（Stage 2 加語義線索）
         vendor_spending        9  跨單集中消費同一供應商（Stage 3 分析）
         approval_bypass        8  審批缺失或秒批（lag < 0.09 天）
         quote_manipulation     6  報價操控旗幟（文字隱藏型，Stage 2 語義植入）
─────────────────────────────────────────────────────────────────
合計                         500
```

---

## 八、審批門檻

| 金額 | 審批者 | ID |
|------|--------|-----|
| < USD 1,000 | 採購主管 | `A-PROC-01` |
| USD 1,000 – 5,000 | 技術長 | `A-CTO` |
| > USD 5,000 | 執行長 | `A-CEO` |

`border_value` 異常：把總金額壓在 $950–999 或 $4750–4999，讓低階審批者簽了本應更高層才能批的金額。

---

## 九、Q&A 自我測試

**Q1：Monte Carlo 跑幾次？**
> 每筆訂單做一次隨機抽樣（7 個欄位各抽一次），500 筆就是 500 輪。「Monte Carlo」指的是整個用隨機抽樣建立資料集的策略，不是跑一個固定迴圈幾千次。

**Q2：為什麼 price_median_usd 用幾何平均，不用算術平均？**
> Log-Normal 分佈的中心參數是 e^μ，剛好等於幾何平均。算術平均會被高價格拉偏，幾何平均不會。

**Q3：Mahalanobis 在 Stage 1 有算嗎？**
> 沒有。Stage 1 只生成資料。Mahalanobis 在 Stage 3 才算，需要先有正常訂單的樣本來估計 μ 和 Σ。

**Q4：RANDOM_SEED = 42 可以改嗎？**
> 可以，但改了之後 500 筆訂單會完全不同，後面所有分析都要重跑。論文提交前不要改。

**Q5：injection_plan = "none" 的訂單在 Stage 3 可能被標為異常嗎？**
> 可能。Mahalanobis 看的是統計距離，如果某筆「正常」訂單的 4 個特徵組合剛好落在 χ² 門檻外，它也會被標為邊界案例。這是正常的統計現象，不是 bug。

**Q6：為什麼算 σ 用 ln，最後卻說用 e^？**
> **σ 永遠是 ln(價格) 這個 Normal 的標準差**，所以範圍用 ln(高) − ln(低)。**e^** 只在把抽到的 z 變回「美元單價」時出現；兩步各司其職，沒有矛盾。

---

## 十、下一步路線圖（Next Steps）

你目前完成的是 **Stage 0 + Stage 1**，整個 Pipeline 共四個 Stage：

```
Stage 0  Mouser API 抓取真實零件價格 / 前置時間          ← 已完成（內嵌在 generate_dataset.py）
Stage 1  Monte Carlo 生成 500 筆合成採購訂單              ← 已完成（generate_dataset.py）
Stage 2  用 DeepSeek 生成語意欄位（description, reason）  ← 下一步
Stage 3  Qwen3 7B 本地做異常偵測（Mahalanobis Distance）  ← 最後一步
```

---

### Stage 2：生成語意欄位（`generate_semantics.py` 已實作）

Stage 1 已從 Mouser 寫入 **`item_description`**（API 的 `Description`）。Stage 2 補 Stage 1 留空的兩欄：

- **`purchase_note`**：採購備註／內部說明  
- **`supplier_profile`**：供應商側敘述

**運作方式：**

1. 自動找 `data/` 內最新的 `orders_<TS>.csv`（也可用 `--input` 指定）  
2. 每列建構 prompt：  
   - `injection_plan == "none"` → 中性、合理的內部備註  
   - `injection_plan != "none"` → 在備註裡**暗藏 PACE 線索**（如 `border_value` 暗示卡審批門檻、`unusual_vendor` 寫成新成立貿易公司…）  
3. 呼叫 DeepSeek `deepseek-chat`（OpenAI 相容 `/chat/completions`，`response_format=json_object`）  
4. 解析回傳 JSON `{purchase_note, supplier_profile}` 寫回 DataFrame  
5. **每 10 列自動 checkpoint**（`SAVE_EVERY`）；中斷後再執行會自動跳過已完成列  
6. 輸出檔：`data/orders_stage2_<同樣時間戳>.csv`

**金鑰**：從 env 讀 `DEEPSEEK_API_KEY`（已支援 `dataset/.env`）。

**執行：**

```powershell
python dataset\generate_semantics.py            # 處理最新 orders_*.csv
python dataset\generate_semantics.py --limit 5  # 只先跑 5 筆測試
python dataset\generate_semantics.py --input data\orders_20260420_015519.csv
```

**可調參數（檔頭常數）**：`LANGUAGE`（預設 `English`，可改 `Traditional Chinese`）、`TEMPERATURE`、`SAVE_EVERY`、`MAX_RETRIES`。

---

### Stage 3：異常偵測（Mahalanobis Distance + Qwen3 7B）

Stage 3 用 Stage 2 的完整資料集：

1. 從 `injection_plan == "none"` 的訂單計算 **μ（均值向量）** 和 **Σ（共變異數矩陣）**，特徵是：
   ```
   [unit_price_usd, quantity, approval_lag_days, expected_delivery_lag_days]
   ```
2. 對所有 500 筆訂單計算 Mahalanobis Distance
3. 設門檻（χ² 分佈，自由度 4）：
   - d < √χ²(0.95) → 正常
   - d > √χ²(0.99) → 異常
4. 輸出偵測結果，計算 Precision / Recall / F1（對比 `injection_plan` 的真實標籤）
5. Qwen3 7B 看偵測結果，用自然語言解釋每個異常的原因

---

### 現在建議的優先順序

1. **跑 Stage 2** — `python dataset\generate_semantics.py --limit 5` 先試 5 筆，確認 JSON 解析無誤、`.env` 讀得到 key、輸出檔出現。  
2. **跑全量 Stage 2** — `python dataset\generate_semantics.py`，500 筆約數分鐘；可 Ctrl+C，已完成列已落地。  
3. **抽檢輸出** — 打開 `data/orders_stage2_<TS>.csv`，挑幾筆 `injection_plan != "none"` 的列，看 `purchase_note` 是否有暗藏的 PACE 線索。  
4. **Stage 3** — 跑 `prepare_stage3.py`：用 stage2 xlsx 算 8 項偏差特徵 + Mahalanobis D²，再切成 15 題實驗樣本（UI 用）+ 485 筆 RAG 語料（JSONL）。不做偵測、不套用任何規則。

學術引用（Stage 1 異常注入規則來源）：  
> Westerski, A. *et al.* (2021). *PACE: Procurement Anomaly Detection at A\*STAR*. 本研究 8 種異常注入規則據此設計。

---

*最後更新：2026-04-21*  
*對應腳本：`generate_dataset.py`*
