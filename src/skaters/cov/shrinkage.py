"""Ledoit-Wolf shrinkage toward identity.

Shrinks the sample correlation toward the identity matrix,
which guarantees positive definiteness and reduces estimation
error for high-dimensional or short-sample settings.
"""

from __future__ import annotations
import math


def ledoit_wolf_cov(y: list[float], state: dict | None,
                    alpha: float = 0.05,
                    shrinkage: float = 0.5) -> tuple[list[float], list[float], dict]:
    """Online Ledoit-Wolf shrinkage estimator.

    Computes EMA covariance, extracts correlations, shrinks toward
    the identity, then reconstitutes the covariance.

    Args:
        y: observation vector (length n)
        state: prior state
        alpha: EMA smoothing for mean and variance
        shrinkage: blend toward identity in (0, 1).
            0 = pure empirical. 1 = pure identity.

    Returns:
        mean, cov (shrunk), state
    """
    n = len(y)
    if state is None:
        state = {
            "mean": list(y),
            "var": [0.0] * n,
            "corr": [1.0 if i == j else 0.0 for i in range(n) for j in range(n)],
            "n": 1,
        }
        return list(y), [0.0] * (n * n), state

    mean = state["mean"]
    var = state["var"]
    corr = state["corr"]
    state["n"] += 1

    # Update mean
    delta = [y[i] - mean[i] for i in range(n)]
    for i in range(n):
        mean[i] += alpha * delta[i]

    # Update variances
    delta2 = [y[i] - mean[i] for i in range(n)]
    for i in range(n):
        var[i] = (1 - alpha) * var[i] + alpha * delta[i] * delta2[i]

    # Update correlations (work in standardized space for stability)
    for i in range(n):
        si = math.sqrt(var[i]) if var[i] > 1e-16 else 1e-8
        for j in range(i + 1, n):
            sj = math.sqrt(var[j]) if var[j] > 1e-16 else 1e-8
            z_cross = (delta[i] / si) * (delta[j] / sj)
            idx = i * n + j
            corr[idx] = (1 - alpha) * corr[idx] + alpha * z_cross
            # Clamp to [-1, 1] for stability
            corr[idx] = max(-1.0, min(1.0, corr[idx]))
            corr[j * n + i] = corr[idx]

    # Shrink correlation toward identity
    shrunk_cov = [0.0] * (n * n)
    for i in range(n):
        si = math.sqrt(var[i]) if var[i] > 1e-16 else 1e-8
        for j in range(n):
            sj = math.sqrt(var[j]) if var[j] > 1e-16 else 1e-8
            if i == j:
                shrunk_cov[i * n + j] = var[i]
            else:
                r = (1 - shrinkage) * corr[i * n + j]
                shrunk_cov[i * n + j] = r * si * sj

    return list(mean), shrunk_cov, state
