"""
效能對比腳本：比較優化前（baseline, commit 45464c3）與優化後（optimized, Task1-3）
的 aiRound() 思考時間。

用法:
    cd src/_bench
    python benchmark_ai.py

需要先準備好 ai_baseline.dll 與 ai_optimized.dll（放在本目錄下，或用參數指定路徑）：
    gcc -shared -o ai_baseline.dll -fPIC ai_baseline.c
    gcc -shared -o ai_optimized.dll -fPIC ai_optimized.c
"""
import ctypes
import time
import sys

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


# 基礎中局走法序列，以中心點的偏移表示（換棋盤大小不必重寫座標）
BASE_OFFSETS = [
    (0, 0, 1), (0, 1, 2), (1, 1, 1), (-1, -1, 2),
    (2, 2, 1), (-1, 1, 2), (-2, -2, 1), (1, -1, 2),
    (3, 3, 1), (-2, 2, 2), (1, 2, 1), (0, 2, 2),
    (2, 0, 1), (3, -1, 2),
]

EXTRA_OFFSETS = [
    (4, -2, 1), (-3, 3, 2), (-1, -2, 1), (2, -2, 2),
    (5, -3, 1), (-4, 4, 2), (0, -2, 1), (1, -2, 2),
    (-2, 0, 1), (4, 2, 2), (-3, -3, 1), (5, 5, 2),
]


def scenarios():
    """5 個「不同」盤面（同一開局，逐步加深），避免同盤面重複呼叫造成置換表
    命中而失真——每個都只測一次（冷快取），比較接近真實對局中每手都不同盤面的情況。

    需要先呼叫過 bind_lib()，否則不知道棋盤中心在哪。
    """
    c = BOARD_MAX // 2
    base = [(c + dx, c + dy, p) for dx, dy, p in BASE_OFFSETS]
    extra = [(c + dx, c + dy, p) for dx, dy, p in EXTRA_OFFSETS]
    out = []
    for i in range(0, len(extra) + 1, 4):
        moves = base + extra[:i]
        out.append((f"{len(moves)} stones", moves))
    return out


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
]


def profile_hotspots(dll_path="./ai_profiled.dll"):
    """量測各函數佔 aiRound 單手耗時的比例（需要 ai_profiled.dll）。

    先跑：python gen_profiled.py && gcc -shared -o ai_profiled.dll -fPIC ai_profiled.c

    這些秒數是 inclusive 且互相巢狀的（checkLine 被 evaluate/sortMoves/endGame 呼叫），
    所以不能相加當 100%。每一行各自讀作「該函數的總耗時佔這一手的比例」。
    miniMax 是遞迴的，inclusive 時間等於整次搜索，因此只計次不計時。

    呼叫次數極高的函數（checkLine、judgeMove）的佔比含計時本身的開銷，會偏高。
    排名可信，絕對數字不可信。
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
        for fname, counter, getter in PROFILED:
            calls = ctypes.c_longlong.in_dll(lib, counter).value
            if getter:
                sec = getattr(lib, getter)()
                share = (sec / wall * 100) if wall > 0 else 0
                print(f"    {fname:<14}{calls:>12}{sec:>10.4f}{share:>8.1f}%")
            else:
                print(f"    {fname:<14}{calls:>12}{'-':>10}{'-':>9}")


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
              "先跑 python gen_profiled.py && gcc -shared -o ai_profiled.dll -fPIC ai_profiled.c)")
