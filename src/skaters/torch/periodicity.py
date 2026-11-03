"""Online periodicity detection on tensors: the twin of
:mod:`skaters.periodicity` (running EMA autocorrelation at candidate lags).

Same arithmetic order as the reference; the running mean, variance and
per-lag cross terms are 0-d float64 tensors so the detector's scores can
sit on a graph. Ranking (sort by |acf| descending, stable) is decided on
float values, as ordering is not differentiable anyway; the scores returned
are tensors.
"""

from __future__ import annotations

import torch

from skaters.periodicity import DEFAULT_LAGS
from skaters.torch.dist import DTYPE, _t


def _zero():
    return torch.zeros((), dtype=DTYPE)


def period_detector(lags=None, alpha: float = 0.01, min_observations: int = 50):
    """``(y, state) -> (scores, state)``; scores are ``[(lag, acf_tensor), ...]``
    sorted by ``|acf|`` descending, empty before ``min_observations``."""
    if lags is None:
        lags = list(DEFAULT_LAGS)
    max_lag = max(lags)

    def _detect(y, state=None):
        y = _t(y)
        if state is None:
            state = {
                "buffer": [],
                "n": 0,
                "mean": _zero(),
                "var": _zero(),
                "cross": {L: _zero() for L in lags},
            }
        buf = state["buffer"]
        buf.append(y)
        state["n"] += 1

        diff = y - state["mean"]
        state["mean"] = state["mean"] + alpha * diff
        state["var"] = (1 - alpha) * (state["var"] + alpha * diff * diff)
        mu = state["mean"]
        var = state["var"]

        for L in lags:
            if len(buf) > L:
                y_lagged = buf[-(L + 1)]
                cross = (y - mu) * (y_lagged - mu)
                state["cross"][L] = (1 - alpha) * state["cross"][L] + alpha * cross

        if len(buf) > max_lag + 1:
            buf.pop(0)

        if state["n"] < min_observations or bool(var < 1e-12):
            return [], state

        scores = []
        for L in lags:
            if state["n"] > L:
                acf = state["cross"][L] / var if bool(var > 0) else _zero()
                scores.append((L, acf))
        scores.sort(key=lambda x: abs(float(x[1].detach())), reverse=True)
        return scores, state

    return _detect


def top_periods(scores, threshold: float = 0.3, max_periods: int = 3) -> list[int]:
    """Lags among the top ``max_periods`` whose ``|acf|`` reaches ``threshold``."""
    return [lag for lag, acf in scores[:max_periods] if bool(torch.abs(_t(acf)) >= threshold)]
