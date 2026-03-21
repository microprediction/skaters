"""Exponential moving average skater.

Pure online, O(1) per observation. Returns only point forecasts.
"""

from __future__ import annotations


def ema(alpha: float = 0.05, k: int = 1):
    """Create an EMA skater.

    Args:
        alpha: smoothing factor in (0,1). Small = slow, large = fast.
        k: forecast horizon (number of steps ahead).

    Returns:
        A skater callable: (y, state) -> (list[float], state)
    """
    assert 0 < alpha < 1

    def _skater(y: float, state: dict | None) -> tuple[list[float], dict]:
        if state is None:
            return [y] * k, {"level": y}
        level = state["level"] + alpha * (y - state["level"])
        return [level] * k, {"level": level}

    _skater.__name__ = f"ema(alpha={alpha}, k={k})"
    return _skater
