"""N0：平行自對弈產生訓練棋譜。

用法: python datagen.py <dll> <games> <out.txt> [--params p.json] [--extra 2-6] [--seed 1] [--jobs 14]

開局 = RIF 三手 + 隨機 extra 手（引擎確定性，不隨機就只有 104 盤不同的棋）。
輸出每行: 走法序列 x,y,p ... | nopen=N result=W
"""
import argparse
import json
import multiprocessing as mp
import os
import random
import sys
import time

import engine
from openings_rif import OPENINGS

_black = _white = None


def _init(dll, params):
    global _black, _white
    pid = os.getpid()
    _black = engine.load(dll, f"dg{pid}_b")
    _white = engine.load(dll, f"dg{pid}_w")
    if params:
        engine.set_params(_black, params)
        engine.set_params(_white, params)


def _task(args):
    seed, lo, hi = args
    rng = random.Random(seed)
    c = engine.selfplay.BOARD_MAX // 2
    base = [(c + dx, c + dy, p) for dx, dy, p in rng.choice(OPENINGS)]
    opening = engine.random_opening(rng, _black, base, rng.randint(lo, hi))
    w, moves, reason = engine.play(_black, _white, opening)
    return moves, len(opening), w, reason


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dll')
    ap.add_argument('games', type=int)
    ap.add_argument('out')
    ap.add_argument('--params')
    ap.add_argument('--extra', default='2-6')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--jobs', type=int, default=14)
    a = ap.parse_args()
    lo, hi = map(int, a.extra.split('-'))
    params = json.load(open(a.params)) if a.params else None

    t0 = time.time()
    tasks = [(a.seed * 1_000_003 + i, lo, hi) for i in range(a.games)]
    res_count, reasons, seen = {}, {}, set()
    with mp.Pool(a.jobs, _init, (os.path.abspath(a.dll), params)) as pool, open(a.out, 'w') as f:
        for moves, nopen, w, reason in pool.imap_unordered(_task, tasks, chunksize=4):
            key = tuple(moves)
            if key in seen:  # 重複的對局不寫，避免同一盤棋重複計權
                reasons['dup'] = reasons.get('dup', 0) + 1
                continue
            seen.add(key)
            res_count[w] = res_count.get(w, 0) + 1
            reasons[reason] = reasons.get(reason, 0) + 1
            f.write(' '.join(f"{x},{y},{p}" for x, y, p in moves) + f" | nopen={nopen} result={w}\n")
    print(f"{a.games} games in {time.time() - t0:.0f}s  results={res_count}  endings={reasons}")


if __name__ == '__main__':
    main()
