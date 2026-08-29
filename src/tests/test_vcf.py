"""VCF（連續衝四強制勝）算殺搜索測試。

測試直接打 `vcfProbe`（算殺入口）而不是隔著 `aiRound` 猜，這樣「這手是不是算殺算出來的」
不必用時間或走法去推論。另外有一組端到端測試，把連殺實際下完確認真的成五。

場景設計原則（計畫 Step 4）：先在紙上推過強制勝序列，再固化成斷言。
TestScenarioSanity 就是把那個「人工驗證」寫成可執行的檢查——場景擺錯比沒有測試更糟。

需要先編譯共享庫：
    cd src && gcc -shared -o ai.dll -fPIC ai.c
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

BLACK, WHITE = 1, 2

# --- 場景 ------------------------------------------------------------------
# 白棋兩手連殺（座標相對中心點）：
#
#   橫排 y=0：白 (-2,0) (-1,0) (0,0)，左端被黑 (-3,0) 堵住
#   直行 x=1：白 (1,1) (1,2)
#
#   第 1 手 白(1,0) → 橫排成四 (-2..1)，左端是黑子，成五點只有 (2,0) 一個 → 衝四
#   黑被迫擋 (2,0)
#   第 2 手 白(1,3) → 直行成四 (1,0)(1,1)(1,2)(1,3)，兩端 (1,-1)(1,4) 都空 → 活四
#   黑擋不完 → 白成五
#
# 黑棋的閒子擺在遠處的 2x2，不構成任何四，也不干擾上面兩條線。
LADDER = [
    (-2, 0, WHITE), (-1, 0, WHITE), (0, 0, WHITE),
    (1, 1, WHITE), (1, 2, WHITE),
    (-3, 0, BLACK),
    (5, 4, BLACK), (6, 4, BLACK), (5, 5, BLACK), (6, 5, BLACK),
]

# 對照組：把直行那一頭堵掉，第 2 手做不出活四，連殺不成立
LADDER_BLOCKED = LADDER + [(1, 3, BLACK), (1, -1, BLACK)]


@pytest.fixture(scope="module")
def ai():
    lib = ctypes.CDLL(LIB_PATH)
    lib.getBoardMax.restype = ctypes.c_int
    board_max = lib.getBoardMax()
    board_type = (ctypes.c_int * board_max) * board_max
    board_ptr = ctypes.POINTER(board_type)

    lib.initZobristTable.restype = None
    lib.initTranspositionTable.restype = None
    lib.aiRound.restype = None
    lib.aiRound.argtypes = [board_ptr, ctypes.c_int, ctypes.c_int,
                            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    lib.judgeMove.restype = ctypes.c_int
    lib.judgeMove.argtypes = [board_ptr, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.vcfProbe.restype = ctypes.c_int
    lib.vcfProbe.argtypes = [board_ptr, ctypes.c_int,
                             ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    lib.getVcfNodes.restype = ctypes.c_longlong
    lib.initZobristTable()

    m = board_max // 2

    class Engine:
        BOARD_MAX = board_max
        MID = m

        @staticmethod
        def build(offsets):
            board = board_type()
            for dx, dy, colour in offsets:
                board[m + dy][m + dx] = colour
            return board

        @staticmethod
        def vcf(offsets, attacker):
            """回傳 (found, (dx, dy))；found 為 0 時座標無意義。"""
            board = Engine.build(offsets)
            wx, wy = ctypes.c_int(-1), ctypes.c_int(-1)
            found = lib.vcfProbe(ctypes.byref(board), attacker,
                                 ctypes.byref(wx), ctypes.byref(wy))
            return found, (wx.value - m, wy.value - m)

        @staticmethod
        def vcf_nodes():
            return lib.getVcfNodes()

        @staticmethod
        def five_points(offsets, player):
            board = Engine.build(offsets)
            out = []
            for y in range(board_max):
                for x in range(board_max):
                    if board[y][x] == 0 and lib.judgeMove(
                            ctypes.byref(board), x, y, player) == 2:
                        out.append((x - m, y - m))
            return out

        @staticmethod
        def four_moves(offsets, player):
            """player 落下去會生出至少一個成五點的空點——也就是「成四著法」。"""
            board = Engine.build(offsets)
            out = []
            for y in range(board_max):
                for x in range(board_max):
                    if board[y][x] != 0:
                        continue
                    if lib.judgeMove(ctypes.byref(board), x, y, player) < 1:
                        continue
                    board[y][x] = player
                    threat = any(
                        board[qy][qx] == 0 and lib.judgeMove(
                            ctypes.byref(board), qx, qy, player) == 2
                        for qy in range(board_max) for qx in range(board_max)
                    )
                    board[y][x] = 0
                    if threat:
                        out.append((x - m, y - m))
            return out

        @staticmethod
        def move(offsets, player):
            board = Engine.build(offsets)
            round_counter = max(len(offsets) + 1, 9)  # 避開開局分支與淺化深度
            bx, by = ctypes.c_int(-1), ctypes.c_int(-1)
            lib.initTranspositionTable()
            lib.aiRound(ctypes.byref(board), player, round_counter,
                        ctypes.byref(bx), ctypes.byref(by))
            return bx.value - m, by.value - m

    return Engine


def occupied(offsets):
    return {(dx, dy) for dx, dy, _ in offsets}


class TestScenarioSanity:
    """先確認場景擺對了，再拿它去驗證引擎。"""

    def test_first_move_is_a_simple_four(self, ai):
        """白 (1,0) 之後成五點恰好一個 → 是衝四，不是活四也不是普通手。"""
        after = LADDER + [(1, 0, WHITE)]
        assert ai.five_points(after, WHITE) == [(2, 0)]

    def test_second_move_is_an_open_four(self, ai):
        """黑擋 (2,0) 後，白 (1,3) 要做出兩個成五點 → 活四，擋不完。"""
        after = LADDER + [(1, 0, WHITE), (2, 0, BLACK), (1, 3, WHITE)]
        assert sorted(ai.five_points(after, WHITE)) == [(1, -1), (1, 4)]

    def test_black_has_no_counter_threat(self, ai):
        """黑棋全程不能有自己的成五點，否則不是乾淨的連殺場景。"""
        assert ai.five_points(LADDER, BLACK) == []
        after = LADDER + [(1, 0, WHITE)]
        assert ai.five_points(after, BLACK) == []

    def test_ladder_has_a_continuation(self, ai):
        """原場景：黑擋 (2,0) 之後，白仍有成四著法可以續攻。"""
        after = LADDER + [(1, 0, WHITE), (2, 0, BLACK)]
        assert (1, 3) in ai.four_moves(after, WHITE)

    def test_blocked_variant_kills_the_ladder(self, ai):
        """對照組：同樣位置補兩顆黑子後，白棋一個成四著法都沒有，攻勢斷在這裡。"""
        after = LADDER_BLOCKED + [(1, 0, WHITE), (2, 0, BLACK)]
        assert ai.four_moves(after, WHITE) == []


class TestVcfFindsForcedWin:
    def test_finds_the_ladder(self, ai):
        found, (dx, dy) = ai.vcf(LADDER, WHITE)
        assert found, "VCF 沒有找到這個兩手連殺"
        assert (dx, dy) == (1, 0), f"起手應為 (1,0)，實際 ({dx},{dy})"

    def test_plays_the_ladder_through_to_five(self, ai):
        """端到端：讓 aiRound 實際下完連殺，黑棋每次都下唯一擋點。"""
        pos = list(LADDER)
        for _ in range(6):
            dx, dy = ai.move(pos, WHITE)
            assert (dx, dy) not in occupied(pos), f"白棋走在已有棋子的位置 ({dx},{dy})"
            pos = pos + [(dx, dy, WHITE)]
            if not ai.five_points(pos, WHITE):
                pytest.fail(f"白棋走了非強制手 ({dx},{dy})，連殺斷掉")
            blocks = ai.five_points(pos, WHITE)
            if len(blocks) >= 2:
                return  # 活四，黑擋不完 → 連殺成立
            pos = pos + [(blocks[0][0], blocks[0][1], BLACK)]
        pytest.fail("6 手之內沒有下出活四或成五")


class TestNoFalseWin:
    """保守性回歸：寧可漏殺，不可誤判必勝。"""

    def test_no_vcf_when_ladder_is_blocked(self, ai):
        found, _ = ai.vcf(LADDER_BLOCKED, WHITE)
        assert not found, "連殺已被堵死，VCF 卻回報必勝（假勝）"

    def test_no_vcf_on_empty_board(self, ai):
        found, _ = ai.vcf([(0, 0, WHITE), (1, 1, BLACK)], WHITE)
        assert not found

    def test_no_vcf_when_defender_wins_first(self, ai):
        """守方已有成五點時，攻方的衝四救不回來，不能回報必勝。"""
        pos = [(-2, 0, WHITE), (-1, 0, WHITE), (0, 0, WHITE),
               (1, 1, WHITE), (1, 2, WHITE), (-3, 0, BLACK),
               # 黑棋橫排四顆，下一手就能成五
               (-2, 5, BLACK), (-1, 5, BLACK), (0, 5, BLACK), (1, 5, BLACK)]
        assert ai.five_points(pos, BLACK), "場景擺錯：黑棋沒有成五點"
        found, _ = ai.vcf(pos, WHITE)
        assert not found, "守方能搶先成五，VCF 卻回報必勝"

    def test_defends_instead_of_attacking(self, ai):
        """對手有衝四時整個引擎必須擋，不能被算殺帶著去搶攻。"""
        pos = [(-2, 0, WHITE), (-1, 0, WHITE), (0, 0, WHITE),
               (1, 1, WHITE), (1, 2, WHITE), (-3, 0, BLACK),
               (-2, 5, BLACK), (-1, 5, BLACK), (0, 5, BLACK), (1, 5, BLACK)]
        black_fives = ai.five_points(pos, BLACK)
        dx, dy = ai.move(pos, WHITE)
        assert (dx, dy) in black_fives, (
            f"白棋走 ({dx},{dy})，沒擋住黑棋的成五點 {black_fives}"
        )


class TestBudget:
    def test_quiet_position_is_cheap(self, ai):
        """沒有四可沖的局面，算殺應該在第一層就返回，不能燒掉節點預算。"""
        ai.vcf([(0, 0, WHITE), (1, 1, BLACK), (2, 2, WHITE), (3, 3, BLACK)], WHITE)
        assert ai.vcf_nodes() <= 2
