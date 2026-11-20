"""Ordinary candidate-chain plumbing for the canonical benchmark runner."""

from skaters.conjugate import conjugate
from skaters.leaf import leaf

from .transform import orbit_transform


def orbit_extras(k):
    """One new depth-one candidate, using the existing residual leaf."""
    return [(conjugate(leaf(k=k), orbit_transform(), k=k), 1)]


def orbit_dists(ch, h=1, pooled=True):
    from arm_adapters import laplace_extra_periods_dists
    from foundation_study import TEST
    from skaters.parade import parade

    if pooled:
        return laplace_extra_periods_dists(ch, h, periods=(), extra=orbit_extras)
    f = parade(orbit_extras(h)[0][0], k=h)
    state = None
    queue = []
    out = []
    start = len(ch) - TEST
    for i, y in enumerate(ch):
        if len(queue) >= h and i >= start:
            out.append(queue[-h][h - 1])
        dists, state = f(y, state)
        queue.append(dists)
        if len(queue) > h:
            queue.pop(0)
    return out
