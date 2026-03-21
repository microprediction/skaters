"""Lightweight online running statistics (pure Python, no dependencies).

Welford's algorithm for mean/variance, plus exponentially weighted variants.
"""

from __future__ import annotations
import math


def running_var_init() -> dict:
    """Initialize state for Welford's online variance."""
    return {"n": 0, "mean": 0.0, "m2": 0.0}


def running_var_update(state: dict, x: float) -> dict:
    """Update running mean/variance with a new observation (Welford)."""
    n = state["n"] + 1
    delta = x - state["mean"]
    mean = state["mean"] + delta / n
    delta2 = x - mean
    m2 = state["m2"] + delta * delta2
    return {"n": n, "mean": mean, "m2": m2}


def running_var_get(state: dict) -> tuple[float, float]:
    """Return (mean, variance) from running stats state."""
    if state["n"] < 2:
        return state["mean"], float("inf")
    return state["mean"], state["m2"] / (state["n"] - 1)


def running_std_get(state: dict) -> float:
    """Return standard deviation from running stats state."""
    _, var = running_var_get(state)
    return math.sqrt(var) if math.isfinite(var) else float("inf")


def running_mse_get(state: dict) -> float:
    """Return mean squared error (second moment) from running stats of errors.

    MSE = bias² + variance, so it penalizes both systematic and random error.
    """
    if state["n"] < 1:
        return float("inf")
    mean, var = running_var_get(state)
    if not math.isfinite(var):
        return float("inf")
    return mean * mean + var
