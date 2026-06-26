"""Edge-case / robustness regression tests.

Every prediction must be a *valid* Dist: finite mean, std strictly positive and
finite, monotone quantiles. These guard the numerical fixes for catastrophic
cancellation in the variance, pruning degeneracies, and transform overflow.
"""

import math

import pytest

from skaters.dist import Dist
from skaters.transform import yeo_johnson
from skaters.api import laplace

POLICIES = [laplace]

DEGENERATE_SERIES = {
    "constant": [3.0] * 40,
    "all_zero": [0.0] * 40,
    "single_obs": [5.0],
    "huge_alternating": [1e12, -1e12] * 20,
    "tiny": [1e-12 * i for i in range(40)],
    "all_negative": [-(i + 1.0) for i in range(40)],
    "monotonic": [float(i) for i in range(40)],
    "alternating": [1.0 if i % 2 else -1.0 for i in range(40)],
    "step": [0.0] * 20 + [100.0] * 20,
}


def _is_valid(d):
    if not math.isfinite(d.mean):
        return False
    if not (d.std > 0 and math.isfinite(d.std)):
        return False
    return d.quantile(0.9) >= d.quantile(0.1) - 1e-6


@pytest.mark.parametrize("factory", POLICIES, ids=lambda f: f.__name__)
@pytest.mark.parametrize("series", DEGENERATE_SERIES.values(), ids=DEGENERATE_SERIES.keys())
def test_policies_emit_valid_dist_on_degenerate_input(factory, series):
    f = factory(1)
    state, last = None, None
    for y in series:
        dists, state = f(y, state)
        last = dists[0]
    assert _is_valid(last), f"invalid Dist: mean={last.mean} std={last.std}"


def test_var_stable_under_large_mean():
    # E[X^2] - E[X]^2 cancels here (9e16 - 9e16 = 0); the centered form does not.
    assert abs(Dist([(1.0, 1e8, 1.0)]).std - 1.0) < 1e-3
    # a tight component at a large mean must keep std > 0
    assert Dist([(1.0, 3.0, 1e-16)]).std > 0


def test_prune_degenerate_does_not_crash():
    assert len(Dist([(0.5, 0.0, 1.0), (0.5, 5.0, 1.0)]).prune(0).components) == 1
    assert len(Dist([(1.0, 0.0, 1.0)]).prune(0).components) == 1
    assert len(Dist([(1.0, 0.0, 1.0)]).prune(5).components) == 1


def test_yeo_johnson_inverse_no_overflow():
    # an absurd transformed mean must give a finite (if huge) std, not crash/inf
    out = yeo_johnson(0.0)[1]([Dist([(1.0, 800.0, 1.0)])], {})[0]
    assert math.isfinite(out.std) and out.std > 0
    assert math.isfinite(out.mean)
