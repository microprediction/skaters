"""Terminal-stage variants: transfer candidate distributional knowledge.

laplace's terminal_leaf_ensemble collapses the candidate mixture to its MEAN
and re-derives the whole predictive from residual history through one global
leaf. On near-martingale FRED change-series that is free (location is the only
transferable knowledge); on seasonal data it discards exactly what matters
(see comparisons/laplace-vs-csp/). Two repairs, both "model first, conform
last" with a richer object conformed:

  terminal_stud_ensemble  leaf models the STUDENTIZED residual (y-mu_t)/s_t,
                          where mu_t, s_t are the candidate mixture's mean and
                          std; issues leaf*s_t + mu_t. Any candidate's scale
                          knowledge transfers; flat-scale candidates reduce it
                          to the stock terminal exactly.
  terminal_pit_ensemble   terminal layer is a monotone recalibration of the
                          FULL candidate mixture F_t: track PITs u=F_t(y),
                          issue F_t^{-1}(g^{-1}(tau)) on a quantile grid.
                          Everything transfers (width, skew, shape).

Benchmark-side for the experiment; candidates include seasonal_scale
compositions (the scale carriers) at the stock periods plus BENCH_CSP_M.
"""
from __future__ import annotations
import math
import os
from collections import deque

import numpy as np

from skaters.api import _build_candidates
from skaters.conjugate import conjugate
from skaters.dist import Dist
from skaters.leaf import crps_leaf, leaf as plain_leaf
from skaters.parade import parade
from skaters.sticky import sticky
from skaters.tails import gpdtails
from skaters.transform import seasonal_difference, seasonal_scale

TAUS = np.linspace(0.02, 0.98, 41)


def _candidates(k=1):
    """Stock population + seasonal_scale compositions (the scale carriers)."""
    cands, depths, _ = _build_candidates(k)
    periods = {7, 12, 24}
    m = os.environ.get("BENCH_CSP_M")
    if m and int(m) > 1:
        periods.add(int(m))
    for p in sorted(periods):
        cands.append(conjugate(conjugate(plain_leaf(k=k), seasonal_scale(p, 0.05), k=k),
                               seasonal_difference(p), k=k))
        depths.append(2)
        cands.append(conjugate(plain_leaf(k=k), seasonal_scale(p, 0.1, center=True), k=k))
        depths.append(1)
    return cands, depths


def _clamp_lp(lp):
    if lp > 20.0:
        return 20.0
    return lp if lp >= -20.0 else -20.0


def _weights(log_w):
    mx = max(log_w)
    w = [math.exp(v - mx) for v in log_w]
    tot = sum(w)
    return [v / tot for v in w]


def _mix_moments(all_dists, w):
    mu = sum(wi * d[0].mean for wi, d in zip(w, all_dists))
    m2 = sum(wi * (d[0].var + d[0].mean ** 2) for wi, d in zip(w, all_dists))
    var = max(m2 - mu * mu, 1e-18)
    return mu, math.sqrt(var)


def terminal_stud_ensemble(learning_rate=0.8, complexity_penalty=0.005,
                           forget=0.99, k=1):
    cands, depths = _candidates(k)
    n = len(cands)
    tleaf = crps_leaf(k=1, scale_alpha=0.03)

    def _skater(y, state):
        if state is None:
            state = {"sub": [None] * n, "qdist": [deque() for _ in range(n)],
                     "log_w": [0.0] * n, "leaf_state": None, "leaf_pred": None,
                     "pend": deque()}          # (mu_t, s_t) awaiting resolution
        all_dists = []
        for i, f in enumerate(cands):
            di, state["sub"][i] = f(y, state["sub"][i])
            all_dists.append(di)
        for i in range(n):
            q = state["qdist"][i]
            if q:
                lp = _clamp_lp(q.popleft().logpdf(y))
                state["log_w"][i] = (forget * state["log_w"][i]
                                     + learning_rate * lp - complexity_penalty * depths[i])
            q.append(all_dists[i][0])
        w = _weights(state["log_w"])
        mu, s = _mix_moments(all_dists, w)
        if state["pend"]:
            mu_prev, s_prev = state["pend"].popleft()
            z = (y - mu_prev) / s_prev
            ld, state["leaf_state"] = tleaf(z, state["leaf_state"])
            state["leaf_pred"] = ld[0]
        state["pend"].append((mu, s))
        if state["leaf_pred"] is not None:
            pred = state["leaf_pred"].affine(s, mu)
        else:
            pred = Dist.combine([d[0] for d in all_dists], w)
            if len(pred) > 20:
                pred = pred.prune(20)
        return [pred], state

    return _skater


def terminal_pit_ensemble(learning_rate=0.8, complexity_penalty=0.005,
                          forget=0.99, k=1, warm=100, window=500):
    cands, depths = _candidates(k)
    n = len(cands)

    def _skater(y, state):
        if state is None:
            state = {"sub": [None] * n, "qdist": [deque() for _ in range(n)],
                     "log_w": [0.0] * n, "pits": deque(maxlen=window),
                     "pend": deque()}          # mixture Dists awaiting resolution
        all_dists = []
        for i, f in enumerate(cands):
            di, state["sub"][i] = f(y, state["sub"][i])
            all_dists.append(di)
        for i in range(n):
            q = state["qdist"][i]
            if q:
                lp = _clamp_lp(q.popleft().logpdf(y))
                state["log_w"][i] = (forget * state["log_w"][i]
                                     + learning_rate * lp - complexity_penalty * depths[i])
            q.append(all_dists[i][0])
        w = _weights(state["log_w"])
        F = Dist.combine([d[0] for d in all_dists], w)
        if len(F) > 20:
            F = F.prune(20)
        if state["pend"]:
            state["pits"].append(state["pend"].popleft().cdf(y))
        state["pend"].append(F)
        if len(state["pits"]) >= warm:
            # Recalibrated CDF is h(F(x)) with h the empirical CDF of the PITs;
            # its tau-quantile is F^{-1}(u_tau) at u_tau = tau-quantile of PITs.
            u = np.quantile(np.asarray(state["pits"], float), TAUS)
            u = np.clip(u, 1e-4, 1 - 1e-4)
            vals = np.array([F.quantile(float(ui)) for ui in u])
            vals = np.maximum.accumulate(vals)
            import bench_core as bc
            pred = bc.grid_dist(TAUS, vals) or F
        else:
            pred = F
        return [pred], state

    return _skater


def laplace_stud():
    return parade(gpdtails(sticky(terminal_stud_ensemble(), k=1), k=1), k=1)


def laplace_pit():
    return parade(gpdtails(sticky(terminal_pit_ensemble(), k=1), k=1), k=1)
