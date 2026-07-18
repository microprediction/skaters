"""The diffuse floor: laplace must never emit a predictive so narrow that a jump
detonates the log-score.

Real FRED series triggered this in the study (WLCFOCEL, USINTDMRKTJPY, the H41RES*
Fed balance-sheet series): a long near-constant run collapses the predictive scale
toward zero, then one jump gives a logpdf of ~-1e23. Those series live in the
gitignored FRED cache and are screened out of the *study* as out-of-scope, so
here we reproduce the same failure mode synthetically and assert the *core*
forecaster degrades gracefully once any scale has been seen.
"""
import math
import random

from skaters import laplace


def _roll(changes, diffuse):
    f = laplace(1, diffuse=diffuse)
    state = None
    pend = None
    lps = []
    for y in changes:
        if pend is not None:
            lps.append(pend[0].logpdf(y))
        pend, state = f(y, state)
    return lps


def test_floor_bounds_a_collapse_then_jump():
    """After a scale has been seen, a large jump costs tens of nats, not 1e20."""
    rng = random.Random(0)
    ch = [rng.gauss(0.0, 1.0) for _ in range(400)] + [1.0e4] + [rng.gauss(0.0, 1.0) for _ in range(10)]
    lps = _roll(ch, diffuse=1e-12)
    assert all(math.isfinite(v) for v in lps)
    assert min(lps) > -1.0e3        # bounded — no detonation


def test_floor_is_negligible_on_a_normal_series():
    """At the default weight the floor barely moves a well-behaved series."""
    rng = random.Random(1)
    ch = [rng.gauss(0.0, 1.0) for _ in range(500)]
    on = _roll(ch, diffuse=1e-12)
    off = _roll(ch, diffuse=0.0)
    m_on = sum(on) / len(on)
    m_off = sum(off) / len(off)
    assert abs(m_on - m_off) < 5e-3


def test_floor_preserves_point_interval_and_crps():
    """The floor touches logpdf/cdf only; mean, std, quantiles, CRPS are the body's."""
    rng = random.Random(2)
    ch = [rng.gauss(0.0, 1.0) for _ in range(300)]
    fa, fb = laplace(1, diffuse=1e-12), laplace(1, diffuse=0.0)
    sa = sb = None
    da = db = None
    for y in ch:
        da, sa = fa(y, sa)
        db, sb = fb(y, sb)
    a, b = da[0], db[0]
    assert a.mean == b.mean
    assert a.std == b.std
    for p in (0.025, 0.5, 0.975):
        assert a.quantile(p) == b.quantile(p)
    y0 = a.mean
    assert a.crps(y0) == b.crps(y0)
    assert math.isfinite(a.logpdf(y0))
