"""Regression tests: no leaf should crash on pathological input.

The CRPS leaf's exponentiated-gradient update used to overflow exp() to inf on
some streams, normalizing to nan mixture weights and tripping the
``Dist`` weight-sum assertion. Fed a short periodic series through the full
``laplace`` pipeline, the unfixed code crashed around step ~74k. These tests lock
in the stabilized update and confirm the other leaves stay safe too.
"""

import math

import pytest

from skaters import laplace
from skaters.leaf import crps_leaf, scale_mixture_leaf, garch_leaf

# The exact periodic series that crashed the unfixed pipeline.
PERIODIC = [0.01, -0.02, 0.0, 0.03, -0.01, 0.02, -0.03, 0.015,
            0.005, -0.025, 0.008, -0.012, 0.02, -0.018, 0.004]


def _assert_valid(d):
    if hasattr(d, "body"):          # GPD tail splice: check it, then the body
        assert math.isfinite(d.logpdf(d.body.mean))
        assert 0.0 <= d.cdf(d.body.mean) <= 1.0
        d = d.body
    wsum = sum(w for w, _, _ in d.components)
    assert abs(wsum - 1.0) < 1e-9
    assert math.isfinite(d.mean) and math.isfinite(d.std) and d.std >= 0.0


def test_laplace_periodic_stream_stays_finite():
    """The full pipeline emits a finite forecast throughout a long run.

    Two bugs used to bite this stream far into a run: the CRPS-leaf exp() overflow
    (AssertionError, ~74k) and RLS covariance windup in the AR transforms (P
    inflating by 1/lam each step until it overflowed to inf around ~74k, giving
    nan coefficients). Both are fixed; the forecast now stays well-formed.
    """
    f = laplace(1)
    state = None
    for i in range(120_000):
        dists, state = f(PERIODIC[i % len(PERIODIC)], state)
        if i % 20_000 == 0:
            _assert_valid(dists[0])
    _assert_valid(dists[0])


@pytest.mark.parametrize("make", [crps_leaf, scale_mixture_leaf, garch_leaf])
def test_leaf_periodic_stream_does_not_crash(make):
    f = make()
    state = None
    for i in range(20_000):
        dists, state = f(PERIODIC[i % len(PERIODIC)], state)
    _assert_valid(dists[0])


@pytest.mark.parametrize("make", [crps_leaf, scale_mixture_leaf, garch_leaf])
def test_leaf_extreme_values_do_not_crash(make):
    f = make()
    state = None
    for y in [0.0, 1e-12, 1e3, -1e3, 1e6, -1e6, 1e9, -1e-9, 1e12]:
        dists, state = f(y, state)
        _assert_valid(dists[0])
