"""Real-data test of laplace_scale_garch_grid: the simpler alternative to
the Kalman-grid design -- swap the exact-noise-law/Kalman apparatus for
skaters' existing garch transform applied directly to the PIT-residual z
stream, hedged the same NFL-safe way (a small fixed grid including an
identity candidate, combined by bayesian_ensemble). See laplace_on_scale.py
for the derivation and why a single unhedged garch-on-z setting failed on
real data the same way every other point-estimate design did.

Same 5-series local FRED sample and paired-scoring methodology as
run_kalman_grid_fred.py, so the two are directly comparable.

Usage: PYTHONPATH=src python benchmarks/residual-transform/run_garch_grid_fred.py
"""
from __future__ import annotations
import math
import os
import statistics as st
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import run_study as rs         # noqa: E402 -- load_local_series, _hac_mean_se
import laplace_on_scale as los  # noqa: E402

N_SERIES = 5
WARMUP = 100
CRPS_EVERY = 20


def run_series(ys):
    f = los.laplace_scale_garch_grid()
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


DATASETS = {
    "fred": rs.load_local_series,
    "waveform": rs.load_waveform_series,
}


def main(dataset_name="fred", n=N_SERIES):
    series = DATASETS[dataset_name](n=n)
    print(f"[garch-grid/{dataset_name}] {len(series)} series", flush=True)
    t0 = time.time()
    log_means, log_medians, frac_pos_list, crps_means = [], [], [], []
    for i, (sid, ys) in enumerate(series):
        lp0, lp1, cr0, cr1 = run_series(ys)
        d_log = [a - b for a, b in zip(lp1, lp0)]
        d_crps = [a - b for a, b in zip(cr0, cr1)]
        mean, se = rs._hac_mean_se(d_log)
        median = sorted(d_log)[len(d_log) // 2] if d_log else float("nan")
        crps_mean = sum(d_crps) / len(d_crps) if d_crps else float("nan")
        frac_pos = sum(1 for x in d_log if x > 0) / len(d_log) if d_log else float("nan")
        log_means.append(mean)
        log_medians.append(median)
        frac_pos_list.append(frac_pos)
        crps_means.append(crps_mean)
        print(f"  {i+1}/{len(series)} {sid}: log_mean={mean:+.4f}(se {se:.4f}) "
              f"median={median:+.4f} frac>0={frac_pos:.2f} crps_mean={crps_mean:+.5f} n={len(d_log)}",
              flush=True)

    n_done = len(log_means)
    print(f"\n[garch-grid/{dataset_name}] n={n_done} series, {time.time()-t0:.1f}s")
    print(f"  log-score delta: mean of means={st.mean(log_means):+.4f}  "
          f"median of means={st.median(log_means):+.4f}  "
          f"frac series with positive mean={sum(1 for x in log_means if x>0)/n_done:.2f}")
    print(f"  median of per-series medians={st.median(log_medians):+.4f}  "
          f"frac series with positive median={sum(1 for x in log_medians if x>0)/n_done:.2f}")
    print(f"  mean of per-series frac>0={st.mean(frac_pos_list):.3f}")
    print(f"  crps delta: mean of means={st.mean(crps_means):+.5f}")


if __name__ == "__main__":
    dataset_name = sys.argv[1] if len(sys.argv) > 1 else "fred"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else N_SERIES
    main(dataset_name, n)
