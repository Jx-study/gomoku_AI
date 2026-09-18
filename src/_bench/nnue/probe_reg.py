"""probe.py 加 weight decay 的變體，用來把過擬合與特徵本身的資訊上限分開看。

用法: python probe_reg.py <feats.npz> [--acc 64] [--l1 32] [--epochs 30] [--seed 0] [--wd 0.0]

判讀標準與模型結構同 probe.py（見 probe_common.py）。

額外印出保留集 MSE 的最佳點（而非只看訓練結束時的終值）：過擬合模式下終值沒有
參考價值，weight decay 掃描要比的是每組設定各自的最佳點。
"""
import argparse

import numpy as np
import torch
import torch.nn as nn

import probe_common as pc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('feats')
    ap.add_argument('--acc', type=int, default=64)
    ap.add_argument('--l1', type=int, default=32)
    ap.add_argument('--epochs', type=int, default=30)
    ap.add_argument('--batch', type=int, default=1024)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--wd', type=float, default=0.0, help='Adam weight decay')
    a = ap.parse_args()

    n_feats, bf, boff, wf, woff, y_black, rng, tr, te = pc.load_split(a.feats, a.seed)

    torch.manual_seed(a.seed)
    model = pc.Probe(n_feats, a.acc, a.l1)
    opt = torch.optim.Adam(model.parameters(), lr=a.lr, weight_decay=a.wd)
    loss_fn = nn.MSELoss()
    run = pc.make_run_epoch(model, opt, loss_fn, bf, boff, wf, woff, y_black, a.batch, rng)

    const = float(np.mean((y_black[te] - y_black[tr].mean()) ** 2))
    te_b = te_w = float('nan')
    best_avg, best_ep = float('inf'), -1
    for ep in range(a.epochs):
        model.train()
        tr_b, tr_w = run(tr, True, True), run(tr, False, True)
        model.eval()
        with torch.no_grad():
            te_b, te_w = run(te, True, False), run(te, False, False)
        avg = (te_b + te_w) / 2
        if avg < best_avg:
            best_avg, best_ep = avg, ep + 1
        print(f"epoch {ep+1}/{a.epochs} train={tr_b:.5f}/{tr_w:.5f} test={te_b:.5f}/{te_w:.5f}")

    pc.print_baseline(const, te_b, te_w, label='probe test 終值(黑/白)')
    print(f"probe test 最佳點(平均) {best_avg:.5f} @ epoch {best_ep}")
    pc.print_gate_note()


if __name__ == '__main__':
    main()
