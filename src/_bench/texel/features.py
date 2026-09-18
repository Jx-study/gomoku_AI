"""棋譜 -> 訓練局面的棋型計數（由 C 端 checkNow 抽取，不在 Python 重寫棋型分類）。

用法: python features.py <dll> <games.txt> <out.npz>

只取「黑方待下」的局面：搜索的最終迭代裡，黑 ai 的葉節點（8 或 6 層）與白 ai 的葉節點
（7 或 5 層）都落在黑方待下，所以 evaluate 在實戰中幾乎只看到這種局面。
每個局面存雙方 16 種棋型計數，以及 C 端 evaluate 在兩個視角的分數（對拍用）。
"""
import ctypes
import sys

import numpy as np

import engine


def parse(path):
    """每行: 走法序列 x,y,p ... | nopen=N result=W，格式同 datagen.py 的輸出。"""
    games = []
    for line in open(path):
        seq, meta = line.split('|')
        moves = [tuple(map(int, t.split(','))) for t in seq.split()]
        kv = dict(t.split('=') for t in meta.split())
        games.append((moves, int(kv['nopen']), int(kv['result'])))
    return games


def main():
    dll, src, out = sys.argv[1:4]
    lib = engine.load(dll, 'feat')
    n = engine.selfplay.BOARD_MAX
    games = parse(src)
    gid, ply, left, c1s, c2s, ev1s, ev2s, res = [], [], [], [], [], [], [], []
    b = [ctypes.c_int() for _ in range(4)]
    for g, (moves, nopen, result) in enumerate(games):
        board = [[0] * n for _ in range(n)]
        # 終局那一手之前的局面都不是終局；i = 盤上子數
        for i, (x, y, p) in enumerate(moves):
            if i >= nopen and i % 2 == 0:
                cb = engine.to_cboard(board)
                lib.getBounds(cb, *[ctypes.byref(v) for v in b])
                bounds = [v.value for v in b]
                c1 = (ctypes.c_int * 16)()
                c2 = (ctypes.c_int * 16)()
                lib.checkNow(cb, *bounds, 1, c1)
                lib.checkNow(cb, *bounds, 2, c2)
                gid.append(g); ply.append(i); left.append(len(moves) - i)
                c1s.append(list(c1)); c2s.append(list(c2))
                ev1s.append(lib.evaluate(cb, *bounds, 1))
                ev2s.append(lib.evaluate(cb, *bounds, 2))
                res.append(result)
            board[y][x] = p
    np.savez_compressed(out, gid=np.array(gid), ply=np.array(ply), left=np.array(left),
                        c1=np.array(c1s, dtype=np.int64), c2=np.array(c2s, dtype=np.int64),
                        ev1=np.array(ev1s, dtype=np.int64), ev2=np.array(ev2s, dtype=np.int64),
                        result=np.array(res))
    print(f"{len(games)} games -> {len(gid)} positions -> {out}")


if __name__ == '__main__':
    main()
