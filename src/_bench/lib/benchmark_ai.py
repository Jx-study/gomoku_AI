"""熱點量測：各函數在單手 aiRound() 裡被呼叫幾次、耗時多久。

由 bench.py hotspots 呼叫 profile_hotspots()，插樁版的生成、編譯與刪除都在那裡。

檔案裡另有 bench_dll() 與 bench_repeated_position() 兩個早期的兩版計時對比，
以及呼叫它們的 __main__ 區塊。走法與速度對比現在用 bench.py moves，
__main__ 的預設路徑指向已刪除的 ai_baseline.dll / ai_optimized.dll。
"""
import ctypes
import time
import sys

import positions

# 棋盤大小由 dll 的 getBoardMax() 決定（ai.c 是唯一定義處），首次 bind_lib() 時填入
BOARD_MAX = None
CBoardType = None


def bind_lib(dll_path):
    """載入 dll、以它的 getBoardMax() 決定棋盤大小、綁好 ctypes 簽名。"""
    global BOARD_MAX, CBoardType
    lib = ctypes.CDLL(dll_path)
    try:
        lib.getBoardMax.restype = ctypes.c_int
        size = lib.getBoardMax()
    except AttributeError:
        sys.exit(f"error: {dll_path} 沒有 export getBoardMax()，無法得知它編譯時用的棋盤大小。\n"
                 f"       不確定兩顆 dll 在同樣大小的棋盤上比較時，數據沒有意義。\n"
                 f"       請改用有 getBoardMax() 的版本當基準。")
    if BOARD_MAX is None:
        BOARD_MAX = size
        CBoardType = (ctypes.c_int * BOARD_MAX) * BOARD_MAX
    elif size != BOARD_MAX:
        sys.exit(f"error: 兩顆 dll 的棋盤大小不同（{BOARD_MAX} vs {size}），無法對比")
    lib.initZobristTable.restype = None
    lib.aiRound.restype = None
    lib.aiRound.argtypes = [
        ctypes.POINTER(CBoardType),
        ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ]
    lib.initZobristTable()
    return lib


def make_board():
    return [[0] * BOARD_MAX for _ in range(BOARD_MAX)]


def to_c_board(board):
    c_board = CBoardType()
    for i in range(BOARD_MAX):
        for j in range(BOARD_MAX):
            c_board[i][j] = board[i][j]
    return c_board


def play(moves):
    board = make_board()
    for x, y, player in moves:
        board[y][x] = player
    return board


def scenarios():
    """量測用的盤面，定義在 positions.py（與 bench.py budget 同一組）。

    需要先呼叫過 bind_lib()，否則不知道棋盤中心在哪。
    """
    return positions.suite(BOARD_MAX)


def bench_dll(dll_path, label):
    lib = bind_lib(dll_path)

    print(f"\n=== {label} ({dll_path}) ===")
    results = []
    for name, moves in scenarios():
        board = play(moves)
        c_board = to_c_board(board)
        bestx = ctypes.c_int()
        besty = ctypes.c_int()
        round_counter = len(moves) + 1
        ai_player = 2  # 下一手輪到白棋（AI）

        t0 = time.perf_counter()
        lib.aiRound(ctypes.byref(c_board), ai_player, round_counter,
                    ctypes.byref(bestx), ctypes.byref(besty))
        t1 = time.perf_counter()
        elapsed = t1 - t0
        results.append(elapsed)
        print(f"  {name}: {elapsed:.3f}s  move=({bestx.value},{besty.value})")

    total = sum(results)
    print(f"  --- total: {total:.3f}s across {len(results)} distinct positions ---")
    return total


def bench_repeated_position(dll_path, label, repeats=3):
    """展示 Task 2（跨回合保留置換表）在『同一盤面重複被查詢』時的加速效果。
    注意：真實對局不會發生同盤面重複呼叫，這裡純粹是為了展示 TT 重用的效果。"""
    lib = bind_lib(dll_path)

    name, moves = scenarios()[-1]
    board = play(moves)
    print(f"\n=== {label}: repeated identical position ({name}) ===")
    for r in range(repeats):
        c_board = to_c_board(board)
        bestx = ctypes.c_int()
        besty = ctypes.c_int()
        t0 = time.perf_counter()
        lib.aiRound(ctypes.byref(c_board), 2, len(moves) + 1,
                    ctypes.byref(bestx), ctypes.byref(besty))
        t1 = time.perf_counter()
        print(f"  call {r+1}: {t1 - t0:.3f}s")


# 呼叫數超過這個量級的函數，秒數會被插樁開銷蓋過（見 profile_hotspots）
PROF_NOISY_CALLS = 100_000

# 插樁的函數：(顯示名, 計數器符號, 取秒數的函數名或 None)
PROFILED = [
    ("miniMax",       "g_miniMaxCalls",       None),
    ("sortMoves",     "g_sortMovesCalls",     "getSortMovesSeconds"),
    ("endGame",       "g_endGameCalls",       "getEndGameSeconds"),
    ("evaluate",      "g_evaluateCalls",      "getEvaluateSeconds"),
    ("quickEvaluate", "g_quickEvaluateCalls", "getQuickEvaluateSeconds"),
    ("checkWin",      "g_checkWinCalls",      "getCheckWinSeconds"),
    ("checkLine",     "g_checkLineCalls",     "getCheckLineSeconds"),
    ("judgeMove",     "g_judgeMoveCalls",     "getJudgeMoveSeconds"),
    ("hasAdjacent",   "g_hasAdjacentCalls",   "getHasAdjacentSeconds"),
    ("maxRunAt",      "g_maxRunAtCalls",      "getMaxRunAtSeconds"),
]


def profile_hotspots(dll_path="./ai_profiled.dll"):
    """量測各函數佔 aiRound 單手耗時的比例（需要 ai_profiled.dll）。

    整套流程由 `python bench.py hotspots` 代跑（生成、編譯、量測、刪掉生成物）。

    這些秒數是 inclusive 且互相巢狀的（checkLine 被 evaluate/sortMoves/endGame 呼叫），
    所以不能相加當 100%。每一行各自讀作「該函數的總耗時佔這一手的比例」。
    miniMax 是遞迴的，inclusive 時間等於整次搜索，因此只計次不計時。

    標了 * 的列（呼叫數超過 PROF_NOISY_CALLS）秒數不能用：checkLine 這類函數現在
    只有幾次陣列存取，一對 QueryPerformanceCounter 比它包住的函數還貴。
    這些列只讀呼叫數，工作量改用 bench.py budget。
    """
    lib = bind_lib(dll_path)
    lib.resetProfileCounters.restype = None
    for _, _, getter in PROFILED:
        if getter:
            getattr(lib, getter).restype = ctypes.c_double

    print(f"\n=== 熱點量測 ({dll_path}) ===")
    print("   秒數為 inclusive 且巢狀，不可相加")
    for name, moves in scenarios():
        lib.resetProfileCounters()
        board = play(moves)
        c_board = to_c_board(board)
        bestx = ctypes.c_int()
        besty = ctypes.c_int()

        t0 = time.perf_counter()
        lib.aiRound(ctypes.byref(c_board), 2, len(moves) + 1,
                    ctypes.byref(bestx), ctypes.byref(besty))
        wall = time.perf_counter() - t0

        print(f"\n  {name}: wall={wall:.3f}s")
        print(f"    {'function':<14}{'calls':>12}{'seconds':>10}{'share':>9}")
        noisy = False
        for fname, counter, getter in PROFILED:
            calls = ctypes.c_longlong.in_dll(lib, counter).value
            mark = "*" if calls > PROF_NOISY_CALLS else " "
            noisy = noisy or mark == "*"
            if getter:
                sec = getattr(lib, getter)()
                share = (sec / wall * 100) if wall > 0 else 0
                print(f"    {fname:<14}{calls:>12}{sec:>10.4f}{share:>7.1f}%{mark}")
            else:
                print(f"    {fname:<14}{calls:>12}{'-':>10}{'-':>8}{mark}")
        if noisy:
            print("    * 秒數主要是插樁本身，只讀呼叫數；工作量請用 bench.py budget")


if __name__ == "__main__":
    baseline = sys.argv[1] if len(sys.argv) > 1 else "./ai_baseline.dll"
    optimized = sys.argv[2] if len(sys.argv) > 2 else "./ai_optimized.dll"

    t_base = bench_dll(baseline, "BASELINE (pre Task1-3, commit 45464c3)")
    t_opt = bench_dll(optimized, "OPTIMIZED (Task1-3 applied)")

    print(f"\n=== Summary ===")
    print(f"  baseline total:  {t_base:.3f}s")
    print(f"  optimized total: {t_opt:.3f}s")
    if t_opt > 0:
        print(f"  speedup: {t_base / t_opt:.2f}x")

    bench_repeated_position(baseline, "BASELINE")
    bench_repeated_position(optimized, "OPTIMIZED")

    # 熱點量測（需先跑 gen_profiled.py 並編譯 ai_profiled.dll）
    import os
    if os.path.exists("./ai_profiled.dll"):
        profile_hotspots("./ai_profiled.dll")
    else:
        print("\n(略過熱點量測：找不到 ai_profiled.dll，"
              "改用 python bench.py hotspots）")
