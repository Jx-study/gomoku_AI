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

BOARD_MAX = 22
CBoardType = (ctypes.c_int * BOARD_MAX) * BOARD_MAX


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


# 基礎中局走法序列
BASE_MOVES = [
    (11, 11, 1), (11, 12, 2), (12, 12, 1), (10, 10, 2),
    (13, 13, 1), (10, 12, 2), (9, 9, 1), (12, 10, 2),
    (14, 14, 1), (9, 13, 2), (12, 13, 1), (11, 13, 2),
    (13, 11, 1), (14, 10, 2),
]

EXTRA_MOVES = [
    (15, 9, 1), (8, 14, 2), (10, 9, 1), (13, 9, 2),
    (16, 8, 1), (7, 15, 2), (11, 9, 1), (12, 9, 2),
    (9, 11, 1), (15, 13, 2), (8, 8, 1), (16, 16, 2),
]

# 5 個「不同」盤面（同一開局，逐步加深），避免同盤面重複呼叫造成置換表
# 命中而失真——每個都只測一次（冷快取），比較接近真實對局中每手都不同盤面的情況。
DISTINCT_SCENARIOS = []
for i in range(0, len(EXTRA_MOVES) + 1, 4):
    moves = BASE_MOVES + EXTRA_MOVES[:i]
    DISTINCT_SCENARIOS.append((f"{len(moves)} stones", moves))


def bench_dll(dll_path, label):
    lib = ctypes.CDLL(dll_path)
    lib.initZobristTable.restype = None
    lib.aiRound.restype = None
    lib.aiRound.argtypes = [
        ctypes.POINTER(ctypes.c_int * BOARD_MAX * BOARD_MAX),
        ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ]
    lib.initZobristTable()

    print(f"\n=== {label} ({dll_path}) ===")
    results = []
    for name, moves in DISTINCT_SCENARIOS:
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
    lib = ctypes.CDLL(dll_path)
    lib.initZobristTable.restype = None
    lib.aiRound.restype = None
    lib.aiRound.argtypes = [
        ctypes.POINTER(ctypes.c_int * BOARD_MAX * BOARD_MAX),
        ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ]
    lib.initZobristTable()

    name, moves = DISTINCT_SCENARIOS[-1]
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
    lib = ctypes.CDLL(dll_path)
    lib.initZobristTable.restype = None
    lib.aiRound.restype = None
    lib.aiRound.argtypes = [
        ctypes.POINTER(ctypes.c_int * BOARD_MAX * BOARD_MAX),
        ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ]
    lib.resetProfileCounters.restype = None
    lib.getEvaluateSeconds.restype = ctypes.c_double
    lib.initZobristTable()

    print(f"\n=== 方案 B: evaluate() 佔比量測 ({dll_path}) ===")
    for name, moves in DISTINCT_SCENARIOS:
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
