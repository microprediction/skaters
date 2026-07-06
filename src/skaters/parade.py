"""The prediction parade: online calibration diagnostics in the state.

Each incoming observation is resolved against the predictions previously made
*for it* — the m-step-ahead predictive issued m steps ago, for m = 1..k. After
``dists, state = f(y, state)`` on a parade-wrapped skater:

    state["pit"][m-1]   the probability integral transform of y under the
                        m-step-ahead predictive issued m steps ago — roughly
                        Uniform(0, 1) when that predictive is calibrated;
    state["z"][m-1]     the same value pushed through the standard-normal
                        quantile — roughly N(0, 1) when calibrated, so |z|
                        reads directly as "how surprising was this point".

Entries are ``None`` until the corresponding prediction has matured (the first
m observations, for horizon m). The wrapper is pass-through for the forecasts
themselves: ``dists`` is exactly the base skater's output.

Named for the prediction parade of the ``timemachines`` package, where
forecasts marched in quarantine until they met their ground truth.
"""

from __future__ import annotations
import math
from collections import deque
from skaters.dist import Dist

_STD_NORMAL = Dist.gaussian(0.0, 1.0)
# Clamp the PIT away from {0, 1}: |z| is then bounded by the standard-normal
# quantile at 1e-12, about 7.03, and the bisection in Dist.quantile stays
# inside its +-8 sigma bracket. No input can produce an infinite z.
_EPS = 1e-12


def parade(base, k: int):
    """Wrap ``base`` (a skater emitting k horizons) with PIT/z bookkeeping."""

    def _skater(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {"base": None, "pending": deque(maxlen=k),
                     "pit": [None] * k, "z": [None] * k}
        pend = state["pending"]
        n = len(pend)
        pit = [None] * k
        z = [None] * k
        for m in range(1, k + 1):
            if m <= n:
                d = pend[n - m][m - 1]        # issued m steps ago, horizon m
                u = d.cdf(y)
                if not math.isfinite(u):      # degenerate predictive or bad y:
                    continue                  # leave this horizon's entry None
                u = min(max(u, _EPS), 1.0 - _EPS)
                pit[m - 1] = u
                z[m - 1] = _STD_NORMAL.quantile(u)
        dists, state["base"] = base(y, state["base"])
        pend.append(list(dists))
        state["pit"] = pit
        state["z"] = z
        return dists, state

    _skater.__name__ = f"parade({getattr(base, '__name__', '?')}, k={k})"
    return _skater
