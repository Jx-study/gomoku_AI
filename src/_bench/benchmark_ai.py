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


def profile_evaluate_share(dll_path="./ai_profiled.dll"):
    """方案 B：量測 evaluate() 是否仍是瓶頸（需要 ai_profiled.dll，見 ai_profiled.c）。
    回報 evaluate() 佔 aiRound() 總耗時的比例，以及 evaluate 呼叫次數 / miniMax 節點數的比例。"""
    lib = bind_lib(dll_path)
    lib.resetProfileCounters.restype = None
    lib.getEvaluateSeconds.restype = ctypes.c_double

    print(f"\n=== 方案 B: evaluate() 佔比量測 ({dll_path}) ===")
    for name, moves in scenarios():
        lib.resetProfileCounters()
        board = play(moves)
        c_board = to_c_board(board)
        bestx = ctypes.c_int()
        besty = ctypes.c_int()

        t0 = time.perf_counter()
        lib.aiRound(ctypes.byref(c_board), 2, len(moves) + 1,
                    ctypes.byref(bestx), ctypes.byref(besty))
        t1 = time.perf_counter()
        wall = t1 - t0

        eval_calls = ctypes.c_longlong.in_dll(lib, "g_evaluateCalls").value
        minimax_calls = ctypes.c_longlong.in_dll(lib, "g_miniMaxCalls").value
        eval_seconds = lib.getEvaluateSeconds()

        share = (eval_seconds / wall * 100) if wall > 0 else 0
        node_ratio = (eval_calls / minimax_calls * 100) if minimax_calls > 0 else 0
        print(f"  {name}: wall={wall:.3f}s  evaluate_time={eval_seconds:.3f}s ({share:.1f}%)  "
              f"evaluate_calls={eval_calls}  miniMax_nodes={minimax_calls} (leaf ratio {node_ratio:.1f}%)")


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

    # Task 4 方案 B：量測 evaluate() 是否仍是瓶頸（需先編譯 ai_profiled.dll）
    import os
    if os.path.exists("./ai_profiled.dll"):
        profile_evaluate_share("./ai_profiled.dll")
