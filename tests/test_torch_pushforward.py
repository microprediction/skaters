"""skaters.torch pushforward: TorchPushforwardDist agrees with the reference
PushforwardDist (including affine/shift/scale, test_pushforward_affine.py),
and a log score through an exact inverse differentiates in the map."""
import math

import pytest

torch = pytest.importorskip("torch")

from skaters.dist import Dist                                          # noqa: E402
from skaters.transform import log_transform, yeo_johnson              # noqa: E402
from skaters.torch import from_reference                              # noqa: E402
from skaters.torch.dist import TorchDist                              # noqa: E402
from skaters.torch.pushforward import TorchPushforwardDist            # noqa: E402

INNER = Dist([(0.6, 0.2, 0.7), (0.4, -0.5, 1.3)])


def _pairs():
    _, ref_yj = yeo_johnson(0.0, exact=True)
    _, ref_log = log_transform()
    t_yj = from_reference("yeo_johnson", lmbda=0.0, exact=True)
    t_log = from_reference("log_transform")
    tin = TorchDist.from_reference(INNER)
    return {"table": (ref_yj([INNER], {})[0], t_yj.inverse_k([tin], {})[0]),
            "analytic": (ref_log([INNER], {})[0], t_log.inverse_k([tin], {})[0])}


def _same(r, t):
    for p in (0.01, 0.2, 0.5, 0.8, 0.99):
        assert float(t.quantile(p)) == pytest.approx(r.quantile(p), rel=1e-9, abs=1e-12)
    for p in (0.05, 0.4, 0.9):
        x = r.quantile(p)
        assert float(t.cdf(x)) == pytest.approx(r.cdf(x), abs=1e-12)
        assert float(t.logpdf(x)) == pytest.approx(r.logpdf(x), abs=1e-9)
        assert float(t.crps(x)) == pytest.approx(r.crps(x), rel=1e-9, abs=1e-12)
    assert float(t.mean) == pytest.approx(r.mean, rel=1e-9, abs=1e-12)
    assert float(t.std) == pytest.approx(r.std, rel=1e-9)


@pytest.mark.parametrize("kind", ["table", "analytic"])
def test_matches_reference(kind):
    r, t = _pairs()[kind]
    assert isinstance(t, TorchPushforwardDist)
    _same(r, t)


@pytest.mark.parametrize("kind", ["table", "analytic"])
@pytest.mark.parametrize("a,b", [(2.5, -1.0), (0.3, 4.0), (-1.7, 0.5)])
def test_affine_matches_reference(kind, a, b):
    r, t = _pairs()[kind]
    _same(r.affine(a, b), t.affine(a, b))


def test_shift_and_scale():
    r, t = _pairs()["table"]
    _same(r.shift(1.5), t.shift(1.5))
    _same(r.scale(-2.0), t.scale(-2.0))
    with pytest.raises(ValueError):
        t.scale(0.0)


def test_log_score_differentiates_in_the_map():
    t = from_reference("yeo_johnson", lmbda=0.5, exact=True)
    d = t.inverse_k([TorchDist.from_reference(INNER)], {})[0]
    loss = -d.logpdf(0.7) - d.logpdf(-0.4)
    loss.backward()
    g = t.lmbda.grad
    assert g is not None and math.isfinite(float(g)) and float(g) != 0.0
