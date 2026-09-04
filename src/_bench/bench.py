"""AI 引擎效能與正確性量測的統一入口。

規則與狀態層的自動化測試在 src/tests/（pytest）；這裡量的是速度、工作量與棋力。
實作在 lib/，這支只負責分派與路徑處理。

python bench.py --help 列出子命令，python bench.py <子命令> --help 顯示參數。
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "lib")
SRC_DIR = os.path.normpath(os.path.join(HERE, ".."))   # src/
AI_C = os.path.join(SRC_DIR, "ai.c")
AI_DLL = os.path.join(SRC_DIR, "ai.dll")

EPILOG = """\
想知道的事 -> 用哪個子命令

  改動有沒有改變走法        moves      行為保持型的改動應該全 SAME
  改動有沒有讓棋力退步      strength   走法本來就會不同時只能看勝率
  下一個該優化誰            budget     三個掃描基元各佔多少工作
  checkLine 每次讀幾格      cells      只量 checkLine，兩個版本對比
  各函數被呼叫幾次          hotspots   呼叫數可信，秒數已被插樁開銷蓋過

判讀標準與已知陷阱見 README.md。
"""


def resolve(path):
    """轉成絕對路徑：使用者給的路徑相對於他的 CWD，子腳本在別的目錄執行。"""
    return os.path.abspath(path)


def need(path, what):
    if not os.path.exists(path):
        sys.exit("bench: 找不到%s：%s" % (what, path))
    return path


def run_script(script, args):
    return subprocess.run([sys.executable, os.path.join(LIB, script)] + list(args)).returncode


def cmd_moves(a):
    baseline = need(resolve(a.baseline), "基準 dll")
    new = need(resolve(a.new), "新版 dll")
    return run_script("ab_fresh.py", [baseline, new])


def cmd_strength(a):
    old = need(resolve(a.old), "舊版 dll")
    new = need(resolve(a.new), "新版 dll")
    if os.path.abspath(old) == os.path.abspath(new):
        sys.exit("bench: 兩顆 dll 必須是不同檔案路徑。ctypes 對同一路徑回傳同一個已載入\n"
                 "      模組，兩個引擎會共用同一份置換表。先 copy 成不同檔名。")
    return run_script("selfplay.py", [old, new] + a.rest)


def cmd_budget(a):
    return run_script("count_budget.py", [need(resolve(a.source), "ai.c")])


def cmd_cells(a):
    args = []
    if a.baseline:
        args.append(need(resolve(a.baseline), "基準 ai.c"))
        if a.new:
            args.append(need(resolve(a.new), "新版 ai.c"))
    elif a.new:
        sys.exit("bench: 只給新版沒給基準時無從對比；基準不指定會用 HEAD:src/ai.c。")
    return run_script("count_cells.py", args)


def cmd_hotspots(a):
    """生成插樁版、編譯、量測、刪掉生成物。

    分成三步手動做時容易漏掉重新生成，量到的會是上一版引擎，而且沒有警告。
    """
    dll = os.path.join(HERE, "ai_profiled.dll")
    generated = os.path.join(LIB, "ai_profiled_core.generated.c")
    try:
        if run_script("gen_profiled.py", []) != 0:
            return 1
        build = subprocess.run(["gcc", "-shared", "-o", dll, "-fPIC",
                                os.path.join(LIB, "ai_profiled.c")],
                               capture_output=True, text=True)
        if build.returncode != 0:
            sys.exit("bench: 編譯 ai_profiled.dll 失敗\n" + build.stderr)
        return subprocess.run(
            [sys.executable, "-c",
             "import benchmark_ai; benchmark_ai.profile_hotspots(%r)" % dll],
            cwd=LIB).returncode
    finally:
        # 插樁產物每次重新生成，留著會有量到舊引擎的風險
        for f in (dll, generated):
            if os.path.exists(f):
                os.remove(f)


def main():
    p = argparse.ArgumentParser(
        prog="bench.py",
        description=__doc__.split("\n\n")[0],
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", metavar="<子命令>")

    m = sub.add_parser("moves", help="走法有沒有變",
                       description="兩顆 dll 在三個沒有立即勝著的盤面上比走法，"
                                   "每個盤面各開一個新 process。行為保持型的改動應該"
                                   "全 SAME。出現 DIFF 先確認基準選對，見 README 陷阱 2。")
    m.add_argument("baseline", help="基準 dll，例如 ./ai_v3_0.dll")
    m.add_argument("new", nargs="?", default=AI_DLL, help="新版 dll，預設 src/ai.dll")
    m.set_defaults(func=cmd_moves)

    s = sub.add_parser("strength", help="棋力有沒有退步",
                       description="兩顆 dll 對打統計勝率。引擎是確定性的，局數開超過"
                                   "「開局數 × 2」只是重播。個位數百分點的差異這個"
                                   "harness 分辨不出來。")
    s.add_argument("old", help="舊版 dll")
    s.add_argument("new", help="新版 dll，必須是不同檔案路徑")
    s.add_argument("rest", nargs=argparse.REMAINDER,
                   help="其餘參數轉給 selfplay：[games] [--quiet] [--pgn <file>]")
    s.set_defaults(func=cmd_strength)

    b = sub.add_parser("budget", help="三個掃描基元的存取預算",
                       description="量 hasAdjacentPiece、maxRunAt、checkLine 各讀了幾個"
                                   "盤面格、各佔多少，另外給出增量維護划不划算的門檻判定。"
                                   "確定性指標，重跑結果相同。")
    b.add_argument("source", nargs="?", default=AI_C, help="要量的 ai.c，預設 src/ai.c")
    b.set_defaults(func=cmd_budget)

    c = sub.add_parser("cells", help="checkLine 每次讀幾格",
                       description="兩個版本對比。不跑 aiRound，用固定種子隨機鋪子掃四個"
                                   "密度。兩版若是同一種實作，比值恆為 1.00x，會提示基準"
                                   "選錯了。")
    c.add_argument("baseline", nargs="?", help="基準 ai.c，不給則用 HEAD:src/ai.c")
    c.add_argument("new", nargs="?", help="新版 ai.c，預設 src/ai.c")
    c.set_defaults(func=cmd_cells)

    h = sub.add_parser("hotspots", help="各函數被呼叫幾次",
                       description="量目前的 src/ai.c，會重新生成並編譯插樁版，量完刪除。"
                                   "呼叫數上萬的函數秒數會標 *，那些列只讀呼叫數。")
    h.set_defaults(func=cmd_hotspots)

    a = p.parse_args()
    if not a.cmd:
        p.print_help()
        return 0
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
