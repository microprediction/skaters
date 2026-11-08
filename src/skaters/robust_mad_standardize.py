"""Sliding median / MAD standardization, as a conjugate transform.

Forward emits against the window already in state, then appends the
observation:

    y' = (y - median) / sigma,    sigma = 1.4826 * MAD

``1.4826 * MAD`` is the normal-consistent scale. ``inverse_k`` applies that
same affine, read from the updated window, to every horizon. State is the
window dict for one stream; streams do not share it.

Until the window has ``min_periods`` points and a nonzero MAD, there is no
robust scale in the state. The emission then uses the same cold start as
:func:`skaters.transform.standardize`: the affine unit is the residual
itself, so the standardized value is ±1, and that unit is stored. A later
flat stretch holds the last informative unit instead of replacing it with a
tiny floor. Dividing a level shift by a hard floor feeds the downstream leaf
one enormous residual, and the leaf's variance never forgets it. The stored
unit is part of the affine map ``inverse_k`` applies; the standardized value
is not clipped.
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
    return 0.5 * ordered[mid - 1] + 0.5 * ordered[mid]


def _mad_sigma(values: list[float], min_periods: int, eps: float) -> float | None:
    """Normal-consistent MAD scale, or None while that scale is uninformative."""
    if len(values) < min_periods:
        return None
    median = _median(values)
    mad = _median([abs(value - median) for value in values])
    sigma = _MAD_TO_SIGMA * mad
    if not math.isfinite(sigma) or sigma < eps:
        return None
    return sigma


def robust_mad_standardize(window: int = 60, min_periods: int = 8, eps: float = 1e-8):
    """Robust standardization by a sliding median and MAD.

    Returns:
        ``(forward, inverse_k)`` for :func:`skaters.conjugate`.
    """
    if not isinstance(window, int) or window < 2:
        raise ValueError("window must be an integer of at least 2")
    if not isinstance(min_periods, int) or min_periods < 2 or min_periods > window:
        raise ValueError("min_periods must be an integer between 2 and window")
    if not (math.isfinite(eps) and eps > 0.0):
        raise ValueError("eps must be positive and finite")

    def _emit_scale(buf: list[float], held: float, y: float) -> float:
        sigma = _mad_sigma(buf, min_periods, eps)
        if sigma is not None:
            return sigma
        if held > eps:
            return held
        dev = abs(y - _median(buf)) if buf else 0.0
        return dev if dev > eps else eps

    def _hold_scale(buf: list[float], held: float, y: float, median: float) -> float:
        learned = _mad_sigma(buf, min_periods, eps)
        if learned is not None:
            return learned
        if held > eps:
            return held
        dev = abs(y - median)
        return dev if dev > eps else eps

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            buf, held = [], eps
        else:
            buf, held = list(state["buf"]), float(state.get("scale", eps))
        if not math.isfinite(y):
            return 0.0, {"buf": buf, "scale": held}
        if not buf:
            return 0.0, {"buf": [y], "scale": held}
        median = _median(buf)
        sigma = _emit_scale(buf, held, y)
        y_prime = (y - median) / sigma
        buf.append(y)
        if len(buf) > window:
            del buf[:-window]
        return y_prime, {"buf": buf, "scale": _hold_scale(buf, held, y, median)}

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        buf = [] if state is None else list(state["buf"])
        held = eps if state is None else float(state.get("scale", eps))
        if not buf:
            return [d.affine(held, 0.0) for d in dists]
        median = _median(buf)
        sigma = _mad_sigma(buf, min_periods, eps)
        if sigma is None:
            sigma = held if held > eps else eps
        return [d.affine(sigma, median) for d in dists]

    return forward, inverse_k
