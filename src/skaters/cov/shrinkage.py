"""Ledoit-Wolf shrinkage toward the diagonal.

Shrinks a covariance matrix toward its own diagonal, which reduces
estimation error for high-dimensional or short-sample settings while
guaranteeing positive (semi)definiteness -- C and diag(C) are both PSD,
and PSD matrices are convex, so (1-rho)*C + rho*diag(C) is PSD for any
rho in [0, 1] whenever C is.
"""

from __future__ import annotations
from skaters.cov.ema_cov import ema_cov


def ledoit_wolf_cov(y: list[float], state: dict | None,
                    alpha: float = 0.05,
                    shrinkage: float = 0.5) -> tuple[list[float], list[float], dict]:
    """Online Ledoit-Wolf shrinkage estimator.

    Delegates the mean/covariance update to `ema_cov` -- a genuine rank-one
    EMA update, PSD by construction -- and shrinks THAT coherent covariance
    toward its diagonal. An earlier version instead updated each pairwise
    correlation independently and clamped it to [-1, 1] on its own; pairwise-
    valid correlations do not imply the resulting MATRIX is PSD (three
    individually-valid correlations can be jointly infeasible), and shrinking
    an already-indefinite matrix by an arbitrary positive amount does not
    necessarily repair it (skaters#224).

    Args:
        y: observation vector (length n)
        state: prior state
        alpha: EMA smoothing for the inner covariance (see `ema_cov`)
        shrinkage: blend toward the diagonal in (0, 1).
            0 = pure empirical covariance. 1 = diagonal (independence).

    Returns:
        mean, cov (shrunk), state
    """
    n = len(y)
    inner_state = state["inner"] if state is not None else None
    mean, cov, inner_state = ema_cov(y, inner_state, alpha)
    state = {"inner": inner_state}

    shrunk_cov = [0.0] * (n * n)
    for i in range(n):
        for j in range(n):
            shrunk_cov[i * n + j] = (
                cov[i * n + j] if i == j else (1.0 - shrinkage) * cov[i * n + j]
            )

    return mean, shrunk_cov, state
