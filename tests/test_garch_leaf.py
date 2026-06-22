"""Tests for the GARCH(1,1)-t terminal leaf and laplace(leaf=garch_leaf)."""

import math
import random

from skaters import garch_leaf, laplace
from skaters.leaf import scale_mixture_leaf


def _garch_t(seed, n=2500, omega=0.05, alpha=0.08, beta=0.90, nu=6):
    rng = random.Random(seed)
    h = omega / max(1e-6, 1 - alpha - beta)
    out = []
    for _ in range(n):
        g = rng.gauss(0, 1)
        chi = sum(rng.gauss(0, 1) ** 2 for _ in range(nu))
        t = (g / math.sqrt(chi / nu)) * math.sqrt((nu - 2) / nu) if chi > 0 else g
        r = math.sqrt(h) * t
        out.append(r)
        h = omega + alpha * (r * r) + beta * h
    return out


def _ll(make, series, burn=300):
    f = make()
    st = None
    pend = None
    lp = n = 0.0
    for i, y in enumerate(series):
        if pend is not None and i > burn:
            v = pend[0].logpdf(y)
            lp += v if math.isfinite(v) else -20.0
            n += 1
        pend, st = f(y, st)
    return lp / n


class TestGarchLeaf:

    def test_runs_and_emits_valid_dists(self):
        f = garch_leaf(k=2)
        st = None
        out = None
        for y in _garch_t(1):
            out, st = f(y, st)
        assert len(out) == 2
        assert all(math.isfinite(d.mean) and d.std > 0 for d in out)

    def test_fits_mean_reverting_variance(self):
        """After refits, alpha+beta < 1 (genuine GARCH, not IGARCH)."""
        f = garch_leaf(k=1)
        st = None
        for y in _garch_t(2):
            _, st = f(y, st)
        assert 0 < st["alpha"] and 0 < st["beta"]
        assert st["alpha"] + st["beta"] < 1.0           # mean reversion (vs EWMA's =1)

    def test_beats_ewma_leaf_on_garch_data(self):
        """The whole point: a GARCH recursion beats the EWMA/IGARCH leaf on
        vol-clustering-with-reversion data."""
        deltas = []
        for s in range(4):
            ser = _garch_t(10 + s)
            deltas.append(_ll(lambda: garch_leaf(k=1), ser) - _ll(lambda: scale_mixture_leaf(k=1), ser))
        assert sum(deltas) / len(deltas) > 0            # garch_leaf wins on average

    def test_laplace_leaf_override(self):
        f = laplace(k=1, leaf=garch_leaf)
        st = None
        out = None
        for y in _garch_t(3, n=600):
            out, st = f(y, st)
        assert len(out) == 1 and out[0].std > 0
