"""Gaussianize as an interior operator: the conformal pattern nested in a grammar.

Tests two claims about the fence-post empirical transform (smoothed, probit-
composed: skaters.transform.gaussianize):

  (a) INTERIOR COMPOSITION. Refitting structure on the Gaussianized stream
      beats stopping at it, so the empirical transform is a composable
      operator, not only a terminal calibration step.
  (b) NESTING PREVENTS A BAD CHOICE. A likelihood-weighted pool that includes
      the conformal-pattern chains is never much worse than the pool without
      them, and rescues the series where a fixed conformal pattern is bad.

Configs (all chains end in the plain Gaussian leaf):

  A  loc_gauss     ema -> leaf                      location + Gaussian leaf
  B  scaled_gauss  ema -> standardize -> leaf       + EWMA scale
  C  conf_raw      ema -> gaussianize -> leaf       raw empirical pooling
                                                    (split-conformal pattern)
  D  conf_scaled   ema -> std -> gaussianize -> leaf  normalized pattern
  E  refit_ar      ema -> std -> gaussianize -> ar(1) -> leaf  interior comp.
  F  refit_noG     ema -> std -> ar(1) -> leaf      same refit, no gaussianize
  G  pool_with     ensemble {leaf, A..F}            grammar nesting conformal
  H  pool_without  ensemble {leaf, A, B, F}         grammar without it

Scores: exact log score via the DELTA_REF reference mixture (ladder_ablation
convention) and analytic CRPS of the raw predictive mixture.

    PYTHONPATH=src python benchmarks/gaussianize_chain.py [N_SERIES]
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ladder_ablation as LA
from skaters.bayesian import bayesian_ensemble
from skaters.conjugate import conjugate
from skaters.leaf import leaf
from skaters.transform import ar, ema_transform, gaussianize, standardize

BURN = LA.BURN
MAX_WORKERS = min(8, (os.cpu_count() or 4))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gaussianize_chain.csv")

CONFIGS = ["A_loc", "B_scaled", "C_conf_raw", "D_conf_scaled",
           "E_refit_ar", "F_refit_noG", "C2_raw_sm", "D2_scaled_sm",
           "E2_refit_sm", "G_pool_with", "H_pool_without", "I_pool_sm"]


def _chain(*transforms):
    sk = leaf(k=1)
    for t in reversed(transforms):
        sk = conjugate(sk, t, k=1)
    return sk


def _candidates(with_gauss, sm=False):
    cands = [(leaf(k=1), 0),
             (_chain(ema_transform(0.1)), 1),
             (_chain(ema_transform(0.1), standardize(0.05)), 2),
             (_chain(ema_transform(0.1), standardize(0.05), ar(1)), 3)]
    if with_gauss:
        g = lambda: gaussianize(smooth=sm)
        cands += [(_chain(ema_transform(0.1), g()), 2),
                  (_chain(ema_transform(0.1), standardize(0.05), g()), 3),
                  (_chain(ema_transform(0.1), standardize(0.05), g(), ar(1)), 4)]
    return cands


def _make(name):
    if name == "A_loc":
        return _chain(ema_transform(0.1))
    if name == "B_scaled":
        return _chain(ema_transform(0.1), standardize(0.05))
    if name == "C_conf_raw":
        return _chain(ema_transform(0.1), gaussianize())
    if name == "D_conf_scaled":
        return _chain(ema_transform(0.1), standardize(0.05), gaussianize())
    if name == "E_refit_ar":
        return _chain(ema_transform(0.1), standardize(0.05), gaussianize(), ar(1))
    if name == "F_refit_noG":
        return _chain(ema_transform(0.1), standardize(0.05), ar(1))
    if name == "C2_raw_sm":
        return _chain(ema_transform(0.1), gaussianize(smooth=True))
    if name == "D2_scaled_sm":
        return _chain(ema_transform(0.1), standardize(0.05), gaussianize(smooth=True))
    if name == "E2_refit_sm":
        return _chain(ema_transform(0.1), standardize(0.05), gaussianize(smooth=True),
                      ar(1))
    cands = _candidates(with_gauss=(name != "H_pool_without"),
                        sm=(name == "I_pool_sm"))
    return bayesian_ensemble([c for c, _ in cands], k=1, learning_rate=0.8,
                             complexity_penalty=0.005,
                             depths=[d for _, d in cands], max_components=20)


def _score(make, series):
    """One prequential pass, both scores. Log score is the exact DELTA_REF
    mixture with the expanding Gaussian (ladder_ablation convention); CRPS is
    the analytic mixture CRPS of the raw predictive."""
    f = make()
    state = None
    pend = None
    lp = cr = 0.0
    n = 0
    mu = 0.0
    m2 = 0.0
    nobs = 0
    for i, y in enumerate(series):
        if pend is not None and i > BURN and nobs > 2 and m2 > 0:
            var = m2 / (nobs - 1)
            lg = -0.5 * math.log(2 * math.pi * var) - (y - mu) ** 2 / (2 * var)
            lq = pend[0].logpdf(y)
            if not math.isfinite(lq):
                lq = -1e12
            a = math.log(1 - LA.DELTA_REF) + lq
            b = math.log(LA.DELTA_REF) + lg
            hi = max(a, b)
            lp += hi + math.log(math.exp(a - hi) + math.exp(b - hi))
            cr += pend[0].crps(y)
            n += 1
        nobs += 1
        d0 = y - mu
        mu += d0 / nobs
        m2 += d0 * (y - mu)
        d, state = f(y, state)
        pend = d
    return (lp / n, cr / n) if n else (float("nan"), float("nan"))


def score(job):
    sid, series = job
    try:
        row = [sid, len(series)]
        for name in CONFIGS:
            ll, cr = _score(lambda nm=name: _make(nm), series)
            row += [ll, cr]
        return row
    except Exception:
        return [sid, len(series)] + [float("nan")] * (2 * len(CONFIGS))


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    data = LA._corpus()
    ids = sorted(data)
    if limit:
        step = max(1, len(ids) // limit)
        ids = ids[::step][:limit]
    jobs = [(sid, data[sid]) for sid in ids]
    print(f"{len(jobs)} series x {len(CONFIGS)} configs, "
          f"{MAX_WORKERS} workers -> {OUT}", flush=True)

    rows = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score, j): j[0] for j in jobs}
        for done, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if done % 10 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}", flush=True)

    rows.sort()
    hdr = ["series", "n"]
    for c in CONFIGS:
        hdr += [f"ll_{c}", f"crps_{c}"]
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(hdr)
        w.writerows(rows)

    good = [r for r in rows if all(isinstance(x, float) and math.isfinite(x)
                                   for x in r[2:])]
    print(f"\n{len(good)}/{len(rows)} series scored on all configs")
    if not good:
        return
    import statistics
    ll = {c: [r[2 + 2 * i] for r in good] for i, c in enumerate(CONFIGS)}
    # CRPS normalized per series by config A so scales are comparable
    cr = {c: [r[3 + 2 * i] / r[3] for r in good] for i, c in enumerate(CONFIGS)}
    print("\nmean log score (nats/obs) and CRPS relative to A (mean/median):")
    for c in CONFIGS:
        print(f"  {c:15s} ll {statistics.mean(ll[c]):+.4f}   "
              f"crps {statistics.mean(cr[c]):.4f}/{statistics.median(cr[c]):.4f}")

    def duel(x, y, tag):
        dl = [a - b for a, b in zip(ll[x], ll[y])]
        dc = [a - b for a, b in zip(cr[x], cr[y])]
        print(f"  {tag}: ll {statistics.mean(dl):+.4f} "
              f"(wins {100 * sum(1 for v in dl if v > 0) / len(dl):.0f}%)  "
              f"crps {statistics.mean(dc):+.4f} "
              f"(wins {100 * sum(1 for v in dc if v < 0) / len(dc):.0f}%)")

    print("\n(a) interior composition:")
    duel("E_refit_ar", "D_conf_scaled", "refit_ar  vs conf_scaled ")
    duel("E_refit_ar", "F_refit_noG", "refit_ar  vs refit_noG   ")
    duel("D_conf_scaled", "C_conf_raw", "conf_scaled vs conf_raw  ")

    print("\n(a') kernel-smoothed C1 variant:")
    duel("E2_refit_sm", "E_refit_ar", "refit_sm  vs refit_linear")
    duel("E2_refit_sm", "F_refit_noG", "refit_sm  vs refit_noG   ")
    duel("E2_refit_sm", "D2_scaled_sm", "refit_sm  vs stop_sm     ")
    duel("D2_scaled_sm", "D_conf_scaled", "stop_sm   vs stop_linear ")

    print("\n(b) nesting prevents a bad choice:")
    duel("G_pool_with", "H_pool_without", "pool_with vs pool_without")
    duel("I_pool_sm", "H_pool_without", "pool_sm   vs pool_without")
    duel("I_pool_sm", "G_pool_with", "pool_sm   vs pool_with   ")
    duel("G_pool_with", "C_conf_raw", "pool_with vs conf_raw    ")
    # left tail: how bad can the fixed conformal pattern get, and does the
    # pool avoid it?  distribution of per-series relative CRPS
    worst = sorted(zip(cr["C_conf_raw"], cr["G_pool_with"]), reverse=True)[:20]
    wc = statistics.mean([a for a, _ in worst])
    wg = statistics.mean([b for _, b in worst])
    print(f"  20 worst conf_raw series: conf_raw rel CRPS {wc:.3f}, "
          f"pool_with on the same series {wg:.3f}")


if __name__ == "__main__":
    main()
