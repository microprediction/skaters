"""Tests for conjugation (change-of-reference-frame composition)."""

import math
import random
from skaters.conjugate import conjugate
from skaters.transform import difference, fractional_difference, standardize
from skaters.ema import ema
from skaters.ensemble import precision_weighted_ensemble
from skaters.conventions import Skater


# --- Basic mechanics ---

def test_conjugate_returns_list():
    f = conjugate(ema(alpha=0.1, k=1), difference(), k=1)
    x, state = f(1.0, None)
    assert isinstance(x, list)
    assert len(x) == 1


def test_conjugate_returns_k_predictions():
    for k in [1, 3, 5]:
        f = conjugate(ema(alpha=0.1, k=k), difference(), k=k)
        x, _ = f(1.0, None)
        assert len(x) == k


def test_satisfies_skater_protocol():
    f = conjugate(ema(alpha=0.1, k=1), difference(), k=1)
    assert isinstance(f, Skater)


def test_state_is_dict():
    f = conjugate(ema(alpha=0.1, k=1), difference(), k=1)
    _, state = f(1.0, None)
    assert isinstance(state, dict)
    assert "t_state" in state
    assert "s_state" in state


def test_name():
    f = conjugate(ema(alpha=0.1, k=1), difference(), k=1)
    assert "conjugate" in f.__name__


# --- Differencing conjugation ---

def test_diff_conjugate_constant_series():
    """On a constant series, diff-conjugated EMA should predict the constant."""
    f = conjugate(ema(alpha=0.3, k=1), difference(), k=1)
    state = None
    for _ in range(100):
        x, state = f(42.0, state)
    assert abs(x[0] - 42.0) < 1e-6


def test_diff_conjugate_linear_trend():
    """On a linear trend y=t, the differences are 1.0, so the
    inner model should learn to predict 1.0, and inverse should
    give us the next value in the trend."""
    f = conjugate(ema(alpha=0.3, k=1), difference(), k=1)
    state = None
    for t in range(200):
        x, state = f(float(t), state)
    # After 200 steps of y=t, next prediction should be ~200
    assert abs(x[0] - 200.0) < 2.0


def test_diff_conjugate_multistep_trend():
    """Multi-step predictions on a linear trend."""
    k = 3
    f = conjugate(ema(alpha=0.3, k=k), difference(), k=k)
    state = None
    for t in range(200):
        x, state = f(float(t), state)
    # Predictions should be ~200, ~201, ~202
    # (EMA predicts constant delta, cumsum gives linear extrapolation)
    # But EMA produces flat predictions in transformed space, so
    # inverse cumsums: anchor + 1*delta, anchor + 2*delta, anchor + 3*delta
    for j in range(k):
        assert abs(x[j] - (199 + (j + 1) * 1.0)) < 3.0


def test_diff_conjugate_competitive():
    """Diff-conjugated model should beat plain EMA on a trending series."""
    random.seed(42)
    k = 1
    f_plain = ema(alpha=0.1, k=k)
    f_conj = conjugate(ema(alpha=0.1, k=k), difference(), k=k)
    s_plain = s_conj = None

    level = 0.0
    drift = 0.5
    errors_plain = []
    errors_conj = []
    for i in range(500):
        level += drift + random.gauss(0, 0.5)
        x_p, s_plain = f_plain(level, s_plain)
        x_c, s_conj = f_conj(level, s_conj)
        if i > 50:
            errors_plain.append(abs(x_p[0] - level))
            errors_conj.append(abs(x_c[0] - level))

    mae_plain = sum(errors_plain) / len(errors_plain)
    mae_conj = sum(errors_conj) / len(errors_conj)
    # Conjugated should be better on trending data
    assert mae_conj < mae_plain


# --- Fractional differencing conjugation ---

def test_frac_diff_conjugate_runs():
    k = 1
    f = conjugate(ema(alpha=0.1, k=k), fractional_difference(d=0.4), k=k)
    state = None
    random.seed(42)
    for _ in range(100):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0])


def test_frac_diff_conjugate_multistep():
    k = 3
    f = conjugate(ema(alpha=0.1, k=k), fractional_difference(d=0.3), k=k)
    state = None
    random.seed(42)
    for _ in range(200):
        x, state = f(random.gauss(0, 1), state)
    assert len(x) == k
    assert all(math.isfinite(v) for v in x)


def test_frac_diff_conjugate_constant():
    """On a constant series, should converge to predicting the constant."""
    k = 1
    f = conjugate(ema(alpha=0.3, k=k), fractional_difference(d=0.4, window=20), k=k)
    state = None
    for _ in range(200):
        x, state = f(5.0, state)
    assert abs(x[0] - 5.0) < 0.5


# --- Standardization conjugation ---

def test_standardize_conjugate_runs():
    k = 1
    f = conjugate(ema(alpha=0.1, k=k), standardize(), k=k)
    state = None
    random.seed(42)
    for _ in range(100):
        x, state = f(random.gauss(100, 10), state)
    assert math.isfinite(x[0])


def test_standardize_conjugate_recovers_scale():
    """Predictions should be in the original scale, not z-scores."""
    k = 1
    f = conjugate(ema(alpha=0.05, k=k), standardize(alpha=0.01), k=k)
    state = None
    random.seed(42)
    for _ in range(500):
        x, state = f(random.gauss(1000, 50), state)
    # Prediction should be near 1000, not near 0
    assert abs(x[0] - 1000) < 200


# --- Composition with ensemble ---

def test_conjugate_ensemble():
    """Conjugation should compose with ensemble."""
    k = 2
    inner = precision_weighted_ensemble(
        [ema(alpha=0.05, k=k), ema(alpha=0.2, k=k)], k=k
    )
    f = conjugate(inner, difference(), k=k)
    state = None
    random.seed(42)
    for _ in range(100):
        x, state = f(random.gauss(0, 1), state)
    assert len(x) == k
    assert all(math.isfinite(v) for v in x)


# --- Stress tests ---

def test_many_observations_no_crash():
    f = conjugate(ema(alpha=0.1, k=1), difference(), k=1)
    state = None
    for i in range(50_000):
        x, state = f(float(i % 100), state)
    assert math.isfinite(x[0])


def test_frac_diff_long_run_stable():
    f = conjugate(ema(alpha=0.1, k=1), fractional_difference(d=0.4, window=30), k=1)
    state = None
    random.seed(42)
    for _ in range(10_000):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0])
    assert abs(x[0]) < 100  # should not diverge
