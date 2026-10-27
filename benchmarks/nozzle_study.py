"""How much does the reconstruction nozzle alone move a quantile-only model's
score, holding the model (TimesFM3) and the data fixed?

Runs TimesFM3 zero-shot on real held-out FRED series (same protocol as
foundation_study.py: 128-length context, one-step-ahead), captures its raw
9-decile output once per test step, and scores that SAME output through
every nozzle in nozzles.py. The model and the data never change across
columns; only the reconstruction does.

    PYTHONPATH=src:benchmarks .venv-timesfm3/bin/python benchmarks/nozzle_study.py
"""
from __future__ import annotations
import os
import sys
import random
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fred
from study import _scope_tag
import nozzles

N_SERIES = int(os.environ.get("NOZZLE_N", 50))
CTX = int(os.environ.get("NOZZLE_CTX", 128))
TEST = int(os.environ.get("NOZZLE_TEST", 32))
MIN_CHANGES = TEST + CTX + 50
DEVICE = os.environ.get("FM_DEVICE", "cpu")
LEVELS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def _laplace_test_dists(ch, start):
    """laplace(1)'s predictive for each test point ch[t], t >= start, issued
    after ch[t-1] was observed (the stepping of arm_adapters.laplace_dists)."""
    from skaters.api import laplace
    f = laplace(1); st = None; pend = None; out = []
    for t, x in enumerate(ch):
        if t >= start:
            out.append(pend)
        d, st = f(x, st)
        pend = d[0]
    return out


def run():
    from timesfm3 import TimesFM3Evaluator, ModelConfig
    model = TimesFM3Evaluator(ModelConfig(
        checkpoint_path="google/timesfm-3.0-pytorch", per_core_batch_size=32, device=DEVICE))

    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    random.Random(0).shuffle(ids)
    picked = []
    for sid in ids:
        lv = fred._load_levels(sid)
        ch = fred._to_changes(lv) if lv else []
        if len(ch) >= MIN_CHANGES and not _scope_tag(ch):
            picked.append((sid, ch[-(MIN_CHANGES + 200):]))
        if len(picked) >= N_SERIES:
            break
    print(f"[nozzle] {len(picked)} series, CTX={CTX} TEST={TEST} device={DEVICE}", flush=True)

    totals = {name: 0.0 for name in nozzles.NOZZLES}
    n_tot = 0
    spreads = []
    # laplace on the same points, as the comparator the reconstruction numbers
    # need (issue #269): per-series mean of laplace minus each nozzle, paired.
    lap_total = 0.0
    paired = {name: [] for name in nozzles.NOZZLES}

    for sid, ch in picked:
        n = len(ch); start = n - TEST
        ctx_windows = [np.asarray(ch[t - CTX:t], dtype=np.float32) for t in range(start, n)]
        targets = [ch[t] for t in range(start, n)]
        lap_dists = _laplace_test_dists(ch, start)
        series_diff = {name: 0.0 for name in nozzles.NOZZLES}

        outs = list(model.predict_batch(
            ctx_windows, horizon=1, return_quantiles=True, use_symmetric_averaging=False,
            make_positive=False, univariate=True))

        for i, y in enumerate(targets):
            q = np.asarray(outs[i].quantiles, dtype=float)
            q = q[0] if q.ndim == 3 else q
            q = q[0] if q.ndim == 2 else q
            scores = nozzles.score_all(LEVELS, q, y)
            lp_lap = max(lap_dists[i].logpdf(y), -20.0)
            lap_total += lp_lap
            for name, (lp, _) in scores.items():
                totals[name] += lp
                series_diff[name] += lp_lap - max(lp, -20.0)
            spreads.append(nozzles.spread(scores))
            n_tot += 1
        for name in nozzles.NOZZLES:
            paired[name].append(series_diff[name] / len(targets))
        print(f"  {sid} done", flush=True)

    print(f"\n[nozzle] {n_tot} scored points, {len(picked)} series, TimesFM3 fixed:")
    for name in nozzles.NOZZLES:
        print(f"  {name}: mean logpdf {totals[name]/n_tot:+.4f}")
    print(f"  laplace on the same points: mean logpdf {lap_total/n_tot:+.4f}")
    for name in nozzles.NOZZLES:
        d = np.asarray(paired[name])
        print(f"  laplace minus {name}, per-series mean dLL (floor -20): median {np.median(d):+.4f}, "
              f"laplace better on {int((d > 0).sum())}/{len(d)} series")
    print(f"  mean per-point nozzle spread (max-min logpdf): {np.mean(spreads):.4f}")
    print(f"  median per-point nozzle spread: {np.median(spreads):.4f}")
    grid_mean = totals["grid"] / n_tot
    for name in nozzles.NOZZLES:
        if name != "grid":
            print(f"  {name} vs grid, mean logpdf diff: {totals[name]/n_tot - grid_mean:+.4f}")


if __name__ == "__main__":
    run()
