"""The objective knob: model first (likelihood trunk), conform last (CRPS leaf)."""

import math
import random

import pytest

from skaters.api import laplace
from skaters.leaf import crps_leaf, scale_mixture_leaf
from skaters.dist import Dist


def _run_last(f, series):
    state, out = None, None
    for y in series:
        d, state = f(y, state)
        out = d[0]
    return out


def test_crps_leaf_is_a_valid_leaf():
    f = crps_leaf(1)
    out = _run_last(f, [random.gauss(0, 1) for _ in range(200)])
    assert isinstance(out, Dist) and out.std > 0 and math.isfinite(out.logpdf(0.0))


def test_crps_is_the_default_objective():
    # default laplace uses the CRPS leaf (15-component FINE basis), the
    # likelihood objective uses the 5-component scale mixture — so the two
    # differ in component count after the terminal leaf dominates.
    random.seed(0)
    series = [random.gauss(0, 1) for _ in range(300)]
    d_default = _run_last(laplace(1), series)
    d_like = _run_last(laplace(1, objective="likelihood"), series)
    assert len(d_default.components) != len(d_like.components)
    assert len(d_default.components) >= 15      # FINE basis


def test_objective_validation():
    with pytest.raises(ValueError):
        laplace(1, objective="coverage")
    with pytest.raises(ValueError):
        laplace(1, objective="nonsense")


def test_crps_objective_helps_on_heavy_tails():
    # Student-t(3): the CRPS-default should not be worse than likelihood here
    # (heavy tails are where conform-last pays).
    random.seed(3)
    def t3():
        g = random.gauss(0, 1)
        v = sum(random.gauss(0, 1) ** 2 for _ in range(3)) / 3
        return g / math.sqrt(v)
    series = [t3() for _ in range(800)]

    def mean_logpdf(f):
        state, pend, lp, n = None, None, 0.0, 0
        for i, y in enumerate(series):
            if pend is not None and i > 200:
                lp += pend[0].logpdf(y); n += 1
            d, state = f(y, state); pend = d
        return lp / n
    assert mean_logpdf(laplace(1)) >= mean_logpdf(laplace(1, objective="likelihood")) - 0.02
