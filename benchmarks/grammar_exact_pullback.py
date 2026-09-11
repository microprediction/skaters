"""Exact-pullback log scores for the grammar paper's ladder configs.

The campaign scores a nine-particle Gaussian-mixture representation of the
pulled-back predictive. That is exact scoring of an approximate
distribution, not exact change of variables, and part of the operator's
apparent log-score tax could be representation error. This runner scores
the exact pullback instead:

    log p_Y(y) = log q(m(y)) + log |m'(y)|,

with m the composed forward map evaluated purely (states untouched), the
Jacobian computed analytically per rung (EMA shift 1, standardize 1/sigma,
gaussianize segment slope, AR shift 1), q the terminal predictive in the
innermost coordinate, and the usual DELTA_REF reference blend applied in
observation space. The exact map excludes the |z| <= z_max learner-input
channel, matching the paper's separation. No particles are involved.

Configs: D0x (ema, std, gauss -> fixed N(0,1)), Dx (-> leaf),
Ex (ema, std, gauss, ar -> leaf), Fx (ema, std, ar -> leaf).

Writes grammar_exact_pullback.csv (log score only; CRPS is not computed).

Run:  python grammar_exact_pullback.py [limit]
"""
from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import bisect
import csv
import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ladder_ablation as LA
import gaussianize_chain as GC
from skaters.dist import Dist
from skaters.leaf import leaf
from skaters.transform import ar, ema_transform, gaussianize, standardize

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "grammar_exact_pullback.csv")
EPS = 1e-8


# ------------------------------------------------- pure per-rung evaluation
def _pure_ema(y, state):
    if state is None:
        return y, 1.0
    return y - state["level"], 1.0


def _pure_std(y, state):
    if state is None:
        return y, 1.0
    diff = y - state["mu"]
    var = state["var"]
    if var > EPS * EPS:
        sigma = math.sqrt(var)
    else:
        sigma = abs(diff) if abs(diff) > EPS else EPS
    return diff / sigma, 1.0 / sigma


def _pure_gauss(y, state):
    if state is None:
        return y, 1.0
    knots = state["knots"]
    if knots is None:
        n, mu, m2 = state["n"], state["mu"], state["m2"]
        var = m2 / (n - 1) if n > 2 else 0.0
        sigma = math.sqrt(var) if var > 0 else 1e-8
        if sigma <= 1e-8:
            sigma = max(abs(y - mu), 1e-8)
        return ((y - mu) / sigma if n else 0.0), 1.0 / sigma
    cs, zs, _ = knots
    if y <= cs[0]:
        s = (zs[1] - zs[0]) / (cs[1] - cs[0])
        return zs[0] + s * (y - cs[0]), s
    if y >= cs[-1]:
        s = (zs[-1] - zs[-2]) / (cs[-1] - cs[-2])
        return zs[-1] + s * (y - cs[-1]), s
    i = bisect.bisect_right(cs, y) - 1
    s = (zs[i + 1] - zs[i]) / (cs[i + 1] - cs[i])
    return zs[i] + s * (y - cs[i]), s


def _pure_ar(y, state):
    if state is None:
        return y, 1.0
    buf, phi = state["buffer"], state["phi"]
    p = len(phi)
    if len(buf) >= p:
        pred = sum(phi[i] * buf[-(i + 1)] for i in range(p))
        return y - pred, 1.0
    return y, 1.0


_PURE = {"ema": _pure_ema, "std": _pure_std, "gauss": _pure_gauss, "ar": _pure_ar}


# ----------------------------------------------------------- chain scoring
def make_chain(name):
    if name == "D0x":
        kinds = ["ema", "std", "gauss"]
        terminal = None                       # fixed N(0,1)
    elif name == "Dx":
        kinds = ["ema", "std", "gauss"]
        terminal = leaf(k=1)
    elif name == "Ex":
        kinds = ["ema", "std", "gauss", "ar"]
        terminal = leaf(k=1)
    elif name == "Fx":
        kinds = ["ema", "std", "ar"]
        terminal = leaf(k=1)
    else:
        raise ValueError(name)
    makers = {"ema": lambda: ema_transform(0.1), "std": lambda: standardize(0.05),
              "gauss": lambda: gaussianize(), "ar": lambda: ar(1)}
    fwds = [makers[k]()[0] for k in kinds]
    return kinds, fwds, terminal


def score_series(name, series):
    kinds, fwds, terminal = make_chain(name)
    states = [None] * len(kinds)
    t_state = None
    pend = Dist.gaussian(0.0, 1.0) if terminal is None else None
    lp = 0.0
    n = 0
    mu = m2 = 0.0
    nobs = 0
    for i, y in enumerate(series):
        # exact pullback score of the pending predictive at y
        if (pend is not None and i > GC.BURN and nobs > 2 and m2 > 0):
            u, logdet = y, 0.0
            ok = True
            for k, st in zip(kinds, states):
                u, d = _PURE[k](u, st)
                if not (d > 0) or not math.isfinite(u):
                    ok = False
                    break
                logdet += math.log(d)
            if ok:
                lq = pend.logpdf(u) + logdet
            else:
                lq = -1e12
            if not math.isfinite(lq):
                lq = -1e12
            var = m2 / (nobs - 1)
            lg = -0.5 * math.log(2 * math.pi * var) - (y - mu) ** 2 / (2 * var)
            a = math.log(1 - LA.DELTA_REF) + lq
            b = math.log(LA.DELTA_REF) + lg
            hi = max(a, b)
            lp += hi + math.log(math.exp(a - hi) + math.exp(b - hi))
            n += 1
        nobs += 1
        d0 = y - mu
        mu += d0 / nobs
        m2 += d0 * (y - mu)
        # actual updates
        u = y
        for j, (k, f) in enumerate(zip(kinds, fwds)):
            u, states[j] = f(u, states[j])
        if terminal is not None:
            dists, t_state = terminal(u, t_state)
            pend = dists[0]
    return lp / n if n else float("nan")


CONFIGS = ["D0x", "Dx", "Ex", "Fx"]


def score(job):
    sid, series = job
    try:
        return [sid, len(series)] + [score_series(c, series) for c in CONFIGS]
    except Exception:
        return [sid, len(series)] + [float("nan")] * len(CONFIGS)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    data = LA._corpus()
    ids = sorted(data)
    if limit:
        step = max(1, len(ids) // limit)
        ids = ids[::step][:limit]
    jobs = [(sid, data[sid]) for sid in ids]
    print(f"{len(jobs)} series x {len(CONFIGS)} exact-pullback configs", flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=GC.MAX_WORKERS) as ex:
        futs = {ex.submit(score, j): j[0] for j in jobs}
        for k, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if k % 50 == 0:
                print(f"{k}/{len(jobs)}", flush=True)
    rows.sort(key=lambda r: r[0])
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "n"] + [f"ll_{c}" for c in CONFIGS])
        w.writerows(rows)
    import statistics as st
    for j, c in enumerate(CONFIGS):
        vals = [r[2 + j] for r in rows if r[2 + j] == r[2 + j]]
        print(f"  {c:4s} exact-pullback ll {st.mean(vals):+.4f}  (n={len(vals)})")


if __name__ == "__main__":
    main()
