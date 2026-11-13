"""gibrat / log_transform: forecasts never cross the bound, the pushforward
is the exact change of variables, and exact=True transforms accept laplace's
tail-spliced predictive."""
import math
import random

import pytest

from skaters import Dist, conjugate, gibrat, laplace, log_transform
from skaters.transform import yeo_johnson


def _rate(n, seed=7, scale=0.05):
    rng = random.Random(seed)
    x, out = 0.0, []
    for _ in range(n):
        x += 0.05 * (-x) + 0.2 * rng.gauss(0.0, 1.0)
        out.append(scale * math.exp(x))
    return out


def _last(f, ys):
    state = None
    for y in ys:
        dists, state = f(y, state)
    return dists


def test_lower_bound_holds_at_every_horizon():
    for d in _last(gibrat(k=3), _rate(200)):
        assert d.quantile(1e-4) > 0.0
        assert d.cdf(0.0) < 1e-9
        assert d.mean > 0.0 and d.std > 0.0


def test_upper_bound_and_shifted_lower_bound():
    ys = [1.0 - y for y in _rate(150)]
    for d in _last(gibrat(k=2, upper=1.0), ys):
        assert d.quantile(1 - 1e-4) < 1.0
    for d in _last(gibrat(lower=-3.0), [y - 3.0 for y in _rate(150)]):
        assert d.quantile(1e-4) > -3.0


def test_observation_on_the_bound_raises():
    forward, _ = log_transform()
    with pytest.raises(ValueError):
        forward(0.0, None)
    forward, _ = log_transform(upper=2.0)
    with pytest.raises(ValueError):
        forward(2.5, None)
    with pytest.raises(ValueError):
        log_transform(lower=0.0, upper=1.0)


def test_pushforward_is_lognormal_closed_form():
    """N(m, s) in log space pushed through exp is LogNormal(m, s): check the
    logpdf (with Jacobian), median and mean against the closed form."""
    m, s = math.log(0.2), 0.4
    _, inverse_k = log_transform()
    d = inverse_k([Dist([(1.0, m, s)])], {})[0]
    for y in (0.08, 0.2, 0.5):
        exact = -math.log(y * s * math.sqrt(2 * math.pi)) - (math.log(y) - m) ** 2 / (2 * s * s)
        assert d.logpdf(y) == pytest.approx(exact, abs=1e-3)   # Jacobian from the 400-knot table
    assert d.quantile(0.5) == pytest.approx(math.exp(m), rel=1e-6)
    assert d.mean == pytest.approx(math.exp(m + s * s / 2), rel=1e-6)


def test_exact_yeo_johnson_accepts_spliced_laplace():
    """exact=True used to read d.components, which laplace's SplicedDist lacks."""
    d = _last(conjugate(laplace(), yeo_johnson(0.0, exact=True), k=1), _rate(120))[0]
    assert d.quantile(0.1) < d.quantile(0.5) < d.quantile(0.9)
    assert d.quantile(0.001) > -1.0
    assert math.isfinite(d.mean) and d.std > 0.0


def test_hand_composition_matches_gibrat():
    ys = _rate(120)
    a = _last(gibrat(), ys)[0]
    b = _last(conjugate(laplace(), log_transform(lower=0.0), k=1), ys)[0]
    for p in (0.05, 0.5, 0.95):
        assert a.quantile(p) == b.quantile(p)
