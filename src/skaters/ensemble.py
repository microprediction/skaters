"""Precision-weighted ensemble of skaters.

Combines multiple online skaters by weighting inversely proportional
to their empirical forecast variance. Each sub-model's errors are
tracked internally via parade-style queues.

The ensemble itself is a skater — it returns list[float] predictions.
Wrap it with an envelope if you also want uncertainty bands.
"""

from __future__ import annotations
import math
from collections import deque
from skaters.runstats import running_var_init, running_var_update, running_mse_get


def precision_weighted_ensemble(skaters: list, k: int = 1, floor: float = 1e-6):
    """Create a precision-weighted ensemble skater.

    Args:
        skaters: list of skater callables
        k: forecast horizon
        floor: minimum precision to prevent zero-weight

    Returns:
        A skater callable: (y, state) -> (list[float], state)
    """
    n = len(skaters)
    assert n > 0

    def _skater(y: float, state: dict | None) -> tuple[list[float], dict]:
        if state is None:
            state = {
                "sub": [None] * n,
                "queues": [[deque() for _ in range(k)] for _ in range(n)],
                "stats": [[running_var_init() for _ in range(k)] for _ in range(n)],
            }

        # Run all sub-models and collect predictions
        preds = []
        for i, f in enumerate(skaters):
            x_i, state["sub"][i] = f(y, state["sub"][i])
            preds.append(x_i)

        # Resolve pending predictions and update error stats
        for i in range(n):
            for h in range(k):
                q = state["queues"][i][h]
                if q:
                    error = y - q.popleft()
                    state["stats"][i][h] = running_var_update(state["stats"][i][h], error)
                state["queues"][i][h].append(preds[i][h])

        # Precision-weighted combination per horizon (weight by 1/MSE)
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

            w_total = sum(weights)
            combined.append(
                sum(w * preds[i][h] for i, w in enumerate(weights)) / w_total
            )

        return combined, state

    _skater.__name__ = f"precision_weighted_ensemble(n={n}, k={k})"
    return _skater
