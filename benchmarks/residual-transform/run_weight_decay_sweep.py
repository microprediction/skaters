"""Sensitivity of laplace_scale_kalman_grid to weight_decay. The default
(0.999) was hand-picked, not derived; the homogenization cell model
earlier this session showed real sensitivity to this exact kind of
discount-rate constant (0.995 forgot too fast and lost most of the
no-regret guarantee on the iid null). Cheap to check whether the
Kalman-grid result is similarly fragile, or already robust.

Usage: PYTHONPATH=src python benchmarks/residual-transform/run_weight_decay_sweep.py [dataset] [n]
"""
from __future__ import annotations
import math
import os
import statistics as st
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import run_study as rs         # noqa: E402
import laplace_on_scale as los  # noqa: E402

WARMUP = 100
CRPS_EVERY = 20
WEIGHT_DECAYS = [0.99, 0.995, 0.999, 0.9999, 1.0]

DATASETS = {"fred": rs.load_local_series, "waveform": rs.load_waveform_series}


def run_series(ys, weight_decay):
    f = los.laplace_scale_kalman_grid(weight_decay=weight_decay)
    state = None
    lp0, lp1 = [], []
    for t, y in enumerate(ys):
        dists, state = f(y, state)
        if WARMUP <= t < len(ys) - 1:
            y_next = ys[t + 1]
            raw = state["raw"]
            corrected = dists[0]
            a0, a1 = raw.logpdf(y_next), corrected.logpdf(y_next)
            if math.isfinite(a0) and math.isfinite(a1):
                lp0.append(a0)
                lp1.append(a1)
    return lp0, lp1


def main(dataset_name="fred", n=20):
    series = DATASETS[dataset_name](n=n)
    print(f"[weight-decay-sweep/{dataset_name}] {len(series)} series", flush=True)
    t0 = time.time()
    for wd in WEIGHT_DECAYS:
        log_means, log_medians = [], []
        for sid, ys in series:
            lp0, lp1 = run_series(ys, wd)
            d = [a - b for a, b in zip(lp1, lp0)]
            mean, _ = rs._hac_mean_se(d)
            median = sorted(d)[len(d) // 2] if d else float("nan")
            log_means.append(mean)
            log_medians.append(median)
        n_done = len(log_means)
        print(f"  weight_decay={wd}: mean of means={st.mean(log_means):+.4f}  "
              f"median of medians={st.median(log_medians):+.4f}  "
              f"frac pos mean={sum(1 for x in log_means if x>0)/n_done:.2f}  "
              f"frac pos median={sum(1 for x in log_medians if x>0)/n_done:.2f}",
              flush=True)
    print(f"\n[weight-decay-sweep/{dataset_name}] done, {time.time()-t0:.1f}s")


if __name__ == "__main__":
    dataset_name = sys.argv[1] if len(sys.argv) > 1 else "fred"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    main(dataset_name, n)
