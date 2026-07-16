"""seasonal_scale: phase-indexed standardization."""
import math
import random

from skaters.dist import Dist
from skaters.transform import seasonal_scale


def _run(ys, period, **kw):
    fwd, inv = seasonal_scale(period, **kw)
    state = None
    outs = []
    for y in ys:
        yp, state = fwd(y, state)
        outs.append(yp)
    return outs, inv, state


def test_phase_variance_is_normalized():
    rng = random.Random(0)
    scales = [0.1, 1.0, 5.0]
    ys = [scales[t % 3] * rng.gauss(0, 1) for t in range(3000)]
    outs, _, _ = _run(ys, 3, alpha=0.05)
    tail = outs[600:]
    for p in range(3):
        v = [x for i, x in enumerate(tail) if (i + 600) % 3 == p]
        sd = math.sqrt(sum(x * x for x in v) / len(v))
        assert 0.8 < sd < 1.25, (p, sd)


def test_inverse_width_tracks_forecast_phase():
    rng = random.Random(1)
    scales = [0.1, 1.0, 5.0]
    ys = [scales[t % 3] * rng.gauss(0, 1) for t in range(3000)]
    _, inv, state = _run(ys, 3, alpha=0.05)
    unit = [Dist.gaussian(0.0, 1.0)]
    # After 3000 observations the next step has phase 3000 % 3 == 0, etc.
    for h_offset in range(3):
        d = inv(unit, state)[0]
        want = scales[(3000 + 0) % 3]
        got = d.std
        assert 0.7 * want < got < 1.4 * want, (want, got)
        break  # h indexing checked separately below
    # Check the three phases via three unit dists at h = 0, 1, 2.
    ds = inv([Dist.gaussian(0.0, 1.0)] * 3, state)
    for h in range(3):
        want = scales[(3000 + h) % 3]
        assert 0.7 * want < ds[h].std < 1.4 * want, (h, want, ds[h].std)


def test_center_recovers_phase_means():
    rng = random.Random(2)
    means = [-4.0, 0.0, 7.0]
    ys = [means[t % 3] + rng.gauss(0, 0.5) for t in range(3000)]
    _, inv, state = _run(ys, 3, alpha=0.05, center=True)
    ds = inv([Dist.gaussian(0.0, 1.0)] * 3, state)
    for h in range(3):
        want = means[(3000 + h) % 3]
        assert abs(ds[h].mean - want) < 0.5, (h, want, ds[h].mean)


def test_constant_series_is_finite():
    ys = [2.5] * 200
    outs, inv, state = _run(ys, 7, alpha=0.05)
    assert all(math.isfinite(x) for x in outs)
    d = inv([Dist.gaussian(0.0, 1.0)], state)[0]
    assert math.isfinite(d.mean) and math.isfinite(d.std)


def test_thin_phases_shrink_to_global():
    # Only two full cycles of a long period: per-phase stats are unreliable,
    # so the width must stay near the global scale rather than collapse.
    rng = random.Random(3)
    ys = [rng.gauss(0, 2.0) for _ in range(104)]
    _, inv, state = _run(ys, 52, alpha=0.05)
    d = inv([Dist.gaussian(0.0, 1.0)], state)[0]
    assert 1.0 < d.std < 4.0, d.std
