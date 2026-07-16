"""Monte-Carlo convergence of CSP scores in the sample budget.

CSP (the official csp-forecaster package) emits B predictive samples per step;
our harness scores a KDE-smoothed quantile grid of them. Before trusting any
win-rate we show the scores CONVERGE as B doubles: for each budget we run three
independent seed replicates over the canonical daily FRED series and report the
mean CRPS / logpdf plus the seed-to-seed spread. The spread should shrink like
1/sqrt(B) and the means should stabilise well below the laplace-vs-CSP gap.

    PYTHONPATH=src python benchmarks/comparisons/csp_convergence.py

Writes csp-convergence.csv next to this file and prints the table.
"""
import csv
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BENCH = os.path.dirname(_HERE)
sys.path.insert(0, _BENCH)

import numpy as np

import bench_core as bc
import fred
from csp_forecaster import ConformalSeasonalPool

BUDGETS = [64, 128, 256, 512, 1024, 2048]
SEEDS = [1, 2, 3]
M = int(os.environ.get("BENCH_CSP_M", 5))          # business-day week
WIN = int(os.environ.get("BENCH_CSP_WIN", 750))
TEST = 300


def score_series(ch, budget, seed):
    y = np.asarray(ch, float)
    start = max(bc.BURN, len(y) - TEST)
    lp = cr = 0.0
    n = 0
    for t in range(start, len(y)):
        win = y[max(0, t - WIN):t]
        if len(win) <= 2 * M:
            continue
        f = ConformalSeasonalPool(mode="fast", random_state=seed * 1_000_000 + t)
        s = f.fit(win, seasonal_period=M).predict(H=1, n_samples=budget).samples[0]
        taus = np.linspace(0.02, 0.98, 41)
        d = bc.grid_dist(taus, np.quantile(s, taus))
        if d is None:
            continue
        a, b = bc.score_dist(d, y[t])
        lp += a; cr += b; n += 1
    return (lp / n, cr / n, n) if n else (float("nan"), float("nan"), 0)


def main():
    data = fred.load_fred()
    if not data:
        print("no FRED data (need FRED_API_KEY or cache)"); return 1
    print(f"[convergence] {len(data)} canonical series, m={M}, "
          f"budgets {BUDGETS}, seeds {SEEDS}", flush=True)
    out = os.path.join(_HERE, "laplace-vs-csp", "csp-convergence.csv")
    rows = []
    for budget in BUDGETS:
        per_seed = []
        for seed in SEEDS:
            vals = [score_series(ch, budget, seed) for ch in data.values()]
            lp = float(np.mean([v[0] for v in vals]))
            cr = float(np.mean([v[1] for v in vals]))
            per_seed.append((lp, cr))
            rows.append([budget, seed, f"{lp:.6f}", f"{cr:.6f}"])
        lps = [p[0] for p in per_seed]; crs = [p[1] for p in per_seed]
        print(f"  B={budget:5d}  CRPS {np.mean(crs):.6f} (spread {max(crs)-min(crs):.6f})"
              f"  LL {np.mean(lps):.4f} (spread {max(lps)-min(lps):.4f})", flush=True)
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["n_samples", "seed", "mean_logpdf", "mean_crps"])
        w.writerows(rows)
    print(f"[convergence] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
