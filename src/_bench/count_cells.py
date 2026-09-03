"""量 `checkLine` 每次呼叫讀取幾個盤面格——確定性的效能代理指標。

`checkLine` 單次只有幾十奈秒，計時會被 CPU 頻率、排程、背景程序蓋過；存取格數跑幾次都一樣，
而且直接對應改動的本質：逐格掃描遇對手子或連續兩空格就 break，查表版每方向必須掃滿 10 格
才能得到索引。

做法與 gen_profiled.py 同一套路：讀 ai.c，只在盤面存取處插一個計數器，ai.c 本身不修改，
每次執行重新生成。

用法（在 src/_bench/ 下）：
    python count_cells.py old.c [new.c]        # new 預設 ../ai.c
    python count_cells.py                      # 基準預設 HEAD:src/ai.c

基準要選「只差你這一項」的版本（見 README 陷阱 2）；兩版若是同一種實作，比值恆為 1.00x。
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_NEW = os.path.join(HERE, "..", "ai.c")
# 中間檔放本目錄而非系統暫存區：Windows 的應用程式控制原則會擋掉暫存區裡的執行檔
WORKDIR = os.path.join(HERE, "_count_cells_tmp")

# 涵蓋開局到中盤：掃描版的存取量隨密度上升，查表版恆定，比值要看區間而非單點
STONE_COUNTS = [8, 18, 50, 80]

# 兩種實作各自的「讀取一格」位置。抽不到就報錯，不靜默給出錯的數字
PROBES = [
    # 逐格掃描版 checkConsecutive：通過邊界檢查才真的讀 board
    ("逐格掃描",
     "if (nx >= 0 && nx < (BOARD_MAX) && ny >= 0 && ny < (BOARD_MAX)) {",
     "if (nx >= 0 && nx < (BOARD_MAX) && ny >= 0 && ny < (BOARD_MAX)) {\n                cells_read++;"),
    # 查表版 encodeWindow：中心以外每一格都要讀（出界也要判斷）
    ("查表",
     "        if (off == 0) continue;   // 中心不入索引",
     "        if (off == 0) continue;   // 中心不入索引\n        cells_read++;"),
]

DRIVER = r"""
#include <stdio.h>
long cells_read = 0;
void checkLine(int b[%(bm)d][%(bm)d], int x, int y, int p, int ml[14]);
static int board[%(bm)d][%(bm)d];

int main(void) {
    /* 固定種子鋪子：兩版看到完全相同的盤面，差異才只來自實作 */
    unsigned s = 12345;
    int placed = 0;
    while (placed < %(stones)d) {
        s = s * 1103515245u + 12345u; int x = (s >> 16) %% %(bm)d;
        s = s * 1103515245u + 12345u; int y = (s >> 16) %% %(bm)d;
        if (!board[y][x]) { board[y][x] = (placed %% 2) + 1; placed++; }
    }
    int warm[14] = {0};
    checkLine(board, %(mid)d, %(mid)d, 1, warm);   /* 查表版首次呼叫要建表，不計入 */

    cells_read = 0;
    int calls = 0;
    for (int y = 0; y < %(bm)d; y++)
        for (int x = 0; x < %(bm)d; x++) {
            if (board[y][x]) continue;
            int ml[14] = {0};
            checkLine(board, x, y, 1, ml);
            calls++;
        }
    printf("%%.2f %%ld %%d\n", (double)cells_read / calls, cells_read, calls);
    return 0;
}
"""


def board_max(src):
    m = re.search(r"^#define\s+BOARD_MAX\s+(\d+)", src, re.M)
    if not m:
        sys.exit("count_cells: ai.c 抽不到 BOARD_MAX——定義格式可能改了。")
    return int(m.group(1))


def instrument(src, label):
    """插入計數器，回傳（插樁後的原始碼, 命中的實作名）。"""
    out = src
    kind = None
    for name, needle, replacement in PROBES:
        if needle in out:
            out = out.replace(needle, replacement, 1)
            kind = name
            break
    if kind is None:
        sys.exit("count_cells: %s 找不到任何盤面存取點——探針要跟著 ai.c 更新。" % label)
    return "extern long cells_read;\n" + out, kind


def measure(src_path, stones, workdir):
    with open(src_path, encoding="utf-8") as f:
        src = f.read()
    label = os.path.basename(src_path)
    bm = board_max(src)

    core = os.path.join(workdir, "core_%s.c" % label.replace(".", "_"))
    instrumented, kind = instrument(src, label)
    with open(core, "w", encoding="utf-8") as f:
        f.write(instrumented)

    drv = os.path.join(workdir, "drv.c")
    with open(drv, "w", encoding="utf-8") as f:
        f.write(DRIVER % {"bm": bm, "stones": stones, "mid": bm // 2})

    exe = os.path.join(workdir, "probe.exe")
    build = subprocess.run(["gcc", "-O2", "-o", exe, drv, core],
                           capture_output=True, text=True)
    if build.returncode != 0:
        sys.exit("count_cells: 編譯 %s 失敗\n%s" % (label, build.stderr))

    run = subprocess.run([exe], capture_output=True, text=True)
    if run.returncode != 0:
        sys.exit("count_cells: 執行 %s 失敗\n%s" % (label, run.stderr))
    per, total, calls = run.stdout.split()
    return float(per), int(total), int(calls), kind


def main():
    new_src = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_NEW
    if len(sys.argv) > 1:
        old_src = sys.argv[1]
        old_label = os.path.basename(old_src)
    else:
        old_src = None
        old_label = "HEAD:src/ai.c"

    shutil.rmtree(WORKDIR, ignore_errors=True)
    os.makedirs(WORKDIR)
    try:
        workdir = WORKDIR
        if old_src is None:
            old_src = os.path.join(workdir, "head.c")
            head = subprocess.run(["git", "show", "HEAD:src/ai.c"],
                                  capture_output=True, text=True, cwd=HERE)
            if head.returncode != 0:
                sys.exit("count_cells: 取不到 HEAD:src/ai.c\n" + head.stderr)
            with open(old_src, "w", encoding="utf-8") as f:
                f.write(head.stdout)

        rows = []
        old_kind = new_kind = None
        for stones in STONE_COUNTS:
            o, _, _, old_kind = measure(old_src, stones, workdir)
            n, _, _, new_kind = measure(new_src, stones, workdir)
            rows.append((stones, o, n))

        print("每次 checkLine 讀取的盤面格數（確定性，重跑結果相同）\n")
        print("%-6s %12s %12s %8s" % ("子數", "before", "after", "比值"))
        for stones, o, n in rows:
            ratio = ("%.2fx" % (n / o)) if o else "—"
            print("%-6d %12.2f %12.2f %8s" % (stones, o, n, ratio))

        print("\nbefore = %s（%s）" % (old_label, old_kind))
        print("after  = %s（%s）" % (os.path.relpath(new_src, HERE), new_kind))
        if old_kind == new_kind:
            print("\n警告：兩版是同一種實作，比值恆為 1.00x——基準選錯了。"
                  "要挑實作真的不同的版本，見 README 陷阱 2。")
    finally:
        shutil.rmtree(WORKDIR, ignore_errors=True)


if __name__ == "__main__":
    main()
