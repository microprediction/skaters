"""Tests for convenience API."""

import math
import random
from skaters.api import (
    rapidly,
    quickly,
    slowly,
    sluggishly,
    ensemble,
)
from skaters.conventions import Skater
from skaters.dist import Dist


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


def test_all_factories_return_dist():
    for factory in [rapidly, quickly, slowly, sluggishly, ensemble]:
        f = factory(k=1)
        x, _ = f(1.0, None)
        assert isinstance(x[0], Dist)


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
            xs.append(x[0].mean)

    # rapidly > quickly > slowly > sluggishly in tracking
    for i in range(len(xs) - 1):
        assert xs[i] < xs[i + 1], f"{factories[i].__name__} should be slower than {factories[i+1].__name__}"


def test_default_k():
    """All factories should default to k=1."""
    for factory in [rapidly, quickly, slowly, sluggishly, ensemble]:
        f = factory()
        x, _ = f(1.0, None)
        assert len(x) == 1


def test_dist_has_std():
    """The returned Dist should carry uncertainty information."""
    f = ensemble(k=1)
    state = None
    random.seed(42)
    for _ in range(50):
        x, state = f(random.gauss(0, 1), state)
    assert x[0].std > 0
    assert math.isfinite(x[0].std)
