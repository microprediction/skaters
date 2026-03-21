"""Tests for calibrated envelope."""

import math
import random
from skaters.ema import ema
from skaters.calibrated import calibrated_envelope, GAUSSIAN_1SIGMA
from skaters.api import ensemble_calibrated


def test_output_structure():
    f = calibrated_envelope(ema(alpha=0.1, k=2), k=2)
    out, state = f(1.0, None)
    assert "mean" in out
    assert "std" in out
    assert len(out["mean"]) == 2
    assert len(out["std"]) == 2


def test_initial_std_is_inf():
    f = calibrated_envelope(ema(alpha=0.1, k=1), k=1)
    out, _ = f(1.0, None)
    assert out["std"][0] == float("inf")


def test_std_becomes_finite():
    f = calibrated_envelope(ema(alpha=0.1, k=1), k=1)
    state = None
    random.seed(42)
    for _ in range(100):
        out, state = f(random.gauss(0, 1), state)
    assert math.isfinite(out["std"][0])
    assert out["std"][0] > 0


def test_mean_passes_through():
    """Calibrated envelope should not alter the skater's predictions."""
    inner = ema(alpha=0.2, k=3)
    f_bare = ema(alpha=0.2, k=3)
    f_cal = calibrated_envelope(inner, k=3)
    s_bare = s_cal = None
    random.seed(42)
    for _ in range(50):
        y = random.gauss(0, 1)
        x_bare, s_bare = f_bare(y, s_bare)
        out_cal, s_cal = f_cal(y, s_cal)
        for h in range(3):
            assert abs(x_bare[h] - out_cal["mean"][h]) < 1e-12


def test_coverage_converges_toward_target():
    """After enough data, the calibrated std should yield ~68% coverage."""
    random.seed(123)
    k = 1
    f = calibrated_envelope(ema(alpha=0.1, k=k), k=k)
    state = None

    # Feed data and track whether |error| < std
    predictions = []
    stds = []
    actuals = []

    for i in range(1000):
        y = random.gauss(0, 1)
        out, state = f(y, state)
        if predictions:
            error = y - predictions[-1]
            s = stds[-1]
            if math.isfinite(s) and s > 0:
                actuals.append(abs(error) <= s)
        predictions.append(out["mean"][0])
        stds.append(out["std"][0])

    # Check coverage over last 500 observations
    recent = actuals[-500:]
    coverage = sum(recent) / len(recent)
    # Should be roughly 68% ± generous margin
    assert 0.45 < coverage < 0.90, f"coverage={coverage:.3f}, expected ~0.68"


def test_narrow_std_for_predictable_series():
    """A nearly constant series should get small std."""
    f = calibrated_envelope(ema(alpha=0.3, k=1), k=1)
    state = None
    random.seed(42)
    for _ in range(200):
        out, state = f(10.0 + random.gauss(0, 0.01), state)
    assert out["std"][0] < 0.1


def test_wide_std_for_noisy_series():
    """A very noisy series should get large std."""
    f = calibrated_envelope(ema(alpha=0.1, k=1), k=1)
    state = None
    random.seed(42)
    for _ in range(200):
        out, state = f(random.gauss(0, 100), state)
    assert out["std"][0] > 10


def test_multihorizon():
    k = 5
    f = calibrated_envelope(ema(alpha=0.1, k=k), k=k)
    state = None
    random.seed(42)
    for _ in range(200):
        out, state = f(random.gauss(0, 1), state)
    assert len(out["std"]) == k
    assert all(math.isfinite(s) for s in out["std"])


def test_custom_target():
    """A target of 0.3 should yield narrower bands than 0.95."""
    random.seed(42)
    f_narrow = calibrated_envelope(ema(alpha=0.1, k=1), k=1, target=0.3)
    f_wide = calibrated_envelope(ema(alpha=0.1, k=1), k=1, target=0.95)
    s_n = s_w = None
    for _ in range(2000):
        y = random.gauss(0, 1)
        out_n, s_n = f_narrow(y, s_n)
        out_w, s_w = f_wide(y, s_w)
    # Lower target → candidates with smaller std are preferred
    assert out_n["std"][0] < out_w["std"][0]


def test_custom_decays():
    f = calibrated_envelope(ema(alpha=0.1, k=1), k=1, decays=[0.99, 0.9])
    state = None
    random.seed(42)
    for _ in range(100):
        out, state = f(random.gauss(0, 1), state)
    assert math.isfinite(out["std"][0])


def test_single_decay_candidate():
    f = calibrated_envelope(ema(alpha=0.1, k=1), k=1, decays=[None])
    state = None
    random.seed(42)
    for _ in range(100):
        out, state = f(random.gauss(0, 1), state)
    assert math.isfinite(out["std"][0])


def test_ensemble_calibrated_convenience():
    f = ensemble_calibrated(k=2)
    state = None
    random.seed(42)
    for _ in range(100):
        out, state = f(random.gauss(0, 1), state)
    assert "mean" in out
    assert "std" in out
    assert len(out["mean"]) == 2


def test_adapts_to_regime_change():
    """Std should increase when the series becomes noisier."""
    f = calibrated_envelope(ema(alpha=0.1, k=1), k=1)
    state = None
    random.seed(42)

    # Quiet regime
    for _ in range(300):
        out, state = f(random.gauss(0, 0.1), state)
    std_quiet = out["std"][0]

    # Noisy regime
    for _ in range(300):
        out, state = f(random.gauss(0, 10.0), state)
    std_noisy = out["std"][0]

    assert std_noisy > std_quiet * 2


def test_name():
    f = calibrated_envelope(ema(alpha=0.1, k=1), k=1)
    assert "calibrated" in f.__name__


def test_many_observations_no_crash():
    f = calibrated_envelope(ema(alpha=0.1, k=1), k=1)
    state = None
    random.seed(42)
    for _ in range(10_000):
        out, state = f(random.gauss(0, 1), state)
    assert math.isfinite(out["std"][0])
