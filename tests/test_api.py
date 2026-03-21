"""Tests for convenience API."""

import math
import random
from skaters.api import (
    rapidly,
    quickly,
    slowly,
    sluggishly,
    ensemble,
    ensemble_with_envelope,
)
from skaters.conventions import Skater


def test_all_factories_return_skaters():
    for factory in [rapidly, quickly, slowly, sluggishly, ensemble]:
        f = factory(k=1)
        assert isinstance(f, Skater)


def test_all_factories_accept_k():
    for factory in [rapidly, quickly, slowly, sluggishly, ensemble]:
        for k in [1, 3, 5]:
            f = factory(k=k)
            x, state = f(1.0, None)
            assert len(x) == k


def test_speed_ordering():
    """Faster models should track a step change more quickly."""
    factories = [sluggishly, slowly, quickly, rapidly]
    states = [None] * 4
    models = [f(k=1) for f in factories]

    # Burn in at 0
    for _ in range(100):
        for i, f in enumerate(models):
            _, states[i] = f(0.0, states[i])

    # Step to 100, measure after 20 steps
    for _ in range(20):
        xs = []
        for i, f in enumerate(models):
            x, states[i] = f(100.0, states[i])
            xs.append(x[0])

    # rapidly > quickly > slowly > sluggishly in tracking
    for i in range(len(xs) - 1):
        assert xs[i] < xs[i + 1], f"{factories[i].__name__} should be slower than {factories[i+1].__name__}"


def test_ensemble_with_envelope_returns_dict():
    f = ensemble_with_envelope(k=3)
    state = None
    random.seed(42)
    for _ in range(50):
        out, state = f(random.gauss(0, 1), state)
    assert "mean" in out
    assert "std" in out
    assert len(out["mean"]) == 3
    assert len(out["std"]) == 3
    assert all(math.isfinite(s) for s in out["std"])


def test_ensemble_with_envelope_decay():
    f = ensemble_with_envelope(k=1, decay=0.9)
    state = None
    random.seed(42)
    for _ in range(50):
        out, state = f(random.gauss(0, 1), state)
    assert math.isfinite(out["std"][0])


def test_default_k():
    """All factories should default to k=1."""
    for factory in [rapidly, quickly, slowly, sluggishly, ensemble]:
        f = factory()
        x, _ = f(1.0, None)
        assert len(x) == 1


def test_ensemble_with_envelope_default_k():
    f = ensemble_with_envelope()
    out, _ = f(1.0, None)
    assert len(out["mean"]) == 1
