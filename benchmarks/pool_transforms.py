"""Candidate transforms for laplace's pool that have not been tested yet.

Each is a (forward, inverse_k) pair in the skaters.transform protocol, used
only by the laplace(+...) arms in arm_adapters.py. All are one-step (h=1)
transforms: inverse_k raises for more than one horizon, because the arms run
at h=1 and a multi-step inverse would need its own derivation and synthetic
test (see the exact-synthetic-tests note).

The pool's candidates act as mean forecasters (their spread only sets their
weight), so every transform here changes the conditional mean.

- integrate:   changes -> running level, so a level model (ou_transform) can
               revert the level; the inverse maps the level predictive back
               to a change. Shift-invariant, so the unknown starting level
               does not matter.
- ma1:         MA(1) on changes with a fixed coefficient (overdifferencing,
               or the change-space form of level reversion).
- huber_ema:   EMA whose update clips the residual at c running absolute
               deviations, so one jump does not drag the level.
- setar1:      AR(1) with a separate coefficient for rises and falls,
               each fitted by exponentially forgetting least squares.
- phase_trend_anchor is re-exported from nns_ideas (#113).
"""
from __future__ import annotations

import math

from skaters.dist import Dist

from nns_ideas import phase_trend_anchor  # noqa: F401  (#113, re-exported)


def _one_step(dists: list[Dist]) -> Dist:
    if len(dists) != 1:
        raise NotImplementedError("pool_transforms are h=1 only")
    return dists[0]


def integrate():
    """y'_t = L_t = sum of y up to t (the inverse of difference).

    Inverse: the inner model predicts L_{t+1}; the change is L_{t+1} - L_t,
    so its Dist is the level Dist shifted by -L_t.
    """

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        level = 0.0 if state is None else state["level"]
        if math.isfinite(y):
            level += y
        return level, {"level": level}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        return [_one_step(dists).shift(-state["level"])]

    return forward, inverse_k


def ma1(theta: float):
    """x_t = e_t + theta e_{t-1}: forward emits e_t = x_t - theta e_{t-1};
    the one-step mean of x is theta e_t. Invertible for |theta| < 1."""
    assert -1.0 < theta < 1.0

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        e_prev = 0.0 if state is None else state["e"]
        e = y - theta * e_prev
        if not math.isfinite(e):
            e = 0.0
        return e, {"e": e}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        return [_one_step(dists).shift(theta * state["e"])]

    return forward, inverse_k


def huber_ema(alpha: float = 0.1, c: float = 2.0, beta: float = 0.05):
    """Residual from a level updated with a clipped residual:
    level += alpha * clip(r, -c s, c s), s an EWMA (rate beta) of |r|.
    Like ema_transform, the residual is taken against the prior level."""
    assert 0 < alpha < 1 and c > 0 and 0 < beta < 1

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None or not math.isfinite(y):
            y0 = y if math.isfinite(y) else (0.0 if state is None else state["level"])
            s = 0.0 if state is None else state["s"]
            return 0.0, {"level": y0, "s": s}
        r = y - state["level"]
        s = state["s"]
        b = c * s if s > 0.0 else abs(r)          # first residual passes unclipped
        level = state["level"] + alpha * max(-b, min(b, r))
        s = abs(r) if s == 0.0 else s + beta * (abs(r) - s)
        return r, {"level": level, "s": s}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        return [_one_step(dists).shift(state["level"])]

    return forward, inverse_k


def setar1(lam: float = 0.99, ridge: float = 1.0, cap: float = 0.95):
    """Two-regime AR(1) on changes, the regime set by the sign of the last
    change: x_t = phi_r x_{t-1} + e_t with r = (x_{t-1} >= 0). Each phi_r is
    exponentially forgetting least squares, sum(x x_prev) / (sum(x_prev^2) +
    ridge), clipped to [-cap, cap]."""
    assert 0 < lam <= 1 and ridge > 0 and 0 < cap < 1

    def _phi(st: dict, r: int) -> float:
        p = st["sxy"][r] / (st["sxx"][r] + ridge)
        return max(-cap, min(cap, p))

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            st = {"sxy": [0.0, 0.0], "sxx": [0.0, 0.0], "x": y if math.isfinite(y) else 0.0}
            return 0.0, st
        if not math.isfinite(y):
            return 0.0, state
        xp = state["x"]
        r = 1 if xp >= 0.0 else 0
        resid = y - _phi(state, r) * xp
        sxy, sxx = list(state["sxy"]), list(state["sxx"])
        sxy[r] = lam * sxy[r] + y * xp
        sxx[r] = lam * sxx[r] + xp * xp
        return resid, {"sxy": sxy, "sxx": sxx, "x": y}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        xp = state["x"]
        return [_one_step(dists).shift(_phi(state, 1 if xp >= 0.0 else 0) * xp)]

    return forward, inverse_k
