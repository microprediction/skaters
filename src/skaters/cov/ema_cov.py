"""Exponentially weighted online covariance.

Recent observations count more. Adapts to non-stationarity.
"""

from __future__ import annotations
import math


def ema_cov(y: list[float], state: dict | None, alpha: float = 0.05) -> tuple[list[float], list[float], dict]:
    """Update exponentially weighted mean and covariance.

    Args:
        y: observation vector (length n)
        state: prior state (None on first call)
        alpha: smoothing factor in (0, 1). Smaller = longer memory.

    Returns:
        mean: current EMA mean vector
        cov: current EWM covariance matrix (flat, n*n)
        state: updated state
    """
    n = len(y)
    if state is None:
        state = {
            "mean": list(y),
            "cov": [0.0] * (n * n),
            "n": 1,
        }
        return list(y), [0.0] * (n * n), state

    mean = state["mean"]
    cov = state["cov"]
    state["n"] += 1

    delta = [y[i] - mean[i] for i in range(n)]
    for i in range(n):
        mean[i] += alpha * delta[i]
    for i in range(n):
        for j in range(n):
            cov[i * n + j] = (1 - alpha) * (cov[i * n + j] + alpha * delta[i] * delta[j])

    return list(mean), list(cov), state
