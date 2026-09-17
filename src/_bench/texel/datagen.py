"""N0：平行自對弈產生訓練棋譜。

用法: python datagen.py <dll> <games> <out.txt> [--params p.json] [--extra 2-6] [--seed 1] [--jobs 14]

開局 = RIF 三手 + 隨機 extra 手（引擎確定性，不隨機就只有 104 盤不同的棋）。
輸出每行: 走法序列 x,y,p ... | nopen=N result=W

illegal／boardfull 結尾不寫入（跟 dup 一樣只計入 reasons），最終行數可能略少於 games。
boardfull 是雙方封鎖到棋盤下滿仍無人連五的和局，不是引擎異常，但這種僵局對訓練沒有價值。

斷點續跑：out 檔已存在時，以檔案現有行數當作「已完成局數」續跑到 games，不會重新生成前面已經有的局（task 的 seed 依全域 index 算，index 不重複用）。
中途中斷、games 沒跑滿，直接用原指令重跑即可接著跑，不必砍掉重來。

out 檔旁的 <out>.dllhash 記錄生成當下 ai.dll 的 sha256。
續跑時若目前傳入的 dll 雜湊對不上，代表 dll 已經換過版本（棋型分類/評分/搜索都可能不同），直接報錯要求手動處理，不會把新舊 dll 生成的棋局悄悄混進同一份檔案。
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import os
import random
import sys
import time

import engine
from openings_rif import OPENINGS


def _dll_hash(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


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

    dll_hash = _dll_hash(a.dll)
    hash_path = a.out + '.dllhash'
    done = 0
    if os.path.exists(a.out):
        with open(a.out) as f:
            done = sum(1 for _ in f)
        if os.path.exists(hash_path) and open(hash_path).read().strip() != dll_hash:
            sys.exit(f"{a.out} 是用別的 ai.dll 生成的（雜湊對不上 {hash_path}），先手動處理再重跑")
    if done >= a.games:
        print(f"{a.out} 已有 {done} 局 >= 目標 {a.games}，不需要再跑")
        return
    if done:
        print(f"{a.out} 已有 {done} 局，續跑剩下 {a.games - done} 局")
    with open(hash_path, 'w') as f:
        f.write(dll_hash + '\n')

    t0 = time.time()
    tasks = [(a.seed * 1_000_003 + i, lo, hi) for i in range(done, a.games)]
    res_count, reasons, seen = {}, {}, set()
    with mp.Pool(a.jobs, _init, (os.path.abspath(a.dll), params)) as pool, open(a.out, 'a') as f:
        for moves, nopen, w, reason in pool.imap_unordered(_task, tasks, chunksize=4):
            reasons[reason] = reasons.get(reason, 0) + 1
            if reason in ('illegal', 'boardfull'):
                continue
            key = tuple(moves)
            if key in seen:  # 重複的對局不寫，避免同一盤棋重複計權
                reasons['dup'] = reasons.get('dup', 0) + 1
                continue
            seen.add(key)
            res_count[w] = res_count.get(w, 0) + 1
            f.write(' '.join(f"{x},{y},{p}" for x, y, p in moves) + f" | nopen={nopen} result={w}\n")
            f.flush()  # 逐局落盤，斷點續跑靠這行才不會漏算已完成局數
    print(f"{a.games - done} games in {time.time() - t0:.0f}s  results={res_count}  endings={reasons}")


if __name__ == '__main__':
    main()
