"""Tests for the EMA skater."""

import math
import pytest
from skaters.ema import ema


def test_first_call_echoes_input():
    f = ema(alpha=0.1, k=1)
    x, state = f(42.0, None)
    assert x == [42.0]
    assert state is not None


def test_returns_k_predictions():
    for k in [1, 3, 7]:
        f = ema(alpha=0.1, k=k)
        x, _ = f(1.0, None)
        assert len(x) == k


def test_all_predictions_are_float():
    f = ema(alpha=0.1, k=3)
    x, _ = f(1.0, None)
    assert all(isinstance(v, float) for v in x)


def test_converges_to_constant():
    f = ema(alpha=0.3, k=1)
    state = None
    for _ in range(1000):
        x, state = f(7.0, state)
    assert abs(x[0] - 7.0) < 1e-10


def test_responds_to_step_change():
    f = ema(alpha=0.1, k=1)
    state = None
    # Burn in at 0
    for _ in range(100):
        x, state = f(0.0, state)
    assert abs(x[0]) < 1e-6
    # Step to 100
    for _ in range(100):
        x, state = f(100.0, state)
    # Should have moved significantly toward 100
    assert x[0] > 90.0


def test_fast_alpha_tracks_faster():
    f_fast = ema(alpha=0.5, k=1)
    f_slow = ema(alpha=0.01, k=1)
    s_fast = s_slow = None
    # Burn in at 0
    for _ in range(50):
        _, s_fast = f_fast(0.0, s_fast)
        _, s_slow = f_slow(0.0, s_slow)
    # Step to 10
    for _ in range(10):
        x_fast, s_fast = f_fast(10.0, s_fast)
        x_slow, s_slow = f_slow(10.0, s_slow)
    assert x_fast[0] > x_slow[0]


def test_state_is_dict():
    f = ema(alpha=0.1, k=1)
    _, state = f(1.0, None)
    assert isinstance(state, dict)
    assert "level" in state


def test_state_carries_forward():
    f = ema(alpha=0.1, k=1)
    x1, s1 = f(10.0, None)
    x2, s2 = f(10.0, s1)
    assert x1 == x2  # constant input, same output
    assert s1["level"] == s2["level"]


def test_invalid_alpha_raises():
    with pytest.raises(AssertionError):
        ema(alpha=0.0)
    with pytest.raises(AssertionError):
        ema(alpha=1.0)
    with pytest.raises(AssertionError):
        ema(alpha=-0.1)
    with pytest.raises(AssertionError):
        ema(alpha=1.5)


def test_name_contains_params():
    f = ema(alpha=0.05, k=3)
    assert "0.05" in f.__name__
    assert "3" in f.__name__


def test_flat_predictions_for_all_horizons():
    """EMA has no trend model, so all k horizons should be the same."""
    f = ema(alpha=0.1, k=5)
    state = None
    for y in [1.0, 2.0, 3.0, 4.0, 5.0]:
        x, state = f(y, state)
    assert len(set(x)) == 1  # all horizons identical


def test_negative_observations():
    f = ema(alpha=0.2, k=1)
    state = None
    for _ in range(100):
        x, state = f(-50.0, state)
    assert abs(x[0] - (-50.0)) < 1e-6


def test_alternating_values():
    f = ema(alpha=0.5, k=1)
    state = None
    for i in range(200):
        y = 10.0 if i % 2 == 0 else -10.0
        x, state = f(y, state)
    # Should be near 0 (the mean of alternating +10/-10)
    assert abs(x[0]) < 5.0


def test_many_observations_no_crash():
    f = ema(alpha=0.01, k=1)
    state = None
    for i in range(100_000):
        x, state = f(float(i % 100), state)
    assert math.isfinite(x[0])
