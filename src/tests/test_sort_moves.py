"""`sortMoves` 候選生成的回歸測試。

背景見 Note/technical/loss-analysis-jump-three-gap.md：AI 執黑對局，白棋在
y=9 這一行擺出 `..WW.W..`（兩端皆空的跳三，`classifyWindow` 碼 11，偏活
跳三），AI 該防守的缺口 (4,9) 因為候選生成的高優先防守策略只認
`op_now[3]`/`op_now[9]`（活三／跳活三），漏掉了 `op_now[11]`，從未進入
候選列表，最終輸棋。

本檔驗證兩件事：
1. 該缺口點確實在 `sortMoves` 的候選列表中，且排在最前面（防守策略分數）。
2. 用該局面完整重放，`classifyWindow`/`checkLine` 把這個跳三正確分類成
   碼 11（見 test_pattern_table.py 的對應單元測試），本檔只驗候選生成
   這一層有沒有把它撿起來。

需要先編譯共享庫：
    cd src && gcc -shared -o ai.dll -fPIC zobrist.c pattern.c boardstate.c lines.c eval.c movegen.c vcf.c search.c ai.c
找不到時整個模組會被 skip。
"""
import ctypes
import os
import platform

import pytest

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BLACK = 1
WHITE = 2


def _lib_filename():
    system = platform.system()
    if system == "Windows":
        return "ai.dll"
    if system == "Darwin":
        return "libai.dylib"
    return "libai.so"


LIB_PATH = os.path.join(SRC_DIR, _lib_filename())

pytestmark = pytest.mark.skipif(
    not os.path.exists(LIB_PATH),
    reason=f"{_lib_filename()} 未編譯；先執行 gcc -shared -o ai.dll -fPIC zobrist.c pattern.c boardstate.c lines.c eval.c movegen.c vcf.c search.c ai.c",
)


class Move(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int), ("score", ctypes.c_int)]


@pytest.fixture(scope="module")
def sort_moves():
    """回傳 sort_moves(stones, player) -> [(x, y, score), ...]，依分數降冪。"""
    lib = ctypes.CDLL(LIB_PATH)
    lib.getBoardMax.restype = ctypes.c_int
    board_max = lib.getBoardMax()
    board_type = (ctypes.c_int * board_max) * board_max

    lib.sortMoves.restype = None
    lib.sortMoves.argtypes = [
        ctypes.POINTER(board_type),
        ctypes.POINTER(Move * (board_max * board_max)),
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int,
    ]
    lib.getBounds.restype = None
    lib.getBounds.argtypes = [ctypes.POINTER(board_type)] + [ctypes.POINTER(ctypes.c_int)] * 4

    def _call(stones, player):
        board = board_type()
        for x, y, colour in stones:
            board[y][x] = colour
        min_x, max_x, min_y, max_y = (ctypes.c_int() for _ in range(4))
        lib.getBounds(ctypes.byref(board), ctypes.byref(min_x), ctypes.byref(max_x),
                      ctypes.byref(min_y), ctypes.byref(max_y))
        moves = (Move * (board_max * board_max))()
        count = ctypes.c_int(0)
        lib.sortMoves(ctypes.byref(board), moves, ctypes.byref(count),
                      min_x.value, max_x.value, min_y.value, max_y.value, player)
        return [(moves[i].x, moves[i].y, moves[i].score) for i in range(count.value)]

    return _call


class TestOpenJumpThreeDefenseIsCandidateGenerated:
    """loss-analysis-jump-three-gap.md 記錄的局面：白棋跳三缺口必須進候選列表。"""

    # 第 18 手後的局面（黑棋視角，AI 執黑）：白棋在 y=9 有 (2,9)(3,9)(5,9)，
    # 缺口 (4,9) 補上即兩端全開的活四。棋譜見筆記的完整記錄，這裡只取
    # 觸發漏防所需的最小子集。
    STONES = [
        (7, 7, BLACK), (7, 6, WHITE), (6, 6, BLACK), (8, 8, WHITE), (5, 7, BLACK),
        (6, 7, WHITE), (5, 8, BLACK), (5, 9, WHITE), (4, 8, BLACK), (3, 9, WHITE),
        (4, 7, BLACK), (4, 5, WHITE), (3, 8, BLACK), (2, 8, WHITE), (6, 8, BLACK),
        (7, 8, WHITE), (5, 6, BLACK), (2, 9, WHITE),
    ]

    def test_gap_point_is_generated_as_top_priority_defense(self, sort_moves):
        moves = sort_moves(self.STONES, BLACK)
        assert moves, "sortMoves 未產生任何候選"
        assert moves[0][:2] == (4, 9), (
            f"(4,9) 應為最高分候選（高優先防守策略），實際候選列表：{moves}"
        )

    def test_white_gap_stone_classifies_as_open_jump_three(self):
        """(2,9)/(3,9) 這組跳三，classifyWindow 應判成碼 11（偏活跳三），
        兩端皆空——這是觸發高優先防守策略的必要條件。"""
        lib = ctypes.CDLL(LIB_PATH)
        lib.getBoardMax.restype = ctypes.c_int
        board_max = lib.getBoardMax()
        board_type = (ctypes.c_int * board_max) * board_max
        lib.checkLine.restype = None
        lib.checkLine.argtypes = [
            ctypes.POINTER(board_type),
            ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int * 16),
        ]
        board = board_type()
        for x, y, colour in self.STONES:
            board[y][x] = colour
        line = (ctypes.c_int * 16)()
        lib.checkLine(ctypes.byref(board), 3, 9, WHITE, line)
        assert line[11] == 1, f"(3,9) 的棋型應為碼 11（偏活跳三），實際 line={list(line)}"
