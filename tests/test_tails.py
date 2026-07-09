"""The GPD tail splice (skaters.tails): the conditional tail fit."""
import math
import random

from skaters import laplace
from skaters.dist import Dist
from skaters.tails import SplicedDist, gpdtails, _phi, _phi_inv


def _spliced_example():
    """A hand-built splice around a unit Gaussian body."""
    body = Dist.gaussian(0.0, 1.0)
    return SplicedDist(body, t_lo=-2.054, t_up=2.054,
                       zeta_lo=0.02, zeta_up=0.02,
                       g_lo=0.1, s_lo=0.6, g_up=0.2, s_up=0.7)


def test_phi_inv_roundtrip():
    for p in (1e-9, 1e-4, 0.02425, 0.3, 0.5, 0.7, 0.97575, 1 - 1e-4, 1 - 1e-9):
        assert abs(_phi(_phi_inv(p)) - p) < 1e-10 * max(p, 1 - p, 1e-3)


def test_spliced_cdf_is_a_cdf():
    d = _spliced_example()
    xs = [x / 10.0 for x in range(-80, 81)]
    cs = [d.cdf(x) for x in xs]
    assert all(0.0 <= c <= 1.0 for c in cs)
    assert all(b >= a - 1e-12 for a, b in zip(cs, cs[1:]))   # monotone
    assert d.cdf(-8.0) < 1e-3 and d.cdf(8.0) > 1 - 1e-3


def test_spliced_density_matches_cdf():
    """pdf must be the derivative of cdf (checked by central differences),
    which also verifies total mass — the rescale constant is doing its job."""
    d = _spliced_example()
    h = 1e-5
    for x in (-3.5, -2.5, -1.0, 0.0, 1.3, 2.5, 4.0):
        num = (d.cdf(x + h) - d.cdf(x - h)) / (2 * h)
        assert abs(num - d.pdf(x)) < 1e-3 * max(d.pdf(x), 1e-6)


def test_spliced_quantile_roundtrip():
    d = _spliced_example()
    for p in (0.001, 0.005, 0.02, 0.1, 0.5, 0.9, 0.98, 0.995, 0.999):
        assert abs(d.cdf(d.quantile(p)) - p) < 1e-6


def test_laplace_emits_spliced_dists_after_warmup():
    rng = random.Random(5)
    f = laplace(1)
    state = None
    x = 0.0
    for _ in range(700):
        x = 0.5 * x + rng.gauss(0, 1)
        dists, state = f(x, state)
    assert isinstance(dists[0], SplicedDist)
    assert math.isfinite(dists[0].logpdf(x))
    assert math.isfinite(dists[0].crps(x))
    # tails="gaussian" opts out
    f0 = laplace(1, tails="gaussian")
    s0 = None
    for _ in range(700):
        _, s0 = f0(0.0, s0)


def test_z_tail_honesty_on_heavy_tailed_stream():
    """The point of the splice: erfc on the parade z must keep its promise
    at 1e-2/1e-3 on a heavy-tailed stream, where the Gaussian read runs hot."""
    rng = random.Random(9)
    f = laplace(1)
    state = None
    n = a2 = a3 = 0
    for t in range(40000):
        # Student-t-ish innovations: Gaussian with occasional 3x scale
        s = 3.0 if rng.random() < 0.05 else 1.0
        y = rng.gauss(0, s)
        _, state = f(y, state)
        z = state["z"][0]
        if z is not None and t > 2000:
            n += 1
            p = math.erfc(abs(z) / math.sqrt(2.0))
            if p < 1e-2:
                a2 += 1
            if p < 1e-3:
                a3 += 1
    assert n > 30000
    assert a2 / n < 2.5e-2
    assert a3 / n < 3.5e-3


def test_state_is_pure_data():
    import json
    rng = random.Random(3)
    f = gpdtails(lambda y, s: ([Dist.gaussian(0.0, 1.0)], s), k=1)
    state = None
    for _ in range(800):
        _, state = f(rng.gauss(0, 1), state)
    tails = state["tails"]
    json.dumps(tails)          # tail state must be JSON-serializable
    assert tails[0]["up"]["t"] is not None
