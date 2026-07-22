"""Tests for the exact pushforward inverse (skaters.pushforward)."""

import math
import random
from skaters.dist import Dist
from skaters.pushforward import PushforwardDist, table_from_map
from skaters.transform import yeo_johnson, power_transform
from skaters.conjugate import conjugate
from skaters.leaf import leaf

SQRT2PI = math.sqrt(2.0 * math.pi)


def _identity_table(lo=-8.0, hi=8.0, step=0.125):
    grid = []
    x = lo
    while x <= hi + 1e-12:
        grid.append(x)
        x += step
    return grid, list(grid)


class TestIdentityTable:
    """Through the identity map the pushforward IS the inner Dist."""

    def test_logpdf_exact(self):
        ys, zs = _identity_table()
        inner = Dist([(0.6, -0.3, 0.5), (0.3, 0.4, 1.2), (0.1, 0.0, 3.0)])
        pf = PushforwardDist(inner, ys, zs)
        for x in (-2.7, -1.0, 0.0, 0.4, 3.1):
            assert abs(pf.logpdf(x) - inner.logpdf(x)) < 1e-9

    def test_crps_close(self):
        ys, zs = _identity_table()
        inner = Dist.gaussian(0.0, 1.0)
        pf = PushforwardDist(inner, ys, zs)
        for x in (-2.7, -1.0, 0.0, 1.3, 3.1):
            exact = inner.crps(x)
            assert abs(pf.crps(x) - exact) < 0.01 * max(exact, 0.05)

    def test_cdf_quantile_roundtrip(self):
        ys, zs = _identity_table()
        pf = PushforwardDist(Dist.gaussian(0.5, 2.0), ys, zs)
        for p in (0.05, 0.3, 0.5, 0.9):
            assert abs(pf.cdf(pf.quantile(p)) - p) < 1e-6

    def test_moments_match(self):
        ys, zs = _identity_table()
        inner = Dist([(0.7, 0.2, 0.8), (0.3, -0.5, 1.5)])
        pf = PushforwardDist(inner, ys, zs)
        assert abs(pf.mean - inner.mean) < 1e-6
        assert abs(pf.std - inner.std) < 1e-3


class TestLognormalClosedForm:
    """yeo_johnson(0) is log1p on the POSITIVE branch, so a component whose
    z-mass stays positive pushes to a shifted lognormal exactly. (The
    negative branch is quadratic, a detail the first version of this test
    got wrong.)"""

    def _pf(self, m, s):
        _, inverse_k = yeo_johnson(0.0, exact=True)
        return inverse_k([Dist.gaussian(m, s)], {})[0]

    def test_logpdf_matches_lognormal(self):
        m, s = 0.3, 0.5
        pf = self._pf(m, s)
        for y in (0.1, 0.5, 1.0, 2.0, 5.0):    # z = log1p(y) > 0: log branch
            z = math.log1p(y)
            want = (-0.5 * ((z - m) / s) ** 2 - math.log(s * SQRT2PI)
                    - math.log1p(y))          # -log dinv = -z
            assert abs(pf.logpdf(y) - want) < 2e-3

    def test_mean_matches_lognormal(self):
        m, s = 3.0, 0.3                        # z-mass entirely positive
        pf = self._pf(m, s)
        want = math.exp(m + 0.5 * s * s) - 1.0
        assert abs(pf.mean - want) < 1e-3 * (1.0 + abs(want))

    def test_exact_carries_skew_delta_does_not(self):
        m, s = 0.0, 0.5
        pf = self._pf(m, s)
        up = pf.quantile(0.9) - pf.quantile(0.5)
        dn = pf.quantile(0.5) - pf.quantile(0.1)
        assert up > 1.2 * dn                      # right-skewed in y
        _, inv_delta = yeo_johnson(0.0)
        d = inv_delta([Dist.gaussian(m, s)], {})[0]
        up_d = d.quantile(0.9) - d.quantile(0.5)
        dn_d = d.quantile(0.5) - d.quantile(0.1)
        assert abs(up_d - dn_d) < 1e-6 * max(up_d, 1.0)   # symmetric


class TestDefaultUnchanged:

    def test_delta_path_is_default(self):
        _, inv_default = yeo_johnson(0.5)
        _, inv_exact = yeo_johnson(0.5, exact=True)
        d = Dist.gaussian(1.0, 0.3)
        out_default = inv_default([d], {})[0]
        out_exact = inv_exact([d], {})[0]
        assert isinstance(out_default, Dist)
        assert isinstance(out_exact, PushforwardDist)

    def test_power_transform_exact_smoke(self):
        _, inverse_k = power_transform(0.5, exact=True)
        pf = inverse_k([Dist.gaussian(2.0, 0.4)], {})[0]
        assert math.isfinite(pf.logpdf(pf.mean))
        assert pf.std > 0


class TestComposition:

    def test_conjugated_skater_runs_and_scores(self):
        random.seed(3)
        f = conjugate(leaf(k=3), yeo_johnson(0.0, exact=True), k=3)
        state = None
        level = 5.0
        pend = None
        lps = []
        for _ in range(200):
            level = max(level * math.exp(random.gauss(0, 0.1)), 1e-3)
            if pend is not None:
                lps.append(pend[0].logpdf(level))
            pend, state = f(level, state)
        assert all(math.isfinite(v) for v in lps[10:])

    def test_components_shim_supports_combine(self):
        _, inverse_k = yeo_johnson(0.0, exact=True)
        pf = inverse_k([Dist.gaussian(0.5, 0.3)], {})[0]
        mixed = Dist.combine([Dist(pf.components), Dist.gaussian(0.0, 1.0)])
        assert math.isfinite(mixed.logpdf(0.2))

    def test_table_from_map_monotone(self):
        ys, zs = table_from_map(lambda z: math.expm1(min(z, 350.0)), -3.0, 3.0)
        assert all(b > a for a, b in zip(ys, ys[1:]))
        assert all(b > a for a, b in zip(zs, zs[1:]))
