"""SplicedDist.affine: conjugating laplace with an affine transform
(standardize, garch, seasonal_scale, ema_transform) calls .affine on the
predictive, which laplace's tail-spliced SplicedDist lacked. The splice is
defined in the body's PIT space, so an affine map moves only the body; the
cdf/quantile/logpdf of the mapped law must equal the change of variables."""
import math
import random

import pytest

from skaters import conjugate, laplace
from skaters.tails import SplicedDist
from skaters.transform import seasonal_scale, standardize


def _series(n, seed=3):
    rng = random.Random(seed)
    x, out = 0.0, []
    for _ in range(n):
        x = 0.9 * x + rng.gauss(0.0, 1.0) * (1.0 + 0.5 * math.sin(len(out) / 7.0))
        out.append(x)
    return out


def _spliced():
    f, st = laplace(), None
    for y in _series(1500):
        d, st = f(y, st)
    assert isinstance(d[0], SplicedDist)
    return d[0]


@pytest.mark.parametrize("a,b", [(2.5, -1.0), (0.1, 3.0), (-1.5, 0.7)])
def test_affine_is_the_change_of_variables(a, b):
    d = _spliced()
    e = d.affine(a, b)
    assert isinstance(e, SplicedDist)
    for p in (0.001, 0.05, 0.5, 0.95, 0.999):
        assert e.quantile(p) == pytest.approx(a * d.quantile(p if a > 0 else 1 - p) + b, rel=1e-6, abs=1e-9)
    for x in (-2.0, 0.3, 4.0):
        assert e.cdf(a * x + b) == pytest.approx(d.cdf(x) if a > 0 else 1 - d.cdf(x), abs=1e-9)
        assert e.logpdf(a * x + b) == pytest.approx(d.logpdf(x) - math.log(abs(a)), abs=1e-6)


def test_affine_rejects_zero():
    with pytest.raises(ValueError):
        _spliced().affine(0.0, 1.0)


@pytest.mark.parametrize("transform", [lambda: standardize(0.05), lambda: seasonal_scale(7)])
def test_affine_transforms_wrap_laplace_past_the_splice(transform):
    """Before the fix this raised AttributeError once the GPD splice was live."""
    f, st = conjugate(laplace(), transform(), k=1), None
    for y in _series(1500):
        d, st = f(y, st)
    assert math.isfinite(d[0].logpdf(0.0))
    assert d[0].quantile(0.1) < d[0].quantile(0.9)
