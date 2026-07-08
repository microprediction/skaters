"""Extreme finite inputs: no finite float may crash or poison the tree.

Found 2026-07-08 while hardening timemachines. Three failure modes on
huge-but-finite observations, all fixed by the parade input gate (state
sanity, part two) plus a NaN guard in ``Dist.prune``:

1. A 1e300 tick raised OverflowError inside the AR inverse (Python
   floats raise on ``**`` overflow where ``*`` would give inf).
2. A 1e100 tick did not raise but silently drove the predictive mean to
   NaN, which is arguably worse.
3. Once components went NaN, ``Dist.prune`` crashed with a TypeError:
   its pair-selection scan never assigned ``best_i`` because every NaN
   comparison is False.

The gate is magnitude-relative (twelve orders above the current
predictive level, absolute cap 1e60), NOT sigma-relative: after a
degenerate-variance stretch a legitimate value sits billions of sigmas
out and must pass. The tests at the bottom pin that identity property.
"""

import math

from skaters import laplace
from skaters.dist import Dist

BASE = [math.sin(0.1 * t) for t in range(200)]


def _feed(ys, k=1):
    f, st = laplace(k), None
    for y in ys:
        dists, st = f(y, st)
    return dists, st


def _all_finite(dists):
    return all(math.isfinite(d.mean) and math.isfinite(d.std) for d in dists)


def test_1e300_spike_does_not_crash():
    dists, st = _feed(BASE + [1e300] + BASE)
    assert _all_finite(dists)


def test_1e100_spike_keeps_predictive_finite():
    dists, _ = _feed(BASE + [1e100] + BASE)
    assert _all_finite(dists)


def test_prune_survives_nan_components():
    d = Dist([(0.5, float("nan"), 1.0)] + [(0.5 / 30, float(i), 1.0)
                                           for i in range(30)])
    assert len(d.prune(8)) <= 8


def test_relentless_extremes():
    for ys in ([1e300] * 100,
               [10.0 ** (t % 280) for t in range(300)],
               [10.0 ** -(t % 280) for t in range(300)],
               BASE + [-1e300, 1e300] * 3 + BASE):
        dists, _ = _feed(ys)
        assert _all_finite(dists)


def test_spike_still_reads_as_maximal_surprise():
    """The gate must not blunt the diagnostics: PIT/z see the raw y."""
    f, st = laplace(1), None
    for y in BASE:
        _, st = f(y, st)
    _, st = f(1e300, st)
    assert abs(st["z"][0]) > 6.9


def test_gate_passes_legitimate_recovery_from_degenerate_variance():
    """After a stretch of zeros the predictive variance collapses; a real
    value arriving then is billions of sigmas out and must NOT be gated
    (this killed a sigma-relative gate design)."""
    dists, st = _feed([0.0] * 100 + [35.0] * 30)
    assert abs(dists[0].mean - 35.0) < 1.0


def test_gate_is_identity_on_ultra_predictable_streams():
    """A date-like stream has predictive std far below its step size; its
    steps are legitimate and the forecast must track them exactly."""
    dists, _ = _feed([736000.0 + t for t in range(300)])
    assert abs(dists[0].mean - 736300.0) < 1.0
