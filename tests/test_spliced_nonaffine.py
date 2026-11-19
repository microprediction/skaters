"""Transforms that read mixture components, fed laplace's tail-spliced
predictive. The nonlinear inverses (power_transform, yeo_johnson,
gaussianize) emit the exact pushforward of the spliced law; the k>1
widening of ema_transform, seasonal_difference and seasonal_anchor widens
the body and lets the splice follow it."""
import math
import random

import pytest

from skaters import conjugate, laplace
from skaters.pushforward import PushforwardDist
from skaters.tails import SplicedDist
from skaters.transform import (_widen, ema_transform, gaussianize, power_transform,
                               seasonal_anchor, seasonal_difference, yeo_johnson)


def _series(n, seed=5):
    rng = random.Random(seed)
    x, out = 0.0, []
    for t in range(n):
        x = 0.9 * x + rng.gauss(0.0, 1.0) * (1.0 + 0.5 * math.sin(t / 7.0))
        out.append(x)
    return out


def _run(f, n=1500):
    st, d = None, None
    for y in _series(n):
        d, st = f(y, st)
    return d


def _spliced():
    d = _run(laplace())[0]
    assert isinstance(d, SplicedDist)
    return d


def _sane(d):
    assert math.isfinite(d.logpdf(d.quantile(0.5)))
    qs = [d.quantile(p) for p in (0.001, 0.1, 0.5, 0.9, 0.999)]
    assert all(a < b for a, b in zip(qs, qs[1:]))
    assert math.isfinite(d.mean) and d.std > 0


@pytest.mark.parametrize("make,inv", [
    (lambda: power_transform(0.5), lambda z: math.copysign(abs(z) ** 2.0, z)),
    (lambda: yeo_johnson(0.0), lambda z: math.expm1(z) if z >= 0 else 1.0 - math.sqrt(1.0 - 2.0 * z)),
])
def test_nonlinear_inverse_is_the_exact_pushforward(make, inv):
    d = _spliced()
    _, inverse_k = make()
    e = inverse_k([d], {})[0]
    assert isinstance(e, PushforwardDist)
    for p in (0.001, 0.05, 0.5, 0.95, 0.999):
        assert e.quantile(p) == pytest.approx(inv(d.quantile(p)), rel=1e-4, abs=1e-6)
    for z in (-1.0, 0.2, 1.5):
        assert e.cdf(inv(z)) == pytest.approx(d.cdf(z), abs=1e-3)   # table resolution


def test_widen_moves_the_body_and_keeps_the_splice():
    d = _spliced()
    e = _widen(d, 2.0, 0.5)
    assert isinstance(e, SplicedDist)
    assert (e.t_lo, e.t_up, e.zeta_lo, e.zeta_up) == (d.t_lo, d.t_up, d.zeta_lo, d.zeta_up)
    assert e.body.mean == pytest.approx(d.body.mean + 2.0)
    assert e.body.var == pytest.approx(d.body.var + 0.5)


@pytest.mark.parametrize("name,make,k", [
    ("power_transform", lambda: power_transform(0.5), 1),
    ("yeo_johnson", lambda: yeo_johnson(0.5), 1),
    ("gaussianize", lambda: gaussianize(), 1),
    ("ema_transform", lambda: ema_transform(0.05), 3),
    ("seasonal_difference", lambda: seasonal_difference(2), 3),
    ("seasonal_anchor", lambda: seasonal_anchor(2), 3),
])
def test_conjugated_laplace_runs(name, make, k):
    ds = _run(conjugate(laplace(k), make(), k), n=600)   # splice is live from ~510
    assert len(ds) == k
    for d in ds:
        _sane(d)
