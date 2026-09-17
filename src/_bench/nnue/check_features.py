"""把 cell-code 特徵按棋型碼彙總，與 C 端 checkNow 的計數逐筆對拍。

用法: python check_features.py <dll> <games.txt> [n_games]

不過這關就不要往下走：特徵與引擎看到的棋型不一致，後面所有訓練都是在學別的東西。
對拍只跑前幾十局，因為不一致是系統性的（方向表順序或索引規則錯），不需要全量。
"""
import ctypes
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'texel'))
import engine  # noqa: E402
import features_pos as F  # noqa: E402


def main():
    dll, games = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    lib = engine.load(dll, 'chkfeat')
    table = F.bind(lib)
    n = engine.selfplay.BOARD_MAX
    b = [ctypes.c_int() for _ in range(4)]
    checked = bad = 0

    for moves, nopen, _ in F.parse(games)[:limit]:
        board = [[0] * n for _ in range(n)]
        for i, (x, y, p) in enumerate(moves):
            if i >= nopen and i % 2 == 0:
                feats = F.extract(lib, table, board, n, 'cell-code')
                cb = engine.to_cboard(board)
                lib.getBounds(cb, *[ctypes.byref(v) for v in b])
                bounds = [v.value for v in b]
                for color in (1, 2):
                    cnt = (ctypes.c_int * 16)()
                    lib.checkNow(cb, *bounds, color, cnt)
                    mine = np.zeros(16, dtype=np.int64)
                    for f in feats[color - 1]:
                        mine[f % F.N_CODES + 1] += 1
                    checked += 1
                    if list(mine[1:16]) != list(cnt)[1:16]:
                        bad += 1
            board[y][x] = p

    print(f"checked={checked} mismatches={bad}")
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
