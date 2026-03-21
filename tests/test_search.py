"""Tests for adaptive search over the transform tree."""

import math
import random
from skaters.search import search, _init_pool, _build_from_recipe, _warmup, _make_entry
from skaters.leaf import leaf
from skaters.dist import Dist
from collections import deque


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
    assert pool[0]["depth"] == 0
    assert pool[0]["recipe"] == []
    assert all(p["depth"] <= 1 for p in pool)


def test_pool_has_recipes():
    pool = _init_pool(k=1)
    recipes = [tuple(p["recipe"]) for p in pool]
    assert () in recipes
    assert ("diff",) in recipes


def test_maintains_buffer():
    f = search(k=1, replay_buffer=100)
    state = None
    random.seed(42)
    for _ in range(50):
        _, state = f(random.gauss(0, 1), state)
    assert len(state["buffer"]) == 50


def test_buffer_bounded():
    f = search(k=1, replay_buffer=20)
    state = None
    random.seed(42)
    for _ in range(100):
        _, state = f(random.gauss(0, 1), state)
    assert len(state["buffer"]) == 20


# --- Warmup / Replay ---

def test_warmup_builds_state():
    """After warmup, a candidate should have non-None state."""
    entry = _make_entry(leaf(k=1), depth=0, recipe=[], k=1)
    buf = deque([1.0, 2.0, 3.0, 4.0, 5.0])
    _warmup(entry, buf, k=1)
    assert entry["s"] is not None
    assert entry["dists"] is not None
    assert entry["warmed"] is True
    assert entry["age"] == 5


def test_warmup_produces_valid_predictions():
    """After warmup, the queued prediction should be a proper Dist."""
    entry = _make_entry(leaf(k=1), depth=0, recipe=[], k=1)
    buf = deque([1.0, 2.0, 3.0])
    _warmup(entry, buf, k=1)
    assert len(entry["queues"][0]) == 1
    assert isinstance(entry["queues"][0][0], Dist)


def test_warmed_candidates_score_immediately():
    """After expansion + warmup, new candidates should start accumulating log-weights."""
    f = search(k=1, expand_interval=50, max_pool=50, replay_buffer=200)
    state = None
    random.seed(42)
    for _ in range(60):
        _, state = f(random.gauss(0, 1), state)

    # Find candidates added during expansion (depth >= 2)
    deep = [e for e in state["pool"] if e["depth"] >= 2]
    if deep:
        # They should be warmed and have non-zero log weights after a few more steps
        for _ in range(20):
            _, state = f(random.gauss(0, 1), state)
        deep = [e for e in state["pool"] if e["depth"] >= 2]
        for e in deep:
            assert e["warmed"]


# --- Expansion ---

def test_pool_grows_after_expansion():
    f = search(k=1, expand_interval=50, max_pool=50, replay_buffer=200)
    state = None
    random.seed(42)
    for _ in range(30):
        _, state = f(random.gauss(0, 1), state)
    initial_size = len(state["pool"])
    for _ in range(30):
        _, state = f(random.gauss(0, 1), state)
    assert len(state["pool"]) > initial_size


def test_expansion_creates_deeper_models():
    f = search(k=1, expand_interval=50, max_pool=50, max_depth=2, replay_buffer=200)
    state = None
    random.seed(42)
    for _ in range(60):
        _, state = f(random.gauss(0, 1), state)
    max_depth = max(e["depth"] for e in state["pool"])
    assert max_depth >= 2


def test_no_duplicate_recipes():
    f = search(k=1, expand_interval=30, max_pool=50, replay_buffer=100)
    state = None
    random.seed(42)
    for _ in range(100):
        _, state = f(random.gauss(0, 1), state)
    recipes = [tuple(e["recipe"]) for e in state["pool"]]
    assert len(recipes) == len(set(recipes))


def test_no_same_transform_twice_in_row():
    f = search(k=1, expand_interval=30, max_pool=50, replay_buffer=100)
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
    f = search(k=1, expand_interval=30, max_pool=max_pool, replay_buffer=100)
    state = None
    random.seed(42)
    for _ in range(300):
        _, state = f(random.gauss(0, 1), state)
    assert len(state["pool"]) <= max_pool


# --- Recipe builder ---

def test_build_from_recipe_empty():
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
    f = search(k=1, expand_interval=100, max_pool=20, replay_buffer=200)
    state = None
    level = 0.0
    for _ in range(500):
        level += random.gauss(0, 1)
        x, state = f(level, state)
    assert math.isfinite(x[0].mean)
    assert x[0].std > 0


def test_on_trending():
    random.seed(42)
    f = search(k=1, expand_interval=100, max_pool=20, replay_buffer=200)
    state = None
    for t in range(500):
        x, state = f(float(t) + random.gauss(0, 1), state)
    assert x[0].mean > 300


def test_on_mean_reverting():
    random.seed(42)
    f = search(k=1, expand_interval=100, max_pool=20, replay_buffer=200)
    state = None
    level = 0.0
    for _ in range(500):
        level = 0.95 * level + random.gauss(0, 1)
        x, state = f(level, state)
    assert math.isfinite(x[0].mean)


# --- Stress ---

def test_long_run_stable():
    random.seed(42)
    f = search(k=1, expand_interval=200, max_pool=20, replay_buffer=300)
    state = None
    for _ in range(2000):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)
    assert x[0].std > 0
