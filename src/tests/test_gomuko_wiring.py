"""Gomuko.py 與狀態層的接線測試（不開視窗）。

`test_game_state.py` 測的是規則本身；本檔測的是 GUI 層有沒有正確接上——
`GameHistory` 委派、`roundCounter` property、禁手 callback。這一層曾經
出過「規則正確但接線錯」的 bug（悔棋後 current_player 沒重新推導、玩家
連下兩顆同色棋），所以規則測試不能取代它。

透過在 import 前替換 `graphics` 模組來避免開視窗；找不到 ai.dll 時整個
模組 skip（`Gomuko` 在 import 時就會載入共享庫）。
"""
import os
import sys
import types

import pytest

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeGraphicsObject:
    """替身：記錄自己有沒有被 undraw，其餘方法皆為 no-op。"""

    def __init__(self, *args, **kwargs):
        self.undrawn = False

    def undraw(self):
        self.undrawn = True

    def draw(self, *args):
        return self

    def __getattr__(self, name):
        # setFill / setOutline / setText / getX ... 一律吞掉
        return lambda *args, **kwargs: 0


def _install_fake_graphics():
    module = types.ModuleType("graphics")
    for name in ["GraphWin", "Point", "Line", "Circle", "Rectangle",
                 "Text", "Image", "Entry", "Polygon", "Oval"]:
        setattr(module, name, FakeGraphicsObject)
    module.color_rgb = lambda *args: "rgb"
    sys.modules["graphics"] = module


@pytest.fixture(scope="module")
def gomuko():
    """import Gomuko，但不開視窗。需要 ai.dll 已編譯。"""
    _install_fake_graphics()
    cwd = os.getcwd()
    os.chdir(SRC_DIR)          # Gomuko.py 用相對路徑載入 ai.dll
    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)
    try:
        import Gomuko
    except OSError as exc:     # 找不到共享庫
        pytest.skip(f"無法載入 ai.dll：{exc}")
    finally:
        os.chdir(cwd)
    return Gomuko


@pytest.fixture
def history(gomuko):
    return gomuko.GameHistory()


@pytest.fixture
def mid(gomuko):
    return gomuko.const.MIDPOINT_X


@pytest.fixture
def game(gomuko):
    """建立 GomokuGame 但跳過 __init__（那會開視窗）。"""
    obj = gomuko.GomokuGame.__new__(gomuko.GomokuGame)
    obj.board = gomuko.GameHistory()
    obj.board.state.set_forbidden_checker(obj._is_not_forbidden)
    return obj


class TestGameHistoryDelegation:
    def test_board_and_moves_alias_state(self, history):
        assert history.board is history.state.board
        assert history.moves_history is history.state.moves

    def test_add_move_advances_counter(self, history, mid):
        assert history.add_move(mid, mid, 1, FakeGraphicsObject(), FakeGraphicsObject())
        assert history.state.round_counter == 2

    def test_graphics_stay_in_step(self, history, mid):
        history.add_move(mid, mid, 1, FakeGraphicsObject(), FakeGraphicsObject())
        assert len(history.piece_objects) == len(history.moves_history) == 1

    def test_illegal_move_does_not_store_graphics(self, history, mid):
        """圖形清單若比 moves 多一筆，悔棋就會 undraw 到錯的棋子。"""
        history.add_move(mid, mid, 1, FakeGraphicsObject(), FakeGraphicsObject())
        assert history.add_move(0, 0, 2, FakeGraphicsObject(), FakeGraphicsObject()) is False
        assert len(history.piece_objects) == len(history.moves_history) == 1


class TestUndoSync:
    def test_undo_clears_moves_and_graphics(self, history, mid):
        history.add_move(mid, mid, 1, FakeGraphicsObject(), FakeGraphicsObject())
        history.add_move(mid, mid - 1, 2, FakeGraphicsObject(), FakeGraphicsObject())
        pieces = list(history.piece_objects)

        assert history.undo_last_move() == 2
        assert len(history.moves_history) == 0
        assert len(history.piece_objects) == 0
        assert all(p.undrawn for p in pieces)
        assert history.state.round_counter == 1

    def test_odd_undo_removes_one(self, history, mid):
        history.add_move(mid, mid, 1, FakeGraphicsObject(), FakeGraphicsObject())
        assert history.undo_last_move() == 1
        assert len(history.piece_objects) == 0
        assert history.state.round_counter == 1

    def test_undo_empty_returns_zero(self, history):
        assert history.undo_last_move() == 0


class TestClearBoard:
    def test_resets_everything(self, history, mid):
        history.add_move(mid, mid, 1, FakeGraphicsObject(), FakeGraphicsObject())
        history.clear_board()
        assert history.state.round_counter == 1
        assert len(history.moves_history) == 0
        assert len(history.piece_objects) == 0
        assert all(cell == 0 for row in history.board for cell in row)


class TestRoundCounterProperty:
    def test_reads_from_state(self, game, mid):
        assert game.roundCounter == 1
        game.board.add_move(mid, mid, 1, FakeGraphicsObject(), FakeGraphicsObject())
        assert game.roundCounter == 2

    def test_is_read_only(self, game):
        """唯讀是刻意的：手數只能有一份真實來源，避免與盤面脫鉤。"""
        with pytest.raises(AttributeError):
            game.roundCounter = 99


class TestForbiddenCheckerWiring:
    def test_checker_is_consulted(self, game, mid):
        calls = []
        original = game._is_not_forbidden

        def spy(board, x, y, player):
            calls.append((x, y, player))
            return original(board, x, y, player)

        game.board.state.set_forbidden_checker(spy)
        assert game.check_valid_move(mid, mid, 1) is True
        assert calls == [(mid, mid, 1)]

    @pytest.mark.parametrize("x,y", [(-1, -1), (999, 999), (-1, 0)])
    def test_out_of_bounds_never_reaches_c(self, game, x, y):
        """越界座標若進到 C 端會直接 board[y][x] 造成越界讀取（UB）。"""
        calls = []
        game.board.state.set_forbidden_checker(
            lambda board, px, py, p: calls.append((px, py)) or True
        )
        assert game.check_valid_move(x, y, 1) is False
        assert calls == []
