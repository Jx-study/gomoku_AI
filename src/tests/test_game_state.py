"""狀態層測試：輪次、開局規則、悔棋。

每個 class 對應一組不變量；`TestRegressions` 逐一對應本次修掉的 bug，
避免日後重構時再犯。
"""
import pytest

from game_state import GameState, BLACK, WHITE, EMPTY

BOARD_MAX = 15


@pytest.fixture
def state():
    return GameState(BOARD_MAX)


@pytest.fixture
def mid(state):
    return state.midpoint


def play_opening(state, moves):
    """依序落子，全部必須成功。moves = [(x, y), ...]"""
    for x, y in moves:
        assert state.play(x, y), f"expected ({x},{y}) to be legal"


class TestTurnOrder:
    """不變量 2：黑棋恆在奇數手、白棋恆在偶數手。"""

    def test_black_starts(self, state):
        assert state.current_player == BLACK

    @pytest.mark.parametrize("round_counter,expected", [
        (1, BLACK), (2, WHITE), (3, BLACK), (4, WHITE),
        (5, BLACK), (10, WHITE), (99, BLACK), (100, WHITE),
    ])
    def test_player_derived_from_round(self, state, round_counter, expected):
        state.round_counter = round_counter
        assert state.current_player == expected

    def test_alternates_while_playing(self, state, mid):
        play_opening(state, [(mid, mid), (mid, mid - 1), (mid - 1, mid - 1)])
        expected = [BLACK, WHITE, BLACK]
        assert [p for _x, _y, p in state.moves] == expected

    def test_turn_follows_board_after_undo(self, state, mid):
        play_opening(state, [(mid, mid), (mid, mid - 1)])
        assert state.current_player == BLACK      # 第 3 手
        state.undo(2)
        assert state.current_player == BLACK      # 回到第 1 手，仍是黑


class TestCoreInvariant:
    """不變量 1：round_counter == 手數 + 1，任何操作後都成立。"""

    def assert_invariant(self, state):
        assert state.round_counter == state.stone_count() + 1

    def test_holds_initially(self, state):
        self.assert_invariant(state)

    def test_holds_after_plays(self, state, mid):
        play_opening(state, [(mid, mid), (mid, mid - 1), (mid - 1, mid - 1)])
        self.assert_invariant(state)

    def test_holds_through_play_undo_sequence(self, state, mid):
        play_opening(state, [(mid, mid), (mid, mid - 1), (mid - 1, mid - 1)])
        self.assert_invariant(state)
        state.undo()
        self.assert_invariant(state)
        assert state.play(mid + 1, mid + 1)
        self.assert_invariant(state)
        state.undo()
        self.assert_invariant(state)
        state.undo()
        self.assert_invariant(state)


class TestOpeningRules:
    """連珠指定開局：第 1 手天元、第 2 手 3x3、第 3 手 5x5。"""

    def test_move1_must_be_center(self, state, mid):
        assert state.is_valid_move(mid, mid)
        assert not state.is_valid_move(mid + 1, mid)
        assert not state.is_valid_move(0, 0)

    def test_move2_within_3x3(self, state, mid):
        state.play(mid, mid)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue    # 中心已被佔
                assert state.is_valid_move(mid + dx, mid + dy)
        assert not state.is_valid_move(mid + 2, mid)
        assert not state.is_valid_move(mid, mid - 2)

    def test_move3_within_5x5(self, state, mid):
        play_opening(state, [(mid, mid), (mid, mid - 1)])
        assert state.is_valid_move(mid + 2, mid + 2)
        assert not state.is_valid_move(mid + 3, mid)
        assert not state.is_valid_move(mid, mid + 3)

    def test_move4_unrestricted(self, state, mid):
        play_opening(state, [(mid, mid), (mid, mid - 1), (mid - 1, mid - 1)])
        assert state.opening_box_radius() is None
        assert state.is_valid_move(0, 0)

    def test_center_occupied_blocks_reuse(self, state, mid):
        state.play(mid, mid)
        assert not state.is_valid_move(mid, mid)


class TestUndo:
    def test_undo_empty_board(self, state):
        assert state.undo() == 0
        assert state.round_counter == 1

    def test_undo_removes_two(self, state, mid):
        play_opening(state, [(mid, mid), (mid, mid - 1)])
        assert state.undo() == 2
        assert state.stone_count() == 0
        assert state.board[mid][mid] == EMPTY

    def test_undo_repeats_to_empty(self, state, mid):
        play_opening(state, [(mid, mid), (mid, mid - 1), (mid - 1, mid - 1)])
        total = 0
        while True:
            undone = state.undo()
            if not undone:
                break
            total += undone
        assert total == 3
        assert state.stone_count() == 0
        assert state.round_counter == 1

    def test_undo_clears_board_cells(self, state, mid):
        play_opening(state, [(mid, mid), (mid, mid - 1)])
        state.undo()
        assert all(c == EMPTY for row in state.board for c in row)


class TestBounds:
    @pytest.mark.parametrize("x,y", [
        (-1, 0), (0, -1), (BOARD_MAX, 0), (0, BOARD_MAX),
        (-5, -5), (999, 999),
    ])
    def test_out_of_bounds_rejected(self, state, x, y):
        assert not state.is_valid_move(x, y)
        assert not state.play(x, y)

    def test_corners_in_bounds(self, state):
        for x, y in [(0, 0), (0, BOARD_MAX - 1),
                     (BOARD_MAX - 1, 0), (BOARD_MAX - 1, BOARD_MAX - 1)]:
            assert state.in_bounds(x, y)


class TestRegressions:
    """對應本次修掉的具體 bug，命名即描述。"""

    def test_undo_odd_stone_count_does_not_crash(self, state, mid):
        """舊版無條件 pop 兩次，盤面只剩 1 手時拋 IndexError。"""
        state.play(mid, mid)
        assert state.undo() == 1        # 不可拋例外
        assert state.stone_count() == 0

    def test_undo_at_move2_rewinds_counter(self, state, mid):
        """舊版只在 round_counter > 2 才回捲，導致盤面清空但計數器停在 2，
        開局規則從此失效。"""
        state.play(mid, mid)
        assert state.round_counter == 2
        state.undo()
        assert state.round_counter == 1
        assert state.stone_count() == 0

    def test_opening_rule_reapplies_after_undo(self, state, mid):
        """承上：計數器脫鉤後，黑棋第 1 手可落在任意位置。"""
        state.play(mid, mid)
        state.undo()
        assert not state.is_valid_move(0, 0), "第 1 手必須落在天元"
        assert state.is_valid_move(mid, mid)

    def test_undo_odd_count_does_not_flip_turn_owner(self, state, mid):
        """撤銷奇數手後，若另存 current_player 就會奇偶對不上 → 白棋先手。"""
        state.play(mid, mid)            # 黑第 1 手，round_counter -> 2
        assert state.current_player == WHITE
        state.undo()                    # 只撤 1 手，round_counter -> 1
        assert state.current_player == BLACK, "悔棋後應回到黑棋，不可變成白棋先手"

    def test_no_two_consecutive_same_colour_after_undo(self, state, mid):
        """截圖回報的症狀：悔棋後玩家連下兩顆同色棋子。"""
        play_opening(state, [(mid, mid), (mid, mid - 1)])
        state.undo(1)                   # 撤掉白棋那手
        assert state.current_player == WHITE
        state.play(mid + 1, mid)
        colours = [p for _x, _y, p in state.moves]
        assert colours == [BLACK, WHITE], f"顏色順序錯誤: {colours}"

    def test_illegal_move_leaves_state_untouched(self, state, mid):
        """非法落子不得改變盤面或計數器。"""
        state.play(mid, mid)
        before_counter = state.round_counter
        before_board = state.snapshot()
        assert not state.play(0, 0)     # 第 2 手不得落在角落
        assert state.round_counter == before_counter
        assert state.snapshot() == before_board


class TestForbiddenCheckerHook:
    def test_checker_consulted_after_other_rules(self, mid):
        calls = []

        def checker(board, x, y, player):
            calls.append((x, y, player))
            return True

        st = GameState(BOARD_MAX, forbidden_checker=checker)
        st.is_valid_move(-1, -1)            # 越界，不該呼叫 checker
        assert calls == []
        st.is_valid_move(st.midpoint, st.midpoint)
        assert calls == [(st.midpoint, st.midpoint, BLACK)]

    def test_checker_can_reject(self, mid):
        st = GameState(BOARD_MAX, forbidden_checker=lambda *_: False)
        assert not st.is_valid_move(st.midpoint, st.midpoint)
