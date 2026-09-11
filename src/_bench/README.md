# AI 引擎效能與正確性驗證工具

比對兩個版本的 `ai.dll`：一項改動有沒有加速、走法有沒有改變、棋力有沒有退步。
規則與狀態層的自動化測試在 `../tests/`（pytest），這裡只處理 pytest 測不到的部分。

入口是 `bench.py`，實作在 `lib/`。`python bench.py --help` 列出子命令，`python bench.py <子命令> --help` 顯示該命令的參數與判讀標準。

## 前置

`*.dll` 被 `.gitignore` 排除，本目錄只有原始碼與腳本，對照用的 dll 要自己編譯。基準 dll 不預先留著，量測前依當下要隔離的改動，從對應的提交現編一顆：

```bash
git show <commit>:src/ai.c > old.c
gcc -shared -o old.dll -fPIC old.c
```

- `../ai.dll` 是現行版，也是 `bench.py` 的預設對照組；基準 dll 找不到時會報錯
- 棋盤大小一律向 dll 問（`getBoardMax()`），盤面座標以中心點的偏移表示，改了 `ai.c` 的 `BOARD_MAX` 之後腳本不需要跟著改
- 兩個 dll 的棋盤大小不同時會直接報錯
- `bench.py` 會把路徑轉成絕對路徑再交給子腳本，在哪個目錄執行都可以
- 本文件的範例都寫成在 `src/_bench/` 底下執行；`pytest` 例外，要在 repo 根目錄跑

## 子命令

| 子命令 | 回答的問題 | 實作 |
|---|---|---|
| `moves` | 走法有沒有變 | `lib/ab_fresh.py`（每盤面各開一個新 process）與它產生的 `lib/_one.py` |
| `strength` | 棋力有沒有退步 | `lib/selfplay.py`、`lib/openings_rif.py`（RIF 開局池，含旋轉與鏡像變體） |
| `budget` | 下一個該優化誰 | `lib/count_budget.py` |
| `cells` | `checkLine` 每次讀幾格 | `lib/count_cells.py` |
| `hotspots` | 各函數被呼叫幾次 | `lib/gen_profiled.py`、`lib/ai_profiled.c`、`lib/benchmark_ai.py` |

- `lib/positions.py` 是量測用盤面清單的唯一定義處，`budget` 與 `hotspots` 共用
- `lib/ai_profiled.c` 是插樁的 wrapper 層，不含引擎邏輯的複本
- `lib/` 裡的模組都留著 `__main__` 區塊，除錯時可以 `python lib/count_budget.py` 直接跑，但文件與流程一律走 `bench.py`，路徑處理與參數檢查都在那裡

Zobrist 的正確性由 pytest 涵蓋（`../tests/test_zobrist.py`），測三件事：

- key 的位元熵
- 逐手 XOR 與整盤重算是否一致
- 不同手順走到同一盤面是否得到同一把 key

## 用法

```bash
python bench.py --help

# 走法有沒有變
git show <commit>:src/ai.c > base.c     # 基準：只差要隔離的那一項的提交
gcc -shared -o base.dll -fPIC base.c
python bench.py moves ./base.dll        # 新版預設 ../ai.dll

# 棋力有沒有退步
cp ../ai.dll ./new.dll                 # 兩個路徑必須是不同檔案，new.dll 用完可刪
python bench.py strength ./base.dll ./new.dll [games] [--quiet] [--pgn out.pgn]

# 下一個該優化誰
python bench.py budget                 # 量現行 ../ai.c
git show <commit>:src/ai.c > base.c
python bench.py budget base.c          # 量歷史版本，兩次輸出自己比

# checkLine 每次讀幾格；基準不給則用 HEAD:src/ai.c
python bench.py cells
python bench.py cells base.c

# 各函數被呼叫幾次；插樁產物自動生成、量完刪除
python bench.py hotspots
```

pytest 讀 repo 根目錄的 `pytest.ini`，要在根目錄執行：

```bash
pytest src/tests/test_zobrist.py
```

## 該用 `moves` 還是 `strength`

| 改動性質 | 用哪個 | 判準 |
|---|---|---|
| 行為保持（重構、整數化、效能優化） | `moves` | 走法必須完全相同 |
| 刻意改變棋力（權重、排序、搜索策略） | `strength` | 走法本來就會不同，只能看勝率 |

對調權重這類改動跑 `moves` 只會得到一堆 `DIFF`，對判斷棋力沒有幫助。

## 熱點量測

`hotspots` 判斷哪個函數被呼叫得最多。流程是生成、編譯、量測、刪除生成物，`bench.py` 一次做完：

- `lib/gen_profiled.py` 讀 `ai.c`，把目標函數的定義改名為 `prof_real_*`，呼叫處維持原名，
  輸出 `lib/ai_profiled_core.generated.c`（不入版控）
- `lib/ai_profiled.c` 只是 wrapper：`#include` 生成檔，用原名定義同簽名的函數，
  記錄呼叫次數與耗時後轉呼叫 `prof_real_*`。連結時 `ai.c` 內部的呼叫會綁到 wrapper
- `ai.c` 不必修改，每次量測都重新生成

不能用 `#define evaluate prof_real_evaluate` 改名：那會把定義與 `ai.c` 內部的呼叫一起改掉，內部呼叫跳過 wrapper，所有計數器恆為 0，編譯沒有警告。

`ai.c` 的目標函數若改名或改簽名，`gen_profiled.py` 會以非 0 結束並印出是哪個函數抽不到簽名。

插樁的函數：`miniMax`（遞迴，只計次）、`sortMoves`、`endGame`、`evaluate`、`quickEvaluate`、`checkWin`、`checkLine`、`judgeMove`、`hasAdjacentPiece`、`maxRunAt`。

計時用 `QueryPerformanceCounter`；`clock()` 在 Windows 的粒度太粗，量 `checkLine` 會全部讀成 0。

### 數字的意義

- 秒數是 inclusive 且互相巢狀的（`checkLine` 被 `evaluate`、`sortMoves`、`endGame` 各處呼叫），不能相加當 100%
- 每一行讀作「該函數的總耗時佔這一手的比例」
- 呼叫數上萬的函數，秒數已經不能用，這些列會標 `*`：只讀呼叫數，工作量改用 `bench.py budget`

秒數失效是因為一對 `QueryPerformanceCounter` 比 `checkLine` 這種只有幾次陣列存取的函數還貴，插樁本身就蓋過被量的對象。

## 確定性指標

`checkLine` 單次只有幾十奈秒，這個尺度的計時不準：CPU 頻率、排程、cache 狀態、背景程序都會蓋過真正的差異，同一組執行檔重跑，新舊比值可以跳到連哪一版比較快都翻面。`budget` 與 `cells` 改量「做了多少工作」，數字跑幾次都一樣。

`bench.py budget` 量整場搜索，盤面取自 `lib/positions.py`，與 `hotspots` 同一組：

- `hasAdjacentPiece`、`checkLine`、`winsAt` 三個索引/掃描來源各讀了幾格、各佔多少
- `maxRunAt` 已不在生產路徑，讀格數恆為 0
- 增量維護划不划算的門檻判定

`bench.py cells` 只量 `checkLine`，兩個版本對比。它不跑 `aiRound`，而是用固定種子隨機鋪子掃四個密度（子數 8、18、50、80）：

```
每次 checkLine 讀取的盤面格數（確定性，重跑結果相同）

子數           before        after       比值
...

before = HEAD:src/ai.c（逐格掃描）
after  = ../ai.c（查表）
```

掃四個密度是因為兩種實作對密度的反應不同：查表版恆定（四方向各掃滿 10 格才能得到 3 進制索引，少讀一格索引就錯位），逐格掃描版隨盤面變密而略升（遇對手子或連續兩空格就 `break`，盤面越滿要掃越遠才停）。

做法與 `lib/gen_profiled.py` 相同：讀 `ai.c`、只在存取處插一個計數器、`ai.c` 本身不修改、每次執行重新生成。探針找不到對應位置時會以非 0 結束。

兩版若是同一種實作（都查表或都掃描），比值恆為 1.00x，腳本會直接說基準選錯了。

### 什麼時候用哪一種

| 想知道的事 | 用什麼 |
|---|---|
| 下一個該優化誰 | `bench.py budget` 的存取預算 |
| 某個改動讓工作變多還變少 | `bench.py budget`，或 `bench.py cells`（只針對 `checkLine`） |
| 各函數被呼叫幾次 | `bench.py hotspots` 的呼叫數欄 |
| 使用者實際等多久 | `bench.py moves` 的冷啟動秒數 |

要證明某個函數變快了，看確定性證據。秒數只有在差異大到蓋過雜訊時才可用。

## 可能誤判的陷阱

**1. 同一個 process 內連續呼叫會互相污染。**

置換表跨呼叫保留，同一個 process 裡後面的盤面會吃到前面留下的 TT entry。

- 判斷走法有沒有變一律以 `bench.py moves` 為準，它每個盤面各開一個新 process
- `hotspots` 與 `budget` 是同 process 連跑，秒數只能看趨勢
- `budget` 的計數不受影響：污染改變的是搜索量，兩版跑同一組盤面時仍可比

**2. 基準版本要選對，否則會把多項改動算成一項。**

工作區若有尚未提交的改動，`git show HEAD:src/ai.c` 取到的不是「只差你這一項」的版本。要隔離單一改動，應該從當前版本只還原那一項當基準，而不是拿一個更舊的 commit。

**3. 耗時接近 0 的盤面是沒有搜索，不是搜索得快。**

`hotspots` 與 `budget` 的部分盤面會被 `sortMoves` 開頭的 `endGame` 快速路徑短路（找到立即勝著就直接回傳），完全不進 minimax，時間不能用來判斷搜索效能。要量搜索就看 `quiet-*` 那三個沒有立即勝著的盤面（`moves` 用的也是這組）。

**4. selfplay 的勝率解析度有限。**

引擎是確定性的（固定 Zobrist 種子、每局清 TT、開局腳本化），同一個開局永遠打同一盤棋。

- 局數開超過「開局數 × 2」只是重播
- 配對設計（每個開局黑白各打一次）會消掉開局與先手的偏差
- 解析度該以配對差異估算，不是拿總局數套二項式標準誤
- 個位數百分點的差異這個 harness 分辨不出來

## 判讀標準

- **走法**（`moves`）：行為保持型的改動應該全部場景 `OK`。出現 `DIFF` 先確認不是陷阱 1、2，再當成退步處理。
- **工作量**（`budget`、`cells`）：涉及掃描方式的改動先看存取格數。`moves` 的冷啟動秒數只有在差異大到蓋過雜訊時才可用。
- **棋力**（`strength`）：勝率只當迴歸看有沒有明顯變差。要證明某項改動有效，看不受勝率雜訊影響的直接證據，例如算殺類改動量「假勝次數」。
