"""Tests for named search policies."""

import math
import random
from skaters.api import laplace
from skaters.conventions import Skater
from skaters.dist import Dist


ALL_POLICIES = [laplace]


# --- _build_candidates leaf_fn contract (skaters#234) ---------------------

def test_build_candidates_default_is_plain_gaussian_leaf():
    """Omitting leaf_fn must be identical to passing the plain Gaussian
    `leaf` explicitly: same population, same depths, and bit-identical
    emissions on the same series."""
    from skaters.api import _build_candidates
    from skaters.leaf import leaf
    default, d_depths, _ = _build_candidates(1)
    explicit, e_depths, _ = _build_candidates(1, leaf_fn=leaf)
    assert len(default) == len(explicit)
    assert d_depths == e_depths
    r = random.Random(3)
    series = [r.gauss(0, 1) for _ in range(150)]
    for cd, ce in zip(default, explicit):
        sd = se = None
        for y in series:
            (dd,), sd = cd(y, sd)
            (de,), se = ce(y, se)
            assert dd.mean == de.mean and dd.std == de.std


def test_build_candidates_propagates_leaf_factory_to_every_candidate():
    """leaf_fn is called once per candidate with the requested k, for k=1
    and k=3, so an explicit factory reaches every member of the population."""
    from skaters.api import _build_candidates
    from skaters.leaf import leaf
    for k in (1, 3):
        calls = []

        def counting_leaf(k=k, _calls=calls):
            _calls.append(k)
            return leaf(k=k)

        candidates, _, _ = _build_candidates(k, leaf_fn=counting_leaf)
        assert len(calls) == len(candidates)
        assert all(kk == k for kk in calls)


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


def test_laplace_default():
    f = laplace()
    x, _ = f(1.0, None)
    assert len(x) == 1
    assert isinstance(x[0], Dist)


def test_cost_budget_limits_search():
    from skaters.search import search
    f = search(k=1, cost_budget=3.0, expand_interval=30, max_pool=20)
    state = None
    random.seed(42)
    for _ in range(100):
        _, state = f(random.gauss(0, 1), state)
    for entry in state["pool"]:
        assert entry["cost"] <= 3.0
