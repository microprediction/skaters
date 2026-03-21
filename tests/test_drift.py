"""Tests for the drift transform (random walk with adaptive drift)."""

import copy
import math
import random
from skaters.transform import drift, difference
from skaters.conjugate import conjugate
from skaters.leaf import leaf
from skaters.dist import Dist


# --- Basic mechanics ---

def test_forward_first_is_zero():
    fwd, _ = drift()
    y_p, state = fwd(1.0, None)
    assert y_p == 0.0
    assert state["mu"] == 0.0


def test_forward_returns_finite():
    fwd, _ = drift()
    state = None
    random.seed(42)
    for _ in range(500):
        y_p, state = fwd(random.gauss(0, 1), state)
    assert math.isfinite(y_p)


def test_drift_estimate_converges_to_true_drift():
    """On a series with constant drift μ=0.5, the estimate should converge."""
    random.seed(42)
    fwd, _ = drift(alpha=0.01, shrinkage=0.001)
    state = None
    y = 0.0
    for _ in range(5000):
        y += 0.5 + random.gauss(0, 1)
        _, state = fwd(y, state)
    # mu should be near 0.5
    assert abs(state["mu"] - 0.5) < 0.15, f"mu={state['mu']:.4f}, expected ~0.5"


def test_drift_shrinks_to_zero_without_drift():
    """On a pure random walk (no drift), mu should stay near zero."""
    random.seed(42)
    fwd, _ = drift(alpha=0.002, shrinkage=0.001)
    state = None
    y = 0.0
    for _ in range(2000):
        y += random.gauss(0, 1)
        _, state = fwd(y, state)
    assert abs(state["mu"]) < 0.1, f"mu={state['mu']:.4f}, expected ~0"


def test_shrinkage_zero_allows_drift_to_persist():
    """Without shrinkage, even a temporary drift persists."""
    random.seed(42)
    fwd, _ = drift(alpha=0.01, shrinkage=0.0)
    state = None
    y = 0.0
    # Phase 1: drift of 1.0 for 500 steps
    for _ in range(500):
        y += 1.0 + random.gauss(0, 0.5)
        _, state = fwd(y, state)
    mu_after_drift = state["mu"]
    # Phase 2: no drift for 500 steps
    for _ in range(500):
        y += random.gauss(0, 0.5)
        _, state = fwd(y, state)
    mu_after_no_drift = state["mu"]
    # Without shrinkage, mu decays more slowly
    assert abs(mu_after_no_drift) > 0.01


def test_shrinkage_kills_stale_drift():
    """With shrinkage, a drift that stops should decay toward zero."""
    random.seed(42)
    fwd, _ = drift(alpha=0.01, shrinkage=0.005)
    state = None
    y = 0.0
    # Phase 1: strong drift
    for _ in range(500):
        y += 2.0 + random.gauss(0, 0.5)
        _, state = fwd(y, state)
    mu_peak = state["mu"]
    assert mu_peak > 1.0
    # Phase 2: no drift for a long time
    for _ in range(2000):
        y += random.gauss(0, 0.5)
        _, state = fwd(y, state)
    # Shrinkage should have pulled mu back toward zero
    assert abs(state["mu"]) < mu_peak * 0.3


# --- Inverse ---

def test_inverse_returns_dist():
    fwd, inv = drift()
    state = None
    random.seed(42)
    for _ in range(100):
        _, state = fwd(random.gauss(0, 1), state)
    result = inv([Dist.gaussian(0.0, 1.0)], state)
    assert isinstance(result[0], Dist)


def test_inverse_includes_drift():
    """Inverse should shift by last + (h+1)*mu, not just last."""
    fwd, inv = drift(alpha=0.01, shrinkage=0.0)
    state = None
    y = 0.0
    random.seed(42)
    # Build up a drift estimate
    for _ in range(1000):
        y += 1.0 + random.gauss(0, 0.5)
        _, state = fwd(y, state)

    mu = state["mu"]
    last = state["last"]
    # Predict 3 steps ahead with zero residuals
    dists_in = [Dist.gaussian(0.0, 0.5)] * 3
    result = inv(dists_in, state)

    for h in range(3):
        expected = last + (h + 1) * mu
        assert abs(result[h].mean - expected) < 0.5, (
            f"h={h+1}: mean={result[h].mean:.2f}, expected≈{expected:.2f}"
        )


def test_inverse_variance_grows():
    fwd, inv = drift()
    state = None
    random.seed(42)
    for _ in range(200):
        _, state = fwd(random.gauss(0, 1), state)
    k = 5
    dists_in = [Dist.gaussian(0.0, 1.0)] * k
    result = inv(dists_in, state)
    stds = [d.std for d in result]
    for h in range(1, k):
        assert stds[h] >= stds[h - 1] - 1e-10


# --- Bijection ---

def test_bijection_k1():
    fwd, inv = drift()
    state = None
    random.seed(42)
    series = [0.0]
    for _ in range(199):
        series.append(series[-1] + 0.3 + random.gauss(0, 1))
    for y in series[:150]:
        _, state = fwd(y, state)
    snap = copy.deepcopy(state)
    y_next = series[150]
    y_p, _ = fwd(y_next, copy.deepcopy(snap))
    recovered = inv([Dist.gaussian(y_p, 1e-6)], snap)
    assert abs(recovered[0].mean - y_next) < 0.01


def test_bijection_k3():
    fwd, inv = drift()
    state = None
    random.seed(42)
    series = [0.0]
    for _ in range(199):
        series.append(series[-1] + 0.2 + random.gauss(0, 1))
    for y in series[:180]:
        _, state = fwd(y, state)
    snap = copy.deepcopy(state)
    future = series[180:183]
    transformed = []
    fwd_state = copy.deepcopy(snap)
    for y_f in future:
        y_p, fwd_state = fwd(y_f, fwd_state)
        transformed.append(y_p)
    dists_in = [Dist.gaussian(v, 1e-6) for v in transformed]
    recovered = inv(dists_in, snap)
    for h in range(3):
        assert abs(recovered[h].mean - future[h]) < 0.1


# --- Composition ---

def test_drift_leaf(self=None):
    k = 1
    f = conjugate(leaf(k=k), drift(), k=k)
    state = None
    random.seed(42)
    for _ in range(300):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)


def test_beats_pure_random_walk_on_drift_series():
    """drift|leaf should beat diff|leaf on a series with true drift."""
    random.seed(42)
    y = 0.0
    series = []
    for _ in range(2000):
        y += 0.3 + random.gauss(0, 1)
        series.append(y)

    f_rw = conjugate(leaf(k=1), difference(), k=1)
    f_drift = conjugate(leaf(k=1), drift(alpha=0.005, shrinkage=0.001), k=1)
    s_rw = s_dr = None
    ll_rw = []
    ll_dr = []

    prev_rw = prev_dr = None
    for i, y_obs in enumerate(series):
        d_rw, s_rw = f_rw(y_obs, s_rw)
        d_dr, s_dr = f_drift(y_obs, s_dr)
        if i > 200 and prev_rw is not None:
            ll_rw.append(Dist.gaussian(prev_rw, d_rw[0].std).logpdf(y_obs))
            ll_dr.append(Dist.gaussian(prev_dr, d_dr[0].std).logpdf(y_obs))
        prev_rw = d_rw[0].mean
        prev_dr = d_dr[0].mean

    mean_ll_rw = sum(lp for lp in ll_rw if math.isfinite(lp)) / len(ll_rw)
    mean_ll_dr = sum(lp for lp in ll_dr if math.isfinite(lp)) / len(ll_dr)
    assert mean_ll_dr > mean_ll_rw, (
        f"drift didn't beat random walk: {mean_ll_dr:.3f} vs {mean_ll_rw:.3f}"
    )


def test_long_run_stable():
    f = conjugate(leaf(k=1), drift(), k=1)
    state = None
    random.seed(42)
    for _ in range(10_000):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)
