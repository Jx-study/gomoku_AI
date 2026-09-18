"""調參版 vs 原版對打：同一顆 dll，兩組評估參數，每個開局黑白互換各打一局。

用法: python match.py <dll> <A.json|default> <B.json|default> [--rif] [--random N --seed S] [--jobs 14]

--rif 用 104 組 RIF 開局（selfplay 的基準池）；--random N 另加 N 組 RIF + 2~6 隨機手的開局。
報告以「配對」為單位：A 兩局全勝 / 各勝一局 / B 兩局全勝。只有非平分的配對帶有強弱資訊。
"""
import argparse
import json
import math
import multiprocessing as mp
import os
import random

import engine
from openings_rif import OPENINGS

_A = _B = None


def _params(spec):
    return None if spec == 'default' else json.load(open(spec))


def _init(dll, pa, pb):
    global _A, _B
    pid = os.getpid()
    _A = engine.load(dll, f"mA{pid}")
    _B = engine.load(dll, f"mB{pid}")
    if pa:
        engine.set_params(_A, pa)
    if pb:
        engine.set_params(_B, pb)


def _pair(opening):
    w1, m1, _ = engine.play(_A, _B, opening)   # A 執黑
    w2, m2, _ = engine.play(_B, _A, opening)   # B 執黑
    a = (1.0 if w1 == 1 else 0.5 if w1 == 0 else 0.0) + (1.0 if w2 == 2 else 0.5 if w2 == 0 else 0.0)
    return a, len(m1), len(m2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dll')
    ap.add_argument('A')
    ap.add_argument('B')
    ap.add_argument('--rif', action='store_true')
    ap.add_argument('--random', type=int, default=0)
    ap.add_argument('--seed', type=int, default=999)
    ap.add_argument('--jobs', type=int, default=14)
    a = ap.parse_args()

    # 開局在主 process 產生：需要 dll 判黑棋禁手
    lib = engine.load(a.dll, 'mgen')
    c = engine.selfplay.BOARD_MAX // 2
    openings = []
    if a.rif:
        openings += [[(c + dx, c + dy, p) for dx, dy, p in o] for o in OPENINGS]
    rng = random.Random(a.seed)
    for _ in range(a.random):
        base = [(c + dx, c + dy, p) for dx, dy, p in rng.choice(OPENINGS)]
        openings.append(engine.random_opening(rng, lib, base, rng.randint(2, 6)))
    assert openings, "開局池是空的：至少要給 --rif 或 --random N 其中一個"

    with mp.Pool(a.jobs, _init, (os.path.abspath(a.dll), _params(a.A), _params(a.B))) as pool:
        res = pool.map(_pair, openings, chunksize=2)
    scores = [r[0] for r in res]
    n = len(scores)
    total = sum(scores)
    wins2, split, loss2 = scores.count(2.0), sum(1 for s in scores if 0 < s < 2), scores.count(0.0)
    # 配對差異的標準誤：離差取自樣本均值
    mean = total / n
    sd = math.sqrt(sum((s - mean) ** 2 for s in scores) / max(n - 1, 1))
    se = sd / math.sqrt(n) / 2          # 換算成勝率的標準誤
    print(f"{n} pairs ({2 * n} games): A {total:.1f} / {2 * n}  = {total / (2 * n) * 100:.1f}%  "
          f"(±{1.96 * se * 100:.1f}% 95% CI)")
    print(f"  A 2-0: {wins2}   1-1: {split}   B 2-0: {loss2}")
    lens = [r[1] for r in res] + [r[2] for r in res]
    print(f"  game length median {sorted(lens)[len(lens) // 2]}")
    if a.rif and a.random:
        k = len(OPENINGS)
        for name, part in (('rif', scores[:k]), ('random', scores[k:])):
            print(f"  {name:6s} {sum(part) / (2 * len(part)) * 100:.1f}%  "
                  f"(2-0 {part.count(2.0)} / 1-1 {sum(1 for s in part if 0 < s < 2)} / 0-2 {part.count(0.0)})")


if __name__ == '__main__':
    main()
