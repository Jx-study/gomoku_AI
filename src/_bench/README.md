# `_bench/` — AI 引擎效能與正確性驗證工具

這裡的腳本用來比對**兩個版本的 `ai.dll`**：確認一項改動有沒有加速、以及**走法有沒有改變**。
沒有自動化測試框架，這是目前驗證引擎改動的主要手段。

`*.dll` 被 `.gitignore` 排除，所以本目錄只有原始碼與腳本；要跑之前得先自己編譯出對照用的 dll。

## 取出歷史版本來對照

`ai.dll` 從未進版控，但 `ai.c` 有。要拿任一歷史版本當基準：

```bash
git show <commit>:src/ai.c > old.c
gcc -shared -o old.dll -fPIC old.c
```

## 工具

| 檔案 | 用途 |
|---|---|
| `ab_fresh.py` | **建議優先用這個。** 每個盤面各開一個全新 process 比對兩版 dll |
| `ab.py` | 同上，但全部在同一個 process 跑（較快，但見下方警告） |
| `_one.py` | `ab_fresh.py` 自動產生的 worker，不要手動執行或刪除 |
| `zob_key_probe.py` | 探測 `currentZobristKey` 是否與實際盤面相符（Zobrist 正確性） |
| `benchmark_ai.py` | 舊版對照腳本（Task 1-3 時期），場景較容易被 `endGame` 短路 |
| `ai_baseline.c` / `ai_optimized.c` / `ai_profiled.c` | Task 1-3 時期的歷史快照；`ai_profiled.c` 內含 `evaluate()` 計時器 |

### 用法

```bash
python ab_fresh.py <baseline.dll> [<new.dll>]   # new 預設 ../ai.dll
python ab.py       <baseline.dll> [<new.dll>]
python zob_key_probe.py [<dll> ...]             # 預設檢查 ../ai.dll
```

## ⚠️ 兩個會讓你誤判的陷阱

**1. 同一個 process 內連續呼叫會互相污染。**
置換表是跨呼叫保留的，所以在 `ab.py` 裡「後面的盤面」會吃到前面留下的 TT entry，可能回報**假的走法差異**。判斷「走法有沒有變」一律以 `ab_fresh.py` 為準；`ab.py` 只適合看大略的速度趨勢。

**2. 基準版本要選對，否則會把多項改動算成一項。**
若工作區有尚未提交的改動，`git show HEAD:src/ai.c` 取到的**不是**「只差你這一項」的版本。要隔離單一改動的效果，應該從**當前版本**只還原那一項來當基準，而不是拿一個更舊的 commit。

（實例：`ai_baseline.c` 早於迭代加深與 TT bestMove，用它當基準會同時包含三項改動的差異，走法自然會不同——那不是退步。）

## 判讀標準

- **走法**：行為保持型的改動（重構、整數化）應該 **7 個場景全部 `OK`**。出現 `**DIFF**` 先確認不是上面兩個陷阱，再當成真的退步處理。
- **速度**：以 `ab_fresh.py` 的冷啟動數字為準。
