"""Core-ready prototype of the sidecar feature: laplace safely absorbing a
third-party model's forecast stream.

These are composable ONLINE skaters (f(y, state) -> ([Dist]*k, state)), the exact
shape src/skaters uses, so promotion is a move not a rewrite. Zero extra deps: a
sidecar is a skater that yields the external model's per-step predictive Dist —
the wire format — never the model itself (which runs in its own venv and streams
its forecasts in lockstep).

Two layers, matching the study's @lap and &lap:

    recal = sidecar_recalibrate(fm_skater)        # @lap: PIT recalibration
    f     = sidecar_portfolio(laplace(1), recal)  # &lap: never-worse portfolio

`sidecar_recalibrate` predicts in the FM's own CDF space — z = Phi^{-1}(F_fm(y)),
an internal laplace forecasts the z-series, invert F_fm^{-1}(Phi(.)) — keeping the
FM's full shape and fixing only calibration. `sidecar_portfolio` is a long-only
online log-score blend of a base forecaster and the recalibrated sidecar, started
tilted to the base (the trusted incumbent) so the sidecar must earn its weight.

Skater convention (like terminal_leaf_ensemble): closures live in the wrapper,
state is pure data.
"""
from __future__ import annotations
import math

import numpy as np

import foundation_study as fs
from predictions import _norm_ppf as _nppf
from skaters.api import laplace


def _ncdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


_L = [0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5,
      0.6, 0.7, 0.8, 0.9, 0.95, 0.975, 0.99]


def _clip01(u):
    return min(max(u, 1e-6), 1.0 - 1e-6)


def _clamp_lp(lp):
    return 20.0 if lp > 20.0 else (-20.0 if not (lp >= -20.0) else lp)


def mix_dists(dists, w):
    """Weighted-CDF mixture of arbitrary Dists (handles SplicedDist), rebuilt as a
    quantile_dist on the standard grid by per-level bisection."""
    lo = min(d.quantile(0.001) for d in dists)
    hi = max(d.quantile(0.999) for d in dists)
    if not (hi > lo):
        hi = lo + 1e-9
    qs = []
    for p in _L:
        a, b = lo, hi
        for _ in range(40):
            mid = 0.5 * (a + b)
            if sum(wi * d.cdf(mid) for wi, d in zip(w, dists)) < p:
                a = mid
            else:
                b = mid
        qs.append(0.5 * (a + b))
    return fs.quantile_dist(_L, list(np.maximum.accumulate(qs)))


def sidecar_recalibrate(fm):
    """@lap as a streaming skater. `fm` is a skater yielding the external model's
    1-step predictive Dist. Returns a skater whose predictive is the FM's own
    distribution with its calibration corrected by an internal laplace in z-space."""
    _lap = laplace(1)                       # internal z-predictor (closure here)

    def f(y, state):
        if state is None:
            state = {"lap": None, "fm": None, "F_pend": None}
        # Resolve the just-observed y against the FM predictive made last step,
        # map to a normal score, and advance the internal laplace on the z-series.
        z = 0.0
        if state["F_pend"] is not None:
            z = _nppf(_clip01(state["F_pend"].cdf(y)))
        zd, state["lap"] = _lap(z, state["lap"])
        G = zd[0]                            # laplace predictive for next z
        fd, state["fm"] = fm(y, state["fm"])
        F_next = fd[0]
        state["F_pend"] = F_next
        # Invert: recalibrated p-quantile of y is F_next^{-1}(Phi(G^{-1}(p))).
        qs = [F_next.quantile(_clip01(_ncdf(G.quantile(p)))) for p in _L]
        return [fs.quantile_dist(_L, list(np.maximum.accumulate(qs)))], state

    f.__name__ = "sidecar_recalibrate"
    return f


def sidecar_portfolio(base, side, forget=0.98, eta=0.8, base_prior=2.0):
    """&lap as a streaming skater. Long-only online log-score portfolio of a base
    forecaster and a sidecar, tilted to the base by `base_prior` log-units so the
    sidecar must earn weight. Never worse than base in the limit."""
    def f(y, state):
        if state is None:
            state = {"b": None, "s": None, "lw": [base_prior, 0.0], "pend": None}
        if state["pend"] is not None:        # learn from the resolved prediction
            for j, d in enumerate(state["pend"]):
                state["lw"][j] = forget * state["lw"][j] + eta * _clamp_lp(d.logpdf(y))
        bd, state["b"] = base(y, state["b"])
        sd, state["s"] = side(y, state["s"])
        b0, s0 = bd[0], sd[0]
        m = max(state["lw"]); w = [math.exp(x - m) for x in state["lw"]]
        tot = sum(w); w = [x / tot for x in w]
        state["pend"] = [b0, s0]
        return [mix_dists([b0, s0], w)], state

    f.__name__ = "sidecar_portfolio"
    return f


def laplace_sidecar(fm, base_prior=2.0, **lap_kwargs):
    """Convenience: laplace + recalibrated sidecar portfolio (the &lap forecaster).
    `fm` streams the external model's predictive; laplace is the trusted base."""
    return sidecar_portfolio(laplace(1, **lap_kwargs), sidecar_recalibrate(fm),
                             base_prior=base_prior)


# --------------------------------------------------------------------- self-test
if __name__ == "__main__":
    # A deliberately OVER-CONFIDENT stub FM: forecasts a decent mean (EMA of y)
    # but with far-too-small variance. Recalibration should widen it to ~nominal
    # coverage, and the portfolio should never trail plain laplace by much.
    from skaters.dist import Dist

    def stub_fm(y, state):
        st = {"ema": y} if state is None else state
        st["ema"] = 0.7 * st["ema"] + 0.3 * y
        return [Dist.gaussian(st["ema"], 0.15)], st          # too sharp on purpose

    rng = np.random.default_rng(0)
    n = 1500
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.6 * y[t - 1] + rng.normal(0, 1.0)           # AR(1), true sd ~1

    def run(skater):
        st = None; pend = None; cov = ll = m = 0
        for t in range(n):
            if pend is not None and t > 300:
                d = pend
                lo, hi = d.quantile(0.05), d.quantile(0.95)
                cov += lo <= y[t] <= hi
                lp = d.logpdf(y[t]); ll += max(lp, -20.0) if math.isfinite(lp) else -20.0
                m += 1
            out, st = skater(y[t], st); pend = out[0]
        return cov / m, ll / m

    raw = laplace(1)
    fm_raw = stub_fm
    recal = sidecar_recalibrate(stub_fm)
    port = laplace_sidecar(stub_fm)

    def run_fm(fm):
        st = None; pend = None; cov = ll = m = 0
        for t in range(n):
            if pend is not None and t > 300:
                lo, hi = pend.quantile(0.05), pend.quantile(0.95)
                cov += lo <= y[t] <= hi
                lp = pend.logpdf(y[t]); ll += max(lp, -20.0) if math.isfinite(lp) else -20.0
                m += 1
            out, st = fm(y[t], st); pend = out[0]
        return cov / m, ll / m

    print("stub-FM sidecar self-test (AR(1), true sd~1; stub over-confident sd=0.15):")
    print("  raw stub FM      cov90=%.3f  LL=%.3f" % run_fm(stub_fm))
    print("  recalibrated @   cov90=%.3f  LL=%.3f" % run_fm(recal))
    print("  plain laplace    cov90=%.3f  LL=%.3f" % run(raw))
    print("  portfolio &      cov90=%.3f  LL=%.3f" % run(port))
