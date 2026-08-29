"""從 src/ai.c 生成 profiler 用的中間檔（ai_profiled_core.generated.c）。

為什麼需要生成而非 #define 改名：
  用 `#define evaluate prof_real_evaluate` 會把定義與ai.c 內部的呼叫一起改名，
  於是內部呼叫直接跳過 wrapper，所有計數器恆為 0（舊版就是這樣悄悄失效的）。
  這裡只改定義處的名字，呼叫處維持原名。連結時就會綁到 ai_profiled.c 的 wrapper。

ai.c 本身不被修改；每次編譯都重新生成，所以不會像舊 ai_profiled.c 那樣漂成化石。
"""
import os
import re
import sys

# 要插樁的函數：呼叫次數 + inclusive 耗時
TARGETS = [
    "evaluate", "quickEvaluate", "miniMax", "sortMoves",
    "endGame", "checkWin", "checkLine", "judgeMove",
]

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "ai.c")
OUT = os.path.join(HERE, "ai_profiled_core.generated.c")


def main():
    with open(SRC, encoding="utf-8") as f:
        src = f.read()
    original = src

    header = (
        "/* 自動生成，請勿手動編輯 —— 來源 src/ai.c，生成器 src/_bench/gen_profiled.py。\n"
        "   只有函數定義被改名為 prof_real_*；呼叫處維持原名以綁到 wrapper。 */\n"
    )

    # 呼叫處保留原名，但原名的宣告隨定義一起被改掉了，所以要補回 wrapper 的前置宣告。
    # 簽名直接從 ai.c 的定義行抽，不手寫一份會漂移的副本。
    protos = []
    for name in TARGETS:
        m = re.search(
            r"^(?:static\s+)?((?:int|void|bool)\s+)" + name + r"\s*\(([^)]*)\)\s*\{",
            original, re.M | re.S)
        if not m:
            sys.exit("gen_profiled: 抽不出 %s 的簽名——ai.c 的定義格式可能改了。" % name)
        ret, args = m.group(1), " ".join(m.group(2).split())
        protos.append("%s%s(%s);" % (ret, name, args))
    proto_block = ("\n/* wrapper 的前置宣告（簽名抽自 ai.c）*/\n"
                   + "\n".join(protos) + "\n")

    renamed = []
    for name in TARGETS:
        # 定義處的特徵：行首的回傳型別 + 函數名 + '('
        pattern = re.compile(
            r"^((?:static\s+)?(?:int|void|bool)\s+)" + name + r"(\s*\()",
            re.M,
        )
        src, n = pattern.subn(r"\1prof_real_" + name + r"\2", src)
        if n != 1:
            sys.exit("gen_profiled: %s 的定義找到 %d 處（預期 1）——"
                     "ai.c 的簽名可能改了，請更新 TARGETS 或 pattern。" % (name, n))
        renamed.append(name)

    # 宣告要放在它依賴的 BOARD_MAX 與 Move typedef 之後，不能擺在檔頭。
    anchor = re.search(r"^\}\s*Move\s*;\s*$", src, re.M)
    if not anchor:
        sys.exit("gen_profiled: 找不到 Move typedef，無法決定前置宣告的插入位置。")
    cut = anchor.end()
    src = src[:cut] + "\n" + proto_block + src[cut:]

    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write(header + src)

    print("generated %s (%d functions instrumented: %s)"
          % (os.path.basename(OUT), len(renamed), ", ".join(renamed)))


if __name__ == "__main__":
    main()
