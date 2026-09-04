"""搜索裡三個掃描基元各做了多少工作，確定性指標。

checkLine 單次只有幾十奈秒，這個尺度的計時不準，profiler 的插樁本身也比被量的
函數更貴（見 README 的「熱點量測」）。這裡改量每個基元讀取幾個盤面格，
這個數字跑幾次都一樣。

同時回答兩個增量維護的划算門檻（維護成本 vs 查詢省下的掃描）：
    windowIdx（D1c，已上線）：checkLine 呼叫數 / 落子數 > 80 / 40 = 2
    鄰格計數表（D2，待辦）：hasAdjacentPiece 呼叫數 / 落子數 > 24 / 實測格每次

做法與 count_cells.py 相同：讀 ai.c，只插計數器，ai.c 本身不修改，每次執行重新生成。
探針在 ai.c 找不到對應位置時會以非 0 結束。

用法（在 src/_bench/ 下）：
    python bench.py budget [ai.c 路徑]     # 預設 ../ai.c
"""
import os
import re
import shutil
import subprocess
import sys

import positions

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # src/_bench/
DEFAULT_SRC = os.path.join(ROOT, "..", "ai.c")
# 中間檔放 repo 內而非系統暫存區：Windows 的應用程式控制原則會擋掉暫存區裡的執行檔
WORKDIR = os.path.join(ROOT, "_count_budget_tmp")

# 落子/撤銷收斂進 placeStone/removeStone 之後，呼叫端應有 12 處；
# 對不上表示 ai.c 的落子形式改了，計數點要跟著搬
EXPECTED_WRITES = 12

# 鄰格計數表一次落子要更新的格數：5×5 減中心
ADJ_UPDATE_COST = 24
# windowIdx 一次落子要更新的索引數 / 一次 checkLine 省下的格數
WINDOW_UPDATE_COST = 80
WINDOW_QUERY_SAVING = 40

PROBES = [
    # hasAdjacentPiece：呼叫數與讀格數
    ("bool hasAdjacentPiece(int board[BOARD_MAX][BOARD_MAX], int x, int y) {",
     "bool hasAdjacentPiece(int board[BOARD_MAX][BOARD_MAX], int x, int y) {\n"
     "    g_adj_calls++;"),
    ("            if (nx >= 0 && nx < BOARD_MAX && ny >= 0 && ny < BOARD_MAX && board[ny][nx] != 0) {",
     "            g_adj_cells++;\n"
     "            if (nx >= 0 && nx < BOARD_MAX && ny >= 0 && ny < BOARD_MAX && board[ny][nx] != 0) {"),
    # maxRunAt：呼叫數與讀格數
    ("int maxRunAt(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int *hasFive) {",
     "int maxRunAt(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int *hasFive) {\n"
     "    g_run_calls++;"),
    ("                if (board[ny][nx] != player) break;",
     "                g_run_cells++;\n"
     "                if (board[ny][nx] != player) break;"),
    # checkLine：呼叫數（D1c 之後每次固定 4 次索引存取，不必另外數）
    ("void checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int my_line[14]) {",
     "void checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int my_line[14]) {\n"
     "    g_checkline++;"),
    # judgeMove：總呼叫數，以及其中走到 checkLine 的（沒在 maxRunAt 那段就返回的）
    ("int judgeMove(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {\n"
     "    if (board[y][x] != 0) return 0;",
     "int judgeMove(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {\n"
     "    g_judge_calls++;\n"
     "    if (board[y][x] != 0) return 0;"),
    ("    int line[14] = {0};\n    checkLine(board, x, y, player, line);\n    if (player == 1) {",
     "    int line[14] = {0};\n    g_judge_deep++;\n    checkLine(board, x, y, player, line);\n"
     "    if (player == 1) {"),
    # endGame 的兩個 judgeMove 呼叫點分開數：成五那個不需要 checkLine（見 03-impl-d2.md 待辦 A）
    ("                    if (currentPlayer == 1 && judgeMove(board, x, y, 1) < 1) continue;",
     "                    g_eg_forbid++;\n"
     "                    if (currentPlayer == 1 && judgeMove(board, x, y, 1) < 1) continue;"),
    ("                    if (judgeMove(board, x, y, player) == 2) {",
     "                    g_eg_five++;\n"
     "                    if (judgeMove(board, x, y, player) == 2) {"),
    # 落子/撤銷單一入口
    ("static void placeStone(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {",
     "static void placeStone(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {\n"
     "    g_placements++;"),
    ("static void removeStone(int board[BOARD_MAX][BOARD_MAX], int x, int y) {",
     "static void removeStone(int board[BOARD_MAX][BOARD_MAX], int x, int y) {\n"
     "    g_placements++;"),
]

COUNTERS = ["g_adj_calls", "g_adj_cells", "g_run_calls", "g_run_cells",
            "g_checkline", "g_judge_calls", "g_judge_deep",
            "g_eg_forbid", "g_eg_five", "g_placements"]

DRIVER = r"""
#include <stdio.h>

%(defs)s

void initZobristTable(void);
void aiRound(int board[%(bm)d][%(bm)d], int ai, int roundCounter, int *bestx, int *besty);

static int board[%(bm)d][%(bm)d];

/* 所有盤面的落子接成一條，BEGIN/LEN 切出每個盤面 */
static const int MOVES[%(nmoves)d][3] = {
%(moves)s
};
static const int BEGIN[%(nboards)d] = {%(begin)s};
static const int LEN[%(nboards)d] = {%(len)s};

int main(void) {
    initZobristTable();
    for (int b = 0; b < %(nboards)d; b++) {
        for (int y = 0; y < %(bm)d; y++)
            for (int x = 0; x < %(bm)d; x++) board[y][x] = 0;
        for (int i = 0; i < LEN[b]; i++) {
            const int *mv = MOVES[BEGIN[b] + i];
            board[mv[1]][mv[0]] = mv[2];
        }

        %(resets)s
        int bx = -1, by = -1;
        aiRound(board, 2, LEN[b] + 1, &bx, &by);   /* 下一手輪白棋，與 ab_fresh.py 一致 */
        printf("%%d %(fmt)s\n", b, %(args)s);
    }
    return 0;
}
"""


def board_max(src):
    m = re.search(r"^#define\s+BOARD_MAX\s+(\d+)", src, re.M)
    if not m:
        sys.exit("count_budget: ai.c 抽不到 BOARD_MAX，定義格式可能改了。")
    return int(m.group(1))


def instrument(src):
    def_re = re.compile(r"^static (?:void|int) (?:placeStone|removeStone)\(", re.M)
    call_re = re.compile(r"\b(?:placeStone|removeStone)\(")
    calls = len(call_re.findall(src)) - len(def_re.findall(src))
    if calls != EXPECTED_WRITES:
        sys.exit("count_budget: placeStone/removeStone 呼叫處找到 %d 個（預期 %d），"
                 "ai.c 的落子/撤銷形式可能改了。" % (calls, EXPECTED_WRITES))
    out = src
    for needle, replacement in PROBES:
        if needle not in out:
            sys.exit("count_budget: 找不到探針錨點，ai.c 可能改了：\n  %s" % needle[:80])
        out = out.replace(needle, replacement, 1)
    return "".join("extern long long %s;\n" % n for n in COUNTERS) + out


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    with open(src_path, encoding="utf-8") as f:
        src = f.read()
    bm = board_max(src)
    suite = positions.suite(bm)

    flat, begin, length = [], [], []
    for _, moves in suite:
        begin.append(len(flat))
        length.append(len(moves))
        flat.extend(moves)

    shutil.rmtree(WORKDIR, ignore_errors=True)
    os.makedirs(WORKDIR)
    try:
        core = os.path.join(WORKDIR, "core.c")
        with open(core, "w", encoding="utf-8") as f:
            f.write(instrument(src))

        drv = os.path.join(WORKDIR, "drv.c")
        with open(drv, "w", encoding="utf-8") as f:
            f.write(DRIVER % {
                "bm": bm,
                "defs": "\n".join("long long %s = 0;" % n for n in COUNTERS),
                "resets": " ".join("%s = 0;" % n for n in COUNTERS),
                "fmt": " ".join(["%lld"] * len(COUNTERS)),
                "args": ", ".join(COUNTERS),
                "nmoves": len(flat),
                "moves": "\n".join("    {%d, %d, %d}," % mv for mv in flat),
                "nboards": len(suite),
                "begin": ", ".join(str(v) for v in begin),
                "len": ", ".join(str(v) for v in length),
            })

        exe = os.path.join(WORKDIR, "probe.exe")
        build = subprocess.run(["gcc", "-O2", "-o", exe, drv, core],
                               capture_output=True, text=True)
        if build.returncode != 0:
            sys.exit("count_budget: 編譯失敗\n" + build.stderr)
        run = subprocess.run([exe], capture_output=True, text=True)
        if run.returncode != 0:
            sys.exit("count_budget: 執行失敗\n" + run.stderr)

        per_board, tot = [], dict.fromkeys(COUNTERS, 0)
        for line in run.stdout.strip().splitlines():
            vals = [int(v) for v in line.split()]
            row = dict(zip(COUNTERS, vals[1:]))
            per_board.append((suite[vals[0]][0], row))
            for k in COUNTERS:
                tot[k] += row[k]

        print("每個盤面的掃描工作（確定性，重跑結果相同）\n")
        print("%-10s %10s %12s %12s %12s"
              % ("盤面", "落子/撤銷", "hasAdj 讀格", "maxRunAt 讀格", "checkLine"))
        for name, row in per_board:
            print("%-10s %10d %12d %12d %12d"
                  % (name, row["g_placements"], row["g_adj_cells"],
                     row["g_run_cells"], row["g_checkline"]))
        print("%-10s %10d %12d %12d %12d"
              % ("合計", tot["g_placements"], tot["g_adj_cells"],
                 tot["g_run_cells"], tot["g_checkline"]))

        budget = [
            ("hasAdjacentPiece", tot["g_adj_calls"], tot["g_adj_cells"]),
            ("maxRunAt", tot["g_run_calls"], tot["g_run_cells"]),
            ("checkLine(索引)", tot["g_checkline"], tot["g_checkline"] * 4),
        ]
        total_cells = sum(c for _, _, c in budget)
        print("\n三個掃描基元的存取預算（合計）\n")
        print("%-20s %12s %14s %9s %8s" % ("基元", "呼叫數", "讀格數", "格/次", "佔比"))
        for name, calls, cells in budget:
            print("%-20s %12d %14d %9.2f %7.1f%%"
                  % (name, calls, cells, cells / calls if calls else 0,
                     100.0 * cells / total_cells if total_cells else 0))
        print("%-20s %12s %14d" % ("合計", "", total_cells))

        print("\njudgeMove 呼叫 %d 次，其中走到 checkLine 的 %d 次（%.1f%%）"
              % (tot["g_judge_calls"], tot["g_judge_deep"],
                 100.0 * tot["g_judge_deep"] / tot["g_judge_calls"] if tot["g_judge_calls"] else 0))
        print("endGame 內：禁手檢查點 %d 次，成五檢查點 %d 次（後者不需要 checkLine，"
              "佔全部 checkLine 呼叫的 %.1f%%）"
              % (tot["g_eg_forbid"], tot["g_eg_five"],
                 100.0 * tot["g_eg_five"] / tot["g_checkline"] if tot["g_checkline"] else 0))

        p = tot["g_placements"]
        print("\n增量維護的划算門檻（維護成本 vs 查詢省下的掃描）")
        if not p:
            print("  落子數為 0，這組盤面全被 endGame 快速路徑短路，算不出比值")
            return
        win_ratio = tot["g_checkline"] / p
        win_threshold = WINDOW_UPDATE_COST / WINDOW_QUERY_SAVING
        print("  windowIdx（已上線）：checkLine/落子 = %.2f，門檻 %.2f → %s"
              % (win_ratio, win_threshold, "划算" if win_ratio > win_threshold else "不划算"))
        adj_per_call = tot["g_adj_cells"] / tot["g_adj_calls"] if tot["g_adj_calls"] else 0
        if adj_per_call:
            adj_ratio = tot["g_adj_calls"] / p
            adj_threshold = ADJ_UPDATE_COST / adj_per_call
            print("  鄰格計數表（D2 待辦）：hasAdjacentPiece/落子 = %.2f，門檻 %.2f → %s"
                  % (adj_ratio, adj_threshold, "划算" if adj_ratio > adj_threshold else "不划算"))
        else:
            print("  鄰格計數表：hasAdjacentPiece 已不掃描盤面，門檻不適用（D2 已上線）")
    finally:
        shutil.rmtree(WORKDIR, ignore_errors=True)


if __name__ == "__main__":
    main()
