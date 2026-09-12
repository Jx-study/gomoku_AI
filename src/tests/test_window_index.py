"""windowIdx 增量索引的不變量測試。

`boardstate.c` 在 `placeStone` / `removeStone` 之後，`#ifdef WINDOW_IDX_CHECK`
包住一段全盤 × 4 方向 × 兩視角的 `assert`：增量修正後的 `windowIdx` 必須等於
當場對 `encodeWindow` 重算的結果。預設編譯不带這個巨集（保持搜索速度），
所以本檔另外編譯一顆帶 `-DWINDOW_IDX_CHECK` 的 debug DLL 來跑。這個巨集的
`#ifdef` 區段橫跨 `boardstate.c` 與 `lines.c` 兩個模組，要對整個編譯命令生效。

`assert()` 失敗會呼叫 `abort()` 直接砍掉呼叫它的行程——若直接在 pytest 的
行程裡用 ctypes 呼叫，一旦踩雷整個測試套件就跟著死。所以每個場景都用
`subprocess.run` 開一個獨立的 Python 行程載入 debug DLL 跑搜索，斷言失敗
只會讓子行程以非零/負值結束，父行程照樣把它當一般測試失敗回報。

場景取材自 test_vcf.py 的 LADDER（會走進 vcfSearch 的 8 個賦值點）與
test_ai_opening.py 的中局佈局（走 miniMax／findBestMove 的 2 個賦值點），
兩者合起來才會踩過全部 12 處落子/撤銷入口。

需要先能編譯共享庫（本檔的 fixture 會自動用 src/lib/*.c 排除 ai_unity.c 後編譯，
不需要手動執行）：
    cd src && gcc -I lib -shared -o ai.dll -fPIC -DWINDOW_IDX_CHECK lib/zobrist.c lib/pattern.c lib/boardstate.c lib/lines.c lib/eval.c lib/movegen.c lib/vcf.c lib/search.c ai.c
找不到 gcc 時整個模組會被 skip。
"""
import glob
import os
import platform
import shutil
import subprocess
import sys
import textwrap

import pytest

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_DIR = os.path.join(SRC_DIR, "lib")
DEBUG_DIR = os.path.join(SRC_DIR, "_window_idx_debug_build")


def _lib_filename(tag=""):
    system = platform.system()
    if system == "Windows":
        return f"ai_{tag}.dll" if tag else "ai.dll"
    if system == "Darwin":
        return f"libai_{tag}.dylib" if tag else "libai.dylib"
    return f"libai_{tag}.so" if tag else "libai.so"


GCC = shutil.which("gcc")

pytestmark = pytest.mark.skipif(
    GCC is None,
    reason="找不到 gcc，無法編譯帶 WINDOW_IDX_CHECK 的 debug DLL",
)

BLACK, WHITE = 1, 2

# 與 test_vcf.py 相同的兩手連殺場景：走進 vcfSearch 內部的 8 個落子/撤銷點
LADDER = [
    (-2, 0, WHITE), (-1, 0, WHITE), (0, 0, WHITE),
    (1, 1, WHITE), (1, 2, WHITE),
    (-3, 0, BLACK),
    (5, 4, BLACK), (6, 4, BLACK), (5, 5, BLACK), (6, 5, BLACK),
]

# 中局亂局，逼 findBestMove 真的跑 miniMax（非開局分支、非算殺秒殺）
MIDGAME = [
    (0, 0, BLACK), (0, 1, WHITE), (1, 1, BLACK), (-1, -1, WHITE),
    (2, 2, BLACK), (-1, 1, WHITE), (-2, -2, BLACK), (1, -1, WHITE),
    (3, 3, BLACK), (-2, 2, WHITE), (1, 2, BLACK), (0, 2, WHITE),
]


@pytest.fixture(scope="module")
def debug_dll():
    """編譯一顆帶 WINDOW_IDX_CHECK 的 debug DLL，回傳路徑。

    輸出檔名帶 PID，不覆寫舊路徑：子行程用 ctypes.CDLL 載入過的 DLL，
    Windows 有時不會在行程結束當下就釋放檔案 handle，若沿用同一個檔名，
    下一次（甚至下一輪 pytest）gcc 覆寫時會因為目標檔案仍被鎖住而連結
    失敗——mingw 的 gcc 前端這種失敗不一定會印 stderr，只回傳非零。
    """
    os.makedirs(DEBUG_DIR, exist_ok=True)
    out_path = os.path.join(DEBUG_DIR, _lib_filename(f"debug_{os.getpid()}"))
    # WINDOW_IDX_CHECK 的 #ifdef 區段橫跨 boardstate.c 與 lines.c 兩個模組，
    # 巨集要對整個編譯命令生效，不能只傳單一來源檔。排除 ai_unity.c：
    # 它自己 #include 了下面這些同名 .c，一起編會變成重複定義
    lib_paths = sorted(
        p for p in glob.glob(os.path.join(LIB_DIR, "*.c"))
        if os.path.basename(p) != "ai_unity.c"
    )
    src_paths = lib_paths + [os.path.join(SRC_DIR, "ai.c")]
    try:
        result = subprocess.run(
            [GCC, "-I", LIB_DIR, "-shared", "-o", out_path, "-fPIC",
             "-DWINDOW_IDX_CHECK", *src_paths],
            capture_output=True, text=True,
        )
    except OSError as e:
        pytest.fail(f"debug DLL 編譯無法啟動 gcc：{e!r}\nGCC={GCC!r} out_path={out_path!r}")
    if result.returncode != 0:
        pytest.fail(
            f"debug DLL 編譯失敗 (returncode={result.returncode})\n"
            f"stdout:\n{result.stdout!r}\nstderr:\n{result.stderr!r}\n"
            f"GCC={GCC!r} out_path={out_path!r} exists={os.path.exists(out_path)}"
        )
    yield out_path
    try:
        os.remove(out_path)
    except OSError:
        pass   # 子行程可能還沒釋放 handle，留給下次帶新 PID 的 fixture 或人工清理


# 子行程驅動程式：載入指定 DLL，把 offsets 佈到盤面，然後跑一次 aiRound
# 或 vcfProbe。斷言若在 C 端炸開，這個 Python 行程會被 abort() 砍掉，
# 母行程只看到非零/負值的 returncode，不受影響。
_DRIVER = textwrap.dedent(r"""
    import ctypes, sys

    dll_path = sys.argv[1]
    mode = sys.argv[2]   # "aiRound" 或 "vcfProbe"

    lib = ctypes.CDLL(dll_path)
    lib.getBoardMax.restype = ctypes.c_int
    bm = lib.getBoardMax()
    board_type = (ctypes.c_int * bm) * bm
    board_ptr = ctypes.POINTER(board_type)

    lib.initZobristTable.restype = None
    lib.initTranspositionTable.restype = None
    lib.aiRound.restype = None
    lib.aiRound.argtypes = [board_ptr, ctypes.c_int, ctypes.c_int,
                            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    lib.vcfProbe.restype = ctypes.c_int
    lib.vcfProbe.argtypes = [board_ptr, ctypes.c_int,
                             ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    lib.initZobristTable()
    lib.initTranspositionTable()

    m = bm // 2
    board = board_type()
    offsets = eval(sys.argv[3])
    for dx, dy, colour in offsets:
        board[m + dy][m + dx] = colour

    if mode == "aiRound":
        bx, by = ctypes.c_int(-1), ctypes.c_int(-1)
        player = int(sys.argv[4])
        round_counter = max(len(offsets) + 1, 9)
        lib.aiRound(ctypes.byref(board), player, round_counter,
                    ctypes.byref(bx), ctypes.byref(by))
        print(f"OK move=({bx.value - m},{by.value - m})")
    elif mode == "vcfProbe":
        attacker = int(sys.argv[4])
        wx, wy = ctypes.c_int(-1), ctypes.c_int(-1)
        found = lib.vcfProbe(ctypes.byref(board), attacker,
                             ctypes.byref(wx), ctypes.byref(wy))
        print(f"OK found={found} move=({wx.value - m},{wy.value - m})")
    else:
        sys.exit(f"unknown mode {mode}")
""")


def _run_driver(dll_path, mode, offsets, player):
    driver_path = os.path.join(DEBUG_DIR, f"_driver_{os.getpid()}.py")
    with open(driver_path, "w", encoding="utf-8") as f:
        f.write(_DRIVER)
    try:
        return subprocess.run(
            [sys.executable, driver_path, dll_path, mode, repr(offsets), str(player)],
            capture_output=True, text=True, timeout=120,
        )
    finally:
        try:
            os.remove(driver_path)
        except OSError:
            pass


class TestInvariantHoldsOnRealSearches:
    """驅動真實搜索路徑，assert 若失敗會讓子行程 abort，而不是拖垮測試套件。"""

    def test_aiRound_on_midgame_position(self, debug_dll):
        """miniMax 的 2 個落子/撤銷點：吃到 findBestMove 的主搜索迴圈。"""
        r = _run_driver(debug_dll, "aiRound", MIDGAME, WHITE)
        assert r.returncode == 0, (
            f"debug DLL 在 aiRound 中途中止（returncode={r.returncode}）\n"
            f"stdout: {r.stdout}\nstderr: {r.stderr}"
        )
        assert r.stdout.startswith("OK"), f"未預期輸出: {r.stdout}\n{r.stderr}"

    def test_aiRound_on_several_midgame_positions(self, debug_dll):
        """多個中局局面 × 雙方視角，加大踩到不同分支組合的機會。"""
        positions = [
            MIDGAME,
            MIDGAME + [(4, -2, BLACK), (-3, 3, WHITE)],
            MIDGAME + [(-1, -2, BLACK), (2, -2, WHITE), (5, -3, BLACK)],
        ]
        for offsets in positions:
            for player in (BLACK, WHITE):
                r = _run_driver(debug_dll, "aiRound", offsets, player)
                assert r.returncode == 0, (
                    f"debug DLL 在 aiRound 中途中止（offsets={offsets}, player={player}）\n"
                    f"stdout: {r.stdout}\nstderr: {r.stderr}"
                )

    def test_vcfProbe_on_forcing_position(self, debug_dll):
        """LADDER 場景會遞迴進 vcfSearch，吃到它內部的 8 個落子/撤銷點。"""
        r = _run_driver(debug_dll, "vcfProbe", LADDER, WHITE)
        assert r.returncode == 0, (
            f"debug DLL 在 vcfProbe 中途中止（returncode={r.returncode}）\n"
            f"stdout: {r.stdout}\nstderr: {r.stderr}"
        )
        assert "OK found=1" in r.stdout, f"場景應該找到連殺: {r.stdout}\n{r.stderr}"
