"""Exact Shapley attribution of predictive value over the five transform families.

Order-robust companion to ladder_ablation.py. Value function: v(S) = held-out
mean log score (same delta-mixture evaluation, no clipping) of a
likelihood-weighted pool built compositionally from the families in S:

  loc     location/trend trackers (EMA, drift, theta, Holt, differencing)
  scale   EWMA conditional-variance leaves
  seas    seasonal differencing + anchors
  serial  AR(1), AR(2), fractional differencing
  shape   scale-mixture residual leaves, coordinate transforms, GARCH
          (scale-dynamics-and-shape family; when 'scale' is absent its
          mixture leaves use a near-expanding scale so the two families
          stay as separable as the implementation allows)

All 2^5 = 32 subset pools are scored per series; exact Shapley values follow
by linearity. This is the grouping- and order-robust attribution promised in
the paper; the declared-order ladder remains the intuitive presentation.

    PYTHONPATH=src python benchmarks/shapley_ladder.py [N_SERIES]
"""

from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import csv
import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from itertools import combinations
from math import factorial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ladder_ablation as LA
from skaters.bayesian import bayesian_ensemble
from skaters.conjugate import conjugate
from skaters.leaf import leaf, scale_mixture_leaf
from skaters.transform import (
    ar, difference, ema_transform, fractional_difference, garch,
    power_transform, seasonal_anchor, seasonal_difference, yeo_johnson,
)

FAMILIES = ["loc", "scale", "seas", "serial", "shape"]
SUBSETS = [frozenset(c) for r in range(6) for c in combinations(FAMILIES, r)]
MAX_WORKERS = min(8, (os.cpu_count() or 4))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shapley_ladder.csv")


def _leaf_factories(S):
    fac = [lambda: leaf(k=1)]
    if "scale" in S:
        fac.append(lambda: LA.ewma_leaf(k=1))
    if "shape" in S:
        sa = 0.03 if "scale" in S else 0.002
        fac.append(lambda sa=sa: scale_mixture_leaf(k=1, scale_alpha=sa))
    return fac


def _pool(S):
    cands, depths = [leaf(k=1)], [0]

    def add(c, d):
        cands.append(c)
        depths.append(d)

    fac = _leaf_factories(S)
    for lf in fac[1:]:
        add(lf(), 0)
    if "loc" in S:
        for lf in fac:
            for t in LA._location_transforms():
                add(conjugate(lf(), t, k=1), 1)
    if "seas" in S:
        for lf in fac:
            for period in (7, 12, 24):
                add(conjugate(lf(), seasonal_difference(period), k=1), 1)
                add(conjugate(lf(), seasonal_anchor(period), k=1), 1)
    if "serial" in S:
        for lf in fac:
            add(conjugate(lf(), ar(1), k=1), 1)
            add(conjugate(lf(), ar(2, decay=1), k=1), 1)
            for d in (0.2, 0.4):
                add(conjugate(conjugate(lf(), ema_transform(0.1), k=1),
                              fractional_difference(d=d, window=30), k=1), 2)
            for a in (0.05, 0.1):
                add(conjugate(conjugate(lf(), ema_transform(a), k=1),
                              difference(), k=1), 2)
    if "shape" in S:
        mixf = fac[-1]
        add(conjugate(conjugate(mixf(), ema_transform(0.1), k=1), garch(), k=1), 2)
        add(conjugate(conjugate(mixf(), ema_transform(0.1), k=1),
                      power_transform(0.5), k=1), 2)
        add(conjugate(conjugate(mixf(), ema_transform(0.1), k=1),
                      yeo_johnson(0.0), k=1), 2)
    return bayesian_ensemble(cands, k=1, learning_rate=0.8,
                             complexity_penalty=0.005, depths=depths,
                             max_components=20)


def score(job):
    sid, series = job
    try:
        row = [sid, len(series)]
        for S in SUBSETS:
            ll, _ = LA._logpdf(lambda s=S: _pool(s), series)
            row.append(ll)
        return row
    except Exception as e:
        return [sid, len(series)] + [float("nan")] * len(SUBSETS)


def subset_name(S):
    return "+".join(f for f in FAMILIES if f in S) or "none"


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    data = LA._corpus()
    ids = sorted(data)
    if limit:
        step = max(1, len(ids) // limit)
        ids = ids[::step][:limit]
    jobs = [(sid, data[sid]) for sid in ids]
    print(f"{len(jobs)} series x {len(SUBSETS)} subset pools, "
          f"{MAX_WORKERS} workers -> {OUT}", flush=True)

    rows = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score, j): j[0] for j in jobs}
        for done, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if done % 10 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}", flush=True)

    rows.sort()
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["series", "n"] + [subset_name(S) for S in SUBSETS])
        w.writerows(rows)

    good = [r for r in rows if len(r) == 2 + len(SUBSETS)
            and all(isinstance(x, float) and math.isfinite(x) for x in r[2:])]
    print(f"\n{len(good)}/{len(rows)} series scored on all subsets")
    if not good:
        return
    v = {S: sum(r[2 + i] for r in good) / len(good)
         for i, S in enumerate(SUBSETS)}
    total = v[frozenset(FAMILIES)] - v[frozenset()]
    print(f"\nmean v(all) - v(none) = {total:+.4f} nats/obs\n")
    print("exact Shapley values (nats/obs, share of total):")
    nfam = len(FAMILIES)
    for f in FAMILIES:
        phi = 0.0
        for S in SUBSETS:
            if f in S:
                continue
            wgt = factorial(len(S)) * factorial(nfam - len(S) - 1) / factorial(nfam)
            phi += wgt * (v[S | {f}] - v[S])
        print(f"  {f:7s} phi={phi:+.4f}  share={100*phi/total:5.1f}%")


if __name__ == "__main__":
    main()