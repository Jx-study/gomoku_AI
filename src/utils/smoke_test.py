"""發版前的執行期驗證：載入共享庫，跑一次 aiRound，確認回傳合法座標。

用法：python utils/smoke_test.py <共享庫路徑>
exit 0 = 通過；非 0 = 失敗
"""
import ctypes
import sys


def main(lib_path):
    lib = ctypes.CDLL(lib_path)

    # BOARD_MAX 唯一定義處是 lib/types.h，一律從庫讀，不寫死
    lib.getBoardMax.restype = ctypes.c_int
    board_max = lib.getBoardMax()

    lib.initZobristTable.restype = None
    lib.initTranspositionTable.restype = None
    lib.aiRound.restype = None
    lib.aiRound.argtypes = [
        ctypes.POINTER(ctypes.c_int * board_max * board_max),
        ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ]

    # 未初始化就呼叫 aiRound 會讀到未初始化的 Zobrist table 與置換表
    lib.initZobristTable()
    lib.initTranspositionTable()

    board = ((ctypes.c_int * board_max) * board_max)()
    mid = board_max // 2
    board[mid][mid] = 1   # 中心一顆黑子，讓 AI 有可回應的局面

    bestx, besty = ctypes.c_int(), ctypes.c_int()
    # ai=2（白）、roundCounter=2：黑已下第 1 手，輪到 AI 下第 2 手
    lib.aiRound(ctypes.byref(board), 2, 2, ctypes.byref(bestx), ctypes.byref(besty))

    x, y = bestx.value, besty.value
    print(f"aiRound returned ({x}, {y}), BOARD_MAX={board_max}")

    # 0-indexed，合法範圍 0 ~ board_max-1
    if not (0 <= x < board_max and 0 <= y < board_max):
        print(f"FAIL: 座標超出合法範圍 0-{board_max - 1}", file=sys.stderr)
        return 1
    if board[y][x] != 0:
        print(f"FAIL: AI 走在已有棋子的位置 ({x}, {y})", file=sys.stderr)
        return 1

    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
