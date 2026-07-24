"""Adversarial multi-step robustness: a forecast must stay well-posed no matter
what the online fit does during warm-up.

Found 2026-07-24 running laplace on GIFT-Eval level series. laplace(13) produced
quantiles of ~1e13 on a subset of otherwise-ordinary series (values ~1e4). The
cause was NOT scale or degeneracy: recursive least squares fit a NON-STATIONARY
AR from a handful of warm-up points (an AR(2) with companion spectral radius ~32
after three observations), and a non-stationary AR has no convergent multi-step
forecast -- its h-step mean diverges geometrically (32**13 ~ 1e19). The median
was fine throughout; only the extrapolation blew up.

The fix is constrained forecasting: the AR inverse damps its coefficients into
the stationary region before extrapolating (``_ar_stationary``), so the forecast
stays the model's own but convergent. A no-op whenever the fit is already
stationary. These tests pin both the primitive and the end-to-end behaviour.
"""

import math

import pytest

from skaters import laplace
from skaters.transform import ar, _ar_spectral_radius, _ar_stationary


def _run(series, k=1):
    f, st, pend = laplace(k), None, None
    for y in series:
        pend, st = f(float(y), st)
    return pend


# --------------------------------------------------------------------------- #
# The stationarity primitive.
# --------------------------------------------------------------------------- #
def test_spectral_radius_ar1():
    assert _ar_spectral_radius([0.5]) == pytest.approx(0.5)
    assert _ar_spectral_radius([1.5]) == pytest.approx(1.5)


def test_spectral_radius_ar2_real_and_complex():
    # real roots: phi = [0.5, 0.2] -> roots of z^2 - 0.5 z - 0.2
    r = _ar_spectral_radius([0.5, 0.2])
    assert r == pytest.approx(max(abs((0.5 + math.sqrt(0.25 + 0.8)) / 2),
                                   abs((0.5 - math.sqrt(0.25 + 0.8)) / 2)))
    # complex roots (disc < 0): |root| = sqrt(-phi2)
    assert _ar_spectral_radius([0.2, -0.9]) == pytest.approx(math.sqrt(0.9))


def test_stationary_is_noop_when_already_stationary():
    phi = [0.6, 0.2]                       # radius < 1
    assert _ar_stationary(phi) is phi      # returned unchanged, no copy


def test_stationary_damps_explosive_fit():
    phi = [33.63, -33.4]                    # the observed warm-up blow-up
    assert _ar_spectral_radius(phi) > 30
    damped = _ar_stationary(phi)
    assert _ar_spectral_radius(damped) <= 1.0 + 1e-9


def test_stationary_preserves_direction():
    # damping scales; it does not flip signs or reorder the coefficients
    phi = [4.0, -2.0]
    damped = _ar_stationary(phi)
    assert (damped[0] > 0) and (damped[1] < 0)


# --------------------------------------------------------------------------- #
# End-to-end: multi-step forecasts stay bounded through warm-up.
# --------------------------------------------------------------------------- #
def test_multistep_from_three_points_is_bounded():
    # The literal adversarial case: a 13-step forecast off 3 observations must
    # not diverge. Pre-fix this reached ~1e22.
    pend = _run([10995.0, 11000.0, 11035.0], k=13)
    for h, d in enumerate(pend):
        assert math.isfinite(d.quantile(0.9))
        assert abs(d.quantile(0.9)) < 1e7, f"h={h+1} q90 {d.quantile(0.9):.3e}"


def test_multistep_warmup_stays_near_data_range():
    # laplace(13) on a short, gently trending level series (~1e4). Every horizon
    # must land within a small multiple of the data range, not orders beyond it.
    series = [10000.0 + 30.0 * t + 50.0 * math.sin(0.5 * t) for t in range(40)]
    hi = max(abs(v) for v in series)
    pend = _run(series, k=13)
    for h, d in enumerate(pend):
        assert math.isfinite(d.quantile(0.9))
        assert abs(d.quantile(0.9)) < 20 * hi, f"h={h+1} q90 {d.quantile(0.9):.3e}"


def test_large_magnitude_smooth_series_on_scale():
    # A smooth high-magnitude series (values ~1e6): the one-step interval stays a
    # small multiple of the level.
    series = [1e6 + 2e4 * math.sin(0.05 * t) + 100.0 * t for t in range(300)]
    level = 1e6
    d = _run(series, k=1)[0]
    assert d.quantile(0.9) < 3 * level
    assert d.quantile(0.1) > -level


def test_multistep_bounded_across_seeds():
    # Many short random-walk warm-ups at k=13: none may diverge.
    import random
    rng = random.Random(0)
    for _ in range(40):
        base = rng.uniform(1e3, 1e6)
        series = [base]
        for _ in range(6):
            series.append(series[-1] + rng.gauss(0, base * 0.01))
        hi = max(abs(v) for v in series)
        pend = _run(series, k=13)
        assert all(abs(d.quantile(0.9)) < 100 * hi for d in pend)
