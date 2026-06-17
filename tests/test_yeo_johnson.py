"""Tests for the Yeo-Johnson coordinate transform."""

import math

from skaters.dist import Dist
from skaters.transform import yeo_johnson


def test_round_trip_all_reals():
    for L in (-1.0, 0.0, 0.5, 1.0, 1.5, 2.0):
        fwd, inv_k = yeo_johnson(L)
        for y in (-50.0, -3.2, -1.0, 0.0, 0.25, 1.0, 5.0, 1000.0):
            yp, _ = fwd(y, None)
            back = inv_k([Dist([(1.0, yp, 1e-6)])], {})[0].mean
            assert abs(back - y) < 1e-7


def test_identity_at_lambda_one():
    fwd, _ = yeo_johnson(1.0)
    for y in (-3.0, 0.0, 7.0):
        yp, _ = fwd(y, None)
        assert abs(yp - y) < 1e-12


def test_log1p_at_lambda_zero():
    fwd, _ = yeo_johnson(0.0)
    yp, _ = fwd(7.0, None)
    assert abs(yp - math.log1p(7.0)) < 1e-12


def test_inverse_approximately_non_negative():
    # lambda=0 maps log1p space back to levels. The Dist inverse is the delta-
    # method (Gaussian) linearization, so non-negativity is APPROXIMATE: a tight
    # predictive keeps its bulk > 0, but a wide one can cross 0 in the tail
    # because a lognormal is being approximated by a Gaussian. (Exact positivity
    # would need a non-Gaussian Dist, which the library deliberately does not use.)
    _, inv_k = yeo_johnson(0.0)
    tight = inv_k([Dist([(1.0, 2.0, 0.2)])], {})[0]
    assert tight.mean > 0.0 and tight.quantile(0.01) > 0.0
    wide = inv_k([Dist([(1.0, 2.0, 1.0)])], {})[0]
    assert wide.mean > 0.0                     # mean stays positive ...
    assert wide.quantile(0.001) < 0.0          # ... but the linearized tail can cross 0


def test_delta_method_std_positive():
    _, inv_k = yeo_johnson(0.5)
    out = inv_k([Dist([(1.0, 3.0, 0.5)])], {})[0]
    assert out.std > 0 and math.isfinite(out.std)
