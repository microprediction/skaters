"""Tests for covariance-aware HRP ensemble."""

import math
import random
from skaters.hrp_ensemble import hrp_ensemble, _hrp_from_corr
from skaters.ema import ema
from skaters.conjugate import conjugate
from skaters.leaf import leaf
from skaters.transform import difference, drift
from skaters.dist import Dist


def test_returns_dist():
    f = hrp_ensemble([ema(alpha=0.1, k=1), ema(alpha=0.3, k=1)], k=1)
    state = None
    random.seed(42)
    for _ in range(50):
        dists, state = f(random.gauss(0, 1), state)
    assert isinstance(dists[0], Dist)
    assert dists[0].std > 0


def test_multistep():
    f = hrp_ensemble([ema(alpha=0.1, k=3), ema(alpha=0.3, k=3)], k=3)
    state = None
    random.seed(42)
    for _ in range(50):
        dists, state = f(random.gauss(0, 1), state)
    assert len(dists) == 3


def test_weights_update():
    f = hrp_ensemble(
        [ema(alpha=0.1, k=1), ema(alpha=0.3, k=1),
         conjugate(leaf(k=1), difference(), k=1)],
        k=1,
    )
    state = None
    random.seed(42)
    for _ in range(200):
        _, state = f(random.gauss(0, 1), state)
    w = state["weights"][0]
    assert abs(sum(w) - 1.0) < 0.01
    assert all(wi >= 0 for wi in w)


def test_correlated_models_share_weight():
    """Two identical models should share weight, leaving room for a different one."""
    # Two identical EMAs + one diff model
    f = hrp_ensemble(
        [ema(alpha=0.1, k=1), ema(alpha=0.1, k=1),
         conjugate(leaf(k=1), difference(), k=1)],
        k=1,
    )
    state = None
    random.seed(42)
    for _ in range(500):
        _, state = f(random.gauss(0, 1), state)
    w = state["weights"][0]
    # The two identical EMAs should have similar weight
    assert abs(w[0] - w[1]) < 0.4  # HRP ordering can break symmetry
    # The diff model should get meaningful weight (it's uncorrelated)
    assert w[2] > 0.1


def test_single_model():
    f = hrp_ensemble([ema(alpha=0.1, k=1)], k=1)
    state = None
    random.seed(42)
    for _ in range(50):
        dists, state = f(random.gauss(0, 1), state)
    assert math.isfinite(dists[0].mean)


def test_on_trending():
    f = hrp_ensemble(
        [ema(alpha=0.1, k=1), conjugate(leaf(k=1), drift(), k=1)],
        k=1,
    )
    state = None
    random.seed(42)
    for t in range(500):
        dists, state = f(float(t) + random.gauss(0, 1), state)
    assert dists[0].mean > 300


def test_hrp_weights_equal_for_identical():
    """HRP should give equal weight to identical models."""
    var = [1.0, 1.0]
    corr = [1.0, 0.99, 0.99, 1.0]  # nearly identical
    w = _hrp_from_corr(var, corr, 2)
    assert abs(w[0] - w[1]) < 0.1


def test_hrp_favors_uncorrelated():
    """An uncorrelated model should get more weight."""
    var = [1.0, 1.0, 1.0]
    # Models 0 and 1 correlated, model 2 uncorrelated
    corr = [
        1.0, 0.9, 0.0,
        0.9, 1.0, 0.0,
        0.0, 0.0, 1.0,
    ]
    w = _hrp_from_corr(var, corr, 3)
    assert w[2] > w[0]


def test_long_run_stable():
    f = hrp_ensemble(
        [ema(alpha=0.05, k=1), ema(alpha=0.2, k=1)], k=1
    )
    state = None
    random.seed(42)
    for _ in range(5000):
        dists, state = f(random.gauss(0, 1), state)
    assert math.isfinite(dists[0].mean)
    assert dists[0].std > 0
