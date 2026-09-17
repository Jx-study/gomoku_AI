"""N3 Phase 0：量位置感知特徵能把保留集 MSE 壓到多低。

用法: python probe.py <feats.npz> [--acc 64] [--l1 32] [--epochs 30] [--seed 0]

判讀標準（見 Note/plans/05-impl-n3.md 的階段與閘門）：
    test MSE < 0.180        -> 進 Phase 1
    0.180 <= MSE <= 0.188   -> 邊際，要人工判斷
    MSE > 0.188             -> 中止 N3

對照基準來自 N1 Task 8（同一批棋譜、同一種 WDL 標籤、同樣以對局為單位切 80/20）：
常數預測 0.23107、Texel tuned 保留集 0.19106、自由線性模型 0.19235。

網路結構與 C 端推理逐層對應，這樣 Phase 3 量化時不必換架構：
第一層稀疏累加器（黑白共用權重）-> clipped ReLU -> fc1（bias 分色）-> clipped ReLU -> fc2。
"""
import argparse

import numpy as np
import torch
import torch.nn as nn

CLIP = 127.0


class Probe(nn.Module):
    def __init__(self, n_feats, acc, l1):
        super().__init__()
        self.emb = nn.EmbeddingBag(n_feats, acc, mode='sum')
        self.acc_bias = nn.Parameter(torch.zeros(acc))
        self.fc1 = nn.Linear(2 * acc, l1)
        self.fc1_bias_white = nn.Parameter(torch.zeros(l1))
        self.fc2 = nn.Linear(l1, 1)

    def forward(self, bf, boff, wf, woff, black_view):
        ab = self.emb(bf, boff) + self.acc_bias
        aw = self.emb(wf, woff) + self.acc_bias
        v = black_view.unsqueeze(1)
        me = torch.where(v, ab, aw)
        them = torch.where(v, aw, ab)
        a = torch.cat([me, them], dim=1).clamp(0.0, CLIP)
        h = self.fc1(a) + torch.where(v, torch.zeros_like(self.fc1_bias_white),
                                      self.fc1_bias_white)
        return torch.sigmoid(self.fc2(h.clamp(0.0, CLIP))).squeeze(-1)


def make_batch(flat, off, idx):
    """從 ragged 陣列取一批，回傳 EmbeddingBag 要的 (input, offsets)。"""
    parts, offs, cur = [], [], 0
    for i in idx:
        s, e = off[i], off[i + 1]
        parts.append(flat[s:e])
        offs.append(cur)
        cur += e - s
    inp = np.concatenate(parts).astype(np.int64) if cur else np.zeros(0, dtype=np.int64)
    return torch.from_numpy(inp), torch.tensor(offs, dtype=torch.long)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('feats')
    ap.add_argument('--acc', type=int, default=64)
    ap.add_argument('--l1', type=int, default=32)
    ap.add_argument('--epochs', type=int, default=30)
    ap.add_argument('--batch', type=int, default=1024)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()

    d = np.load(a.feats)
    n_feats = int(d['n_feats'])
    bf, boff, wf, woff = d['bf'], d['boff'], d['wf'], d['woff']
    res = d['result']
    y_black = np.where(res == 1, 1.0, np.where(res == 0, 0.5, 0.0)).astype(np.float32)

    # 以對局為單位切 80/20：同一局的局面高度相關，按局面切會讓保留集偷看到訓練局
    gid = d['gid']
    rng = np.random.RandomState(a.seed)
    games = np.unique(gid)
    rng.shuffle(games)
    test_games = set(games[:max(1, int(len(games) * 0.2))].tolist())
    is_test = np.isin(gid, list(test_games))
    tr, te = np.where(~is_test)[0], np.where(is_test)[0]

    torch.manual_seed(a.seed)
    model = Probe(n_feats, a.acc, a.l1)
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    loss_fn = nn.MSELoss()

    def run(idx, view_black, train):
        tot = cnt = 0
        order = rng.permutation(len(idx)) if train else np.arange(len(idx))
        for i in range(0, len(idx), a.batch):
            sel = idx[order[i:i + a.batch]]
            bi, bo = make_batch(bf, boff, sel)
            wi, wo = make_batch(wf, woff, sel)
            v = torch.full((len(sel),), view_black, dtype=torch.bool)
            y = torch.from_numpy(y_black[sel] if view_black else 1.0 - y_black[sel])
            loss = loss_fn(model(bi, bo, wi, wo, v), y)
            if train:
                opt.zero_grad()
                loss.backward()
                opt.step()
            tot += loss.item() * len(sel)
            cnt += len(sel)
        return tot / cnt

    const = float(np.mean((y_black[te] - y_black[tr].mean()) ** 2))
    te_b = te_w = float('nan')
    for ep in range(a.epochs):
        model.train()
        tr_b, tr_w = run(tr, True, True), run(tr, False, True)
        model.eval()
        with torch.no_grad():
            te_b, te_w = run(te, True, False), run(te, False, False)
        print(f"epoch {ep+1}/{a.epochs} train={tr_b:.5f}/{tr_w:.5f} test={te_b:.5f}/{te_w:.5f}")

    print(f"\nconst baseline         {const:.5f}")
    print(f"N1 Texel tuned (參考)   0.19106")
    print(f"N1 free linear (參考)   0.19235")
    print(f"probe test (黑/白)      {te_b:.5f} / {te_w:.5f}")
    print("閘門: < 0.180 進 Phase 1；0.180-0.188 邊際；> 0.188 中止 N3")


if __name__ == '__main__':
    main()
