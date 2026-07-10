"""Deployment robustness of the GPD tail splice (0.13.0 default path).

Adversarial streams a production deployment will eventually meet: constant
series, lattice/repeating values, monster spikes, scale collapse and
recovery, vol-regime whiplash, monotone trends. Throughout: forecasts stay
finite and well-formed, the spliced cdf stays a cdf, quantiles stay
ordered, the state stays serializable, and the detector recovers after the
insult (no permanent deafness, no permanent alarm).
"""
import json
import math
import random

from skaters import laplace
from skaters.dist import Dist
from skaters.tails import SplicedDist


def _assert_wellformed(d, y_near):
    lp = d.logpdf(y_near)
    assert lp == lp                      # not NaN (-inf tolerated: hard atom)
    c = d.cdf(y_near)
    assert 0.0 <= c <= 1.0
    qs = [d.quantile(p) for p in (0.001, 0.25, 0.5, 0.75, 0.999)]
    assert all(math.isfinite(q) for q in qs)
    assert all(b >= a - 1e-9 for a, b in zip(qs, qs[1:]))   # ordered
    probes = [qs[0] - 1.0] + qs + [qs[-1] + 1.0]
    cs = [d.cdf(x) for x in probes]
    assert all(b >= a - 1e-9 for a, b in zip(cs, cs[1:]))   # cdf monotone


def _soak(ys, check_every=997):
    f = laplace(1)
    state = None
    for t, y in enumerate(ys):
        dists, state = f(y, state)
        if t % check_every == 0 and t > 0:
            _assert_wellformed(dists[0], y)
    json.dumps(state["tails"] if "tails" in state
               else state["base"]["tails"])  # tail state serializable
    return dists, state


def test_constant_series():
    """A constant stream must never activate a degenerate splice."""
    dists, state = _soak([3.7] * 4000)
    _assert_wellformed(dists[0], 3.7)


def test_lattice_series():
    """Repeats plus exact grid jumps (the sticky regime)."""
    rng = random.Random(17)
    v, ys = 1.0, []
    for _ in range(6000):
        if rng.random() >= 0.7:
            v += rng.choice([-0.25, 0.25, 0.5])
        ys.append(v)
    dists, _ = _soak(ys)
    _assert_wellformed(dists[0], ys[-1])


def test_monster_spike_then_recovery():
    """A 1e9-sigma spike must not poison the fit or the state: forecasts
    stay finite immediately after, and within a memory the alarm rate on
    quiet data returns to quiet levels (no deafness, no permanent alarm)."""
    rng = random.Random(23)
    f = laplace(1)
    state = None
    for _ in range(3000):
        _, state = f(rng.gauss(0, 1), state)
    dists, state = f(1e9, state)                 # the insult
    _assert_wellformed(dists[0], 0.0)
    alarms = n = 0
    for i in range(3000):                        # quiet again
        y = rng.gauss(0, 1)
        dists, state = f(y, state)
        z = state["z"][0]
        if i > 1000 and z is not None:
            n += 1
            if math.erfc(abs(z) / math.sqrt(2.0)) < 1e-2:
                alarms += 1
        if i % 500 == 0:
            _assert_wellformed(dists[0], y)
    assert n > 1500
    assert alarms / n < 0.06                     # recovered, not deaf/manic


def test_scale_collapse_and_recovery():
    """N(0,1) -> constant (scale collapse) -> N(0,1): the splice must ride
    through the collapse without NaNs and re-emit sane forecasts after."""
    rng = random.Random(31)
    ys = ([rng.gauss(0, 1) for _ in range(2000)] + [0.0] * 2000
          + [rng.gauss(0, 1) for _ in range(2000)])
    dists, _ = _soak(ys)
    _assert_wellformed(dists[0], 0.0)


def test_vol_regime_whiplash_and_trend():
    """Alternating x10 vol regimes on a strong trend."""
    rng = random.Random(41)
    ys, lvl = [], 0.0
    for t in range(8000):
        vol = 10.0 if (t // 700) % 2 else 1.0
        lvl += 0.05 + rng.gauss(0, vol)
        ys.append(lvl)
    dists, _ = _soak(ys)
    _assert_wellformed(dists[0], ys[-1])


def test_spliced_dist_extreme_params():
    """SplicedDist stays well-formed across the parameter corners a
    drifting fit can reach: tiny/huge zeta, negative/heavy gamma, tiny
    sigma."""
    body = Dist.gaussian(0.0, 1.0)
    corners = [
        (1e-12, 1e-12, 0.0, 1.0, 0.0, 1.0),
        (0.2, 0.2, -0.9, 0.3, -0.9, 0.3),
        (0.02, 0.02, 5.0, 1e-6, 5.0, 1e6),
        (0.4, 0.001, 0.5, 2.0, -0.4, 1e-6),
    ]
    for zl, zu, gl, sl, gu, su in corners:
        d = SplicedDist(body, -2.054, 2.054, zl, zu, gl, sl, gu, su)
        _assert_wellformed(d, 0.3)
        _assert_wellformed(d, -5.0)
        _assert_wellformed(d, 5.0)
