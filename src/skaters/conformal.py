"""Online conformal recalibration of a distributional skater.

A skater's predictive distribution can be the right *location* and *scale*
yet the wrong *shape* — a Gaussian leaf under-covers the tails and
over-covers the centre of heavy-tailed residuals, and Bayesian model
averaging washes kurtosis out. Conformal recalibration fixes this from the
outside: it replaces the predictive shape with the empirical distribution
of recent standardized residuals.

This is split conformal prediction on a rolling window, run online:

    z_t = (y_t - mu_t) / sigma_t            standardized residual
    F_calibrated(.) = mu + sigma * Z_emp    Z_emp = recent {z}

The base's mu and sigma still carry the mean forecast and the (possibly
heteroskedastic) scale; conformal supplies the shape non-parametrically, so
heavy tails, skew, and miscalibration are corrected and the predictive
intervals attain approximately their nominal coverage. Pure Python; the
result is still a Dist (a small Gaussian mixture at the empirical
quantiles), so it composes with everything else.
"""

from __future__ import annotations
import math
from collections import deque
from skaters.dist import Dist


def conformal(base, k: int = 1, window: int = 250, min_obs: int = 30,
              n_points: int = 40, bandwidth: float = 1.0):
    """Wrap a skater so its intervals are conformally calibrated online.

    Args:
        base: any skater callable (y, state) -> (list[Dist], state).
        k: forecast horizon (must match base).
        window: rolling calibration window of standardized residuals.
            Smaller = adapts faster to non-stationarity; larger = smoother.
        min_obs: pass the base prediction through unchanged until this many
            residuals have accumulated.
        n_points: number of empirical-quantile components in the calibrated
            Dist (a KDE-style Gaussian mixture).

    Returns:
        A skater callable producing calibrated list[Dist].
    """

    def _skater(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {"base": None, "z": deque(maxlen=window), "pending": None}

        # Resolve the previous one-step prediction into a standardized residual.
        if state["pending"] is not None:
            mu_prev, sigma_prev = state["pending"]
            if sigma_prev > 0:
                state["z"].append((y - mu_prev) / sigma_prev)

        dists, state["base"] = base(y, state["base"])

        d1 = dists[0]
        state["pending"] = (d1.mean, d1.std)

        z = list(state["z"])
        if len(z) < min_obs:
            return dists, state  # warm up on the base distribution

        # Bandwidth (Silverman) for smoothing the empirical residual law.
        n = len(z)
        zmean = sum(z) / n
        zvar = sum((v - zmean) ** 2 for v in z) / n
        zstd = math.sqrt(zvar) if zvar > 0 else 1.0
        h = bandwidth * 0.9 * zstd * n ** (-0.2)

        zs = sorted(z)
        out = []
        for d in dists:
            mu = d.mean
            sigma = d.std
            if sigma <= 0:
                out.append(d)
                continue
            comps = []
            for j in range(n_points):
                q = (j + 0.5) / n_points
                zq = zs[min(int(q * n), n - 1)]
                comps.append((1.0 / n_points, mu + sigma * zq, sigma * h))
            out.append(Dist(comps))
        return out, state

    _skater.__name__ = f"conformal({getattr(base, '__name__', '?')})"
    return _skater
