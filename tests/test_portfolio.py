"""Tests for portfolio (HRP-weighted policy combination)."""

import math
import random
from skaters.portfolio import portfolio, _rank, _rank_correlation_matrix, _hrp_weights
from skaters.api import bachelier, laplace, yule, brown, markowitz
from skaters.dist import Dist
from collections import deque


def test_rank():
    assert _rank([3.0, 1.0, 2.0]) == [3, 1, 2]
    assert _rank([1.0, 1.0, 1.0]) == [1, 2, 3]  # stable sort


def test_hrp_weights_sum_to_one():
    corr = [[1.0, 0.5], [0.5, 1.0]]
    w = _hrp_weights(corr, 2)
    assert abs(sum(w) - 1.0) < 1e-10


def test_hrp_uncorrelated_get_equal_weight():
    corr = [[1.0, 0.0], [0.0, 1.0]]
    w = _hrp_weights(corr, 2)
    assert abs(w[0] - w[1]) < 0.01


def test_hrp_correlated_pair_gets_less():
    """If A and B are correlated but C is uncorrelated, C should get more weight."""
    corr = [
        [1.0, 0.9, 0.1],
        [0.9, 1.0, 0.1],
        [0.1, 0.1, 1.0],
    ]
    w = _hrp_weights(corr, 3)
    assert w[2] > w[0]  # C (uncorrelated) gets more than A (correlated with B)


def test_portfolio_returns_dist():
    f = portfolio([bachelier, laplace], k=1)
    state = None
    random.seed(42)
    for _ in range(50):
        dists, state = f(random.gauss(0, 1), state)
    assert isinstance(dists[0], Dist)
    assert dists[0].std > 0


def test_portfolio_multistep():
    f = portfolio([bachelier, laplace], k=3)
    state = None
    random.seed(42)
    for _ in range(50):
        dists, state = f(random.gauss(0, 1), state)
    assert len(dists) == 3


def test_portfolio_weights_update():
    f = portfolio([bachelier, laplace, yule], k=1, rebalance_interval=50, window=100)
    state = None
    random.seed(42)
    for _ in range(200):
        _, state = f(random.gauss(0, 1), state)
    # Weights should have been rebalanced at least once
    assert sum(state["weights"]) > 0.99


def test_markowitz_runs():
    f = markowitz(k=1)
    state = None
    random.seed(42)
    for _ in range(300):
        dists, state = f(random.gauss(0, 1), state)
    assert math.isfinite(dists[0].mean)
    assert dists[0].std > 0


def test_markowitz_on_trending():
    random.seed(42)
    f = markowitz(k=1)
    state = None
    for t in range(500):
        dists, state = f(float(t) + random.gauss(0, 1), state)
    assert dists[0].mean > 300


def test_markowitz_multistep():
    f = markowitz(k=3)
    state = None
    random.seed(42)
    for _ in range(200):
        dists, state = f(random.gauss(0, 1), state)
    assert len(dists) == 3
    assert all(math.isfinite(d.mean) for d in dists)
