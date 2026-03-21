"""Tests for adaptive search over the transform tree."""

import math
import random
from skaters.search import search, _init_pool, _build_from_recipe
from skaters.dist import Dist


# --- Basic mechanics ---

def test_returns_dist():
    f = search(k=1)
    x, state = f(1.0, None)
    assert isinstance(x[0], Dist)


def test_returns_k_predictions():
    for k in [1, 3]:
        f = search(k=k, max_pool=10)
        state = None
        random.seed(42)
        for _ in range(50):
            x, state = f(random.gauss(0, 1), state)
        assert len(x) == k


def test_initial_pool_populated():
    pool = _init_pool(k=1)
    assert len(pool) > 1
    assert pool[0]["depth"] == 0  # leaf
    assert pool[0]["recipe"] == []
    assert all(p["depth"] <= 1 for p in pool)


def test_pool_has_recipes():
    pool = _init_pool(k=1)
    recipes = [tuple(p["recipe"]) for p in pool]
    assert () in recipes  # leaf
    assert ("diff",) in recipes


# --- Expansion ---

def test_pool_grows_after_expansion():
    f = search(k=1, expand_interval=50, max_pool=50, grace_period=10)
    state = None
    random.seed(42)
    for _ in range(30):
        _, state = f(random.gauss(0, 1), state)
    initial_size = len(state["pool"])

    # Run past the first expansion point
    for _ in range(30):
        _, state = f(random.gauss(0, 1), state)

    assert len(state["pool"]) > initial_size


def test_expansion_creates_deeper_models():
    f = search(k=1, expand_interval=50, max_pool=50, max_depth=2, grace_period=10)
    state = None
    random.seed(42)
    for _ in range(60):
        _, state = f(random.gauss(0, 1), state)

    max_depth = max(e["depth"] for e in state["pool"])
    assert max_depth >= 2


def test_no_duplicate_recipes():
    f = search(k=1, expand_interval=30, max_pool=50, grace_period=10)
    state = None
    random.seed(42)
    for _ in range(100):
        _, state = f(random.gauss(0, 1), state)
    recipes = [tuple(e["recipe"]) for e in state["pool"]]
    assert len(recipes) == len(set(recipes))


def test_no_same_transform_twice_in_row():
    f = search(k=1, expand_interval=30, max_pool=50, grace_period=10)
    state = None
    random.seed(42)
    for _ in range(100):
        _, state = f(random.gauss(0, 1), state)
    for entry in state["pool"]:
        recipe = entry["recipe"]
        for i in range(len(recipe) - 1):
            assert recipe[i] != recipe[i + 1], f"consecutive duplicate in {recipe}"


# --- Pruning ---

def test_pool_bounded():
    max_pool = 15
    f = search(k=1, expand_interval=30, max_pool=max_pool, grace_period=10)
    state = None
    random.seed(42)
    for _ in range(300):
        _, state = f(random.gauss(0, 1), state)
    assert len(state["pool"]) <= max_pool


# --- Recipe builder ---

def test_build_from_recipe_empty():
    """Empty recipe = leaf."""
    f = _build_from_recipe([], k=1)
    x, state = f(1.0, None)
    assert isinstance(x[0], Dist)


def test_build_from_recipe_depth1():
    f = _build_from_recipe(["diff"], k=1)
    state = None
    for y in [1.0, 2.0, 3.0, 4.0]:
        x, state = f(y, state)
    assert math.isfinite(x[0].mean)


def test_build_from_recipe_depth2():
    f = _build_from_recipe(["ema_t(0.1)", "diff"], k=1)
    state = None
    random.seed(42)
    for _ in range(100):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)


# --- Different series types ---

def test_on_random_walk():
    random.seed(42)
    f = search(k=1, expand_interval=100, max_pool=20, grace_period=10)
    state = None
    level = 0.0
    for _ in range(500):
        level += random.gauss(0, 1)
        x, state = f(level, state)
    assert math.isfinite(x[0].mean)
    assert x[0].std > 0


def test_on_trending():
    random.seed(42)
    f = search(k=1, expand_interval=100, max_pool=20, grace_period=10)
    state = None
    for t in range(500):
        x, state = f(float(t) + random.gauss(0, 1), state)
    # Should be tracking near 500
    assert x[0].mean > 300


def test_on_mean_reverting():
    random.seed(42)
    f = search(k=1, expand_interval=100, max_pool=20, grace_period=10)
    state = None
    level = 0.0
    for _ in range(500):
        level = 0.95 * level + random.gauss(0, 1)
        x, state = f(level, state)
    assert math.isfinite(x[0].mean)


# --- Stress ---

def test_long_run_stable():
    random.seed(42)
    f = search(k=1, expand_interval=200, max_pool=20, grace_period=10)
    state = None
    for _ in range(2000):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)
    assert x[0].std > 0


def test_grace_period_prevents_early_death():
    """New candidates shouldn't be killed during grace period."""
    f = search(k=1, expand_interval=30, grace_period=25, max_pool=50)
    state = None
    random.seed(42)
    for _ in range(35):
        _, state = f(random.gauss(0, 1), state)
    # After first expansion at t=30, new candidates should still be alive at t=35
    young = [e for e in state["pool"] if e["age"] < 10]
    assert len(young) > 0
