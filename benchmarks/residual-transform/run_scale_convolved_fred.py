"""Real-data test of laplace_scale_convolved (the "dual-carriage" laplace:
one instance forecasting y, a second forecasting the derived log(z^2)
scale-defect series, combined via the exact log(chi-sq_1) noise law).

Synthetic-only validation (iid null, known-periodic vol, robustness across
8 seeds) is in laplace_on_scale.py / this folder's conversation history.
This is the first real-data check, against the same local FRED sample and
paired-scoring methodology as run_study.py's M0/M1/M2 study, so the numbers
are directly comparable to that study's fred/laplace row.

Usage: PYTHONPATH=src python benchmarks/residual-transform/run_scale_convolved_fred.py
"""
from __future__ import annotations
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import run_study as rs         # noqa: E402 -- load_local_series, _hac_mean_se
import laplace_on_scale as los  # noqa: E402

N_SERIES = 20
WARMUP = 100
CRPS_EVERY = 5


def run_series(ys):
    f = los.laplace_scale_convolved()
    state = None
    lp0, lp1 = [], []
    cr0, cr1 = [], []
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
            if t % CRPS_EVERY == 0:
                b0, b1 = raw.crps(y_next), corrected.crps(y_next)
                if math.isfinite(b0) and math.isfinite(b1):
                    cr0.append(b0)
                    cr1.append(b1)
    return lp0, lp1, cr0, cr1


def main():
    series = rs.load_local_series(n=N_SERIES)
    print(f"[scale-convolved/fred] {len(series)} series", flush=True)
    t0 = time.time()
    log_means, log_medians, crps_means = [], [], []
    for i, (sid, ys) in enumerate(series):
        lp0, lp1, cr0, cr1 = run_series(ys)
        d_log = [a - b for a, b in zip(lp1, lp0)]
        d_crps = [a - b for a, b in zip(cr0, cr1)]  # positive = corrected has LOWER crps
        mean, se = rs._hac_mean_se(d_log)
        median = sorted(d_log)[len(d_log) // 2] if d_log else float("nan")
        crps_mean = sum(d_crps) / len(d_crps) if d_crps else float("nan")
        log_means.append(mean)
        log_medians.append(median)
        crps_means.append(crps_mean)
        frac_pos = sum(1 for x in d_log if x > 0) / len(d_log) if d_log else float("nan")
        print(f"  {i+1}/{len(series)} {sid}: log_mean={mean:+.4f}(se {se:.4f}) "
              f"median={median:+.4f} frac>0={frac_pos:.2f} crps_mean={crps_mean:+.5f} n={len(d_log)}",
              flush=True)

    import statistics as st
    n = len(log_means)
    print(f"\n[scale-convolved/fred] n={n} series, {time.time()-t0:.1f}s")
    print(f"  log-score delta: mean of means={st.mean(log_means):+.4f}  "
          f"median of means={st.median(log_means):+.4f}  "
          f"frac series with positive mean={sum(1 for x in log_means if x>0)/n:.2f}")
    print(f"  median of per-series medians={st.median(log_medians):+.4f}")
    print(f"  crps delta: mean of means={st.mean(crps_means):+.5f}")


if __name__ == "__main__":
    main()
