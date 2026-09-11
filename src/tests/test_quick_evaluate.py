"""`quickEvaluate`（sortMoves 第四層的通用走法評分）測試。

只驗一件事：成五點必須拿到壓過一切棋型的分數。
`checkLine` 對分裂形狀（落子點隔一格外還有己方子）會分類成全零，
成五點因此在 sortMoves 的 `if (score != 0)` 被濾掉——這是漏殺洞。
現由 quickEvaluate 開頭的 `judgeMove(...) == 2` 短路處理。

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

# 活四在 quickEvaluate 的 attack 權重；成五點必須明顯高過它
LIVE_FOUR_SCORE = 100000


@pytest.fixture(scope="module")
def quick_eval():
    """回傳 quick_eval(stones, x, y, player) -> quickEvaluate 的分數。"""
    lib = ctypes.CDLL(LIB_PATH)
    lib.getBoardMax.restype = ctypes.c_int
    board_max = lib.getBoardMax()

    board_type = (ctypes.c_int * board_max) * board_max
    lib.quickEvaluate.restype = ctypes.c_int
    lib.quickEvaluate.argtypes = [
        ctypes.POINTER(board_type),
        ctypes.c_int, ctypes.c_int,          # x, y
        ctypes.c_int, ctypes.c_int,          # minX, maxX
        ctypes.c_int, ctypes.c_int,          # minY, maxY
        ctypes.c_int,                        # player
    ]

    def _eval(stones, x, y, player):
        board = board_type()
        xs = [x] + [sx for sx, _, _ in stones]
        ys = [y] + [sy for _, sy, _ in stones]
        for sx, sy, colour in stones:
            board[sy][sx] = colour
        pad = 2
        min_x = max(min(xs) - pad, 0)
        max_x = min(max(xs) + pad, board_max - 1)
        min_y = max(min(ys) - pad, 0)
        max_y = min(max(ys) + pad, board_max - 1)
        return lib.quickEvaluate(ctypes.byref(board), x, y,
                                 min_x, max_x, min_y, max_y, player)

    _eval.mid = board_max // 2
    return _eval


def line(fixed, along, colour, horizontal=True):
    if horizontal:
        return [(a, fixed, colour) for a in along]
    return [(fixed, a, colour) for a in along]


class TestFiveAlwaysOutscoresEverything:
    @pytest.mark.parametrize("player", [BLACK, WHITE])
    def test_plain_five_scores_high(self, quick_eval, player):
        """乾淨的四連 + 補一手成五：分數要壓過活四。"""
        stones = line(7, [8, 9, 10, 11], player)
        assert quick_eval(stones, 7, 7, player) > LIVE_FOUR_SCORE

    @pytest.mark.parametrize("player", [BLACK, WHITE])
    def test_five_with_far_friendly_stone_scores_high(self, quick_eval, player):
        """落子點左側隔一格外另有己方子（W . _ W W W W）。

        這正是 checkLine 會分類成全零、成五點被 score != 0 濾掉的形狀。
        """
        stones = line(7, [8, 9, 10, 11], player) + line(7, [5], player)
        assert quick_eval(stones, 7, 7, player) > LIVE_FOUR_SCORE

    @pytest.mark.parametrize("dx,dy", [(1, 0), (0, 1), (1, 1), (1, -1)])
    @pytest.mark.parametrize("player", [BLACK, WHITE])
    def test_five_with_far_friendly_stone_all_directions(self, quick_eval, player, dx, dy):
        mid = quick_eval.mid
        stones = [(mid + k * dx, mid + k * dy, player) for k in (1, 2, 3, 4)]
        stones.append((mid - 2 * dx, mid - 2 * dy, player))
        assert quick_eval(stones, mid, mid, player) > LIVE_FOUR_SCORE
