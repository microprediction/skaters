"""Estimate a periodic reference from observed values of each phase."""

from __future__ import annotations

import math

from skaters.dist import Dist
from skaters.parade import _missing, _NO_INFO_STD


def seasonal_reference(period: int, k: int, *, alpha: float = 1.0, scale: float = 1.0):
    """Issue seasonal locations at any lead, including several cycles ahead.

    alpha=1 uses the last observed value of the target phase. A smaller alpha
    averages observations of that phase with an EWMA. Every forecast uses the
    current phase estimate for its target date. Unobserved phases use the most
    recent finite value, or zero before any observation.

    Scale sets the residual's units. It stays fixed across forecast leads.
    The horizon_conjugate inner skater estimates the residual uncertainty.
    During its warmup, the reference's Gaussian is the fallback predictive.
    """
    if not isinstance(period, int) or isinstance(period, bool) or period < 1:
        raise ValueError("period must be a positive integer")
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError("k must be a positive integer")
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be in (0, 1]")
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("scale must be positive and finite")

    def step(y: float, state: dict | None = None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {"n": 0, "levels": [None] * period, "last": None}
        n = state["n"]
        if not _missing(y):
            phase = n % period
            previous = state["levels"][phase]
            state["levels"][phase] = y if previous is None else (1.0 - alpha) * previous + alpha * y
            state["last"] = y
        state["n"] = n + 1

        last = state["last"]
        std = scale if last is not None else _NO_INFO_STD
        fallback = last if last is not None else 0.0
        phase_forecasts = [Dist.gaussian(fallback if level is None else level, std)
                           for level in state["levels"]]
        return [phase_forecasts[(n + h) % period] for h in range(1, k + 1)], state

    step.__name__ = f"seasonal_reference(period={period}, k={k}, alpha={alpha})"
    return step
