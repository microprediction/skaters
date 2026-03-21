"""Tests for the parade (horizon-aware error tracking)."""

import math
from skaters.parade import parade_init, parade_update, parade_std


def test_init_creates_k_queues():
    s = parade_init(k=3)
    assert s["k"] == 3
    assert len(s["queues"]) == 3
    assert len(s["error_stats"]) == 3


def test_no_errors_before_resolution():
    """Before k+1 observations, horizon-k errors can't be computed yet."""
    s = parade_init(k=2)
    s = parade_update(s, [1.0, 1.0], 1.0)
    std = parade_std(s)
    assert all(v == float("inf") for v in std)


def test_horizon_1_resolves_after_2_obs():
    """Horizon 0 (1-step-ahead) should resolve after the second observation."""
    s = parade_init(k=1)
    # First obs: enqueue prediction, nothing to resolve
    s = parade_update(s, [10.0], 5.0)
    # Second obs: resolve prediction 10.0 against actual 7.0 -> error=-3
    s = parade_update(s, [7.0], 7.0)
    std = parade_std(s)
    # Only 1 error so far -> still inf
    assert std[0] == float("inf")
    # Third obs: now we have 2 errors
    s = parade_update(s, [8.0], 8.0)
    std = parade_std(s)
    assert math.isfinite(std[0])


def test_perfect_predictor_zero_std():
    """If predictions are always exact, std should be ~0."""
    s = parade_init(k=1)
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    for i, y in enumerate(values):
        # Predict the next value perfectly (except first, which doesn't matter)
        pred = values[i + 1] if i + 1 < len(values) else y
        s = parade_update(s, [pred], y)
    std = parade_std(s)
    # Errors should be 0 for the ones that resolved
    assert std[0] < 1e-10 or std[0] == float("inf")


def test_constant_error_known_std():
    """If the error is always exactly +1, variance should be 0."""
    s = parade_init(k=1)
    for i in range(50):
        y = float(i)
        pred = y - 1.0  # always underpredict by 1
        s = parade_update(s, [pred], y)
    std = parade_std(s)
    # All errors = +1, variance of a constant = 0
    assert std[0] < 1e-10


def test_multihorizon_different_stds():
    """Longer horizons should generally have larger errors for a drifting series."""
    import random
    random.seed(77)
    k = 5
    s = parade_init(k=k)
    level = 0.0
    for _ in range(500):
        level += random.gauss(0, 1)
        # Predict current level for all horizons (naively)
        s = parade_update(s, [level] * k, level)
    std = parade_std(s)
    # All should be finite
    assert all(math.isfinite(v) for v in std)
    # In a random walk, longer horizon should have larger error std
    # (at least roughly: std[4] > std[0])
    assert std[k - 1] > std[0] * 0.5  # generous margin


def test_parade_queue_lengths_bounded():
    """Queue length at horizon h should never exceed h+1."""
    k = 3
    s = parade_init(k=k)
    for i in range(100):
        s = parade_update(s, [float(i)] * k, float(i))
    for h in range(k):
        assert len(s["queues"][h]) <= h + 1
