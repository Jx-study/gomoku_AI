"""量搜索過程中「落子/撤銷次數」與「checkLine 呼叫次數」的比例。

增量維護索引的成本模型：落子時更新 4 方向 × 10 格 × 黑白兩視角 = 80 次索引修正，
換掉每次 checkLine 的 40 格讀取。所以增量划算的門檻是

    checkLine 呼叫數 / 落子數 > 80 / 40 = 2

比值低於門檻表示維護比查詢還貴，增量就不該做。

做法與 count_cells.py 同一套路：讀 ai.c，只在落子處與 checkLine 入口插計數器，
ai.c 本身不修改，每次執行重新生成。計數是確定性的，重跑結果相同。

用法（在 src/_bench/ 下）：
    python count_updates.py [ai.c 路徑]     # 預設 ../ai.c
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.join(HERE, "..", "ai.c")
# 中間檔放本目錄而非系統暫存區：Windows 的應用程式控制原則會擋掉暫存區裡的執行檔
WORKDIR = os.path.join(HERE, "_count_updates_tmp")

# 與 benchmark_ai.py 同一組盤面，數字才對得上既有的效能紀錄
BASE_OFFSETS = [
    (0, 0, 1), (0, 1, 2), (1, 1, 1), (-1, -1, 2),
    (2, 2, 1), (-1, 1, 2), (-2, -2, 1), (1, -1, 2),
    (3, 3, 1), (-2, 2, 2), (1, 2, 1), (0, 2, 2),
    (2, 0, 1), (3, -1, 2),
]
EXTRA_OFFSETS = [
    (4, -2, 1), (-3, 3, 2), (-1, -2, 1), (2, -2, 2),
    (5, -3, 1), (-4, 4, 2), (0, -2, 1), (1, -2, 2),
    (-2, 0, 1), (4, 2, 2), (-3, -3, 1), (5, 5, 2),
]

# 落子/撤銷收斂進 placeStone/removeStone 之後，寫入格的地方只剩這兩個函數體內各一次；
# 呼叫端的 12 處改成呼叫這兩個函數，計數點跟著搬到函數入口
EXPECTED_WRITES = 12

PROBES = [
    # checkLine 入口
    ("void checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int my_line[14]) {",
     "void checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int my_line[14]) {\n"
     "    g_checkline++;"),
    # 落子/撤銷單一入口，取代舊版直接比對 board[y][x] = ... 的寫入形式
    ("static void placeStone(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {",
     "static void placeStone(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {\n"
     "    g_placements++;"),
    ("static void removeStone(int board[BOARD_MAX][BOARD_MAX], int x, int y) {",
     "static void removeStone(int board[BOARD_MAX][BOARD_MAX], int x, int y) {\n"
     "    g_placements++;"),
    # 順帶量 hasAdjacentPiece 的呼叫數與讀格數
    ("bool hasAdjacentPiece(int board[BOARD_MAX][BOARD_MAX], int x, int y) {",
     "bool hasAdjacentPiece(int board[BOARD_MAX][BOARD_MAX], int x, int y) {\n"
     "    g_adj_calls++;"),
    ("            if (nx >= 0 && nx < BOARD_MAX && ny >= 0 && ny < BOARD_MAX && board[ny][nx] != 0) {",
     "            g_adj_cells++;\n"
     "            if (nx >= 0 && nx < BOARD_MAX && ny >= 0 && ny < BOARD_MAX && board[ny][nx] != 0) {"),
]

DRIVER = r"""
#include <stdio.h>

long long g_placements = 0;
long long g_checkline = 0;
long long g_adj_calls = 0;
long long g_adj_cells = 0;

void initZobristTable(void);
void aiRound(int board[%(bm)d][%(bm)d], int ai, int roundCounter, int *bestx, int *besty);

static int board[%(bm)d][%(bm)d];

static const int MOVES[%(nmoves)d][3] = {
%(moves)s
};
static const int STOPS[%(nstops)d] = {%(stops)s};

int main(void) {
    initZobristTable();
    for (int s = 0; s < %(nstops)d; s++) {
        int n = STOPS[s];
        for (int y = 0; y < %(bm)d; y++)
            for (int x = 0; x < %(bm)d; x++) board[y][x] = 0;
        for (int i = 0; i < n; i++)
            board[MOVES[i][1]][MOVES[i][0]] = MOVES[i][2];

        g_placements = g_checkline = g_adj_calls = g_adj_cells = 0;
        int bx = -1, by = -1;
        aiRound(board, 2, n + 1, &bx, &by);   // 下一手輪白棋，與 benchmark_ai.py 一致
        printf("%%d %%lld %%lld %%lld %%lld\n",
               n, g_placements, g_checkline, g_adj_calls, g_adj_cells);
    }
    return 0;
}
"""


def board_max(src):
    m = re.search(r"^#define\s+BOARD_MAX\s+(\d+)", src, re.M)
    if not m:
        sys.exit("count_updates: ai.c 抽不到 BOARD_MAX——定義格式可能改了。")
    return int(m.group(1))


def instrument(src):
    # 呼叫處（不含函數定義本身）應該有 12 個，對應 Task 1 收斂進 placeStone/removeStone 的 12 處寫入
    def_re = re.compile(r"^static (?:void|int) (?:placeStone|removeStone)\(", re.M)
    call_re = re.compile(r"\b(?:placeStone|removeStone)\(")
    calls = len(call_re.findall(src)) - len(def_re.findall(src))
    if calls != EXPECTED_WRITES:
        sys.exit("count_updates: placeStone/removeStone 呼叫處找到 %d 個（預期 %d）——"
                 "ai.c 的落子/撤銷形式可能改了。" % (calls, EXPECTED_WRITES))
    out = src
    for needle, replacement in PROBES:
        if needle not in out:
            sys.exit("count_updates: 找不到探針錨點，ai.c 可能改了：\n  %s" % needle[:70])
        out = out.replace(needle, replacement, 1)
    decls = ("extern long long g_placements;\nextern long long g_checkline;\n"
             "extern long long g_adj_calls;\nextern long long g_adj_cells;\n")
    return decls + out


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    with open(src_path, encoding="utf-8") as f:
        src = f.read()
    bm = board_max(src)
    c = bm // 2

    moves = [(c + dx, c + dy, p) for dx, dy, p in BASE_OFFSETS + EXTRA_OFFSETS]
    stops = list(range(len(BASE_OFFSETS), len(BASE_OFFSETS) + len(EXTRA_OFFSETS) + 1, 4))

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
                "nmoves": len(moves),
                "moves": "\n".join("    {%d, %d, %d}," % m for m in moves),
                "nstops": len(stops),
                "stops": ", ".join(str(s) for s in stops),
            })

        exe = os.path.join(WORKDIR, "probe.exe")
        build = subprocess.run(["gcc", "-O2", "-o", exe, drv, core],
                               capture_output=True, text=True)
        if build.returncode != 0:
            sys.exit("count_updates: 編譯失敗\n" + build.stderr)

        run = subprocess.run([exe], capture_output=True, text=True)
        if run.returncode != 0:
            sys.exit("count_updates: 執行失敗\n" + run.stderr)

        print("每手搜索中的落子數與 checkLine 呼叫數（確定性）\n")
        print("%-6s %12s %14s %10s" % ("子數", "落子/撤銷", "checkLine", "比值"))
        tot_p = tot_c = tot_ac = tot_ad = 0
        for line in run.stdout.strip().splitlines():
            n, p, cl, ac, ad = (int(v) for v in line.split())
            tot_p += p
            tot_c += cl
            tot_ac += ac
            tot_ad += ad
            ratio = ("%.2f" % (cl / p)) if p else "—"
            print("%-6d %12d %14d %10s" % (n, p, cl, ratio))
        print("%-6s %12d %14d %10s"
              % ("合計", tot_p, tot_c, ("%.2f" % (tot_c / tot_p)) if tot_p else "—"))

        print("\n增量划算門檻：比值 > 2.00（維護 80 次 vs 查詢省下 40 格）")
        if tot_p:
            verdict = "划算" if tot_c / tot_p > 2 else "不划算"
            print("實測合計比值 %.2f → %s" % (tot_c / tot_p, verdict))

        print("\n順帶（鄰格計數表用）：hasAdjacentPiece 呼叫 %d 次，讀格 %d 次，平均 %.2f 格/次"
              % (tot_ac, tot_ad, (tot_ad / tot_ac) if tot_ac else 0))
    finally:
        shutil.rmtree(WORKDIR, ignore_errors=True)


if __name__ == "__main__":
    main()
