# AI 引擎效能與正確性驗證工具

這裡的腳本用來比對兩個版本的 `ai.dll`：確認一項改動有沒有加速、以及走法有沒有改變。
規則與狀態層的自動化測試在 `../tests/`（pytest）；這裡處理那些測不到的東西——速度、棋力。

`*.dll` 被 `.gitignore` 排除，所以本目錄只有原始碼與腳本；要跑之前得先自己編譯出對照用的 dll。

**除非另有註明，本文件的指令都在 `src/_bench/` 底下執行**（`pytest` 是例外，見下）。
文中的 `ai.c` 一律指引擎原始碼 `../ai.c`；`git show` 那類指令的路徑則是 repo 相對。

棋盤大小一律向 dll 問（`getBoardMax()`），盤面座標都以中心點的偏移寫死，所以改 `ai.c` 的
`BOARD_MAX` 之後這些腳本不需要跟著改。兩顆 dll 的棋盤大小不同時會直接報錯而不是給出錯誤數據。

## 取出歷史版本來對照

`ai.dll` 從未進版控，但 `ai.c` 有。要拿任一歷史版本當基準：

```bash
git show <commit>:src/ai.c > old.c
gcc -shared -o old.dll -fPIC old.c
```

## 工具

| 檔案 | 用途 |
|---|---|
| `ab_fresh.py` | 建議優先用這個。每個盤面各開一個全新 process 比對兩版 dll |
| `ab.py` | 同上，但全部在同一個 process 跑（較快，但見下方陷阱 1） |
| `_one.py` | `ab_fresh.py` 自動產生的 worker，不要手動執行或刪除 |
| `selfplay.py` | 兩版 dll 對打統計勝率。驗證「棋力有無退步」的唯一手段 |
| `openings_rif.py` | `selfplay.py` 用的 RIF 開局池（含旋轉與鏡像變體） |
| `benchmark_ai.py` | 對照腳本，另含 `profile_hotspots()` 熱點量測（需 `ai_profiled.dll`） |
| `gen_profiled.py` | 從 `ai.c` 生成插樁用的中間檔。編譯 `ai_profiled.dll` 前必須先跑 |
| `ai_profiled.c` | wrapper 層：計數器與計時，`#include` 生成檔。不含引擎邏輯的複本 |

Zobrist 的正確性改由 pytest 涵蓋：`../tests/test_zobrist.py`（key 的位元熵、逐手 XOR 與整盤
重算是否一致、不同手順走到同一盤面是否得到同一把 key）。原本的 `zob_key_probe.py` 探測的是
Python 端逐手同步 `updateZobristKey` 的情境，該同步已經移除，腳本連同其前提一併刪掉。

## 用法

以下都在 `src/_bench/` 執行：

```bash
python ab_fresh.py <baseline.dll> [<new.dll>]   # new 預設 ../ai.dll
python ab.py       <baseline.dll> [<new.dll>]

# 熱點量測（判斷瓶頸在哪個函數）
python gen_profiled.py                                  # 改完 ai.c 要重跑
gcc -shared -o ai_profiled.dll -fPIC ai_profiled.c
python benchmark_ai.py <baseline.dll> [<new.dll>]

# 棋力對比（改動會改變走法時用這個，不是 ab_fresh.py）
cp ../ai.dll ./new.dll                 # 兩個路徑必須是不同檔案
python selfplay.py ./old.dll ./new.dll
```

pytest 讀 repo 根目錄的 `pytest.ini`，要在**根目錄**執行：

```bash
pytest src/tests/test_zobrist.py     # Zobrist 正確性，不需要編對照組
```

## 該用 `ab_fresh.py` 還是 `selfplay.py`？

| 改動性質 | 用哪個 | 判準 |
|---|---|---|
| 行為保持（重構、整數化、效能優化） | `ab_fresh.py` | 走法必須完全相同 |
| 刻意改變棋力（權重、排序、搜索策略） | `selfplay.py` | 走法本來就會不同，只能看勝率 |

用錯工具會得到無意義的結論：對調權重這類改動跑 `ab_fresh.py`，只會看到一堆 `DIFF`，什麼也證明不了。

## 熱點量測

判斷瓶頸落在哪個函數，是「要不要優化某個函數」的決策依據。

原本的 `ai_profiled.c` 是 `ai.c` 的整份複本，落後主線好幾個版本後照樣編譯得過，量的卻是另一顆
引擎——複製整份原始碼再改，這個做法本身就是陷阱。已改成生成式：

- `gen_profiled.py` 讀 `ai.c`，只把目標函數的定義改名為 `prof_real_*`（呼叫處維持原名），
  輸出 `ai_profiled_core.generated.c`（gitignore，不入版控）
- `ai_profiled.c` 只剩 wrapper：`#include` 生成檔，用原名定義同簽名的函數，記錄呼叫次數
  與耗時後轉呼叫 `prof_real_*`。連結時 `ai.c` 內部的呼叫自然綁到 wrapper
- `ai.c` 完全不必修改，每次編譯都重新生成，不會再漂

不能用 `#define evaluate prof_real_evaluate` 這種改名法：那會把定義與 `ai.c` 內部的呼叫一起
改掉，內部呼叫直接跳過 wrapper，所有計數器恆為 0，而且編譯毫無警告。

漂移防護：`ai.c` 的目標函數若改名或改簽名，`gen_profiled.py` 會以非 0 結束並印出是哪個函數
抽不到簽名，不會靜默產出錯的數字。

插樁的函數：`miniMax`（遞迴，只計次）、`sortMoves`、`endGame`、`evaluate`、`quickEvaluate`、
`checkWin`、`checkLine`、`judgeMove`。

計時用 `QueryPerformanceCounter`（`clock()` 在 Windows 粒度太粗，量 `checkLine` 會整片讀成 0）。

### 熱點數字的判讀

秒數是 inclusive 且互相巢狀的（`checkLine` 被 `evaluate`、`sortMoves`、`endGame` 各處呼叫），
不能相加當 100%。每一行各自讀作「該函數的總耗時佔這一手的比例」。

呼叫次數極高的函數（`checkLine`、`judgeMove`）的佔比含計時本身的開銷，會偏高。排名可信，
絕對數字不可信——拿它去估「查表化能省多少」會高估。

## 可能誤判的陷阱

**1. 同一個 process 內連續呼叫會互相污染。**
置換表是跨呼叫保留的，所以在 `ab.py` 裡「後面的盤面」會吃到前面留下的 TT entry，可能回報假的
走法差異。判斷「走法有沒有變」一律以 `ab_fresh.py` 為準；`ab.py` 只適合看大略的速度趨勢。

**2. 基準版本要選對，否則會把多項改動算成一項。**
若工作區有尚未提交的改動，`git show HEAD:src/ai.c` 取到的不是「只差你這一項」的版本。要隔離
單一改動的效果，應該從當前版本只還原那一項來當基準，而不是拿一個更舊的 commit。

**3. 耗時接近 0 的場景不是「很快」，是根本沒搜索。**
`benchmark_ai.py` 的部分場景會被 `sortMoves` 開頭的 `endGame` 快速路徑短路（找到立即勝著就
直接回傳），完全不進 minimax。這些場景的時間數字不能用來判斷搜索效能——要量搜索，用
`ab_fresh.py` 裡那幾個沒有立即勝著的 `quiet-*` 盤面。

**4. selfplay 的勝率解析度有限。**
引擎是確定性的（固定 Zobrist 種子、每局清 TT、開局腳本化），同一個開局永遠打同一盤棋，所以
局數開超過「開局數 × 2」只是重播，不增加資訊。配對設計（每個開局黑白各打一次）會消掉開局與
先手的偏差，解析度該以配對差異估算，不是拿總局數套二項式標準誤。個位數百分點的差異這個
harness 分辨不出來，別拿它當單一的通過或否決依據。

## 判讀標準

- **走法**：行為保持型的改動（重構、整數化）應該全部場景 `OK`。出現 `DIFF` 先確認不是上面的
  陷阱 1、2，再當成真的退步處理。
- **速度**：以 `ab_fresh.py` 的冷啟動數字為準。
- **棋力**：`selfplay.py` 的勝率只當迴歸看有沒有明顯變差；要證明某項改動有效，優先找不受勝率
  雜訊影響的直接證據（例如算殺類改動量「假勝次數」）。
