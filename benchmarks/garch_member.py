"""Closing the gap to GARCH-t on price/return series (issue #25) — exploration log.

GARCH-t (Bollerslev 1986/1987) is constant-mean + GARCH(1,1) + Student-t, fit by
joint MLE. `garch_leaf` (PR #27) recovers ~53% of the laplace->GARCH-t LL gap with
a coarse-grid GARCH variance + scale-mixture tails, NFL-safe. This file records the
attempts to close MORE of it, scored vs LIVE arch on gap + control populations.

DEAD ENDS (all <= the shipped garch_leaf grid; kept as a record):
  * fitted-nu Student-t tails (vs the scale mixture): WORSE (-59% on the gap).
    The scale-mixture's free EM weights are a richer, more adaptive tail family
    than a single fitted nu.
  * committing the mean (zero-mean / slow-EMA garch): no gain on the gap, and it
    HURTS the control — the trunk was not the handicap.
  * soft-weight meta bayesian_ensemble([laplace, garch]): dilutes (12%) — mixing
    two predictives fattens the tail, so it never reaches the better member.
  * hard SWITCH on running likelihood: cumulative is too sticky (12%); recency-
    discounted (0.99) recovers ~34% but still <= the leaf and never exceeds it.
  * ARMA(1,1)-moment closed-form GARCH fit (phi=rho2/rho1, beta from rho1): WORSE
    (13%) — squared-return ACF is too noisy for an efficient (alpha,beta).
  * full Gaussian QMLE via unconstrained Nelder-Mead: numerically blew up (the
    reason arch exists). Proper GARCH MLE needs bounded reparameterization.

Why GARCH-t is hard to beat: it is correctly specified for returns, fit by
efficient JOINT MLE on a low-dim parameter (near Cramer-Rao), on a population
selected as its home turf. Every cheap modular approximation leaves LL on the
table. (Off-turf it is badly misspecified — it scores ~-0.9 on the control where
laplace scores +3 — which is exactly the No-Free-Lunch story.)

LIVE: Beta-t-GARCH (Harvey 2013, score-driven) — the GARCH recursion driven by the
BOUNDED t-score so outliers saturate instead of blowing up the variance. Online,
parity-friendly, may even beat arch via robustness. See betat_garch_leaf.

    PYTHONPATH=src python benchmarks/garch_member.py     (MAX_SERIES caps each pop)
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
import bench_core as bc
from study import _cfg, _start_for, _rfrac, MIN_CHANGES, MAX_CHANGES
from opponents import _garch_predict
from garch_leaf_study import _laplace_with_leaf
from skaters.leaf import scale_mixture_leaf, garch_leaf
from skaters.conjugate import conjugate
from skaters.transform import ema_transform
from skaters.bayesian import bayesian_ensemble

CFG = _cfg("sota")
REFIT = CFG["refit"]
MAX_WORKERS = min(8, (os.cpu_count() or 4))


def _prep(sid):
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    if len(ch) < MIN_CHANGES:
        return None, None
    if len(ch) > MAX_CHANGES:
        ch = ch[-MAX_CHANGES:]
    return ch, _start_for(len(ch), CFG)


def _arma_garch_fit(resid):
    """Closed-form GARCH(1,1) (omega,alpha,beta) from ARMA(1,1) moments of r^2.

    r_t^2 is ARMA(1,1): AR root phi=alpha+beta, MA root -beta. So phi=rho2/rho1
    (geometric ACF decay) and rho1 pins beta via a quadratic with reciprocal roots
    (take the invertible one). omega by variance targeting. None if degenerate.
    """
    n = len(resid)
    x = [r * r for r in resid]
    mu = sum(x) / n
    if mu <= 0:
        return None
    xc = [xi - mu for xi in x]
    g0 = sum(v * v for v in xc) / n
    if g0 <= 0:
        return None
    g1 = sum(xc[i] * xc[i - 1] for i in range(1, n)) / n
    g2 = sum(xc[i] * xc[i - 2] for i in range(2, n)) / n
    r1, r2 = g1 / g0, g2 / g0
    if r1 <= 1e-3:                         # no vol clustering -> no GARCH signal
        return None
    phi = r2 / r1
    if not (0.0 < phi < 0.999):
        return None
    a = r1 - phi
    if abs(a) < 1e-12:
        return None
    b = 2 * r1 * phi - 1 - phi * phi
    disc = b * b - 4 * a * a
    if disc < 0:
        return None
    sq = math.sqrt(disc)
    t1, t2 = (-b + sq) / (2 * a), (-b - sq) / (2 * a)
    theta = t1 if abs(t1) < abs(t2) else t2    # invertible (|theta|<1) root
    if not (-1.0 < theta < 0.0):               # need beta = -theta in (0,1)
        return None
    beta = -theta
    alpha = phi - beta
    if alpha <= 0 or beta <= 0 or alpha + beta >= 0.999:
        return None
    return (1.0 - phi) * mu, alpha, beta       # omega via variance targeting


def garch_leaf_acf(k: int = 1, gamma: float = 0.02, refit_every: int = 40,
                   min_obs: int = 80, window: int = 400):
    """garch_leaf, but (alpha,beta,omega) fit by the closed-form ARMA-moment trick
    (falls back to the existing grid fit when the moments are degenerate)."""
    from collections import deque
    from skaters.leaf import _SCALE_BASIS, _garch_nll, _GARCH_AB_GRID
    from skaters.dist import Dist
    C = tuple(_SCALE_BASIS); K = len(C)
    one_idx = min(range(K), key=lambda i: abs(C[i] - 1.0))

    def _leaf(y, state):
        if state is None:
            w = [1e-6] * K; w[one_idx] = 1.0
            state = {"h": 0.0, "s2": 0.0, "n": 0, "om": 0.0, "al": 0.05, "be": 0.90,
                     "buf": deque(maxlen=window), "w": w, "lr2": 0.0}
        s = state; s["n"] += 1
        a0 = 0.02 if 0.02 > 1.0 / s["n"] else 1.0 / s["n"]
        s["s2"] = (1 - a0) * s["s2"] + a0 * y * y
        if s["s2"] <= 0:
            s["s2"] = max(y * y, 1e-12)
        h = s["s2"] if s["n"] == 1 else s["om"] + s["al"] * s["lr2"] + s["be"] * s["h"]
        if h <= 1e-300:
            h = s["s2"]
        s["h"] = h; s["lr2"] = y * y; s["buf"].append(y)
        if s["n"] >= min_obs and s["n"] % refit_every == 0 and len(s["buf"]) >= min_obs:
            resid = list(s["buf"])
            fit = _arma_garch_fit(resid)
            if fit is None:                                   # fall back to the grid
                s2 = sum(r * r for r in resid) / len(resid)
                if s2 > 0:
                    al, be = min(_GARCH_AB_GRID, key=lambda ab: _garch_nll(resid, ab[0], ab[1], s2))
                    fit = ((1.0 - al - be) * s2, al, be)
            if fit is not None:
                s["om"], s["al"], s["be"] = fit
        sigma = math.sqrt(h) if (math.isfinite(h) and h > 0) else max(abs(y), 1e-8)
        z = y / sigma; w = s["w"]
        dens = [w[i] * math.exp(-0.5 * z * z / (C[i] * C[i])) / C[i] for i in range(K)]
        tot = sum(dens)
        if tot > 0:
            g = gamma if gamma > 1.0 / s["n"] else 1.0 / s["n"]
            s["w"] = [(1 - g) * w[i] + g * dens[i] / tot for i in range(K)]
        return [Dist([(s["w"][i], 0.0, C[i] * sigma) for i in range(K)])] * k, s

    return _leaf


def betat_garch_leaf(k: int = 1, nu: float = 7.0, gamma: float = 0.02,
                     refit_every: int = 40, min_obs: int = 80, window: int = 400):
    """Beta-t-GARCH (Harvey 2013): the GARCH recursion driven by the BOUNDED
    Student-t score b_t = (nu+1) eps^2 / (nu-2 + eps^2) instead of eps^2, so a huge
    return saturates (b_t -> nu+1) rather than blowing up the variance. Robustness
    is the score-driven win on fat-tailed returns. Scale-mixture tails kept (they
    beat a fitted-nu emission). (alpha,beta) grid-fit on the robust recursion.
    """
    from collections import deque
    from skaters.leaf import _SCALE_BASIS
    from skaters.dist import Dist
    C = tuple(_SCALE_BASIS); K = len(C)
    one_idx = min(range(K), key=lambda i: abs(C[i] - 1.0))
    AB = [(a, b) for a in (0.02, 0.05, 0.08, 0.12, 0.18)
          for b in (0.80, 0.88, 0.93, 0.97) if a + b < 0.999]

    def _bw(eps2):
        return (nu + 1.0) * eps2 / (nu - 2.0 + eps2)

    def _nll(resid, al, be, s2):
        om = max((1.0 - al - be) * s2, 1e-12)
        h = s2; nll = 0.0
        for r in resid:
            eps2 = (r * r) / h if h > 1e-300 else 0.0
            nll += math.log(h) + (r * r) / max(h, 1e-300)
            h = om + al * h * _bw(eps2) + be * h          # robust recursion
        return 0.5 * nll

    def _leaf(y, state):
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
            eps2 = s["lr2"] / s["h"] if s["h"] > 1e-300 else 0.0
            h = s["om"] + s["al"] * s["h"] * _bw(eps2) + s["be"] * s["h"]
        if h <= 1e-300:
            h = s["s2"]
        s["h"] = h; s["lr2"] = y * y; s["buf"].append(y)
        if s["n"] >= min_obs and s["n"] % refit_every == 0 and len(s["buf"]) >= min_obs:
            resid = list(s["buf"]); s2 = sum(r * r for r in resid) / len(resid)
            if s2 > 0:
                al, be = min(AB, key=lambda ab: _nll(resid, ab[0], ab[1], s2))
                s["al"], s["be"] = al, be
                s["om"] = max((1.0 - al - be) * s2, 1e-12)
        sigma = math.sqrt(h) if (math.isfinite(h) and h > 0) else max(abs(y), 1e-8)
        z = y / sigma; w = s["w"]
        dens = [w[i] * math.exp(-0.5 * z * z / (C[i] * C[i])) / C[i] for i in range(K)]
        tot = sum(dens)
        if tot > 0:
            g = gamma if gamma > 1.0 / s["n"] else 1.0 / s["n"]
            s["w"] = [(1 - g) * w[i] + g * dens[i] / tot for i in range(K)]
        return [Dist([(s["w"][i], 0.0, C[i] * sigma) for i in range(K)])] * k, s

    return _leaf


def _meta(lr):
    # idea 1 (soft): run laplace + a zero-mean GARCH member, weight to a MIXTURE.
    return bayesian_ensemble([_laplace_with_leaf(scale_mixture_leaf), garch_leaf(k=1)],
                             k=1, learning_rate=lr)


def _switch(decay=1.0):
    # idea 1+2 (hard): emit the member with the best running log-likelihood, so we
    # SELECT the winner per series instead of mixing (mixing fattens the tail).
    # decay<1 = recency-discounted (shorter memory); decay=1 = full cumulative.
    members = [_laplace_with_leaf(scale_mixture_leaf), garch_leaf(k=1)]
    M = len(members)

    def f(y, state):
        if state is None:
            state = {"sub": [None] * M, "score": [0.0] * M, "last": [None] * M}
        s = state
        for i in range(M):
            if s["last"][i] is not None:
                v = s["last"][i].logpdf(y)
                s["score"][i] = decay * s["score"][i] + (v if math.isfinite(v) else -20.0)
        dists = []
        for i in range(M):
            d, s["sub"][i] = members[i](y, s["sub"][i])
            s["last"][i] = d[0]
            dists.append(d)
        best = max(range(M), key=lambda i: s["score"][i])
        return dists[best], s

    return f


def _score(args):
    sid, is_gap = args
    ch, start = _prep(sid)
    if ch is None:
        return None
    def ll(fac):
        lp, _, n = bc.roll_dist_scores(fac, ch, start)
        return lp if n else float("nan")
    lap = ll(lambda: _laplace_with_leaf(scale_mixture_leaf))
    lapg = ll(lambda: _laplace_with_leaf(garch_leaf))           # standard GARCH grid
    lpb = ll(lambda: _laplace_with_leaf(betat_garch_leaf))      # Beta-t-GARCH (robust)
    bt0 = ll(lambda: betat_garch_leaf(k=1))                     # bare Beta-t-GARCH
    gt = _garch_predict(ch, start, REFIT)
    if not gt or not all(math.isfinite(x) for x in (lap, lapg, lpb, bt0)):
        return None
    return (sid, is_gap, lap, lapg, lpb, bt0, gt[0][1])


_ARMS = {"laplace": 2, "laplace[garch-std]": 3, "laplace[beta-t]": 4, "beta-t only": 5}


def _report(label, out):
    import numpy as np
    if not out:
        print(f"\n{label}: none"); return
    lap = np.array([r[2] for r in out]); gt = np.array([r[6] for r in out])
    gapsz = gt - lap
    print(f"\n=== {label}, n={len(out)} — mean one-step LL (GARCH-t {gt.mean():+.3f}) ===")
    for nm, idx in _ARMS.items():
        a = np.array([r[idx] for r in out])
        closed = (f", closes {100*float((a-lap).sum()/gapsz.sum()):.0f}% of gap"
                  if gapsz.sum() > 0 else "")
        print(f"  {nm:20s} {a.mean():+.3f}   vs laplace {(a-lap).mean():+.4f} nats, "
              f"win {100*np.mean(a>lap):.0f}%, >=GARCH-t {100*np.mean(a>=gt):.0f}%{closed}")


def main():
    rows = {}
    with open(CFG["results"]) as fh:
        for r in csv.DictReader(fh):
            rows.setdefault(r["series"], {})[r["method"]] = (float(r["logpdf"]), float(r["crps"]))
    cont = [s for s, d in rows.items() if "laplace" in d and "GARCH-t" in d
            and not math.isnan(d["laplace"][0]) and not math.isnan(d["GARCH-t"][0]) and _rfrac(s) < 0.05]
    gap = [s for s in cont if rows[s]["GARCH-t"][0] > rows[s]["laplace"][0]]
    ctrl = [s for s in cont if s not in set(gap)]
    cap = int(os.environ.get("MAX_SERIES", "0"))
    if cap:
        gap, ctrl = gap[:cap], ctrl[:cap]
    work = [(s, True) for s in gap] + [(s, False) for s in ctrl]
    print(f"gap: {len(gap)}   control: {len(ctrl)}")

    out = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(_score, w): w for w in work}
        done = 0
        for fut in as_completed(futs):
            r = fut.result(); done += 1
            if r:
                out.append(r)
            if done % 20 == 0:
                print(f"  {done}/{len(work)}", flush=True)

    _report("GAP (GARCH-t's turf)", [r for r in out if r[1]])
    _report("CONTROL (NFL safety)", [r for r in out if not r[1]])


if __name__ == "__main__":
    main()


# Decisive test: full Gaussian QMLE of (omega, alpha, beta) — a proper Bollerslev
# GARCH(1,1) fit (scipy, benchmark-only) + our scale-mixture tails. Upper bound on
# what a pure-Python GARCH MLE member could reach.
def garch_leaf_mle(k: int = 1, refit_every: int = 40, min_obs: int = 80, window: int = 400):
    import math as _m
    from collections import deque
    from scipy.optimize import minimize
    from skaters.leaf import _SCALE_BASIS
    from skaters.dist import Dist
    C = tuple(_SCALE_BASIS); K = len(C)
    one_idx = min(range(K), key=lambda i: abs(C[i] - 1.0))

    def _nll(p, resid, s2):
        om, al, be = p
        if om <= 0 or al < 0 or be < 0 or al + be >= 0.999:
            return 1e18
        h = s2; nll = 0.0
        for r in resid:
            h = om + al * r * r + be * h
            if h <= 1e-300: h = 1e-300
            nll += _m.log(h) + r * r / h
        return 0.5 * nll

    def _leaf(y, state):
        if state is None:
            w = [1e-6] * K; w[one_idx] = 1.0
            state = {"h": 0.0, "s2": 0.0, "n": 0, "om": 1e-6, "al": 0.05, "be": 0.9,
                     "buf": deque(maxlen=window), "w": w, "lr2": 0.0}
        s = state; s["n"] += 1
        a0 = 0.02 if 0.02 > 1.0 / s["n"] else 1.0 / s["n"]
        s["s2"] = (1 - a0) * s["s2"] + a0 * y * y
        if s["s2"] <= 0: s["s2"] = max(y * y, 1e-12)
        h = s["s2"] if s["n"] == 1 else s["om"] + s["al"] * s["lr2"] + s["be"] * s["h"]
        if h <= 1e-300: h = s["s2"]
        s["h"] = h; s["lr2"] = y * y; s["buf"].append(y)
        if s["n"] >= min_obs and s["n"] % refit_every == 0 and len(s["buf"]) >= min_obs:
            resid = list(s["buf"]); s2 = sum(r * r for r in resid) / len(resid)
            if s2 > 0:
                p0 = [max((1 - s["al"] - s["be"]) * s2, 1e-8), s["al"], s["be"]]
                try:
                    r = minimize(_nll, p0, args=(resid, s2), method="Nelder-Mead",
                                 options={"maxiter": 300, "xatol": 1e-6, "fatol": 1e-6})
                    om, al, be = r.x
                    if om > 0 and al >= 0 and be >= 0 and al + be < 0.999:
                        s["om"], s["al"], s["be"] = om, al, be
                except Exception:
                    pass
        sigma = _m.sqrt(h) if (_m.isfinite(h) and h > 0) else max(abs(y), 1e-8)
        z = y / sigma; w = s["w"]
        dens = [w[i] * _m.exp(-0.5 * z * z / (C[i] * C[i])) / C[i] for i in range(K)]
        tot = sum(dens)
        if tot > 0:
            g = 0.02 if 0.02 > 1.0 / s["n"] else 1.0 / s["n"]
            s["w"] = [(1 - g) * w[i] + g * dens[i] / tot for i in range(K)]
        return [Dist([(s["w"][i], 0.0, C[i] * sigma) for i in range(K)])] * k, s
    return _leaf
