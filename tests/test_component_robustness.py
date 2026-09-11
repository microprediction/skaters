"""Every component, driven directly against an adversarial input battery.

The scale/multi-step explosions (a non-stationary AR forecast, garch's variance
recursion on a raw level) were bugs in individual components that only surfaced
once assembled into ``laplace``. This suite tests each transform and each leaf on
its own, so a component that produces a non-finite or wildly-out-of-scale
forecast is caught and localised, not masked by the ensemble.

Two invariants:
  * FINITE  -- no input may produce a non-finite forecast (any component, any
    series, including genuinely pathological ones like a 1e300 spike).
  * BOUNDED -- on well-behaved (if tricky) series, the h-step forecast quantiles
    must stay within a generous multiple of the observed data scale. Genuine
    extrapolation is allowed; divergence by orders of magnitude is not.

A transform is exercised as ``conjugate(leaf(k), transform(), k)`` -- its natural
use inside laplace. Leaves are exercised directly on residual streams.
"""

import math

import pytest

from skaters.conjugate import conjugate
from skaters.leaf import leaf, scale_mixture_leaf, crps_leaf, garch_leaf
from skaters.transform import (
    difference, fractional_difference, standardize, ema_transform, ou_transform,
    garch, power_transform, drift, holt_linear, ar, theta,
    seasonal_difference, seasonal_anchor, yeo_johnson,
)

# --- transform factories (name -> zero-arg builder with sensible defaults) --- #
TRANSFORMS = {
    "difference": difference,
    "fractional_difference": lambda: fractional_difference(0.4, 30),
    "standardize": lambda: standardize(0.05),
    "ema_transform": lambda: ema_transform(0.1),
    "ou_transform": lambda: ou_transform(0.1, 0.02),
    "theta": lambda: theta(0.5),
    "drift": lambda: drift(0.01, 0.005),
    "holt_linear": lambda: holt_linear(0.1, 0.05),
    "garch": garch,
    "seasonal_difference": lambda: seasonal_difference(4),
    "seasonal_anchor": lambda: seasonal_anchor(4),
    "power_transform": lambda: power_transform(0.5),
    "yeo_johnson_log": lambda: yeo_johnson(0.0),
    "yeo_johnson_half": lambda: yeo_johnson(0.5),
    "ar1": lambda: ar(1),
    "ar2": lambda: ar(2, decay=1.0),
    "ar3": lambda: ar(3, decay=1.0),
}

LEAVES = {"leaf": leaf, "scale_mixture_leaf": scale_mixture_leaf,
          "crps_leaf": crps_leaf, "garch_leaf": garch_leaf}


# --- input battery ---------------------------------------------------------- #
def _series(name):
    n = 220
    if name == "large_smooth":
        return [1e6 + 2e4 * math.sin(0.05 * t) + 100.0 * t for t in range(n)]
    if name == "large_trend":
        return [1e6 + 800.0 * t for t in range(n)]
    if name == "huge_magnitude":
        return [1e9 + 1e7 * math.sin(0.05 * t) for t in range(n)]
    if name == "exp_growth":
        return [1e3 * 1.02 ** t for t in range(n)]        # ends ~7e10
    if name == "moderate_noise":
        return [100.0 + 5.0 * math.sin(0.3 * t) + (t % 7 - 3) for t in range(n)]
    if name == "seasonal":
        return [500.0 + 50.0 * math.sin(2 * math.pi * t / 4) for t in range(n)]
    if name == "low_variance_high_level":
        return [1e5 + 1e-3 * (t % 5) for t in range(n)]
    if name == "negative_large":
        return [-1e6 - 500.0 * t for t in range(n)]
    raise KeyError(name)

# Series on which the forecast must stay ON SCALE (bounded).
BOUNDED_SERIES = ["large_smooth", "large_trend", "huge_magnitude", "exp_growth",
                  "moderate_noise", "seasonal", "low_variance_high_level",
                  "negative_large"]

# Pathological inputs: only require FINITE (a model cannot sensibly forecast them).
def _pathological(name):
    if name == "spike_1e300":
        return [1.0] * 100 + [1e300] + [1.0] * 100
    if name == "constant_then_jump":
        return [5.0] * 150 + [9.0] * 50
    if name == "near_nyquist":
        return [1e6 + 1e5 * math.sin(t) for t in range(200)]
    if name == "alternating":
        return [1e4 * (-1) ** t for t in range(200)]
    raise KeyError(name)

# 1e300 is deliberately NOT here: a single 1e300 tick is sanitised by the
# laplace-level parade input gate (see test_extreme_inputs), not by every
# component in isolation, so requiring each transform to survive it alone tests
# an unreachable state.
PATHOLOGICAL = ["constant_then_jump", "near_nyquist", "alternating"]

# A candidate feeds the ensemble its MEAN (terminal.py combines means; a wide
# candidate dist is simply down-weighted). So the stability-critical invariant is
# that the mean never blows up -- an exploding mean poisons mu_h. A generous
# bound: a forecast may extrapolate a few times the data range, never orders of
# magnitude beyond it.
MEAN_BOUND = 100.0
KS = [1, 3, 13]


def _forecast(builder, series, k):
    """Run a single-candidate forecaster over `series`, return the last k-step
    predictive Dist list."""
    f = builder(k)
    st, pend = None, None
    for y in series:
        pend, st = f(float(y), st)
    return pend


def _scale(series):
    lo, hi = min(series), max(series)
    return max(abs(lo), abs(hi), hi - lo, 1e-9)


def _finite(dists):
    return all(math.isfinite(d.mean) and math.isfinite(d.std)
               and math.isfinite(d.quantile(0.9)) and math.isfinite(d.quantile(0.1))
               for d in dists)


# --------------------------------------------------------------------------- #
# Transforms (as conjugate(leaf, transform)) — the main event.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("tname", list(TRANSFORMS))
@pytest.mark.parametrize("sname", BOUNDED_SERIES)
@pytest.mark.parametrize("k", KS)
def test_transform_mean_and_finite(tname, sname, k):
    series = _series(sname)
    builder = lambda kk: conjugate(crps_leaf(k=kk), TRANSFORMS[tname](), k=kk)
    dists = _forecast(builder, series, k)
    assert _finite(dists), f"{tname} on {sname} k={k}: non-finite"
    scale = _scale(series)
    for h, d in enumerate(dists):
        assert abs(d.mean) < MEAN_BOUND * scale, (
            f"{tname} on {sname} k={k} h={h+1}: mean={d.mean:.3e} "
            f">> {MEAN_BOUND}x scale {scale:.3e} -- would poison the ensemble")


@pytest.mark.parametrize("sname", BOUNDED_SERIES)
@pytest.mark.parametrize("k", [1, 13])
def test_full_ensemble_stays_on_scale(sname, k):
    # The ship artifact: full laplace must keep every horizon's quantiles within
    # a small multiple of the data scale, whatever the individual candidates do.
    from skaters import laplace
    series = _series(sname)
    f, st, pend = laplace(k), None, None
    for y in series:
        pend, st = f(float(y), st)
    scale = _scale(series)
    for h, d in enumerate(pend):
        assert math.isfinite(d.quantile(0.9))
        assert abs(d.quantile(0.9)) < 10.0 * scale, (
            f"laplace k={k} on {sname} h={h+1}: q90={d.quantile(0.9):.3e} "
            f">> 10x scale {scale:.3e}")


@pytest.mark.parametrize("tname", list(TRANSFORMS))
@pytest.mark.parametrize("sname", PATHOLOGICAL)
def test_transform_forecast_finite_on_pathological(tname, sname):
    series = _pathological(sname)
    builder = lambda kk: conjugate(crps_leaf(k=kk), TRANSFORMS[tname](), k=kk)
    dists = _forecast(builder, series, 3)
    assert _finite(dists), f"{tname} on {sname}: non-finite"


# --------------------------------------------------------------------------- #
# Leaves directly, on adversarial residual streams.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("lname", list(LEAVES))
@pytest.mark.parametrize("stream", ["mean_zero", "large_mean_small_var",
                                    "large_scale", "tiny_scale", "spiky"])
def test_leaf_forecast_finite_and_on_scale(lname, stream):
    import random
    rng = random.Random(0)
    if stream == "mean_zero":
        ys = [rng.gauss(0, 1) for _ in range(300)]
    elif stream == "large_mean_small_var":
        ys = [1e6 + rng.gauss(0, 1) for _ in range(300)]
    elif stream == "large_scale":
        ys = [rng.gauss(0, 1e5) for _ in range(300)]
    elif stream == "tiny_scale":
        ys = [rng.gauss(0, 1e-6) for _ in range(300)]
    else:  # spiky
        ys = [rng.gauss(0, 1) for _ in range(150)] + [1e8] + [rng.gauss(0, 1) for _ in range(150)]
    f = LEAVES[lname](1)
    st, d = None, None
    for y in ys:
        out, st = f(y, st)
        d = out[0]
    assert math.isfinite(d.quantile(0.9)) and math.isfinite(d.quantile(0.1))
