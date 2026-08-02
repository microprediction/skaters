"""Ladder ablation: price each representation rung on FRED change series.

Companion to the frontier paper's "Measuring representation value" section.
Six NESTED pools, each strictly containing the previous one's candidates:

  R0  unconditional   N(0, expanding var) on the change series (trivial T)
  R1  +location       level/trend trackers (EMA, drift, theta, Holt, diff),
                      pooled residual law (plain Gaussian leaf, Welford var)
                      -- the residual-conformal analogue
  R2  +scale          same mean pool, EWMA-variance Gaussian leaves added
                      -- the normalized-conformal analogue
  R3  +seasonal       seasonal differencing and seasonal anchors added
  R4  +serial state   AR(1), AR(2), fractional differencing, diff+EMA added
  R5  full grammar    laplace(k=1, objective="likelihood") -- adds coordinate
                      transforms, GARCH, mixture shape, the shipped pool

Score: mean held-out one-step log-likelihood after burn-in. The measured
representation value of rung j is Delta_j = L(R_j) - L(R_{j-1}); the paper's
bridge identity reads it as oracle information gain net of estimation cost.
Order-dependence caveat: this is the canonical nesting declared in advance
(location, scale, seasonal, serial, shape); values are conditional on it.

    PYTHONPATH=src python benchmarks/ladder_ablation.py [N_SERIES]
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

import fred
from skaters.api import laplace
from skaters.bayesian import bayesian_ensemble
from skaters.conjugate import conjugate
from skaters.dist import Dist
from skaters.leaf import leaf
from skaters.transform import (
    ar, difference, drift, ema_transform, fractional_difference,
    holt_linear, seasonal_anchor, seasonal_difference, theta,
)

MIN_LEN = 600
BURN = 300
MAX_WORKERS = min(8, (os.cpu_count() or 4))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ladder_ablation.csv")

RUNGS = ["R0_uncond", "R1_location", "R2_scale", "R3_seasonal", "R4_serial", "R5_full"]


def ewma_leaf(k: int = 1, alpha: float = 0.03, floor_frac: float = 0.05):
    """Centered Gaussian leaf with EWMA variance: the conditional-scale state.

    The EWMA std is floored at ``floor_frac`` of the expanding-window root
    mean square (uncentered) so a run of repeated values cannot collapse the
    predictive law to a spike."""
    def _l(y, state):
        if state is None:
            state = {"v": None, "g": None, "n": 0}
        v, g, n = state["v"], state["g"], state["n"] + 1
        v = y * y if v is None else (1.0 - alpha) * v + alpha * y * y
        g = y * y if g is None else g + (y * y - g) / n
        state.update(v=v, g=g, n=n)
        lo = floor_frac * floor_frac * (g if g and math.isfinite(g) else 0.0)
        vv = max(v if (v and math.isfinite(v)) else 0.0, lo)
        std = math.sqrt(vv) if vv > 0 else max(abs(y), 1e-8)
        return [Dist.gaussian(0.0, std)] * k, state
    _l.__name__ = f"ewma_leaf(alpha={alpha})"
    return _l


def _location_transforms():
    ts = [ema_transform(a) for a in (0.01, 0.05, 0.1, 0.3)]
    ts += [drift(alpha=a, shrinkage=s)
           for a, s in ((0.05, 0.01), (0.01, 0.002), (0.002, 0.001), (0.0005, 0.0002))]
    ts += [theta(alpha=a) for a in (0.05, 0.1, 0.3)]
    ts += [holt_linear(alpha=a, beta=b) for a, b in ((0.1, 0.02), (0.1, 0.05), (0.3, 0.1))]
    ts += [difference()]
    return ts


def _pool(rung: str):
    """Nested candidate pools. Each rung's list is a superset of the last."""
    if rung == "R5_full":
        return laplace(k=1, objective="likelihood")

    cands, depths = [leaf(k=1)], [0]

    def add(c, d):
        cands.append(c)
        depths.append(d)

    if rung != "R0_uncond":
        for t in _location_transforms():
            add(conjugate(leaf(k=1), t, k=1), 1)

    if rung in ("R2_scale", "R3_seasonal", "R4_serial"):
        add(ewma_leaf(k=1), 0)
        for t in _location_transforms():
            add(conjugate(ewma_leaf(k=1), t, k=1), 1)

    if rung in ("R3_seasonal", "R4_serial"):
        for period in (7, 12, 24):
            add(conjugate(leaf(k=1), seasonal_difference(period), k=1), 1)
            add(conjugate(ewma_leaf(k=1), seasonal_difference(period), k=1), 1)
            add(conjugate(ewma_leaf(k=1), seasonal_anchor(period), k=1), 1)
            for a in (0.05, 0.1):
                add(conjugate(conjugate(ewma_leaf(k=1), ema_transform(a), k=1),
                              seasonal_difference(period), k=1), 2)

    if rung == "R4_serial":
        add(conjugate(leaf(k=1), ar(1), k=1), 1)
        add(conjugate(ewma_leaf(k=1), ar(1), k=1), 1)
        add(conjugate(ewma_leaf(k=1), ar(2, decay=1), k=1), 1)
        for d in (0.2, 0.4):
            add(conjugate(conjugate(ewma_leaf(k=1), ema_transform(0.1), k=1),
                          fractional_difference(d=d, window=30), k=1), 2)
        for a in (0.05, 0.1, 0.3):
            add(conjugate(conjugate(ewma_leaf(k=1), ema_transform(a), k=1),
                          difference(), k=1), 2)

    return bayesian_ensemble(cands, k=1, learning_rate=0.8,
                             complexity_penalty=0.005, depths=depths,
                             max_components=20)


DELTA_REF = 0.01  # reference-mixture weight: q_eval = (1-d)*q + d*N(mean, var) expanding


def _logpdf(make, series, burn=BURN):
    """Held-out mean log score of the DELTA_REF-mixture with the trivial
    expanding Gaussian. The mixture is a genuine predictive density (no
    clipping), so the reported score is an exact log score and the bridge
    identity applies to it. Returns (mean_logscore, floor_bind_fraction)."""
    f = make()
    state = None
    pend = None
    lp = 0.0
    n = 0
    nbind = 0
    mu = 0.0
    m2 = 0.0
    nobs = 0
    for i, y in enumerate(series):
        if pend is not None and i > burn and nobs > 2 and m2 > 0:
            var = m2 / (nobs - 1)
            lg = -0.5 * math.log(2 * math.pi * var) - (y - mu) ** 2 / (2 * var)
            lq = pend[0].logpdf(y)
            if not math.isfinite(lq):
                lq = -1e12
            a = math.log(1 - DELTA_REF) + lq
            b = math.log(DELTA_REF) + lg
            hi = max(a, b)
            lp += hi + math.log(math.exp(a - hi) + math.exp(b - hi))
            nbind += 1 if b > a else 0
            n += 1
        nobs += 1
        d0 = y - mu
        mu += d0 / nobs
        m2 += d0 * (y - mu)
        d, state = f(y, state)
        pend = d
    return (lp / n if n else float("nan"), nbind / n if n else float("nan"))


def score(job):
    sid, series = job
    try:
        row = [sid, len(series)]
        binds = []
        for rung in RUNGS:
            ll, bind = _logpdf(lambda r=rung: _pool(r), series)
            row.append(ll)
            binds.append(bind)
        return row + binds
    except Exception as e:
        return [sid, len(series)] + [float("nan")] * (2 * len(RUNGS))


def _corpus():
    """All cached FRED series, as changes, filtered to continuous series
    (repeat fraction < 0.05, the convention of study.py) with >= MIN_LEN."""
    out = {}
    for f in sorted(os.listdir(fred._CACHE)):
        if not f.endswith(".csv") or f == "m4_hourly.csv":
            continue
        sid = f[:-4]
        ch = fred._to_changes(fred._load_levels(sid) or [])
        if len(ch) < MIN_LEN:
            continue
        rep = sum(1 for i in range(1, len(ch)) if ch[i] == ch[i - 1]) / (len(ch) - 1)
        if rep < 0.05:
            out[sid] = ch
    return out


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    data = _corpus()
    ids = sorted(data)
    if limit:
        step = max(1, len(ids) // limit)
        ids = ids[::step][:limit]
    jobs = [(sid, data[sid]) for sid in ids]
    print(f"{len(jobs)} continuous series (min_len={MIN_LEN}, burn={BURN}), "
          f"{MAX_WORKERS} workers -> {OUT}")

    rows = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score, j): j[0] for j in jobs}
        for done, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            rows.append(r)
            if done % 10 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}", flush=True)

    rows.sort()
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["series", "n"] + RUNGS + [f"bind_{r}" for r in RUNGS])
        w.writerows(rows)

    good = [r for r in rows if len(r) == 2 + 2 * len(RUNGS)
            and all(isinstance(x, float) and math.isfinite(x) for x in r[2:])]
    print(f"\n{len(good)}/{len(rows)} series scored on all rungs "
          f"(delta-mixture reference weight {DELTA_REF}, no clipping)")
    if not good:
        return
    import random
    import statistics
    m = len(RUNGS)
    means = [sum(r[2 + i] for r in good) / len(good) for i in range(m)]
    binds = [sum(r[2 + m + i] for r in good) / len(good) for i in range(m)]
    total = means[-1] - means[0]
    print(f"\nmean held-out log score per obs (nats) [floor-bind fraction]:")
    for name, mu, b in zip(RUNGS, means, binds):
        print(f"  {name:12s} {mu:+.4f}  [{100*b:.2f}%]")
    print(f"\nmeasured representation values Delta_j (nats/obs), "
          f"total gap {total:+.4f}:")
    rng = random.Random(0)
    for i in range(1, m):
        deltas = [r[2 + i] - r[1 + i] for r in good]
        d = means[i] - means[i - 1]
        med = statistics.median(deltas)
        wins = sum(1 for x in deltas if x > 0) / len(deltas)
        share = 100.0 * d / total if total else float("nan")
        boots = []
        for _ in range(1000):
            s = [deltas[rng.randrange(len(deltas))] for _ in range(len(deltas))]
            boots.append(sum(s) / len(s))
        boots.sort()
        lo, hi = boots[50], boots[949]
        print(f"  +{RUNGS[i][3:]:9s} Delta mean={d:+.4f} "
              f"[90% CI {lo:+.4f},{hi:+.4f}] median={med:+.4f}  "
              f"share={share:5.1f}%  improves on {100*wins:.0f}% of series")


if __name__ == "__main__":
    main()
