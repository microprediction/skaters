"""Tests targeting uncovered lines and edge cases for 100% coverage."""

import math
import random
import pytest
from skaters.dist import Dist
from skaters.spec import (
    build, name, _build_transform, _infer_k, _transform_name,
    ema_spec, ensemble_spec, conjugate_spec, leaf_spec,
    diff_spec, frac_spec, std_spec, ema_t_spec,
)
from skaters.search import search


# --- spec.py error paths ---

def test_build_unknown_op():
    with pytest.raises(ValueError, match="Unknown op"):
        build({"op": "bogus"})


def test_build_transform_unknown_op():
    with pytest.raises(ValueError, match="Unknown transform op"):
        _build_transform({"op": "bogus"})


def test_infer_k_fails_without_k():
    with pytest.raises(ValueError, match="Cannot infer k"):
        _infer_k({"op": "something"})


def test_transform_name_unknown():
    with pytest.raises(ValueError, match="Unknown transform op"):
        _transform_name({"op": "bogus"})


def test_name_unknown_op():
    with pytest.raises(ValueError, match="Unknown op"):
        name({"op": "bogus"})


# --- spec.py: ema_t transform in build/name ---

def test_build_ema_t_conjugate():
    s = conjugate_spec(leaf_spec(k=1), ema_t_spec(0.1))
    f = build(s)
    state = None
    random.seed(42)
    for _ in range(50):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)


def test_name_ema_t():
    s = conjugate_spec(leaf_spec(k=2), ema_t_spec(0.3))
    assert name(s) == "ema_t(0.3)|leaf"


# --- dist.py: __eq__ with non-Dist ---

def test_dist_eq_non_dist():
    d = Dist.gaussian(0.0, 1.0)
    assert d != "not a dist"
    assert d != 42


# --- dist.py: CDF with std=0 (degenerate Gaussian) ---

def test_cdf_zero_std():
    d = Dist([(1.0, 5.0, 0.0)])
    assert d.cdf(4.0) == 0.0
    assert d.cdf(5.0) == 1.0
    assert d.cdf(6.0) == 1.0


def test_pdf_zero_std():
    d = Dist([(1.0, 5.0, 0.0)])
    assert d.pdf(5.0) == float("inf")
    assert d.pdf(4.0) == 0.0


# --- bayesian.py: fallback to uniform when all weights are -inf ---

def test_bayesian_fallback_uniform():
    """When all models produce -inf logpdf, should fallback to uniform weights."""
    from skaters.bayesian import bayesian_ensemble

    # Two models that produce 0-std predictions (degenerate)
    def degen_a(y, state):
        return [Dist([(1.0, 0.0, 0.0)])], state or {}
    degen_a.__name__ = "a"

    def degen_b(y, state):
        return [Dist([(1.0, 100.0, 0.0)])], state or {}
    degen_b.__name__ = "b"

    f = bayesian_ensemble([degen_a, degen_b], k=1, learning_rate=1.0)
    state = None
    # Feed values that don't match either prediction — logpdf will be -inf
    # but clamped to -20, so weights will diverge but not be -inf
    for _ in range(50):
        x, state = f(50.0, state)
    assert math.isfinite(x[0].mean)


# --- search.py: pool pruning when over budget after threshold prune ---

def test_search_heavy_pruning():
    """With a very small max_pool and frequent expansion, pruning should cap the pool."""
    f = search(k=1, expand_interval=20, max_pool=5, replay_buffer=50)
    state = None
    random.seed(42)
    for _ in range(200):
        x, state = f(random.gauss(0, 1), state)
    assert len(state["pool"]) <= 5


# --- search.py: softmax fallback when all log weights are non-finite ---

def test_search_with_constant_zero():
    """Constant zero series — tests degenerate cases throughout."""
    f = search(k=1, expand_interval=30, replay_buffer=50, max_pool=10)
    state = None
    for _ in range(100):
        x, state = f(0.0, state)
    assert math.isfinite(x[0].mean)


# --- Additional leaf edge case ---

def test_leaf_single_observation():
    from skaters.leaf import leaf
    f = leaf(k=1)
    x, state = f(0.0, None)
    assert isinstance(x[0], Dist)
    assert x[0].std > 0  # bootstraps from |y| + eps


# --- Dist logpdf with zero-std component ---

def test_logpdf_zero_std_at_mean():
    d = Dist([(1.0, 5.0, 0.0)])
    lp = d.logpdf(5.0)
    # pdf is inf, log(inf) = inf
    assert lp == float("inf")


def test_logpdf_zero_std_away_from_mean():
    d = Dist([(1.0, 5.0, 0.0)])
    lp = d.logpdf(4.0)
    # pdf is 0, log(0) = -inf
    assert lp == -float("inf")
