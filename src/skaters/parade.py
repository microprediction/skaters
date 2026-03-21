"""Parade: track forecast errors at each horizon incrementally.

A "parade" maintains k queues of pending predictions. When a new
observation arrives, it resolves the oldest prediction at each horizon,
computes the error, and updates running statistics.
"""

from __future__ import annotations
from collections import deque
from skaters.runstats import running_var_init, running_var_update, running_std_get


def parade_init(k: int) -> dict:
    """Initialize parade state for k horizons."""
    return {
        "k": k,
        "queues": [deque() for _ in range(k)],
        "error_stats": [running_var_init() for _ in range(k)],
    }


def parade_update(state: dict, x: list[float], y: float) -> dict:
    """Record new predictions x[0..k-1] and resolve against observation y.

    Args:
        state: parade state
        x: predictions for horizons 1..k
        y: the observation that just arrived

    Returns:
        updated state (std available via parade_std)
    """
    k = state["k"]
    queues = state["queues"]
    error_stats = state["error_stats"]

    # Resolve: the observation y was predicted h steps ago by queue[h]
    for h in range(k):
        if queues[h]:
            predicted = queues[h].popleft()
            error = y - predicted
            error_stats[h] = running_var_update(error_stats[h], error)

    # Enqueue new predictions
    for h in range(k):
        queues[h].append(x[h])

    return state


def parade_std(state: dict) -> list[float]:
    """Return current std estimate at each horizon."""
    return [running_std_get(s) for s in state["error_stats"]]
