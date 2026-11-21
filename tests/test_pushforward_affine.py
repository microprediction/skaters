"""PushforwardDist.affine/shift/scale: the law of a*Y + b. Needed so a
pushforward predictive (exact yeo_johnson, log_transform, a spliced law
through a nonlinear inverse) can be handed to standardize, seasonal_scale or
any other affine transform."""
import math
import random

import pytest

from skaters import conjugate, laplace
from skaters.dist import Dist
from skaters.pushforward import PushforwardDist
from skaters.transform import log_transform, standardize, yeo_johnson


def _dists():
    inner = Dist([(0.6, 0.2, 0.7), (0.4, -0.5, 1.3)])
    _, inv_k = yeo_johnson(0.0, exact=True)
    table = inv_k([inner], {})[0]                       # table + inv_fn
    _, inv_log = log_transform()
    analytic = inv_log([inner], {})[0]                  # analytic fwd/inv
    return {"table": table, "analytic": analytic}


@pytest.mark.parametrize("kind", ["table", "analytic"])
@pytest.mark.parametrize("a,b", [(2.5, -1.0), (0.3, 4.0), (-1.7, 0.5)])
def test_affine_is_the_change_of_variables(kind, a, b):
    d = _dists()[kind]
    e = d.affine(a, b)
    assert isinstance(e, PushforwardDist)
    for p in (0.01, 0.2, 0.5, 0.8, 0.99):
        want = a * d.quantile(p if a > 0 else 1.0 - p) + b
        assert e.quantile(p) == pytest.approx(want, rel=1e-7, abs=1e-9)
    for p in (0.05, 0.4, 0.9):
        x = d.quantile(p)
        y = a * x + b
        want_cdf = d.cdf(x) if a > 0 else 1.0 - d.cdf(x)
        assert e.cdf(y) == pytest.approx(want_cdf, abs=1e-7)
        assert e.logpdf(y) == pytest.approx(d.logpdf(x) - math.log(abs(a)), abs=1e-4)
    assert e.mean == pytest.approx(a * d.mean + b, rel=1e-6, abs=1e-9)
    assert e.std == pytest.approx(abs(a) * d.std, rel=1e-6)
    assert e.crps(a * d.quantile(0.3) + b) == pytest.approx(abs(a) * d.crps(d.quantile(0.3)), rel=1e-3)


def test_shift_and_scale():
    d = _dists()["table"]
    assert d.shift(1.5).quantile(0.3) == pytest.approx(d.quantile(0.3) + 1.5)
    assert d.scale(-2.0).quantile(0.3) == pytest.approx(-2.0 * d.quantile(0.7))
    with pytest.raises(ValueError):
        d.scale(0.0)
    with pytest.raises(ValueError):
        d.affine(0.0, 1.0)


def test_standardize_around_exact_yeo_johnson():
    rng = random.Random(7)
    f = conjugate(conjugate(laplace(), yeo_johnson(0.0, exact=True)), standardize(0.05))
    st = None
    for _ in range(300):
        d, st = f(abs(rng.gauss(3.0, 1.0)), st)
    assert isinstance(d[0], PushforwardDist)
    assert d[0].quantile(0.1) < d[0].quantile(0.9)
    assert math.isfinite(d[0].logpdf(d[0].quantile(0.5)))
