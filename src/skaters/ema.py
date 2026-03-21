"""Exponential moving average skater.

EMA is implemented as conjugation of a leaf (residual distribution
estimator) with the EMA transform (subtracts running level).

Under the hood:  ema(alpha, k) = conjugate(leaf(k), ema_transform(alpha))

This means every EMA skater returns full distributional predictions:
the mean is the EMA level, and the std is the empirical residual std.
"""

from __future__ import annotations
from skaters.leaf import leaf
from skaters.transform import ema_transform
from skaters.conjugate import conjugate


def ema(alpha: float = 0.05, k: int = 1):
    """Create an EMA skater.

    Args:
        alpha: smoothing factor in (0,1). Small = slow, large = fast.
        k: forecast horizon (number of steps ahead).

    Returns:
        A skater callable: (y, state) -> (list[Dist], state)
    """
    f = conjugate(leaf(k=k), ema_transform(alpha), k=k)
    f.__name__ = f"ema(alpha={alpha}, k={k})"
    return f
