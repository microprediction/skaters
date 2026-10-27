"""gpdtails warm-up sample excludes the trunk's fallback ticks.

At horizon m >= 2 the first 2m resolved z's are PITs of the base's warm-up
fallback predictive, not of the body the splice calibrates, so they must not
seed the frozen thresholds. At m = 1 nothing is skipped (k = 1 output is
bit-identical to before this rule). The test counts exactly when thresholds
appear, horizon by horizon, against a deterministic base.
"""
import random

from skaters.dist import Dist
from skaters.tails import gpdtails

WARMUP = 100


def _base(k):
    """A fixed Gaussian base at every horizon: every resolved PIT is informative."""
    def f(y, state):
        return [Dist.gaussian(0.0, 1.0)] * k, state
    return f


def _thresholds_after(n_ticks, k):
    g = random.Random(5)
    f = gpdtails(_base(k), k=k, warmup=WARMUP)
    st = None
    for _ in range(n_ticks):
        _, st = f(g.gauss(0.0, 1.0), st)
    return [th["up"]["t"] is not None for th in st["tails"]]


def test_horizon_one_freezes_after_warmup_exactly():
    # horizon 1 resolves its first z at tick 2, so WARMUP z's are in by tick WARMUP + 1
    assert _thresholds_after(WARMUP, 1) == [False]
    assert _thresholds_after(WARMUP + 1, 1) == [True]


def test_higher_horizons_skip_two_m_resolutions():
    k = 4
    # horizon m resolves its first z at tick m + 1; with 2m skipped it needs
    # WARMUP + 2m resolutions, i.e. is frozen first at tick m + WARMUP + 2m.
    for m in range(2, k + 1):
        frozen_at = m + WARMUP + 2 * m
        assert _thresholds_after(frozen_at - 1, k)[m - 1] is False, m
        assert _thresholds_after(frozen_at, k)[m - 1] is True, m


def test_skip_counter_is_recorded_in_state():
    g = random.Random(5)
    f = gpdtails(_base(3), k=3, warmup=WARMUP)
    st = None
    for _ in range(40):
        _, st = f(g.gauss(0.0, 1.0), st)
    assert [th["skipped"] for th in st["tails"]] == [0, 4, 6]
