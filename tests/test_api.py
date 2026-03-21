"""Tests for named search policies."""

import math
import random
from skaters.api import skater, brown, holt, hosking, laplace, wald, dantzig, bachelier
from skaters.conventions import Skater
from skaters.dist import Dist


ALL_POLICIES = [brown, holt, hosking, laplace, wald, dantzig, bachelier]


def test_all_policies_return_skaters():
    for policy in ALL_POLICIES:
        f = policy(k=1)
        assert isinstance(f, Skater)


def test_all_policies_accept_k():
    for policy in ALL_POLICIES:
        for k in [1, 3]:
            f = policy(k=k)
            x, state = f(1.0, None)
            assert len(x) == k


def test_all_policies_return_dist():
    for policy in ALL_POLICIES:
        f = policy(k=1)
        x, _ = f(1.0, None)
        assert isinstance(x[0], Dist)


def test_all_policies_have_uncertainty():
    random.seed(42)
    for policy in ALL_POLICIES:
        f = policy(k=1)
        state = None
        for _ in range(100):
            x, state = f(random.gauss(0, 1), state)
        assert x[0].std > 0, f"{policy.__name__} has no uncertainty"


def test_all_policies_have_names():
    for policy in ALL_POLICIES:
        f = policy(k=1)
        assert policy.__name__ in f.__name__


def test_all_policies_work_on_trending():
    """Every policy should track a trend eventually."""
    for policy in ALL_POLICIES:
        random.seed(42)
        f = policy(k=1)
        state = None
        for t in range(300):
            x, state = f(float(t) + random.gauss(0, 1), state)
        assert x[0].mean > 200, f"{policy.__name__} failed on trend"


def test_skater_default():
    f = skater()
    x, _ = f(1.0, None)
    assert len(x) == 1
    assert isinstance(x[0], Dist)


def test_skater_aggressiveness():
    for agg in [0.1, 0.5, 0.9]:
        f = skater(k=1, aggressiveness=agg)
        state = None
        random.seed(42)
        for _ in range(50):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0].mean)


def test_dantzig_excludes_expensive():
    """Dantzig should not include fractional differencing (cost=30)."""
    f = dantzig(k=1)
    state = None
    random.seed(42)
    for _ in range(200):
        x, state = f(random.gauss(0, 1), state)
    # Check that all candidates are cheap
    for entry in state["pool"]:
        assert entry["cost"] <= 5.0, f"expensive candidate in dantzig: cost={entry['cost']}, recipe={entry['recipe']}"


def test_cost_budget_limits_search():
    from skaters.search import search
    f = search(k=1, cost_budget=3.0, expand_interval=30, max_pool=20)
    state = None
    random.seed(42)
    for _ in range(100):
        _, state = f(random.gauss(0, 1), state)
    for entry in state["pool"]:
        assert entry["cost"] <= 3.0
