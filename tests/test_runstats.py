"""Tests for Welford's online running statistics."""

import math
from skaters.runstats import (
    running_var_init,
    running_var_update,
    running_var_get,
    running_std_get,
)


def test_single_observation():
    s = running_var_init()
    s = running_var_update(s, 5.0)
    mean, var = running_var_get(s)
    assert mean == 5.0
    assert var == float("inf")  # can't estimate variance from n=1


def test_two_observations():
    s = running_var_init()
    s = running_var_update(s, 3.0)
    s = running_var_update(s, 7.0)
    mean, var = running_var_get(s)
    assert abs(mean - 5.0) < 1e-12
    # sample variance of [3,7] = (3-5)^2 + (7-5)^2 / (2-1) = 8
    assert abs(var - 8.0) < 1e-12


def test_known_dataset():
    """[2, 4, 4, 4, 5, 5, 7, 9] -> mean=5, sample_var=32/7."""
    data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    s = running_var_init()
    for x in data:
        s = running_var_update(s, x)
    mean, var = running_var_get(s)
    assert abs(mean - 5.0) < 1e-10
    assert abs(var - 32.0 / 7.0) < 1e-10


def test_constant_series_zero_variance():
    s = running_var_init()
    for _ in range(100):
        s = running_var_update(s, 42.0)
    mean, var = running_var_get(s)
    assert abs(mean - 42.0) < 1e-12
    assert abs(var) < 1e-12


def test_std_matches_sqrt_var():
    data = [1.0, 3.0, 5.0, 7.0]
    s = running_var_init()
    for x in data:
        s = running_var_update(s, x)
    _, var = running_var_get(s)
    std = running_std_get(s)
    assert abs(std - math.sqrt(var)) < 1e-12


def test_std_inf_for_single_point():
    s = running_var_init()
    s = running_var_update(s, 1.0)
    assert running_std_get(s) == float("inf")


def test_std_inf_for_zero_points():
    s = running_var_init()
    assert running_std_get(s) == float("inf")


def test_numerical_stability_large_offset():
    """Welford should handle large-offset data without catastrophic cancellation."""
    s = running_var_init()
    base = 1e9
    data = [base + 1.0, base + 2.0, base + 3.0, base + 4.0, base + 5.0]
    for x in data:
        s = running_var_update(s, x)
    mean, var = running_var_get(s)
    assert abs(mean - (base + 3.0)) < 1e-3
    assert abs(var - 2.5) < 1e-3


def test_negative_values():
    s = running_var_init()
    for x in [-10.0, -20.0, -30.0]:
        s = running_var_update(s, x)
    mean, var = running_var_get(s)
    assert abs(mean - (-20.0)) < 1e-12
    assert abs(var - 100.0) < 1e-10


def test_incremental_matches_batch():
    """Online result should match the textbook formula."""
    import random
    random.seed(99)
    data = [random.gauss(5, 3) for _ in range(200)]

    s = running_var_init()
    for x in data:
        s = running_var_update(s, x)
    online_mean, online_var = running_var_get(s)

    batch_mean = sum(data) / len(data)
    batch_var = sum((x - batch_mean) ** 2 for x in data) / (len(data) - 1)

    assert abs(online_mean - batch_mean) < 1e-9
    assert abs(online_var - batch_var) < 1e-9


def test_update_returns_new_dict():
    """Each update should return a new dict (immutable-style)."""
    s0 = running_var_init()
    s1 = running_var_update(s0, 1.0)
    assert s0["n"] == 0  # original unchanged
    assert s1["n"] == 1
