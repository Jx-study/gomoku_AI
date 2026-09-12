"""展開 src/lib/ai_unity.c 的本地 #include "*.c"，回傳串接後的原始碼。

ai.c 拆成多檔後，三個對原始碼做文字插樁的工具（gen_profiled.py、
count_budget.py、count_cells.py）都要看到「像單檔時代 ai.c 一樣」的
完整文字，才能沿用既有的正規表示式探針。ai_unity.c 本身只是一串
#include，不含任何函數定義，必須先展開。

只展開副檔名 .c 的本地 include；.h 留給編譯器正常處理（各模組 .c
已各自 #include 需要的 header，展開時不重複讀取 .h 內容）。
"""
import os
import re
import sys

INCLUDE_RE = re.compile(r'^#include\s+"([^"]+\.c)"\s*$', re.M)


def expand(unity_path):
    src_dir = os.path.dirname(unity_path)
    with open(unity_path, encoding="utf-8") as f:
        unity_src = f.read()
    names = INCLUDE_RE.findall(unity_src)
    if not names:
        sys.exit("unity: %s 找不到任何 #include \"*.c\"，"
                 "unity build 的組成可能改了。" % os.path.basename(unity_path))
    parts = []
    for name in names:
        path = os.path.join(src_dir, name)
        if not os.path.exists(path):
            sys.exit("unity: %s 引用的 %s 不存在。" % (os.path.basename(unity_path), name))
        with open(path, encoding="utf-8") as f:
            parts.append(f.read())
    return "\n".join(parts)
