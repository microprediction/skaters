"""How close to arch can we get while staying online? A tightening ladder (issue #25).

Dial a configurable GARCH leaf toward arch one knob at a time and measure, vs LIVE
arch on the gap series:
  * corr(log h), rmse(log h)  -- volatility-path replication (the oracle view)
  * arch_LL - leaf_LL          -- nats behind arch (both bare, on the changes)

Ladder: coarse grid -> fine grid -> free omega -> matched cadence (25/750)
        -> bounded score (Beta-t). Each step stays O(1)/online, no optimizer.

    PYTHONPATH=src python benchmarks/garch_tighten.py        (MAX_SERIES caps gap)
"""

from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import csv
import math
import sys
from collections import deque
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import fred
import bench_core as bc
from study import _cfg, _rfrac, MIN_CHANGES, MAX_CHANGES
from opponents import _garch_predict, FIT_WIN
from garch_replication import _arch_var_path, _leaf_var_path, _agree
from skaters.leaf import _SCALE_BASIS
from skaters.dist import Dist

CFG = _cfg("sota")
MAX_WORKERS = min(8, (os.cpu_count() or 4))

_COARSE = [(a, b) for a in (0.02, 0.05, 0.08, 0.12, 0.18)
           for b in (0.80, 0.88, 0.93, 0.97) if a + b < 0.999]
_FINE = [(round(0.01 + 0.015 * i, 3), round(0.70 + 0.02 * j, 3))
         for i in range(16) for j in range(15)]
_FINE = [(a, b) for (a, b) in _FINE if a + b < 0.999]


def cfg_garch_leaf(k=1, grid=_COARSE, free_omega=False, robust=False, nu=7.0,
                   refit_every=40, window=400, min_obs=80, gamma=0.02):
    C = tuple(_SCALE_BASIS); K = len(C)
    one_idx = min(range(K), key=lambda i: abs(C[i] - 1.0))
    OMC = (0.4, 0.6, 0.8, 1.0, 1.3, 1.7, 2.2) if free_omega else (1.0,)

    def bw(e2):
        return (nu + 1.0) * e2 / (nu - 2.0 + e2) if robust else e2

    def nll(resid, al, be, om, s2):
        h = s2; v = 0.0
        for r in resid:
            e2 = (r * r) / h if h > 1e-300 else 0.0
            v += math.log(max(h, 1e-300)) + (r * r) / max(h, 1e-300)
            h = om + al * h * bw(e2) + be * h
        return v

    def fit(resid):
        s2 = sum(r * r for r in resid) / len(resid)
        if s2 <= 0:
            return None
        best, bestv = None, 1e18
        for (al, be) in grid:
            base = (1.0 - al - be) * s2
            for c in OMC:
                om = max(c * base, 1e-12)
                v = nll(resid, al, be, om, s2)
                if v < bestv:
                    bestv, best = v, (om, al, be)
        return best

    def leaf(y, state):
        if state is None:
            w = [1e-6] * K; w[one_idx] = 1.0
            state = {"h": 0.0, "s2": 0.0, "n": 0, "om": 0.0, "al": 0.05, "be": 0.90,
                     "buf": deque(maxlen=window), "w": w, "lr2": 0.0}
        s = state; s["n"] += 1
        a0 = 0.02 if 0.02 > 1.0 / s["n"] else 1.0 / s["n"]
        s["s2"] = (1 - a0) * s["s2"] + a0 * y * y
        if s["s2"] <= 0:
            s["s2"] = max(y * y, 1e-12)
        if s["n"] == 1:
            h = s["s2"]
        else:
            e2 = s["lr2"] / s["h"] if s["h"] > 1e-300 else 0.0
            h = s["om"] + s["al"] * s["h"] * bw(e2) + s["be"] * s["h"]
        if h <= 1e-300:
            h = s["s2"]
        s["h"] = h; s["lr2"] = y * y; s["buf"].append(y)
        if s["n"] >= min_obs and s["n"] % refit_every == 0 and len(s["buf"]) >= min_obs:
            f = fit(list(s["buf"]))
            if f:
                s["om"], s["al"], s["be"] = f
        sigma = math.sqrt(h) if (math.isfinite(h) and h > 0) else max(abs(y), 1e-8)
        z = y / sigma; w = s["w"]
        dens = [w[i] * math.exp(-0.5 * z * z / (C[i] * C[i])) / C[i] for i in range(K)]
        tot = sum(dens)
        if tot > 0:
            g = gamma if gamma > 1.0 / s["n"] else 1.0 / s["n"]
            s["w"] = [(1 - g) * w[i] + g * dens[i] / tot for i in range(K)]
        return [Dist([(s["w"][i], 0.0, C[i] * sigma) for i in range(K)])] * k, s

    return leaf


LADDER = [
    ("L0 coarse/target/std/40", dict()),
    ("L1 +fine grid",            dict(grid=_FINE)),
    ("L2 +free omega",           dict(grid=_FINE, free_omega=True)),
    ("L3 +matched cadence",      dict(grid=_FINE, free_omega=True, refit_every=25, window=FIT_WIN)),
    ("L4 +bounded score",        dict(grid=_FINE, free_omega=True, refit_every=25, window=FIT_WIN, robust=True)),
]


def _prep(sid):
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    if len(ch) < MIN_CHANGES:
        return None, None
    if len(ch) > MAX_CHANGES:
        ch = ch[-MAX_CHANGES:]
    from study import _start_for
    return ch, _start_for(len(ch), CFG)


def _score(sid):
    ch, start = _prep(sid)
    if ch is None:
        return None
    archv = _arch_var_path(ch, start)
    gt = _garch_predict(ch, start, CFG["refit"])
    if archv is None or not gt:
        return None
    archv = np.asarray(archv); arch_ll = gt[0][1]
    res = {}
    for name, kw in LADDER:
        fac = lambda kw=kw: cfg_garch_leaf(k=1, **kw)
        ours = np.asarray(_leaf_var_path(fac, ch, start))
        ag = _agree(ours, archv)
        ll, _, n = bc.roll_dist_scores(fac, ch, start)
        if ag is None or not n:
            return None
        res[name] = (ag[0], ag[1], arch_ll - ll)      # corr, rmse, LL deficit
    return res


def main():
    rows = {}
    with open(CFG["results"]) as fh:
        for r in csv.DictReader(fh):
            rows.setdefault(r["series"], {})[r["method"]] = (float(r["logpdf"]), float(r["crps"]))
    gap = [s for s, d in rows.items() if "laplace" in d and "GARCH-t" in d
           and not math.isnan(d["laplace"][0]) and not math.isnan(d["GARCH-t"][0])
           and d["GARCH-t"][0] > d["laplace"][0] and _rfrac(s) < 0.05]
    cap = int(os.environ.get("MAX_SERIES", "30"))
    gap = gap[:cap]
    print(f"gap series: {len(gap)}  (fine grid: {len(_FINE)} (alpha,beta) pts)")

    out = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(_score, s): s for s in gap}
        done = 0
        for fut in as_completed(futs):
            r = fut.result(); done += 1
            if r:
                out.append(r)
            if done % 10 == 0:
                print(f"  {done}/{len(gap)}", flush=True)

    print(f"\n=== tightening ladder vs arch, n={len(out)} ===")
    print(f"  {'config':26s}{'corr(log h)':>13s}{'rmse(log h)':>13s}{'LL behind arch':>16s}")
    for name, _ in LADDER:
        corr = np.mean([r[name][0] for r in out])
        rmse = np.mean([r[name][1] for r in out])
        defi = np.mean([r[name][2] for r in out])
        print(f"  {name:26s}{corr:>13.3f}{rmse:>13.3f}{defi:>16.4f}")


if __name__ == "__main__":
    main()
