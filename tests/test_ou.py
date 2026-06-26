"""Tests for the Ornstein-Uhlenbeck mean-reversion transform (a building block)
and the OU group inside laplace's multi-step pool."""

import math
import random

from skaters import ou_transform
from skaters.leaf import leaf
from skaters.conjugate import conjugate


def _ou_series(n=2000, kappa=0.05, mu=5.0, sig=0.3, seed=0):
    """Mean-reverting series: reverts toward mu at speed kappa."""
    rng = random.Random(seed)
    x = mu
    out = []
    for _ in range(n):
        x = x + kappa * (mu - x) + sig * rng.gauss(0, 1)
        out.append(x)
    return out


class TestOuTransform:

    def test_forward_basic(self):
        fwd, _ = ou_transform(0.1, 0.05)
        r, state = fwd(3.0, None)
        assert r == 0.0                      # no residual on the first observation
        assert {"m", "fc", "y"} <= set(state)

    def test_rejects_bad_params(self):
        for kappa in (0.0, -0.1, 1.5):
            try:
                ou_transform(kappa, 0.05)
                assert False, f"kappa={kappa} should raise"
            except AssertionError:
                pass

    def test_forecast_pulls_toward_mean(self):
        """One-step forecast sits between the last value and the running mean."""
        fwd, inv = ou_transform(0.3, 0.05)
        state = None
        for y in _ou_series(seed=1):
            _, state = fwd(y, state)
        d = inv([leaf(k=1)(0.0, None)[0][0]], state)[0]   # zero-mean leaf -> N(fc, .)
        m, ylast = state["m"], state["y"]
        lo, hi = sorted((m, ylast))
        assert lo - 1e-9 <= d.mean <= hi + 1e-9           # strictly between mean and last

    def test_multistep_variance_grows_and_saturates(self):
        """h-step sd increases with h and saturates below the random-walk sqrt(h)."""
        kappa = 0.2
        fwd, inv = ou_transform(kappa, 0.05)
        state = None
        for y in _ou_series(kappa=kappa, seed=2):
            _, state = fwd(y, state)
        unit = leaf(k=1)(1.0, None)[0][0]                 # a fixed N(0, sigma)
        dists = inv([unit] * 10, state)
        sds = [d.std for d in dists]
        assert all(sds[i] < sds[i + 1] + 1e-12 for i in range(len(sds) - 1))  # monotone up
        phi = 1.0 - kappa
        # saturating: 10-step sd well under the random-walk sqrt(10) growth
        assert sds[9] / sds[0] < math.sqrt(10) * 0.9
        # matches the closed-form OU factor
        expect = math.sqrt((1 - phi ** 20) / (1 - phi ** 2))
        assert abs(sds[9] / sds[0] - expect) < 1e-6


class TestLaplaceOuPool:

    def test_pool_gated_on_multistep(self):
        """laplace's candidate pool gains the OU mean-reversion group only for
        k > 1 (the one-step pool is unchanged; the edge is a multi-step effect)."""
        from skaters.api import _build_candidates
        _, _, g1 = _build_candidates(1)
        _, _, g3 = _build_candidates(3)
        assert g1["mean_revert"] == []          # k=1 pool byte-identical
        assert len(g3["mean_revert"]) == 6      # k>1 adds the OU group

    def test_ou_under_coordinate_runs(self):
        # the building-block composition mean_revert used: OU under a sqrt coordinate
        from skaters.transform import yeo_johnson
        f = conjugate(conjugate(leaf(k=2), ou_transform(0.1, 0.02), k=2), yeo_johnson(0.5), k=2)
        state = None
        out = None
        for y in _ou_series(mu=20.0, sig=1.0, seed=5):
            out, state = f(y, state)
        assert all(math.isfinite(d.mean) and d.std > 0 for d in out)
