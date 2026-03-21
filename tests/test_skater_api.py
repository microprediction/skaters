"""Tests for the top-level skater() API."""

import math
import random
from skaters.api import skater
from skaters.dist import Dist


# --- Basic usage ---

def test_default_works():
    f = skater()
    state = None
    random.seed(42)
    for _ in range(50):
        dists, state = f(random.gauss(0, 1), state)
    assert len(dists) == 1
    assert isinstance(dists[0], Dist)


def test_multistep():
    f = skater(k=5)
    state = None
    random.seed(42)
    for _ in range(50):
        dists, state = f(random.gauss(0, 1), state)
    assert len(dists) == 5
    assert all(isinstance(d, Dist) for d in dists)


def test_has_uncertainty():
    f = skater(k=1)
    state = None
    random.seed(42)
    for _ in range(100):
        dists, state = f(random.gauss(0, 1), state)
    assert dists[0].std > 0
    assert math.isfinite(dists[0].std)


def test_has_pdf_cdf_logpdf():
    f = skater(k=1)
    state = None
    random.seed(42)
    for _ in range(100):
        dists, state = f(random.gauss(0, 1), state)
    assert math.isfinite(dists[0].pdf(0.0))
    assert 0 < dists[0].cdf(0.0) < 1
    assert math.isfinite(dists[0].logpdf(0.0))


def test_quantiles():
    f = skater(k=1)
    state = None
    random.seed(42)
    for _ in range(100):
        dists, state = f(random.gauss(0, 1), state)
    lo = dists[0].quantile(0.025)
    hi = dists[0].quantile(0.975)
    assert lo < hi
    assert lo < dists[0].mean < hi


# --- Aggressiveness ---

def test_conservative():
    f = skater(k=1, aggressiveness=0.1)
    state = None
    random.seed(42)
    for _ in range(100):
        dists, state = f(random.gauss(0, 1), state)
    assert math.isfinite(dists[0].mean)


def test_aggressive():
    f = skater(k=1, aggressiveness=0.9)
    state = None
    random.seed(42)
    for _ in range(100):
        dists, state = f(random.gauss(0, 1), state)
    assert math.isfinite(dists[0].mean)


def test_aggressiveness_affects_adaptation():
    """More aggressive should track a step change faster."""
    random.seed(42)
    f_conservative = skater(k=1, aggressiveness=0.1)
    f_aggressive = skater(k=1, aggressiveness=0.9)
    s_con = s_agg = None

    # Burn in at 0
    for _ in range(100):
        _, s_con = f_conservative(0.0, s_con)
        _, s_agg = f_aggressive(0.0, s_agg)

    # Step to 50, measure after 30 steps
    for _ in range(30):
        d_con, s_con = f_conservative(50.0, s_con)
        d_agg, s_agg = f_aggressive(50.0, s_agg)

    # Both should be tracking toward 50
    assert d_agg[0].mean > 30
    assert d_con[0].mean > 30


# --- Works on different series types ---

def test_on_constant_series():
    f = skater(k=1)
    state = None
    for _ in range(200):
        dists, state = f(42.0, state)
    assert abs(dists[0].mean - 42.0) < 2.0


def test_on_random_walk():
    random.seed(42)
    f = skater(k=1)
    state = None
    level = 0.0
    for _ in range(500):
        level += random.gauss(0, 1)
        dists, state = f(level, state)
    assert math.isfinite(dists[0].mean)
    assert dists[0].std > 0


def test_on_trending_series():
    random.seed(42)
    f = skater(k=1)
    state = None
    for t in range(500):
        dists, state = f(float(t) + random.gauss(0, 1), state)
    # Should be tracking near 500
    assert dists[0].mean > 400


def test_on_mean_reverting():
    random.seed(42)
    f = skater(k=1)
    state = None
    level = 0.0
    for _ in range(500):
        level = 0.95 * level + random.gauss(0, 1)
        dists, state = f(level, state)
    assert math.isfinite(dists[0].mean)


def test_on_regime_change():
    random.seed(42)
    f = skater(k=1)
    state = None
    for i in range(500):
        level = 0.0 if i < 250 else 100.0
        dists, state = f(level + random.gauss(0, 1), state)
    # Should have adapted to the new regime
    assert dists[0].mean > 80


# --- Stress ---

def test_many_observations():
    f = skater(k=1)
    state = None
    random.seed(42)
    for _ in range(5000):
        dists, state = f(random.gauss(0, 1), state)
    assert math.isfinite(dists[0].mean)
    assert dists[0].std > 0


def test_name():
    f = skater(k=3, aggressiveness=0.7)
    assert "skater" in f.__name__
