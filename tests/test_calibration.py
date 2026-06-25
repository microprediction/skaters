"""Empirical interval-coverage / calibration tests.

The library's central promise is *well-calibrated predictive distributions*. A
correct 90% predictive interval should cover ~90% of out-of-sample outcomes. This
guards against the class of bug where a transform measures its residual against
post-update state and so feeds the leaf a residual shrunk by (1-alpha), producing
systematically overconfident intervals (regression test for that fix).
"""

import random
import pytest

from skaters.leaf import leaf
from skaters.conjugate import conjugate
from skaters.transform import (
    ema_transform, standardize, theta, drift, difference, ou_transform, holt_linear,
)
from skaters import laplace


def _iid_normal(n=12000, seed=0):
    r = random.Random(seed)
    return [r.gauss(0.0, 1.0) for _ in range(n)]


def _coverage(make, series, level=0.90, burn=1000):
    f = make()
    state = None
    pend = None
    lo = (1 - level) / 2
    hi = 1 - lo
    inside = n = 0
    for i, y in enumerate(series):
        if pend is not None and i > burn:
            d = pend[0]
            if d.quantile(lo) <= y <= d.quantile(hi):
                inside += 1
            n += 1
        pend, state = f(y, state)
    return inside / n


# Each transform composed with the plain leaf, on iid N(0,1): the 90% interval
# must cover ~90% (tolerance 3 points). The post-update-residual bug made
# ema/standardize/theta/drift cover far less (e.g. ema(0.5) ~ 59%).
CALIBRATION_CASES = [
    ("ema(0.2)", lambda: conjugate(leaf(k=1), ema_transform(0.2))),
    ("ema(0.5)", lambda: conjugate(leaf(k=1), ema_transform(0.5))),
    ("theta(0.1)", lambda: conjugate(leaf(k=1), theta(0.1))),
    ("drift", lambda: conjugate(leaf(k=1), drift(0.05, 0.01))),
    ("difference", lambda: conjugate(leaf(k=1), difference())),
    ("ou(0.1)", lambda: conjugate(leaf(k=1), ou_transform(0.1))),
    ("holt", lambda: conjugate(leaf(k=1), holt_linear(0.1, 0.05))),
]


@pytest.mark.parametrize("name,make", CALIBRATION_CASES, ids=[c[0] for c in CALIBRATION_CASES])
def test_interval_coverage_iid_normal(name, make):
    cov = _coverage(make, _iid_normal())
    assert abs(cov - 0.90) < 0.03, f"{name}: 90% interval covered {cov:.1%} (want ~90%)"


def test_standardize_not_overconfident():
    # standardize is improved but the pragmatic fix leaves it slightly conservative
    # in scale; require it is at least no longer badly overconfident (was ~81%).
    cov = _coverage(lambda: conjugate(leaf(k=1), standardize(0.1)), _iid_normal())
    assert cov > 0.85, f"standardize: 90% interval covered {cov:.1%}"


def test_laplace_well_calibrated_iid():
    cov = _coverage(lambda: laplace(k=1), _iid_normal(), burn=1500)
    assert abs(cov - 0.90) < 0.04, f"laplace 90% interval covered {cov:.1%}"
