"""Tests for the doob policy — a committed martingale with a learned vol clock."""

import math
import random

from skaters.api import doob, laplace
from skaters.conventions import Skater


def _run_logpdf(make, series, burn=200):
    f = make()
    state, pend, lp, n = None, None, 0.0, 0
    for i, y in enumerate(series):
        if pend is not None and i > burn:
            v = pend[0].logpdf(y)
            lp += v if math.isfinite(v) else -20.0
            n += 1
        d, state = f(y, state)
        pend = d
    return lp / n if n else float("nan")


def test_doob_is_skater_and_valid():
    f = doob(1)
    assert isinstance(f, Skater)
    state = None
    random.seed(0)
    lvl = 0.0
    out = None
    for _ in range(120):
        lvl += random.gauss(0, 1.0)
        out, state = f(lvl, state)
    assert out[0].std > 0 and math.isfinite(out[0].mean)


def test_doob_mean_is_a_martingale():
    # the committed mean must track the last value (random walk), within the
    # blend's tolerance — not drift off or mean-revert.
    f = doob(1)
    state = None
    series = [5.0, 7.0, 6.0, 9.0, 9.0, 4.0, 8.0, 8.0, 8.0, 3.0]
    out = None
    for y in series:
        out, state = f(y, state)
    assert abs(out[0].mean - series[-1]) < 1.5      # anchored near the last level


def test_doob_competitive_with_laplace_on_a_martingale():
    # On a driftless vol-clustered level (its design regime) doob is competitive
    # with the general forecaster — within a small margin. (Its real edge is on
    # actual near-martingale levels; on synthetics the two are ~tied since both
    # now use the CRPS leaf.)
    random.seed(3)
    lvl, vol, series = 0.0, 1.0, []
    for _ in range(700):
        vol = 0.95 * vol + 0.05 + 0.1 * abs(random.gauss(0, vol))
        lvl += random.gauss(0, vol)
        series.append(lvl)
    assert _run_logpdf(doob, series) >= _run_logpdf(lambda: laplace(1), series) - 0.1
