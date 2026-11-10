"""Parity: the pure-Python granger against its torch training twin.

Runs skaters.granger.granger (from the exported JSON) and
skaters.torch.learned.LearnedLaplace (from the checkpoint the JSON came from)
side by side on seeded streams and compares, at every step, the issued
mixture's log density at the next observation, its mean, its spread and the
mixture weight on laplace. A fresh torch model per stream (the torch trunk
keeps its last log weights as a module attribute).

    PYTHONPATH=src .venv-kumo/bin/python parity/check_granger.py \
        benchmarks/learned_ckpt/monthly_k1_swa5.pt monthly
"""
from __future__ import annotations

import math
import random
import sys

import torch

from skaters.granger import granger, load_params
from skaters.torch.learned import LearnedLaplace

# Three of the four streams agree to ~1e-13; the regime-switching one (volatility
# x5 every 80 steps) reaches ~5e-9 on the weekly parameters, summation-order
# rounding amplified through the weight recursion. The JS port gate is 1e-6.
TOL = 1e-8


def streams(n=300):
    rng = random.Random(11)
    out = {}
    x, xs = 0.0, []
    for t in range(n):
        x += rng.gauss(0, 0.2)
        xs.append(x + math.sin(2 * math.pi * t / 12) + rng.gauss(0, 1))
    out["trend_cycle"] = xs
    out["heavy"] = [rng.gauss(0, 1) / math.sqrt(rng.gammavariate(1.5, 1 / 1.5)) for _ in range(n)]
    x, xs = 50.0, []
    for _ in range(n):
        if rng.random() < 0.3:
            x += 0.5 * rng.choice((-1, 1))
        xs.append(x)
    out["sticky"] = xs
    out["regimes"] = [rng.gauss(0, 5.0 if (t // 80) % 2 else 1.0) for t in range(n)]
    return out


def main(ckpt, freq):
    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    worst = 0.0
    for name, ys in streams().items():
        tm = LearnedLaplace(k=1, pi_lap=float(ck.get("pi_lap", 0.25)))
        tm.load_state_dict(ck["state_dict"]); tm.eval()
        g = granger(1, params=load_params(freq))
        st_t = st_g = None
        dev = 0.0
        with torch.no_grad():
            for t, y in enumerate(ys[:-1]):
                dt, st_t = tm(y, st_t)
                dg, st_g = g(y, st_g)
                a, b = dt[0], dg[0]
                nxt = ys[t + 1]
                for u, v in ((float(a.logpdf(nxt)), b.logpdf(nxt)), (float(a.mean), b.mean),
                             (float(a.std), b.std), (float(a.weights[0]), b.w[0])):
                    if math.isfinite(u) or math.isfinite(v):
                        d = abs(u - v) / max(1.0, abs(u))
                        dev = max(dev, d) if d == d else math.inf   # NaN deviation fails the gate
        worst = max(worst, dev)
        print(f"  {name:12s} max relative deviation {dev:.2e}")
    print(f"[granger parity] {freq}: worst {worst:.2e} ({'OK' if worst < TOL else 'FAIL'} at {TOL:g})")
    return worst < TOL


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1], sys.argv[2]) else 1)
