"""Tests for the Theta transform."""

import copy
import math
import random
from skaters.transform import theta
from skaters.conjugate import conjugate
from skaters.leaf import leaf
from skaters.dist import Dist


def test_forward_first_is_zero():
    fwd, _ = theta()
    y_p, state = fwd(1.0, None)
    assert y_p == 0.0


def test_forward_returns_finite():
    fwd, _ = theta()
    state = None
    random.seed(42)
    for _ in range(500):
        y_p, state = fwd(random.gauss(0, 1), state)
    assert math.isfinite(y_p)


def test_slope_on_linear_trend():
    """OLS slope should converge to the true slope on a linear series."""
    fwd, _ = theta(alpha=0.1)
    state = None
    for t in range(1000):
        _, state = fwd(0.5 * t, state)
    assert abs(state["slope"] - 0.5) < 0.01, f"slope={state['slope']:.4f}"


def test_ses_tracks_level():
    fwd, _ = theta(alpha=0.3)
    state = None
    for _ in range(500):
        _, state = fwd(42.0, state)
    assert abs(state["ses"] - 42.0) < 0.01


def test_inverse_includes_slope():
    """Multi-step forecast should extrapolate with slope/2."""
    fwd, inv = theta(alpha=0.1)
    state = None
    for t in range(500):
        _, state = fwd(float(t), state)
    ses = state["ses"]
    slope = state["slope"]
    dists_in = [Dist.gaussian(0.0, 1.0)] * 5
    result = inv(dists_in, state)
    for h in range(5):
        expected = ses + (h + 1) * slope / 2
        assert abs(result[h].mean - expected) < 1.0


def test_inverse_variance_grows():
    fwd, inv = theta()
    state = None
    random.seed(42)
    for _ in range(200):
        _, state = fwd(random.gauss(0, 1), state)
    dists_in = [Dist.gaussian(0.0, 1.0)] * 5
    result = inv(dists_in, state)
    stds = [d.std for d in result]
    for h in range(1, 5):
        assert stds[h] >= stds[h - 1] - 1e-10


def test_bijection_k1():
    fwd, inv = theta()
    state = None
    random.seed(42)
    series = [random.gauss(0, 1) for _ in range(200)]
    for y in series[:150]:
        _, state = fwd(y, state)
    snap = copy.deepcopy(state)
    y_next = series[150]
    y_p, _ = fwd(y_next, copy.deepcopy(snap))
    recovered = inv([Dist.gaussian(y_p, 1e-6)], snap)
    assert abs(recovered[0].mean - y_next) < 1.0  # state-dependent tolerance


def test_bijection_k3():
    fwd, inv = theta()
    state = None
    random.seed(42)
    series = [float(t) * 0.1 + random.gauss(0, 1) for t in range(200)]
    for y in series[:180]:
        _, state = fwd(y, state)
    snap = copy.deepcopy(state)
    future = series[180:183]
    transformed = []
    fwd_state = copy.deepcopy(snap)
    for y in future:
        y_p, fwd_state = fwd(y, fwd_state)
        transformed.append(y_p)
    dists_in = [Dist.gaussian(v, 1e-6) for v in transformed]
    recovered = inv(dists_in, snap)
    for h in range(3):
        assert abs(recovered[h].mean - future[h]) < 1.0


def test_conjugate_with_leaf():
    k = 1
    f = conjugate(leaf(k=k), theta(0.1), k=k)
    state = None
    random.seed(42)
    for _ in range(300):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)
    assert x[0].std > 0


def test_on_trending_series():
    k = 1
    f = conjugate(leaf(k=k), theta(0.1), k=k)
    state = None
    random.seed(42)
    for t in range(500):
        x, state = f(float(t) + random.gauss(0, 1), state)
    # Should track near 500
    assert x[0].mean > 400


def test_beats_ema_on_trend():
    """Theta should beat plain EMA on a trending series (it has slope)."""
    from skaters.ema import ema
    random.seed(42)
    series = [0.2 * t + random.gauss(0, 1) for t in range(1000)]
    f_ema = ema(alpha=0.1, k=1)
    f_theta = conjugate(leaf(k=1), theta(0.1), k=1)
    s_ema = s_theta = None
    err_ema, err_theta = [], []
    for i, y in enumerate(series):
        d_ema, s_ema = f_ema(y, s_ema)
        d_theta, s_theta = f_theta(y, s_theta)
        if i > 100:
            err_ema.append(abs(d_ema[0].mean - y))
            err_theta.append(abs(d_theta[0].mean - y))
    mae_ema = sum(err_ema) / len(err_ema)
    mae_theta = sum(err_theta) / len(err_theta)
    assert mae_theta < mae_ema


def test_long_run_stable():
    f = conjugate(leaf(k=1), theta(0.1), k=1)
    state = None
    random.seed(42)
    for _ in range(10_000):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)
