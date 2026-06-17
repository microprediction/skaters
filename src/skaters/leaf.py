"""Residual distribution estimator: the leaf of every prediction tree.

The leaf sits at the bottom of a chain of transforms. It receives
(approximately) stationary residuals and estimates their distribution
online. It returns a Dist for each horizon.

This is the only node that "creates" distributional predictions.
Everything above it (transforms, conjugation, ensemble) just
propagates and combines Dists.
"""

from __future__ import annotations
import math
from skaters.dist import Dist
from skaters.runstats import running_var_init, running_var_update, running_var_get


def leaf(k: int = 1):
    """Centered Gaussian residual model.

    Assumes the input is approximately mean-zero residuals (after
    transforms have removed structure). Estimates variance online
    via Welford's algorithm.

    Returns Dist.gaussian(0, sigma) for each horizon. The zero mean
    reflects the assumption that transforms have removed the signal;
    the sigma reflects how much noise is left.
    """

    def _leaf(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {"var": running_var_init()}

        state["var"] = running_var_update(state["var"], y)
        _, var = running_var_get(state["var"])

        if math.isfinite(var) and var > 0:
            std = math.sqrt(var)
        else:
            # Bootstrap: use |y| as a rough scale estimate until we have data
            std = max(abs(y), 1e-8)

        d = Dist.gaussian(0.0, std)
        return [d] * k, state

    _leaf.__name__ = f"leaf(k={k})"
    return _leaf


def heavy_leaf(k: int = 1, excess_kurtosis: float = 6.0):
    """Heavy-tailed residual model: a variance-matched scale mixture.

    Like :func:`leaf`, but emits a two-component scale mixture
    (narrow core + 3x-wider tail) instead of a single Gaussian, so it can
    represent excess kurtosis. The variance is still estimated online via
    Welford and is matched exactly; only the *shape* is heavier.

    A Gaussian leaf systematically under-covers the tails and over-covers
    the centre of heavy-tailed residuals (e.g. financial returns). This
    leaf fixes that. It is added to the candidate pool alongside the
    Gaussian leaf, so the Bayesian ensemble picks whichever fits — heavy
    on fat-tailed data, Gaussian on light-tailed data.

    Args:
        k: forecast horizon.
        excess_kurtosis: target excess kurtosis (Gaussian = 0). With the
            3x tail, the mixing weight is ``excess_kurtosis / 192`` and the
            result approximates a Student-t (≈ t_5 at 6, ≈ t_8 at 3).
    """
    C = 3.0  # tail component is C times wider than the core
    p = min(max(excess_kurtosis / 192.0, 0.0), 0.45)
    # Match variance V: V = sigma1^2 * (1 + (C^2 - 1) p)  =>  sigma1^2 = V * adj
    var_adj = 1.0 / (1.0 + (C * C - 1.0) * p)

    def _leaf(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {"var": running_var_init()}

        state["var"] = running_var_update(state["var"], y)
        _, var = running_var_get(state["var"])

        if math.isfinite(var) and var > 0:
            v = var
        else:
            v = max(abs(y), 1e-8) ** 2

        if p <= 0.0:
            d = Dist.gaussian(0.0, math.sqrt(v))
        else:
            sigma1 = math.sqrt(v * var_adj)
            d = Dist([(1.0 - p, 0.0, sigma1), (p, 0.0, C * sigma1)])
        return [d] * k, state

    _leaf.__name__ = f"heavy_leaf(k={k},ek={excess_kurtosis})"
    return _leaf
