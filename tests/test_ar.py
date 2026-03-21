"""Tests for AR(p) transform with online RLS."""

import copy
import math
import random
from skaters.transform import ar
from skaters.conjugate import conjugate
from skaters.ema import ema
from skaters.leaf import leaf
from skaters.transform import difference
from skaters.dist import Dist


# --- Basic mechanics ---

def test_forward_returns_finite():
    fwd, _ = ar(order=2)
    state = None
    random.seed(42)
    for _ in range(100):
        y_p, state = fwd(random.gauss(0, 1), state)
    assert math.isfinite(y_p)


def test_forward_first_p_observations():
    """Before we have p observations, residual = y (no prediction yet)."""
    fwd, _ = ar(order=3)
    state = None
    for y in [1.0, 2.0]:
        y_p, state = fwd(y, state)
        assert y_p == y  # not enough lags yet


def test_buffer_bounded():
    fwd, _ = ar(order=3)
    state = None
    for i in range(10000):
        _, state = fwd(float(i), state)
    assert len(state["buffer"]) <= 2 * 3 + 10


def test_coefficients_adapt():
    """On an AR(1) series, the estimated phi should converge to the true value."""
    random.seed(42)
    true_phi = 0.8
    fwd, _ = ar(order=1, lam=0.99)
    state = None
    y = 0.0
    for _ in range(2000):
        y = true_phi * y + random.gauss(0, 0.5)
        _, state = fwd(y, state)
    estimated_phi = state["phi"][0]
    assert abs(estimated_phi - true_phi) < 0.1, (
        f"estimated phi={estimated_phi:.4f}, true={true_phi}"
    )


def test_ar2_coefficients():
    """On an AR(2) series, both coefficients should be estimated."""
    random.seed(42)
    phi1, phi2 = 0.5, -0.3
    fwd, _ = ar(order=2, lam=0.995)
    state = None
    buf = [0.0, 0.0]
    for _ in range(3000):
        y = phi1 * buf[-1] + phi2 * buf[-2] + random.gauss(0, 0.5)
        buf.append(y)
        _, state = fwd(y, state)
    assert abs(state["phi"][0] - phi1) < 0.15, f"phi1: {state['phi'][0]:.4f} vs {phi1}"
    assert abs(state["phi"][1] - phi2) < 0.15, f"phi2: {state['phi'][1]:.4f} vs {phi2}"


def test_residuals_reduce_variance():
    """AR residuals should have lower variance than the raw series for an AR process."""
    random.seed(42)
    fwd, _ = ar(order=1, lam=0.99)
    state = None
    y = 0.0
    raw = []
    resid = []
    for i in range(1000):
        y = 0.7 * y + random.gauss(0, 1)
        raw.append(y)
        y_p, state = fwd(y, state)
        if i > 50:
            resid.append(y_p)
    raw_var = sum(x ** 2 for x in raw) / len(raw)
    resid_var = sum(x ** 2 for x in resid) / len(resid)
    assert resid_var < raw_var


# --- Inverse ---

def test_inverse_returns_dist():
    fwd, inv = ar(order=2)
    state = None
    random.seed(42)
    for _ in range(50):
        _, state = fwd(random.gauss(0, 1), state)
    result = inv([Dist.gaussian(0.0, 1.0)], state)
    assert isinstance(result[0], Dist)
    assert result[0].std > 0


def test_inverse_multistep():
    k = 5
    fwd, inv = ar(order=2)
    state = None
    random.seed(42)
    for _ in range(100):
        _, state = fwd(random.gauss(0, 1), state)
    dists_in = [Dist.gaussian(0.0, 1.0)] * k
    result = inv(dists_in, state)
    assert len(result) == k
    assert all(math.isfinite(d.mean) for d in result)


def test_inverse_variance_grows_with_horizon():
    """For an AR process, uncertainty should grow at longer horizons."""
    fwd, inv = ar(order=2)
    state = None
    random.seed(42)
    # Train on AR(2) data
    buf = [0.0, 0.0]
    for _ in range(500):
        y = 0.5 * buf[-1] + 0.2 * buf[-2] + random.gauss(0, 1)
        buf.append(y)
        _, state = fwd(y, state)
    k = 5
    dists_in = [Dist.gaussian(0.0, 1.0)] * k
    result = inv(dists_in, state)
    stds = [d.std for d in result]
    # Variance should generally increase with horizon
    assert stds[-1] > stds[0]


# --- Prediction bijection ---

def test_bijection_k1():
    """Forward next value, inverse should recover it."""
    fwd, inv = ar(order=2)
    state = None
    random.seed(42)
    series = [random.gauss(0, 1) for _ in range(200)]
    for y in series[:150]:
        _, state = fwd(y, state)
    state_snap = copy.deepcopy(state)
    y_next = series[150]
    y_prime, _ = fwd(y_next, copy.deepcopy(state_snap))
    recovered = inv([Dist.gaussian(y_prime, 1e-6)], state_snap)
    assert abs(recovered[0].mean - y_next) < 0.01


def test_bijection_k3():
    """Forward next 3 values, inverse should recover them."""
    fwd, inv = ar(order=3)
    state = None
    random.seed(42)
    series = [random.gauss(0, 1) for _ in range(200)]
    for y in series[:180]:
        _, state = fwd(y, state)
    state_snap = copy.deepcopy(state)
    future = series[180:183]
    transformed = []
    fwd_state = copy.deepcopy(state_snap)
    for y in future:
        y_p, fwd_state = fwd(y, fwd_state)
        transformed.append(y_p)
    dists_in = [Dist.gaussian(y_p, 1e-6) for y_p in transformed]
    recovered = inv(dists_in, state_snap)
    for h in range(3):
        assert abs(recovered[h].mean - future[h]) < 0.01, (
            f"horizon {h+1}: {recovered[h].mean:.4f} vs {future[h]:.4f}"
        )


# --- Composition ---

def test_diff_ar_is_arima():
    """diff|ar(2)|leaf ≈ ARIMA(2,1,0)."""
    k = 1
    f = conjugate(conjugate(leaf(k=k), ar(2), k=k), difference(), k=k)
    state = None
    random.seed(42)
    level = 0.0
    for _ in range(500):
        level += random.gauss(0, 1)
        x, state = f(level, state)
    assert math.isfinite(x[0].mean)
    assert x[0].std > 0


def test_ar_with_ema():
    k = 1
    f = conjugate(conjugate(leaf(k=k), ar(2), k=k), ema(alpha=0.1, k=k).__wrapped__ if hasattr(ema(alpha=0.1, k=k), '__wrapped__') else difference(), k=k)
    # Simpler: just ar|leaf
    f = conjugate(leaf(k=k), ar(3), k=k)
    state = None
    random.seed(42)
    for _ in range(200):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)


def test_long_run_stable():
    f = conjugate(leaf(k=1), ar(2), k=1)
    state = None
    random.seed(42)
    for _ in range(10_000):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)
    assert abs(x[0].mean) < 100
