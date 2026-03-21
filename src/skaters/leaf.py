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
