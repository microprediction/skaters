"""Tier 2: causality in both directions, for skaters and leaves.

(a) No lookahead: perturb every observation after origin o; every predictive
    issued at or before o must be bit-identical.
(b) Responsiveness: the predictive issued after consuming y_t must be the one
    the recursion defines at t+1, i.e. it must already reflect y_t. For the
    scale leaves this is an exact equation read from the leaf's own state, so a
    one-step lag (issue #239) is a hard failure, not a tolerance question.
"""
import copy
import math
import random
import pytest

from skaters.api import laplace
from skaters.conjugate import conjugate
from skaters.leaf import leaf, scale_mixture_leaf, garch_leaf
from skaters.transform import difference, ar, holt_linear, standardize, ema_transform

PROBES = (-2.0, -0.5, 0.0, 0.7, 2.5)


def _sig(d):
    return (d.mean, d.var) + tuple(d.cdf(x) for x in PROBES) + tuple(d.logpdf(x) for x in PROBES)


def _series(n=320, seed=11):
    g = random.Random(seed)
    return [g.gauss(0.0, 1.0) for _ in range(n)]


SKATERS = {
    "laplace(1)":       lambda: laplace(1),
    "laplace(3)":       lambda: laplace(3),
    "leaf(3)":          lambda: leaf(3),
    "scale_mixture(3)": lambda: scale_mixture_leaf(3),
    "garch_leaf(3)":    lambda: garch_leaf(3),
    "diff|leaf":        lambda: conjugate(leaf(3), difference(), 3),
    "ar1|leaf":         lambda: conjugate(leaf(3), ar(1), 3),
    "holt|leaf":        lambda: conjugate(leaf(3), holt_linear(0.3, 0.2), 3),
    "ema|std|leaf":     lambda: conjugate(conjugate(leaf(3), standardize(0.05), 3), ema_transform(0.3), 3),
}


def _run(f, ys):
    st, outs = None, []
    for y in ys:
        d, st = f(y, st)
        outs.append([_sig(x) for x in d])
    return outs


@pytest.mark.parametrize("name", list(SKATERS))
def test_no_lookahead(name):
    ys = _series()
    o = 250
    bumped = ys[:o + 1] + [y + 3.0 for y in ys[o + 1:]]
    a = _run(SKATERS[name](), ys)
    b = _run(SKATERS[name](), bumped)
    for t in range(o + 1):
        assert a[t] == b[t], f"{name}: predictive issued at {t} changed when data after {o} changed"
    assert a[o + 1] != b[o + 1], f"{name}: perturbation had no effect, test proves nothing"


@pytest.mark.parametrize("name", list(SKATERS))
def test_predictive_depends_on_latest_observation(name):
    """Weak form of (b): y_t must enter the predictive issued right after it."""
    ys = _series()
    f = SKATERS[name]()
    st = None
    for y in ys[:-1]:
        _, st = f(y, st)
    d0, _ = f(0.0, copy.deepcopy(st))
    d1, _ = f(6.0, copy.deepcopy(st))
    assert _sig(d0[0]) != _sig(d1[0]), f"{name}: predictive ignores the latest observation"


# ---------------------------------------------------------------- exact leaf timing
def test_gaussian_leaf_variance_includes_latest_observation():
    f = leaf(1)
    st = None
    ys = _series(200)
    for y in ys:
        _, st = f(y, st)
    y_new = 4.0
    (d,), _ = f(y_new, copy.deepcopy(st))
    # Welford on all 201 points, independently
    allv = ys + [y_new]
    n = len(allv); mu = sum(allv) / n
    var = sum((x - mu) ** 2 for x in allv) / (n - 1)
    assert abs(d.var - var) <= 1e-9 * var


def test_scale_mixture_leaf_scale_includes_latest_observation():
    f = scale_mixture_leaf(1, scale_alpha=0.1)
    st = None
    for y in _series(200):
        _, st = f(y, st)
    v_prev = st["v"]; n_prev = st["n"]
    y_new = 4.0
    (d,), _ = f(y_new, copy.deepcopy(st))
    a = max(0.1, 1.0 / (n_prev + 1))
    sigma = math.sqrt((1 - a) * v_prev + a * y_new * y_new)
    comps = d.components                      # scales C_i * sigma; C includes 1.0
    assert any(abs(s - sigma) <= 1e-9 * sigma for _, _, s in comps), (sigma, [s for _, _, s in comps])


@pytest.mark.xfail(strict=True, reason="#239: garch_leaf emits sqrt(h_t) (built from r_{t-1}) as the forecast for r_{t+1}")
def test_garch_leaf_scale_is_next_step_conditional_variance():
    """After consuming r_t the leaf forecasts r_{t+1}; its scale must be
    sqrt(omega + alpha r_t^2 + beta h_t), with (omega, alpha, beta, h_t) read from
    the leaf's own state before the call."""
    f = garch_leaf(1)
    st = None
    for y in _series(400):                     # past min_obs, several refits
        _, st = f(y, st)
    om, al, be, h_t = st["omega"], st["alpha"], st["beta"], st["h"]
    r_t = 3.0
    (d,), _ = f(r_t, copy.deepcopy(st))
    expected = math.sqrt(om + al * r_t * r_t + be * h_t)
    comps = d.components
    assert any(abs(s - expected) <= 1e-9 * expected for _, _, s in comps), \
        (expected, sorted(s for _, _, s in comps))


@pytest.mark.xfail(strict=True, reason="#239: a 6-sigma shock moves the next sd 0.82 -> 0.89 (mixture weights only); the scale itself lags one step")
def test_garch_leaf_reacts_to_a_shock_immediately():
    """Behavioural form of the same contract: a 6-sigma shock must widen the
    very next predictive, not the one after."""
    f = garch_leaf(1)
    st = None
    for y in _series(400):
        _, st = f(y, st)
    (d0,), _ = f(0.0, copy.deepcopy(st))
    (d1,), _ = f(6.0, copy.deepcopy(st))
    assert d1.std > 1.2 * d0.std, (d0.std, d1.std)
