"""Adapters for the canonical runner in benchmarks/run_arm.py."""

from collections import deque

from skaters import laplace, scale_mixture_leaf

from .reference import horizon_conjugate
from .seasonal import seasonal_reference


def seasonal_dists(ch, h, *, alpha, use_laplace=False):
    """Return issued h-step predictives for the canonical final TEST targets."""
    from foundation_study import TEST

    inner = laplace if use_laplace else scale_mixture_leaf
    model = horizon_conjugate(seasonal_reference(period=24, k=h, alpha=alpha), inner, k=h)
    state = None
    pending = deque(maxlen=h)
    out = []
    start = len(ch) - TEST
    for t, y in enumerate(ch):
        if len(pending) == h and t >= start:
            out.append(pending[0][h - 1])
        forecasts, state = model(float(y), state)
        pending.append(forecasts)
    return out
