"""Tests for the model-independent empirical envelope."""

import math
import random
from skaters.ema import ema
from skaters.envelope import envelope


def _constant_skater(value: float, k: int):
    """A skater that always predicts a fixed value."""
    def f(y: float, state: dict | None) -> tuple[list[float], dict]:
        return [value] * k, {}
    f.__name__ = f"constant({value})"
    return f


def test_envelope_output_structure():
    f = envelope(ema(alpha=0.1, k=2), k=2)
    out, state = f(1.0, None)
    assert "mean" in out
    assert "std" in out
    assert len(out["mean"]) == 2
    assert len(out["std"]) == 2


def test_initial_std_is_inf():
    f = envelope(ema(alpha=0.1, k=1), k=1)
    out, _ = f(1.0, None)
    assert out["std"][0] == float("inf")


def test_std_becomes_finite():
    f = envelope(ema(alpha=0.1, k=1), k=1)
    state = None
    random.seed(42)
    for _ in range(50):
        out, state = f(random.gauss(0, 1), state)
    assert math.isfinite(out["std"][0])
    assert out["std"][0] > 0


def test_perfect_predictor_near_zero_std():
    """A constant series with a constant predictor => ~0 error std."""
    inner = _constant_skater(5.0, k=1)
    f = envelope(inner, k=1)
    state = None
    for _ in range(100):
        out, state = f(5.0, state)
    # After enough observations, std should be near 0
    if math.isfinite(out["std"][0]):
        assert out["std"][0] < 1e-10


def test_bad_predictor_large_std():
    """A predictor that's always wrong should have large std."""
    inner = _constant_skater(0.0, k=1)
    f = envelope(inner, k=1)
    state = None
    random.seed(42)
    for _ in range(100):
        out, state = f(random.gauss(100, 10), state)
    assert out["std"][0] > 1.0


def test_mean_passes_through():
    """Envelope should not alter the inner skater's predictions."""
    inner = ema(alpha=0.2, k=3)
    f_bare = ema(alpha=0.2, k=3)
    f_env = envelope(inner, k=3)
    s_bare = s_env = None
    random.seed(42)
    for _ in range(50):
        y = random.gauss(0, 1)
        x_bare, s_bare = f_bare(y, s_bare)
        out_env, s_env = f_env(y, s_env)
        for h in range(3):
            assert abs(x_bare[h] - out_env["mean"][h]) < 1e-12


def test_multihorizon_std():
    f = envelope(ema(alpha=0.1, k=5), k=5)
    state = None
    random.seed(42)
    for _ in range(200):
        out, state = f(random.gauss(0, 1), state)
    assert len(out["std"]) == 5
    assert all(math.isfinite(s) for s in out["std"])


def test_decay_mode_output_structure():
    f = envelope(ema(alpha=0.1, k=2), k=2, decay=0.95)
    state = None
    random.seed(42)
    for _ in range(50):
        out, state = f(random.gauss(0, 1), state)
    assert "mean" in out
    assert "std" in out
    assert len(out["std"]) == 2
    assert all(math.isfinite(s) for s in out["std"])


def test_decay_adapts_to_regime_change():
    """With decay, std should adapt when the error regime changes."""
    inner = _constant_skater(0.0, k=1)
    f = envelope(inner, k=1, decay=0.9)
    state = None

    # Phase 1: low noise
    random.seed(42)
    for _ in range(100):
        out, state = f(random.gauss(0, 0.1), state)
    std_low = out["std"][0]

    # Phase 2: high noise
    for _ in range(100):
        out, state = f(random.gauss(0, 10.0), state)
    std_high = out["std"][0]

    assert std_high > std_low * 2


def test_welford_does_not_forget():
    """Without decay, old errors have equal weight to recent ones."""
    inner = _constant_skater(0.0, k=1)
    f = envelope(inner, k=1)
    state = None

    # Phase 1: high noise
    random.seed(42)
    for _ in range(200):
        out, state = f(random.gauss(0, 10.0), state)
    std_after_noise = out["std"][0]

    # Phase 2: zero noise
    for _ in range(200):
        out, state = f(0.0, state)
    std_after_calm = out["std"][0]

    # Welford averages over all history, so std shouldn't drop dramatically
    assert std_after_calm > std_after_noise * 0.3


def test_envelope_name():
    f = envelope(ema(alpha=0.1, k=1), k=1)
    assert "envelope" in f.__name__


def test_state_is_dict():
    f = envelope(ema(alpha=0.1, k=1), k=1)
    _, state = f(1.0, None)
    assert isinstance(state, dict)
    assert "inner" in state
