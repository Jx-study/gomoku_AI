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


@pytest.fixture(scope="module")
def raw_judge():
    """回傳 raw_judge(stones, x, y, player) -> judgeMove 的原始回傳值。

    與 `judge` 不同，這裡不把「勝著」摺疊成 1，因此可以直接驗證
    2 = 五連/白棋長連。
    """
    lib = ctypes.CDLL(LIB_PATH)
    lib.getBoardMax.restype = ctypes.c_int
    board_max = lib.getBoardMax()

    lib.judgeMove.restype = ctypes.c_int
    lib.judgeMove.argtypes = [
        ctypes.POINTER(ctypes.c_int * board_max * board_max),
        ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ]

    board_type = (ctypes.c_int * board_max) * board_max

    def _judge(stones, x, y, player=BLACK):
        board = board_type()
        for sx, sy, colour in stones:
            board[sy][sx] = colour
        return lib.judgeMove(ctypes.byref(board), x, y, player)

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


class TestWallLimitsThree:
    """牆讓貼邊的實心三成不了活四，依 RIF 不算三，不該湊成三三。

    RIF 的三是功能定義：「能再加一子成為活四」。活四又要求「兩個不同
    的成五點」。落子點在 x=1、黑子在 x=2,3 時，三子貼著左牆，
    往左只剩 x=0 一格，補滿後左端出界、只有一個成五點，是四不是活四，
    所以原形不構成三。同一形狀離開牆邊時兩端都能延伸，才是三。
    """

    def _shapes(self, x):
        """回傳（水平三子中的兩顆, 垂直三子中的兩顆）。落子點為 (x, 7)。"""
        return ([(x + 1, 7, BLACK), (x + 2, 7, BLACK)],
                [(x, 6, BLACK), (x, 8, BLACK)])

    def test_center_double_open_three_forbidden(self, judge):
        """對照組：同一形狀在盤面中央，兩側都有空間 -> 三三禁手。"""
        horizontal, vertical = self._shapes(5)
        assert not is_legal(judge(horizontal + vertical, 5, 7))

    def test_edge_three_is_not_a_three(self, judge):
        """貼左牆的同一形狀。左端空間不足以成活四，不算三 -> 合法。"""
        horizontal, vertical = self._shapes(1)
        assert is_legal(judge(horizontal + vertical, 1, 7))


class TestWallDoesNotHideFour:
    """牆不得讓衝四整個消失——四四加總認 line[12]，漏判就會放行四四。

    形狀 1011 後接白子：填滿缺口即成五，依 RIF 是四。牆封住的是背面那端，
    成五點仍在，所以它仍是四——四只需要一個成五點，這點與三不同。
    """

    def test_center_four_with_blocked_far_end_counts(self, judge):
        """對照組：同形狀在中央，背面是空格 -> 判為跳四，湊成四四。"""
        stones = line(7, [7, 8, 9], BLACK) + [(10, 7, WHITE)]
        stones += line(5, [7, 8, 9], BLACK, horizontal=False) + [(5, 10, WHITE)]
        assert not is_legal(judge(stones, 5, 7))

    def test_edge_four_with_blocked_far_end_counts(self, judge):
        """貼牆的同形狀。牆封住的是背面，成五點仍在，依 RIF 仍是四。"""
        stones = line(7, [2, 3, 4], BLACK) + [(5, 7, WHITE)]
        stones += line(0, [9, 10, 11], BLACK, horizontal=False) + [(0, 12, WHITE)]
        assert not is_legal(judge(stones, 0, 7))


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

    def test_six_with_four_on_one_side_and_one_on_other(self, judge):
        """左 4 右 1 填中間成六連。

        盤面與 test_six_by_filling_gap 的其他構型完全等價（同樣是連續
        六子）。曾因 checkLine 的棋型分類漏判而判成合法，現由
        judgeMove 直接數連續長度（maxRunAt）處理。
        """
        stones = line(7, [3, 4, 5, 6], BLACK) + line(7, [8], BLACK)
        assert not is_legal(judge(stones, 7, 7))

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


class TestFiveDetectionIgnoresShape:
    """成五/長連判定必須只看連續長度，不受周圍棋型影響。

    曾有的錯誤：judgeMove 透過 checkLine 的棋型分類判斷勝負，而
    checkLine 的 gaps == 1 分支只處理 count 為 3、4 的情形。當落子點
    隔一格外還有己方棋子時 count >= 5，所有子條件皆落空、回傳全零，
    於是「明明成五」被判成普通著法——AI 因此漏擋而輸棋。
    現改由 maxRunAt 直接數連續長度。
    """

    WIN = 2

    @pytest.mark.parametrize("extra", [3, 2, 1, 0])
    @pytest.mark.parametrize("player", [BLACK, WHITE])
    def test_five_detected_with_far_friendly_stone(self, raw_judge, player, extra):
        """落子點左側隔一格外另有己方棋子時，仍須認得五連。

        盤面如 `W . _ W W W W`：填入 _ 成五，額外那顆隔開的遠方棋子
        不該讓判定失效（它與五連之間有空位，不構成長連）。
        """
        stones = line(7, [8, 9, 10, 11], player) + line(7, [extra], player)
        assert raw_judge(stones, 7, 7, player) == self.WIN

    @pytest.mark.parametrize("player", [BLACK, WHITE])
    def test_five_detected_with_gap_on_both_sides(self, raw_judge, player):
        """兩側都隔一格另有己方棋子，中間仍是乾淨的五連。"""
        stones = (line(7, [2], player) + line(7, [4, 5, 6, 7], player)
                  + line(7, [10], player))
        assert raw_judge(stones, 8, 7, player) == self.WIN

    @pytest.mark.parametrize("dx,dy", [(1, 0), (0, 1), (1, 1), (1, -1)])
    @pytest.mark.parametrize("player", [BLACK, WHITE])
    def test_five_detected_in_all_directions(self, raw_judge, player, dx, dy):
        mid = raw_judge.mid
        stones = [(mid + k * dx, mid + k * dy, player) for k in (1, 2, 3, 4)]
        stones.append((mid - 2 * dx, mid - 2 * dy, player))   # 隔一格的遠方棋子（不接續）
        assert raw_judge(stones, mid, mid, player) == self.WIN

    def test_black_five_beats_double_three(self, raw_judge):
        """五連優先於禁手：同時成五連與雙三時，黑棋勝而非違規。"""
        stones = (line(7, [3, 4, 5, 6], BLACK)
                  + [(7, 5, BLACK), (7, 6, BLACK), (7, 8, BLACK), (7, 9, BLACK)])
        assert raw_judge(stones, 7, 7, BLACK) == self.WIN

    def test_black_five_beats_overline_in_another_direction(self, raw_judge):
        """五連優先於禁手：水平恰好五連、垂直長連時，黑棋勝而非長連禁手。

        只取四個方向的最長連續長度會讓垂直的七連蓋過水平的五連，
        因此 maxRunAt 另外回報「有無任一方向恰好五連」。
        """
        stones = (line(7, [8, 9, 10, 11], BLACK)
                  + [(7, y, BLACK) for y in (4, 5, 6, 8, 9, 10)])
        assert raw_judge(stones, 7, 7, BLACK) == self.WIN

    def test_white_five_with_overline_in_another_direction_is_win(self, raw_judge):
        """白棋兩者皆勝，方向如何組合都應回傳勝著。"""
        stones = (line(7, [8, 9, 10, 11], WHITE)
                  + [(7, y, WHITE) for y in (4, 5, 6, 8, 9, 10)])
        assert raw_judge(stones, 7, 7, WHITE) == self.WIN

    def test_black_split_overline_is_forbidden(self, raw_judge):
        """左 3 右 3 填中間成七連，黑棋長連禁手（不可判成勝著）。"""
        stones = line(7, [4, 5, 6], BLACK) + line(7, [8, 9, 10], BLACK)
        assert raw_judge(stones, 7, 7, BLACK) < 0

    def test_white_split_overline_is_win(self, raw_judge):
        stones = line(7, [4, 5, 6], WHITE) + line(7, [8, 9, 10], WHITE)
        assert raw_judge(stones, 7, 7, WHITE) == self.WIN
