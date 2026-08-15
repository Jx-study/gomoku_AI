"""連珠禁手規則測試（透過 ctypes 驗證 `ai.dll` 的 `checkUnValid`）。

規則依據 RIF / 日本連珠社：
  - 禁手只適用於**黑棋**；白棋完全無禁手，長連對白棋算勝
  - 黑棋禁手三種：三三、四四、長連（>=6）
  - **五連優先**：同時成五連與禁手時不算禁手，黑棋勝
  - 四三（一個四 + 一個活三）是黑棋唯一的合法致勝手，不可誤判為禁手

`checkUnValid` 回傳值：1 = 合法，0 = 該點已有棋子，負數 = 禁手代碼。
本檔一律只判斷「合法與否」（`== 1`），不依賴特定的負數代碼——註解說
-5 是長連但實作回傳 -6，兩者不一致，而所有呼叫端都只檢查 `!= 1`。

需要先編譯共享庫：
    cd src && gcc -shared -o ai.dll -fPIC ai.c
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
    reason=f"{_lib_filename()} 未編譯；先執行 gcc -shared -o ai.dll -fPIC ai.c",
)


@pytest.fixture(scope="module")
def judge():
    """回傳 judge(stones, x, y, player) -> checkUnValid 的結果。

    stones = [(x, y, colour)]，代表落子前已在盤上的棋子。
    """
    lib = ctypes.CDLL(LIB_PATH)
    lib.getBoardMax.restype = ctypes.c_int
    board_max = lib.getBoardMax()

    lib.checkUnValid.restype = ctypes.c_int
    lib.checkUnValid.argtypes = [
        ctypes.POINTER(ctypes.c_int * board_max * board_max),
        ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ]
    lib.initZobristTable()
    lib.initTranspositionTable()

    board_type = (ctypes.c_int * board_max) * board_max

    def _judge(stones, x, y, player=BLACK):
        board = board_type()
        for sx, sy, colour in stones:
            board[sy][sx] = colour
        return lib.checkUnValid(ctypes.byref(board), x, y, player)

    _judge.board_max = board_max
    _judge.mid = board_max // 2
    return _judge


def is_legal(result):
    return result == 1


def line(fixed, positions, colour=BLACK, horizontal=True):
    """產生一條直線上的棋子。horizontal=True 時 fixed 是 y，否則是 x。"""
    if horizontal:
        return [(p, fixed, colour) for p in positions]
    return [(fixed, p, colour) for p in positions]


class TestWhiteHasNoForbiddenMoves:
    """白棋不受任何禁手限制——長連對白棋是勝利而非違規。"""

    def test_white_overline_allowed(self, judge):
        stones = line(5, [3, 4, 5, 6], WHITE) + line(5, [8], WHITE)
        assert is_legal(judge(stones, 7, 5, WHITE))

    def test_white_double_three_allowed(self, judge):
        stones = [(5, 7, WHITE), (6, 7, WHITE), (7, 5, WHITE), (7, 6, WHITE)]
        assert is_legal(judge(stones, 7, 7, WHITE))

    def test_white_double_four_allowed(self, judge):
        stones = [(4, 7, WHITE), (5, 7, WHITE), (6, 7, WHITE),
                  (7, 4, WHITE), (7, 5, WHITE), (7, 6, WHITE)]
        assert is_legal(judge(stones, 7, 7, WHITE))


class TestBlackDoubleThree:
    def test_cross_double_open_three_forbidden(self, judge):
        stones = [(6, 7, BLACK), (8, 7, BLACK), (7, 6, BLACK), (7, 8, BLACK)]
        assert not is_legal(judge(stones, 7, 7))

    def test_adjacent_double_open_three_forbidden(self, judge):
        stones = [(5, 7, BLACK), (6, 7, BLACK), (7, 5, BLACK), (7, 6, BLACK)]
        assert not is_legal(judge(stones, 7, 7))

    def test_single_open_three_legal(self, judge):
        stones = [(5, 7, BLACK), (6, 7, BLACK)]
        assert is_legal(judge(stones, 7, 7))

    def test_blocked_three_does_not_count(self, judge):
        """被白棋擋住的是眠三，不該與另一個活三湊成雙三。"""
        stones = [(4, 7, WHITE), (5, 7, BLACK), (6, 7, BLACK),
                  (7, 5, BLACK), (7, 6, BLACK)]
        assert is_legal(judge(stones, 7, 7))

    def test_edge_three_does_not_count(self, judge):
        """貼邊的三連一端是牆，屬眠三而非活三。"""
        stones = [(0, 7, BLACK), (1, 7, BLACK), (7, 5, BLACK), (7, 6, BLACK)]
        assert is_legal(judge(stones, 2, 7))


class TestBlackDoubleFour:
    def test_double_four_forbidden(self, judge):
        stones = [(4, 7, BLACK), (5, 7, BLACK), (6, 7, BLACK),
                  (7, 4, BLACK), (7, 5, BLACK), (7, 6, BLACK)]
        assert not is_legal(judge(stones, 7, 7))

    def test_single_four_legal(self, judge):
        stones = [(4, 7, BLACK), (5, 7, BLACK), (6, 7, BLACK)]
        assert is_legal(judge(stones, 7, 7))


class TestFourThreeIsLegal:
    """四三是黑棋唯一的合法致勝手，誤判成禁手會讓黑棋無法取勝。"""

    def test_four_plus_open_three(self, judge):
        stones = [(4, 7, BLACK), (5, 7, BLACK), (6, 7, BLACK),
                  (7, 5, BLACK), (7, 6, BLACK)]
        assert is_legal(judge(stones, 7, 7))

    def test_blocked_four_plus_open_three(self, judge):
        stones = [(3, 7, WHITE), (4, 7, BLACK), (5, 7, BLACK), (6, 7, BLACK),
                  (7, 5, BLACK), (7, 6, BLACK)]
        assert is_legal(judge(stones, 7, 7))


class TestExactFive:
    def test_exact_five_legal(self, judge):
        stones = line(7, [3, 4, 5, 6], BLACK)
        assert is_legal(judge(stones, 7, 7))

    def test_five_takes_priority_over_other_shapes(self, judge):
        """五連與其他棋型同時成立時，五連優先，黑棋勝。"""
        stones = line(7, [3, 4, 5, 6], BLACK) + [
            (7, 5, BLACK), (7, 6, BLACK), (7, 9, BLACK)]
        assert is_legal(judge(stones, 7, 7))


class TestBlackOverline:
    """長連（>=6）對黑棋是禁手。"""

    def test_six_by_extending_right(self, judge):
        stones = line(7, [3, 4, 5, 6, 7], BLACK)
        assert not is_legal(judge(stones, 8, 7))

    def test_six_by_extending_left(self, judge):
        stones = line(7, [4, 5, 6, 7, 8], BLACK)
        assert not is_legal(judge(stones, 3, 7))

    @pytest.mark.parametrize("left,right", [
        ([4, 5, 6], [8, 9]),        # 左3右2
        ([5, 6], [8, 9, 10]),       # 左2右3
        ([6], [8, 9, 10, 11]),      # 左1右4
    ])
    def test_six_by_filling_gap(self, judge, left, right):
        stones = line(7, left, BLACK) + line(7, right, BLACK)
        assert not is_legal(judge(stones, 7, 7))

    def test_seven_in_a_row(self, judge):
        stones = line(7, [2, 3, 4, 5, 6], BLACK) + line(7, [8], BLACK)
        assert not is_legal(judge(stones, 7, 7))

    @pytest.mark.xfail(
        strict=True,
        reason="checkLine 切換掃描方向時會重設連續長度，四子在一側、"
               "一子在另一側時 maxConnect 只算到 5，六連被記成五連而讓"
               "黑棋以長連獲勝。修復見 Note/plans/03-datastructure.md D1"
               "（棋型查表）——checkLine 同時供評估使用，改動需 selfplay 比對。",
    )
    def test_six_with_four_on_one_side_and_one_on_other(self, judge):
        """左 4 右 1 填中間成六連。

        盤面與 test_six_by_filling_gap 的其他構型完全等價（同樣是連續
        六子），判定卻不同，可見問題出在掃描方式而非規則本身。
        """
        stones = line(7, [3, 4, 5, 6], BLACK) + line(7, [8], BLACK)
        assert not is_legal(judge(stones, 7, 7))

    @pytest.mark.xfail(
        strict=False,
        reason="同上；水平/垂直/主對角線皆受影響，副對角線因掃描順序"
               "不同而僥倖正確，故不使用 strict。",
    )
    @pytest.mark.parametrize("dx,dy", [(1, 0), (0, 1), (1, 1), (1, -1)])
    def test_six_four_one_split_in_all_directions(self, judge, dx, dy):
        mid = judge.mid
        stones = [(mid + k * dx, mid + k * dy, BLACK) for k in (-4, -3, -2, -1)]
        stones.append((mid + dx, mid + dy, BLACK))
        assert not is_legal(judge(stones, mid, mid))


class TestOccupiedSquare:
    @pytest.mark.parametrize("player", [BLACK, WHITE])
    def test_occupied_returns_zero(self, judge, player):
        assert judge([(7, 7, BLACK)], 7, 7, player) == 0
