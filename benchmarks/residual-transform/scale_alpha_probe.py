"""Follow-up: is M1's win on waveform data just "laplace's EWMA is too slow"?

laplace's terminal leaf tracks residual variance with an EWMA at a fixed
rate (scale_alpha, default 0.03 on both crps_leaf and scale_mixture_leaf).
M1 (skaters.residual_transform) helped laplace specifically on the waveform
arm (see README.md) -- but M1 also learns its *own* persistence/adaptation
speed online, so a live hypothesis is that M1 isn't finding real serial
structure there, it's just correcting a globally-too-slow default alpha for
that regime. If a faster fixed scale_alpha alone recovers the same gain on
waveform (and, tellingly, HURTS on generic fred data, where the slower
default is presumably already closer to right), that would say M1 is doing
nothing scale_alpha tuning couldn't. If a faster alpha does NOT close the
gap, or hurts waveform too, M1 is catching something a single fixed rate
can't.

This does not use skaters.residual_transform at all -- it's plain laplace
at several scale_alpha values, scored directly, same series/seed/warmup as
run_study.py so the deltas are comparable to its M1-vs-M0 column.

Usage: PYTHONPATH=src python benchmarks/residual-transform/scale_alpha_probe.py
"""
from __future__ import annotations
import csv
import math
import os
import statistics as st
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import run_study as rs  # reuse load_local_series / load_waveform_series / _hac_mean_se

from skaters import laplace

ALPHAS = [0.03, 0.06, 0.10, 0.15, 0.20]   # 0.03 is laplace's own default (the baseline)
WARMUP = rs.WARMUP


def score_series(ys, alpha):
    f = laplace(k=1, tails="gaussian", scale_alpha=alpha)
    state = None
    lp = []
    for t, y in enumerate(ys):
        dists, state = f(y, state)
        if WARMUP <= t < len(ys) - 1:
            v = dists[0].logpdf(ys[t + 1])
            if math.isfinite(v):
                lp.append(v)
    return lp


def main():
    out_rows = []
    for dataset_name, loader in (("fred", rs.load_local_series), ("waveform", rs.load_waveform_series)):
        series = loader()
        print(f"[scale_alpha_probe] dataset={dataset_name} n={len(series)}", flush=True)
        base_lp = {}
        for sid, ys in series:
            base_lp[sid] = score_series(ys, 0.03)
        for alpha in ALPHAS[1:]:
            deltas = []
            for sid, ys in series:
                lp_alpha = score_series(ys, alpha)
                d = [a - b for a, b in zip(lp_alpha, base_lp[sid])]
                mean, se = rs._hac_mean_se(d)
                deltas.append(mean)
                out_rows.append({"dataset": dataset_name, "alpha": alpha, "series": sid,
                                  "mean_delta": mean, "se": se, "n": len(d)})
            n = len(deltas)
            frac_pos = sum(1 for x in deltas if x > 0) / n
            print(f"  alpha={alpha:.2f}  mean={st.mean(deltas):+.4f}  "
                  f"median={st.median(deltas):+.4f}  frac>0={frac_pos:.2f}", flush=True)

    out_csv = os.path.join(_HERE, "scale_alpha_probe.csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f"[scale_alpha_probe] wrote {out_csv}", flush=True)


if __name__ == "__main__":
    main()
