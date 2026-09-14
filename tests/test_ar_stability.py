"""Regression tests for skaters#232: ar()/grouped_ar()'s forward/inverse
coefficient mismatch, and _ar_spectral_radius's single-seed power iteration
missing the true dominant eigenvalue."""

import math
import pytest
from skaters.transform import ar, grouped_ar, _ar_spectral_radius, _ar_stationary
from skaters.search import _build_from_recipe


def test_spectral_radius_finds_dominant_eigenvalue_missed_by_single_seed():
    """phi=[3,-2,0,0,0]: companion characteristic polynomial z^3(z-1)(z-2), true
    radius 2. A single power-iteration seed of all-ones is exactly an
    eigenvector for eigenvalue 1 here, so it never discovers eigenvalue 2 --
    _ar_spectral_radius previously reported 1.0, and _ar_stationary then
    "damped" already-unstable coefficients to a result that was STILL
    non-stationary (true radius 1.998, not the intended 0.999 margin)."""
    phi = [3.0, -2.0, 0.0, 0.0, 0.0]
    radius = _ar_spectral_radius(phi)
    assert radius == pytest.approx(2.0, rel=1e-6)

    damped = _ar_stationary(phi)
    assert _ar_spectral_radius(damped) <= 0.999 + 1e-9


def test_ar_forward_and_inverse_agree_on_coefficients():
    """The blowup reported in skaters#232: a search recipe stacking ar(2) and
    ar(5) on a mostly-zero series with one small-then-large jump used to emit
    an astronomically wide predictive distribution (std ~2.6e10), because
    forward() emitted residuals under the raw RLS coefficients while
    inverse_k() reconstructed the forecast under the stationarity-projected
    ones -- the leaf learned errors from a different predictor than the one
    used to forecast."""
    f = _build_from_recipe(["ar(2)", "ar(5)", "pow(0.5)"], k=1)
    state = None
    for y in [0.0] * 2000 + [1e-8, 1.0, 0.0, 0.0]:
        ds, state = f(y, state)
    assert math.isfinite(ds[0].mean)
    assert math.isfinite(ds[0].std)
    assert ds[0].std < 10.0, f"std={ds[0].std} -- forward/inverse coefficient mismatch reappeared"


def test_ar_phi_used_stays_stationary_after_ill_conditioned_update():
    """A long constant run (near-singular regressor) followed by a jump can
    push the raw RLS phi into a non-stationary region in one step; phi_used
    (what forward() actually emits residuals under, and what inverse_k
    reconstructs with) must always stay in the stationary region."""
    fwd, inv = ar(order=2, lam=0.99, ridge=1.0)
    state = None
    for y in [0.0] * 500 + [5.0, -5.0, 5.0]:
        _, state = fwd(y, state)
    assert _ar_spectral_radius(state["phi_used"]) <= 0.999 + 1e-9


def test_grouped_ar_forward_and_inverse_agree_on_coefficients():
    fwd, inv = grouped_ar(max_lag=8, lam=0.99, ridge=1.0)
    state = None
    for y in [0.0] * 500 + [1e-8, 1.0, 0.0, 0.0]:
        _, state = fwd(y, state)
    from skaters.dist import Dist
    dists = inv([Dist.gaussian(0.0, 1.0)], state)
    assert math.isfinite(dists[0].mean)
    assert math.isfinite(dists[0].std)
    assert _ar_spectral_radius(state["phi_used"]) <= 0.999 + 1e-9
