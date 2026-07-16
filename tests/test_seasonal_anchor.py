"""seasonal_anchor: hedged seasonal location transform."""
import math
import random

from skaters.dist import Dist
from skaters.transform import seasonal_anchor, seasonal_difference


def _run(ys, period, **kw):
    fwd, inv = seasonal_anchor(period, **kw)
    state = None
    outs = []
    for y in ys:
        yp, state = fwd(y, state)
        outs.append(yp)
    return outs, inv, state


def test_weight_zero_matches_seasonal_difference():
    rng = random.Random(0)
    ys = [math.sin(2 * math.pi * t / 7) + rng.gauss(0, 0.3) for t in range(200)]
    a, _, _ = _run(ys, 7, weight=0.0)
    fwd, _ = seasonal_difference(7)
    state = None
    b = []
    for y in ys:
        yp, state = fwd(y, state)
        b.append(yp)
    # identical once the buffer holds a full period
    assert all(abs(x - y) < 1e-12 for x, y in zip(a[8:], b[8:]))


def test_hedge_beats_naive_on_noisy_seasonal():
    rng = random.Random(1)
    season = [5.0 * math.sin(2 * math.pi * p / 12) for p in range(12)]
    ys = [season[t % 12] + rng.gauss(0, 1.0) for t in range(2400)]
    hedged, _, _ = _run(ys, 12, alpha=0.2, weight=0.5)
    naive, _, _ = _run(ys, 12, weight=0.0)
    vh = sum(x * x for x in hedged[400:]) / len(hedged[400:])
    vn = sum(x * x for x in naive[400:]) / len(naive[400:])
    assert vh < vn * 0.85, (vh, vn)   # averaging same-phase noise must help


def test_inverse_shifts_by_anchor():
    rng = random.Random(2)
    season = [3.0 * math.cos(2 * math.pi * p / 5) for p in range(5)]
    ys = [season[t % 5] + rng.gauss(0, 0.2) for t in range(500)]
    _, inv, state = _run(ys, 5, alpha=0.2, weight=0.5)
    ds = inv([Dist.gaussian(0.0, 1.0)] * 3, state)
    for h in range(3):
        want = season[(500 + h) % 5]
        assert abs(ds[h].mean - want) < 0.5, (h, want, ds[h].mean)


def test_inverse_beyond_period_inflates_variance():
    rng = random.Random(3)
    ys = [rng.gauss(0, 1.0) for _ in range(50)]
    _, inv, state = _run(ys, 4, alpha=0.2, weight=0.5)
    ds = inv([Dist.gaussian(0.0, 1.0)] * 6, state)   # h=4,5 recover through h=0,1
    assert ds[5].var > ds[0].var                      # anchor uncertainty convolved
    assert all(math.isfinite(d.mean) and math.isfinite(d.std) for d in ds)
