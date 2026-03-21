"""Model-independent empirical prediction envelope.

Wraps any skater and tracks forecast errors at each horizon using
online statistics. Provides regularized std estimates that can be
used as confidence bands.

The envelope is the sole source of uncertainty — skaters just predict.
"""

from __future__ import annotations
import math
from collections import deque
from skaters.runstats import running_var_init, running_var_update, running_std_get


def envelope(skater, k: int = 1, decay: float | None = None):
    """Wrap a skater with an empirical error envelope.

    Args:
        skater: any skater callable (y, state) -> (list[float], state)
        k: forecast horizon (must match the skater's k)
        decay: if set, use exponentially weighted variance with this
               decay factor (0 < decay < 1, smaller = faster forgetting).
               If None, use Welford's (uniform weighting over all history).

    Returns:
        A callable: (y, state) -> (x_dict, state) where x_dict contains
        "mean" (point forecasts) and "std" (empirical error std per horizon).
    """

    def _enveloped(y: float, state: dict | None) -> tuple[dict, dict]:
        if state is None:
            state = {
                "inner": None,
                "queues": [deque() for _ in range(k)],
                "error_stats": [running_var_init() for _ in range(k)],
            }
            if decay is not None:
                state["ew_var"] = [{"mean": 0.0, "var": 0.0, "n": 0} for _ in range(k)]

        # Run the inner skater
        x, state["inner"] = skater(y, state["inner"])

        # Resolve pending predictions against this observation
        queues = state["queues"]
        error_stats = state["error_stats"]
        for h in range(k):
            if queues[h]:
                predicted = queues[h].popleft()
                error = y - predicted
                if decay is not None:
                    _ew_update(state["ew_var"][h], error, decay)
                else:
                    error_stats[h] = running_var_update(error_stats[h], error)

        # Enqueue new predictions
        for h in range(k):
            queues[h].append(x[h])

        # Compute std
        if decay is not None:
            std = [_ew_std(state["ew_var"][h]) for h in range(k)]
        else:
            std = [running_std_get(s) for s in error_stats]

        return {"mean": x, "std": std}, state

    _enveloped.__name__ = f"envelope({getattr(skater, '__name__', '?')})"
    return _enveloped


def _ew_update(ew: dict, x: float, decay: float) -> None:
    """Exponentially weighted online variance update (in-place)."""
    ew["n"] += 1
    if ew["n"] == 1:
        ew["mean"] = x
        ew["var"] = 0.0
        return
    diff = x - ew["mean"]
    ew["mean"] = decay * ew["mean"] + (1 - decay) * x
    ew["var"] = decay * (ew["var"] + (1 - decay) * diff * diff)


def _ew_std(ew: dict) -> float:
    """Get std from exponentially weighted state."""
    if ew["n"] < 2:
        return float("inf")
    return math.sqrt(ew["var"]) if ew["var"] > 0 else float("inf")
