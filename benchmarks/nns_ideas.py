"""Experiments from the NNS idea inventory (skaters#113).

pm_leaf         Partial-moment terminal leaf: lower/upper partial second
                moments of the residual stream via two EWMAs (bias-corrected),
                fitted to a two-piece normal whose quantile grid becomes the
                predictive Dist. Two numbers of state buy a skewed predictive;
                the Gaussian leaf is the sigma_l == sigma_r special case.
                Use as laplace(leaf=pm_leaf).

phase_trend_anchor
                Per-phase Holt: each phase keeps its own level and per-visit
                trend; the anchor blends (level + trend) with the
                seasonal-naive. seasonal_anchor is the beta=0 special case.
                NNS.ARMA regresses the same-phase component series; this is
                the one-parameter version of that idea.
"""
from __future__ import annotations
import math

import numpy as np
from scipy.stats import norm

import bench_core as bc
from skaters.dist import Dist

_TAUS = np.linspace(0.02, 0.98, 41)


def pm_leaf(k: int = 1, scale_alpha: float = 0.03):
    """Two-piece-normal residual leaf from partial-moment EWMAs."""

    def _leaf(r: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {"lpm": 0.0, "upm": 0.0, "n": 0}
        a = scale_alpha
        state["lpm"] = (1 - a) * state["lpm"] + a * (r * r if r < 0 else 0.0)
        state["upm"] = (1 - a) * state["upm"] + a * (r * r if r >= 0 else 0.0)
        state["n"] += 1
        corr = 1.0 - (1.0 - a) ** state["n"]
        lpm = max(state["lpm"] / corr, 1e-18)
        upm = max(state["upm"] / corr, 1e-18)
        if state["n"] < 30:
            d = Dist.gaussian(0.0, max(math.sqrt(lpm + upm), 1e-8))
            return [d] * k, state
        # Two-piece normal matching E[r^2 1(r<0)] = LPM, E[r^2 1(r>=0)] = UPM:
        # sigma_l^3/(sigma_l+sigma_r) = LPM and symmetrically, so
        # sigma_l/sigma_r = (LPM/UPM)^(1/3), sigma_r^2 = UPM (1 + ratio).
        ratio = (lpm / upm) ** (1.0 / 3.0)
        sig_r = math.sqrt(upm * (1.0 + ratio))
        sig_l = ratio * sig_r
        p_l = sig_l / (sig_l + sig_r)
        qs = np.where(
            _TAUS < p_l,
            sig_l * norm.ppf(np.clip(_TAUS / (2 * p_l), 1e-9, 1 - 1e-9)),
            sig_r * norm.ppf(np.clip((_TAUS - p_l) / (2 * (1 - p_l)) + 0.5,
                                     1e-9, 1 - 1e-9)),
        )
        d = bc.grid_dist(_TAUS, qs) or Dist.gaussian(0.0, math.sqrt(lpm + upm))
        return [d] * k, state

    _leaf.__name__ = f"pm_leaf(k={k})"
    return _leaf


def phase_trend_anchor(period: int, alpha: float = 0.2, beta: float = 0.1,
                       weight: float = 0.5):
    """Residual from a hedged per-phase Holt anchor (level + per-visit trend)."""
    assert period >= 1 and 0 < alpha < 1 and 0 <= beta < 1

    def _anchor(lev, tr, snaive):
        return (weight * (lev + tr) + (1 - weight) * snaive) if lev is not None else snaive

    def forward(y, state):
        if state is None:
            return 0.0, {"lev": [None] * period, "tr": [0.0] * period,
                         "buffer": [y], "n": 1}
        buf = state["buffer"]
        p = state["n"] % period
        snaive = buf[-period] if len(buf) >= period else buf[-1]
        y_prime = y - _anchor(state["lev"][p], state["tr"][p], snaive)
        lev = state["lev"][p]
        if lev is None:
            state["lev"][p] = y
        else:
            new_lev = lev + state["tr"][p] + alpha * (y - lev - state["tr"][p])
            state["tr"][p] = (1 - beta) * state["tr"][p] + beta * (new_lev - lev)
            state["lev"][p] = new_lev
        buf.append(y)
        if len(buf) > 2 * period:
            buf.pop(0)
        state["n"] += 1
        return y_prime, state

    def inverse_k(dists, state):
        buf = state["buffer"]
        out = []
        for h in range(len(dists)):
            p = (state["n"] + h) % period
            idx = len(buf) - period + h
            snaive = buf[idx] if 0 <= idx < len(buf) else buf[-1]
            out.append(dists[h].shift(_anchor(state["lev"][p], state["tr"][p], snaive)))
        return out

    return forward, inverse_k
