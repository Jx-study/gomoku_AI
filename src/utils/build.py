"""跨平台編譯腳本：把 lib/ 下的 C 模組與 ai.c 編成共享庫。

輸出檔名依平台自動選副檔名（Windows: ai.dll，Linux: ai.so，macOS: ai.dylib），
放在 src/ 根目錄，與 Gomuko.py 載入的路徑一致。

用法（在 src/ 下執行）：
    python utils/build.py
"""
import platform
import subprocess
import sys
from pathlib import Path

MODULES = [
    "zobrist.c", "pattern.c", "boardstate.c", "lines.c",
    "eval.c", "movegen.c", "vcf.c", "search.c",
]

EXT_BY_SYSTEM = {"Windows": "dll", "Linux": "so", "Darwin": "dylib"}


def main():
    src_dir = Path(__file__).resolve().parent.parent
    lib_dir = src_dir / "lib"

    ext = EXT_BY_SYSTEM.get(platform.system())
    if ext is None:
        sys.exit(f"build: 不支援的平台：{platform.system()}")

    output = src_dir / f"ai.{ext}"
    sources = [str(lib_dir / m) for m in MODULES] + ["ai.c"]
    cmd = ["gcc", "-I", str(lib_dir), "-shared", "-o", str(output), "-fPIC", *sources]

    print(" ".join(cmd))
    subprocess.run(cmd, cwd=src_dir, check=True)


if __name__ == "__main__":
    main()
