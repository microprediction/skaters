"""Tests for the precision-weighted ensemble."""

import math
import random
import pytest
from skaters.ema import ema
from skaters.ensemble import precision_weighted_ensemble
from skaters.dist import Dist


def _offset_skater(offset: float, k: int):
    """A skater that predicts a fixed offset (ignores input), returning list[Dist]."""
    def f(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        return [Dist.gaussian(offset, 1.0)] * k, {}
    f.__name__ = f"offset({offset})"
    return f


def test_returns_list():
    f = precision_weighted_ensemble([ema(alpha=0.1, k=1)], k=1)
    x, state = f(1.0, None)
    assert isinstance(x, list)


def test_returns_k_predictions():
    for k in [1, 3, 5]:
        f = precision_weighted_ensemble(
            [ema(alpha=0.1, k=k), ema(alpha=0.3, k=k)], k=k
        )
        x, _ = f(1.0, None)
        assert len(x) == k


def test_returns_dist_objects():
    f = precision_weighted_ensemble([ema(alpha=0.1, k=1)], k=1)
    x, _ = f(1.0, None)
    assert isinstance(x[0], Dist)


def test_single_model_ensemble_equals_model():
    """Ensemble of one should match the underlying model's mean."""
    inner = ema(alpha=0.2, k=2)
    ens = precision_weighted_ensemble([ema(alpha=0.2, k=2)], k=2)
    s_inner = s_ens = None
    random.seed(42)
    for _ in range(50):
        y = random.gauss(0, 1)
        x_inner, s_inner = inner(y, s_inner)
        x_ens, s_ens = ens(y, s_ens)
    for h in range(2):
        assert abs(x_inner[h].mean - x_ens[h].mean) < 1e-10


def test_favors_better_model():
    """Ensemble should weight toward the more accurate model over time."""
    random.seed(42)
    k = 1
    # Good model: EMA that tracks the signal well
    good = ema(alpha=0.3, k=k)
    # Bad model: always predicts 100
    bad = _offset_skater(100.0, k=k)

    f = precision_weighted_ensemble([good, bad], k=k)
    state = None
    for _ in range(200):
        y = random.gauss(5.0, 1.0)
        x, state = f(y, state)

    # Should be much closer to ~5.0 than to 100.0
    assert abs(x[0].mean - 5.0) < 5.0


def test_equal_models_equal_weight():
    """Two identical models should produce the same result as one."""
    k = 1
    f1 = precision_weighted_ensemble([ema(alpha=0.1, k=k)], k=k)
    f2 = precision_weighted_ensemble([ema(alpha=0.1, k=k), ema(alpha=0.1, k=k)], k=k)
    s1 = s2 = None
    random.seed(42)
    for _ in range(100):
        y = random.gauss(0, 1)
        x1, s1 = f1(y, s1)
        x2, s2 = f2(y, s2)
    assert abs(x1[0].mean - x2[0].mean) < 1e-10


def test_competitive_with_best_individual():
    """Ensemble should not be much worse than the best individual."""
    random.seed(42)
    k = 1
    alphas = [0.01, 0.05, 0.1, 0.3]
    individuals = [ema(alpha=a, k=k) for a in alphas]
    ens = precision_weighted_ensemble(
        [ema(alpha=a, k=k) for a in alphas], k=k
    )

    states = [None] * len(alphas)
    s_ens = None
    errors = {i: [] for i in range(len(alphas))}
    errors_ens = []

    level = 0.0
    for step in range(500):
        level = 0.95 * level + random.gauss(0, 1)
        x_ens, s_ens = ens(level, s_ens)
        for i, f in enumerate(individuals):
            x_i, states[i] = f(level, states[i])
            if step > 50:
                errors[i].append(abs(x_i[0].mean - level))
        if step > 50:
            errors_ens.append(abs(x_ens[0].mean - level))

    mae_ens = sum(errors_ens) / len(errors_ens)
    worst_mae = max(sum(v) / len(v) for v in errors.values())
    # Ensemble should be better than the worst individual
    assert mae_ens < worst_mae


def test_many_models():
    k = 1
    skaters = [ema(alpha=a, k=k) for a in [0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5]]
    f = precision_weighted_ensemble(skaters, k=k)
    state = None
    random.seed(42)
    for _ in range(100):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)


def test_floor_prevents_zero_weight():
    """Even a terrible model should retain floor-level weight and not crash."""
    random.seed(42)
    k = 1
    good = ema(alpha=0.1, k=k)
    terrible = _offset_skater(1000.0, k=k)
    f = precision_weighted_ensemble([good, terrible], k=k, floor=1e-6)
    state = None
    for _ in range(200):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)


def test_multihorizon():
    k = 4
    f = precision_weighted_ensemble(
        [ema(alpha=0.1, k=k), ema(alpha=0.3, k=k)], k=k
    )
    state = None
    random.seed(42)
    for _ in range(50):
        x, state = f(random.gauss(0, 1), state)
    assert len(x) == 4
    assert all(math.isfinite(v.mean) for v in x)


def test_empty_skaters_raises():
    with pytest.raises(AssertionError):
        precision_weighted_ensemble([], k=1)


def test_state_is_dict():
    f = precision_weighted_ensemble([ema(alpha=0.1, k=1)], k=1)
    _, state = f(1.0, None)
    assert isinstance(state, dict)
    assert "sub" in state


def test_name():
    f = precision_weighted_ensemble(
        [ema(alpha=0.1, k=1), ema(alpha=0.2, k=1)], k=1
    )
    assert "n=2" in f.__name__
