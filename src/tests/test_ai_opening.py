"""C 引擎（ai.dll）開局分支測試。

需要先編譯共享庫：
    cd src && gcc -shared -o ai.dll -fPIC ai.c

找不到共享庫時整個模組會被 skip，而不是讓測試套件失敗——這樣沒編譯的
環境仍可執行純 Python 的狀態層測試。
"""
import ctypes
import os
import platform

import pytest

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    reason=f"{_lib_filename()} 未編譯；先執行 gcc -shared -o ai.dll -fPIC ai.c",
)


@pytest.fixture(scope="module")
def ai():
    lib = ctypes.CDLL(LIB_PATH)
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
    lib.initZobristTable()
    lib.initTranspositionTable()

    board_type = (ctypes.c_int * board_max) * board_max

    class Engine:
        BOARD_MAX = board_max
        MID = board_max // 2

        @staticmethod
        def move(stones, player, round_counter):
            """stones = [(x, y, colour)]；回傳 (x, y, board)。"""
            board = board_type()
            for x, y, colour in stones:
                board[y][x] = colour
            bx, by = ctypes.c_int(), ctypes.c_int()
            lib.aiRound(ctypes.byref(board), player, round_counter,
                        ctypes.byref(bx), ctypes.byref(by))
            return bx.value, by.value, board

    return Engine


def assert_legal(engine, x, y, board, box_radius=None):
    assert 0 <= x < engine.BOARD_MAX, f"x={x} 超出棋盤"
    assert 0 <= y < engine.BOARD_MAX, f"y={y} 超出棋盤"
    assert board[y][x] == 0, f"AI 走在已有棋子的位置 ({x},{y})"
    if box_radius is not None:
        assert abs(x - engine.MID) <= box_radius, f"({x},{y}) 超出開局範圍"
        assert abs(y - engine.MID) <= box_radius, f"({x},{y}) 超出開局範圍"


class TestOpeningMoves:
    def test_black_move1_is_center(self, ai):
        x, y, _ = ai.move([], 1, 1)
        assert (x, y) == (ai.MID, ai.MID)

    @pytest.mark.parametrize("trial", range(5))
    def test_white_move2_inside_3x3(self, ai, trial):
        x, y, board = ai.move([(ai.MID, ai.MID, 1)], 2, 2)
        assert_legal(ai, x, y, board, box_radius=1)

    @pytest.mark.parametrize("dx,dy", [
        (dx, dy)
        for dx in (-1, 0, 1) for dy in (-1, 0, 1)
        if not (dx == 0 and dy == 0)
    ])
    def test_black_move3_inside_5x5(self, ai, dx, dy):
        """白棋第 2 手可能落在 3x3 的任一點，黑第 3 手都要合法。"""
        stones = [(ai.MID, ai.MID, 1), (ai.MID + dx, ai.MID + dy, 2)]
        x, y, board = ai.move(stones, 1, 3)
        assert_legal(ai, x, y, board, box_radius=2)


class TestDegenerateStates:
    """悔棋等異常狀態可能讓開局分支面對非預期盤面，仍不得回傳非法座標。"""

    def test_move3_all_diagonals_occupied(self, ai):
        m = ai.MID
        stones = [(m, m, 1),
                  (m - 1, m - 1, 2), (m + 1, m - 1, 2),
                  (m - 1, m + 1, 2), (m + 1, m + 1, 2)]
        x, y, board = ai.move(stones, 1, 3)
        assert_legal(ai, x, y, board)

    def test_move2_full_3x3_occupied(self, ai):
        m = ai.MID
        stones = [(i, j, 1 if (i + j) % 2 else 2)
                  for j in range(m - 1, m + 2)
                  for i in range(m - 1, m + 2)]
        x, y, board = ai.move(stones, 2, 2)
        assert_legal(ai, x, y, board)


class TestNoOccupiedReturns:
    """回歸測試：舊版第 3 手的 else-if 守衛檢查的點與候選無關，
    改用右上角後也從未再檢查佔用，異常盤面下會回傳已有棋子的座標。"""

    @pytest.mark.parametrize("occupied", [
        [(-1, -1)],
        [(-1, -1), (1, -1)],
        [(-1, -1), (1, -1), (-1, 1)],
    ])
    def test_move3_skips_occupied_diagonals(self, ai, occupied):
        m = ai.MID
        stones = [(m, m, 1)] + [(m + dx, m + dy, 2) for dx, dy in occupied]
        x, y, board = ai.move(stones, 1, 3)
        assert_legal(ai, x, y, board)
