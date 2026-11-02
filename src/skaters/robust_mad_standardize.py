"""Sliding median / MAD standardization, as a conjugate transform.

Forward emits against the window already in state, then appends the
observation:

    y' = (y - median) / sigma,    sigma = 1.4826 * MAD

``1.4826 * MAD`` is the normal-consistent scale. ``inverse_k`` applies that
same affine, read from the updated window, to every horizon. State is the
window dict for one stream; streams do not share it.

Until ``min_periods`` observations are in the window, or when MAD is 0, the
scale used for division is floored. The location is always the exact window
median, so after a flat stretch a new level occupies the window in
``window`` steps. The median step does not shrink with the MAD.
"""

from __future__ import annotations

import math

from skaters.dist import Dist

# Consistency factor: 1.4826 * MAD estimates sigma for a normal sample.
_MAD_TO_SIGMA = 1.4826


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _sigma(values: list[float], median: float, min_periods: int, eps: float) -> float | None:
    """Normal-consistent MAD scale, or None when the window is still short."""
    if len(values) < min_periods:
        return None
    mad = _median([abs(value - median) for value in values])
    sigma = _MAD_TO_SIGMA * mad
    if sigma < eps:
        return eps
    return sigma


def robust_mad_standardize(window: int = 60, min_periods: int = 8, eps: float = 1e-8):
    """Robust standardization by a sliding median and MAD.

    Returns:
        ``(forward, inverse_k)`` for :func:`skaters.conjugate`.
    """
    if window < 2:
        raise ValueError("window must be at least 2")
    if min_periods < 2 or min_periods > window:
        raise ValueError("min_periods must lie between 2 and window")
    if eps <= 0.0:
        raise ValueError("eps must be positive")

    def _location_scale(buf: list[float]) -> tuple[float, float]:
        if not buf:
            return 0.0, eps
        median = _median(buf)
        sigma = _sigma(buf, median, min_periods, eps)
        if sigma is None:
            return median, eps
        return median, sigma

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        buf = [] if state is None else list(state["buf"])
        if not math.isfinite(y):
            return 0.0, {"buf": buf}
        if not buf:
            return 0.0, {"buf": [y]}
        median = _median(buf)
        sigma = _sigma(buf, median, min_periods, eps)
        if sigma is None:
            dev = abs(y - median)
            sigma = dev if dev > eps else eps
        y_prime = (y - median) / sigma
        buf.append(y)
        if len(buf) > window:
            del buf[:-window]
        return y_prime, {"buf": buf}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        median, sigma = _location_scale([] if state is None else state["buf"])
        return [d.affine(sigma, median) for d in dists]

    return forward, inverse_k
