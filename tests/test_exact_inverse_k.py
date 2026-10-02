"""Tier 1: multi-step inverse_k against independent oracles, on NON-degenerate inputs.

Two oracle families, neither of which calls inverse_k:

1. Forward-simulation (dgp.propagated_moments). For a transform whose forward
   map is affine in y, the forward recursion alone determines what y_{t+h+1}
   is as a function of the future innovations. Mean and variance follow by
   linearity. Where a textbook closed form exists (ETS A,N,N and A,A,N, plain
   cumsum) the oracle is checked against it first, so the oracle itself is
   under test too.

2. Frozen-coefficient closed forms, for transforms whose forward re-estimates
   coefficients from y (AR by RLS) or whose documented inverse contract fixes
   the coefficients at the origin (standardize, OU). The formula is the
   documented contract evaluated by hand.

Every schedule has UNEQUAL per-horizon variances and NONZERO means. The old
tests fed the same Dist at every horizon, which is the one input on which a
wrong variance formula agrees with the right one.

Variance and mean propagation both follow the forward recursion everywhere
(#245 ar/grouped_ar, #242 holt, #253 theta, #254 ema, #255 fractional_difference,
#256 ou, #257 drift, #258 seasonal_anchor). theta's variance is held to 3% because
the running-OLS slope's O(1/t) response is dropped; theta's deterministic path is
the Theta method's own forecast function, not the recursion's, and stays a strict
xfail by design. The mean part changes laplace's
multi-step means through the fast_slow chains (standardize feeds a nonzero mean
into the outer transform), which is why it was evaluated on the harness
separately from the variance part.
"""
import math
import pytest

from skaters.dist import Dist
from skaters.transform import (difference, drift, holt_linear, ema_transform, theta,
                               ou_transform, seasonal_difference, seasonal_anchor,
                               fractional_difference, standardize, ar, grouped_ar)
import dgp

SCHEDULES = {
    "increasing": [1.0, 4.0, 9.0, 16.0, 25.0],
    "decreasing": [25.0, 16.0, 9.0, 4.0, 1.0],
    "bumpy":      [1.0, 0.25, 9.0, 1.0, 4.0],
}
MEANS = [0.3, -0.2, 0.5, 0.1, -0.4]
H = 5
REL = 1e-9


def _dists(means, vars_):
    return [Dist.gaussian(m, math.sqrt(v)) for m, v in zip(means, vars_)]


def _close(a, b, rel=REL):
    return abs(a - b) <= rel * max(1.0, abs(a), abs(b))


def _history(seed=3, n=60):
    """A short series with level, trend and noise so transform states are non-trivial."""
    import random
    g = random.Random(seed)
    y, v = [], 10.0
    for t in range(n):
        v += 0.05 + g.gauss(0.0, 0.5)
        y.append(v)
    return y


def _xf(reason):
    return pytest.mark.xfail(strict=True, reason=reason)


# --------------------------------------------------- oracle self-checks
@pytest.mark.parametrize("sched", list(SCHEDULES))
def test_oracle_matches_textbook_ets_ann(sched):
    v = SCHEDULES[sched]
    tx = ema_transform(0.3)
    st = dgp.forward_state(tx, _history())
    _, var_fwd, _ = dgp.propagated_moments(tx, st, MEANS, v)
    for a, b in zip(var_fwd, dgp.ets_ann_var(0.3, v)):
        assert _close(a, b)


@pytest.mark.parametrize("sched", list(SCHEDULES))
def test_oracle_matches_textbook_ets_aan(sched):
    v = SCHEDULES[sched]
    tx = holt_linear(0.3, 0.2)
    st = dgp.forward_state(tx, _history())
    _, var_fwd, _ = dgp.propagated_moments(tx, st, MEANS, v)
    for a, b in zip(var_fwd, dgp.ets_aan_var(0.3, 0.3 * 0.2, v)):
        assert _close(a, b)


@pytest.mark.parametrize("sched", list(SCHEDULES))
def test_oracle_matches_cumsum_for_difference(sched):
    v = SCHEDULES[sched]
    tx = difference()
    st = dgp.forward_state(tx, _history())
    _, var_fwd, _ = dgp.propagated_moments(tx, st, MEANS, v)
    for h in range(H):
        assert _close(var_fwd[h], sum(v[:h + 1]))


# --------------------------------------------------- forward-simulation oracle
FORWARD_LINEAR = {
    "difference":            lambda: difference(),
    "drift":                 lambda: drift(alpha=0.01, shrinkage=0.0),
    "drift_shrink":          lambda: drift(alpha=0.01, shrinkage=0.002),
    "holt_linear":           lambda: holt_linear(0.3, 0.2),
    "ema_transform":         lambda: ema_transform(0.3),
    "theta":                 lambda: theta(0.2),
    "seasonal_difference":   lambda: seasonal_difference(3),
    "seasonal_anchor":       lambda: seasonal_anchor(3, alpha=0.3, weight=0.5),
    "fractional_difference": lambda: fractional_difference(0.4, window=20),
}

VAR_XFAIL = {}   # every forward-linear inverse now matches its own forward recursion
MEAN_XFAIL = {}   # earlier innovation means are carried through the learned state too


def _params(xfails):
    return [pytest.param(n, marks=_xf(xfails[n])) if n in xfails else n for n in FORWARD_LINEAR]


@pytest.mark.parametrize("sched", list(SCHEDULES))
@pytest.mark.parametrize("name", [n for n in _params(MEAN_XFAIL) if n != "theta"])
def test_inverse_mean_matches_forward_recursion(name, sched):
    tx = FORWARD_LINEAR[name]()
    st = dgp.forward_state(tx, _history())
    v = SCHEDULES[sched]
    mean_o, _, _ = dgp.propagated_moments(tx, st, MEANS, v)
    out = tx[1](_dists(MEANS, v), st)
    for h in range(H):
        assert _close(out[h].mean, mean_o[h], 1e-7), (name, h, out[h].mean, mean_o[h])


@pytest.mark.parametrize("sched", list(SCHEDULES))
@pytest.mark.parametrize("name", [n for n in _params(VAR_XFAIL) if n != "theta"])
def test_inverse_variance_matches_forward_recursion(name, sched):
    tx = FORWARD_LINEAR[name]()
    st = dgp.forward_state(tx, _history())
    v = SCHEDULES[sched]
    _, var_o, _ = dgp.propagated_moments(tx, st, MEANS, v)
    out = tx[1](_dists(MEANS, v), st)
    for h in range(H):
        assert _close(out[h].var, var_o[h], 1e-7), (name, h, out[h].var, var_o[h])


@pytest.mark.parametrize("sched", list(SCHEDULES))
def test_theta_inverse_variance_is_ses_closed_form(sched):
    """theta = SES + half OLS slope. The inverse carries the SES response alpha
    exactly (c_0 = 1, c_j = alpha, i.e. the ETS(A,N,N) form, issue #253)."""
    v = SCHEDULES[sched]
    tx = theta(0.2)
    st = dgp.forward_state(tx, _history())
    out = tx[1](_dists(MEANS, v), st)
    for h, e in enumerate(dgp.ets_ann_var(0.2, v)):
        assert _close(out[h].var, e), (h, out[h].var, e)


@_xf("By design: the Theta method's point forecast ses + h*b/2 (Assimakopoulos & "
     "Nikolopoulos 2000, as the docstring states) is not the forward recursion's own "
     "zero-innovation path (with eps = 0, ses moves by alpha*b/2 per step and the OLS "
     "slope re-estimates). The innovation means ARE carried with the SES weights; the "
     "deterministic path differs by ~0.05 at h = 1 here. A forecast-function change, "
     "not a propagation fix, and it would move laplace's theta candidates' means.")
@pytest.mark.parametrize("sched", list(SCHEDULES))
def test_theta_inverse_mean_matches_forward_recursion(sched):
    v = SCHEDULES[sched]
    tx = theta(0.2)
    st = dgp.forward_state(tx, _history())
    mean_o, _, _ = dgp.propagated_moments(tx, st, MEANS, v)
    out = tx[1](_dists(MEANS, v), st)
    for h in range(H):
        assert _close(out[h].mean, mean_o[h], 1e-7), (h, out[h].mean, mean_o[h])


@pytest.mark.parametrize("sched", list(SCHEDULES))
def test_theta_inverse_variance_near_forward_recursion(sched):
    """The running-OLS slope also responds to future innovations, by O(1/t)
    (~1e-3 at t=60). That term is dropped, so agreement with the full forward
    recursion is to 3%, not 1e-7."""
    v = SCHEDULES[sched]
    tx = theta(0.2)
    st = dgp.forward_state(tx, _history())
    _, var_o, _ = dgp.propagated_moments(tx, st, MEANS, v)
    out = tx[1](_dists(MEANS, v), st)
    for h in range(H):
        assert abs(out[h].var / var_o[h] - 1.0) < 0.03, (h, out[h].var, var_o[h])


# --------------------------------------------------- frozen-coefficient closed forms
def _ar_state(phi, buf):
    p = len(phi)
    return {"buffer": list(buf), "phi": list(phi), "P": [1.0] * (p * p), "n": len(buf)}


@pytest.mark.parametrize("sched", list(SCHEDULES))
@pytest.mark.parametrize("phi", [[0.5], [0.9], [0.5, -0.3]], ids=["ar1_0.5", "ar1_0.9", "ar2"])
def test_ar_inverse_variance_is_psi_convolution(phi, sched):
    """Issue #245 (fixed): Var = sum_i psi_{h-i}^2 v_i. Before the fix, phi=0.5 and
    v=[1,4,9] gave 11.81 against 10.06 exact; v=[9,4,1] gave 1.31 against 2.56."""
    v = SCHEDULES[sched]
    _, inv = ar(order=len(phi))
    st = _ar_state(phi, [0.2, -0.1][:len(phi)])
    out = inv(_dists(MEANS, v), st)
    exp = dgp.ar_var(phi, v)
    for h in range(H):
        assert _close(out[h].var, exp[h]), (h, out[h].var, exp[h])


@pytest.mark.parametrize("phi", [[0.5], [0.5, -0.3]], ids=["ar1", "ar2"])
def test_ar_inverse_mean_is_ar_recursion(phi):
    v = SCHEDULES["bumpy"]
    _, inv = ar(order=len(phi))
    buf = [0.2, -0.1][:len(phi)]
    st = _ar_state(phi, buf)
    out = inv(_dists(MEANS, v), st)
    hist = list(buf)
    for h in range(H):
        m = MEANS[h] + sum(phi[j] * hist[-1 - j] for j in range(len(phi)))
        hist.append(m)
        assert _close(out[h].mean, m), (h, out[h].mean, m)


@pytest.mark.parametrize("sched", list(SCHEDULES))
def test_grouped_ar_inverse_variance_is_psi_convolution(sched):
    """grouped_ar(max_lag=3): lag 1 -> group 0, lags 2-3 -> group 1 (per its docstring)."""
    v = SCHEDULES[sched]
    _, inv = grouped_ar(max_lag=3)
    theta_ = [0.4, 0.1]
    phi = [theta_[0], theta_[1], theta_[1]]
    st = {"buffer": [0.3, -0.2, 0.1], "theta": theta_, "P": [1.0, 0.0, 0.0, 1.0], "n": 3}
    out = inv(_dists(MEANS, v), st)
    exp = dgp.ar_var(phi, v)
    for h in range(H):
        assert _close(out[h].var, exp[h]), (h, out[h].var, exp[h])


@pytest.mark.parametrize("sched", list(SCHEDULES))
def test_standardize_inverse_is_frozen_affine(sched):
    v = SCHEDULES[sched]
    _, inv = standardize(alpha=0.05)
    st = {"mu": 2.5, "var": 4.0}
    out = inv(_dists(MEANS, v), st)
    for h in range(H):
        assert _close(out[h].mean, 2.0 * MEANS[h] + 2.5)
        assert _close(out[h].var, 4.0 * v[h])


OU_PHI = 0.8
OU_STATE = {"m": 1.0, "fc": 1.4, "y": 1.5}


def _ou_var(v):
    return [sum(OU_PHI ** (2 * (h - i)) * v[i] for i in range(h + 1)) for h in range(len(v))]


@pytest.mark.parametrize("sched", list(SCHEDULES))
def test_ou_inverse_variance_under_its_frozen_m_contract(sched):
    """Issue #256 (fixed): the per-horizon scale now gives sum_i phi^2(h-i) v_i."""
    v = SCHEDULES[sched]
    _, inv = ou_transform(kappa=1.0 - OU_PHI, alpha=0.05)
    out = inv(_dists(MEANS, v), OU_STATE)
    exp = _ou_var(v)
    for h in range(H):
        assert _close(out[h].var, exp[h]), (h, out[h].var, exp[h])


# --------------------------------------------------- the masking case, on record
@pytest.mark.parametrize("name", ["ar1", "ar2", "grouped_ar", "ou"])
def test_245_class_is_exact_for_equal_variances(name):
    """The #245 class agrees with the oracle when every horizon has the same
    variance. That is why an equal-variance schedule must never be the only
    multi-step check. (The #242 class is wrong even here, so it has no such test.)"""
    v = [2.0] * H
    if name == "ar1":
        _, inv = ar(1); st = _ar_state([0.5], [0.2]); exp = dgp.ar_var([0.5], v)
    elif name == "ar2":
        _, inv = ar(2); st = _ar_state([0.5, -0.3], [0.2, -0.1]); exp = dgp.ar_var([0.5, -0.3], v)
    elif name == "grouped_ar":
        _, inv = grouped_ar(max_lag=3)
        st = {"buffer": [0.3, -0.2, 0.1], "theta": [0.4, 0.1], "P": [1.0, 0.0, 0.0, 1.0], "n": 3}
        exp = dgp.ar_var([0.4, 0.1, 0.1], v)
    else:
        _, inv = ou_transform(kappa=1.0 - OU_PHI, alpha=0.05); st = OU_STATE; exp = _ou_var(v)
    out = inv(_dists(MEANS, v), st)
    for h in range(H):
        assert _close(out[h].var, exp[h]), (name, h, out[h].var, exp[h])
