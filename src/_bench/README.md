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
| `selfplay.py` | **兩版 dll 對打統計勝率。** 驗證「棋力有無退步」的唯一手段 |
| `benchmark_ai.py` | Task 1-3 時期的對照腳本。**獨有功能：** `evaluate()` 佔比量測（需 `ai_profiled.dll`） |
| `ai_profiled.c` | `ai.c` 的加計數器版本，供 `benchmark_ai.py` 量測 `evaluate()` 耗時佔比 |

### 用法

```bash
python ab_fresh.py <baseline.dll> [<new.dll>]   # new 預設 ../ai.dll
python ab.py       <baseline.dll> [<new.dll>]
python zob_key_probe.py [<dll> ...]             # 預設檢查 ../ai.dll

# evaluate() 佔比量測（判斷瓶頸在不在評估函數）
gcc -shared -o ai_profiled.dll -fPIC ai_profiled.c
python benchmark_ai.py <baseline.dll> [<new.dll>]

# 棋力對比（改動會改變走法時用這個，不是 ab_fresh.py）
cp ../ai.dll ./new.dll                 # 兩個路徑必須是不同檔案
python selfplay.py ./old.dll ./new.dll 20
```

### 該用 `ab_fresh.py` 還是 `selfplay.py`？

| 改動性質 | 用哪個 | 判準 |
|---|---|---|
| **行為保持**（重構、整數化、效能優化） | `ab_fresh.py` | 走法必須**完全相同** |
| **刻意改變棋力**（權重、排序、搜索策略） | `selfplay.py` | 走法本來就會不同，只能看**勝率** |

用錯工具會得到無意義的結論：對 A5b 這種調權重的改動跑 `ab_fresh.py`，只會看到一堆 `**DIFF**`，什麼也證明不了。

### `evaluate()` 佔比量測的用途

`benchmark_ai.py` 末段會輸出 `evaluate()` 佔 `aiRound()` 的時間比例。這是**決定要不要優化評估函數的依據**——實測顯示佔比僅 ~1%，因此
[01-engineering.md](../../Note/plans/Done/01-engineering.md) Task 4（增量式評估）評估後決定**不執行**。
未來若有大改動，重跑這項確認瓶頸是否已轉移，再決定要不要動 `evaluate()`。

## ⚠️ 兩個會讓你誤判的陷阱

**1. 同一個 process 內連續呼叫會互相污染。**
置換表是跨呼叫保留的，所以在 `ab.py` 裡「後面的盤面」會吃到前面留下的 TT entry，可能回報**假的走法差異**。判斷「走法有沒有變」一律以 `ab_fresh.py` 為準；`ab.py` 只適合看大略的速度趨勢。

**2. 基準版本要選對，否則會把多項改動算成一項。**
若工作區有尚未提交的改動，`git show HEAD:src/ai.c` 取到的**不是**「只差你這一項」的版本。要隔離單一改動的效果，應該從**當前版本**只還原那一項來當基準，而不是拿一個更舊的 commit。

（實例：`ai_baseline.c` 早於迭代加深與 TT bestMove，用它當基準會同時包含三項改動的差異，走法自然會不同——那不是退步。）

**3. 耗時 0.00x 秒的場景不是「很快」，是根本沒搜索。**
`benchmark_ai.py` 的 18/22/26 stones 場景會被 `sortMoves` 開頭的 `endGame` 快速路徑短路（找到立即勝著就直接回傳），完全不進 minimax。這些場景的時間數字不能用來判斷搜索效能——要量搜索，用 `ab_fresh.py` 裡那幾個沒有立即勝著的 `quiet-*` 盤面。

## 判讀標準

- **走法**：行為保持型的改動（重構、整數化）應該 **7 個場景全部 `OK`**。出現 `**DIFF**` 先確認不是上面兩個陷阱，再當成真的退步處理。
- **速度**：以 `ab_fresh.py` 的冷啟動數字為準。
