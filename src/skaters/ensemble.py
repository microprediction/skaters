"""Precision-weighted ensemble of skaters.

Combines multiple online skaters by weighting inversely proportional
to their empirical forecast MSE. Each sub-model's errors are tracked
internally via parade-style queues (using the Dist mean as the point
prediction for error tracking).

The ensemble combines distributional predictions using Dist.combine(),
which produces an exact weighted Gaussian mixture — no information is
lost during combination.
"""

from __future__ import annotations
import math
from collections import deque
from skaters.dist import Dist
from skaters.runstats import running_var_init, running_var_update, running_mse_get


def precision_weighted_ensemble(skaters: list, k: int = 1, floor: float = 1e-6):
    """Create a precision-weighted ensemble skater.

    Args:
        skaters: list of skater callables
        k: forecast horizon
        floor: minimum precision to prevent zero-weight

    Returns:
        A skater callable: (y, state) -> (list[Dist], state)
    """
    n = len(skaters)
    assert n > 0

    def _skater(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {
                "sub": [None] * n,
                "queues": [[deque() for _ in range(k)] for _ in range(n)],
                "stats": [[running_var_init() for _ in range(k)] for _ in range(n)],
            }

        # Run all sub-models and collect distributional predictions
        all_dists = []
        for i, f in enumerate(skaters):
            dists_i, state["sub"][i] = f(y, state["sub"][i])
            all_dists.append(dists_i)

        # Resolve pending predictions (using Dist mean) and update error stats.
        # Horizon h (0-based) is (h+1)-step-ahead, so the mean issued h+1 steps
        # ago is the one that targeted the current y: buffer h+1 predictions,
        # then resolve. (At h=0 this is the ordinary one-step lag.)
        for i in range(n):
            for h in range(k):
                q = state["queues"][i][h]
                q.append(all_dists[i][h].mean)
                if len(q) > h + 1:
                    pred_mean = q.popleft()
                    error = y - pred_mean
                    state["stats"][i][h] = running_var_update(state["stats"][i][h], error)

        # Compute precision weights from MSE, then combine Dists per horizon
        combined = []
        for h in range(k):
            weights = []
            for i in range(n):
                mse = running_mse_get(state["stats"][i][h])
                if math.isfinite(mse) and mse > 0:
                    w = 1.0 / mse
                else:
                    w = floor
                weights.append(max(w, floor))

            # Combine distributional predictions at this horizon
            horizon_dists = [all_dists[i][h] for i in range(n)]
            combined.append(Dist.combine(horizon_dists, weights))

        return combined, state

    _skater.__name__ = f"precision_weighted_ensemble(n={n}, k={k})"
    return _skater
