"""Tests for the Kahneman policy: think fast and slow.

Kahneman is a *prior* over the shared candidate population — it boosts the
candidates with a fast process tracker on the outside and a slowly-varying
residual scale (standardize, long half-life) on the inside. The point
forecast reacts fast; the residual distribution drifts slowly.
"""

import math
import random
from skaters.api import kahneman, _build_candidates
from skaters.conventions import Skater
from skaters.dist import Dist


# --- the fast/slow candidates live in the SHARED pool ---

def test_fast_slow_group_is_in_shared_pool():
    candidates, depths, groups = _build_candidates(k=1)
    assert "fast_slow" in groups
    assert len(groups["fast_slow"]) >= 4
    for i in groups["fast_slow"]:
        assert 0 <= i < len(candidates)
        assert depths[i] == 2  # tracker (outer) + standardize (inner)


def test_kahneman_shares_population_with_others():
    """Kahneman is a prior, not a separate family: same pool size as laplace."""
    from skaters.api import laplace  # noqa: local import keeps top clean
    # Both build from _build_candidates, so the live ensembles cover the
    # same number of sub-models.
    cands, _, _ = _build_candidates(k=1)
    f = kahneman(k=1)
    x, state = f(1.0, None)
    assert len(state["sub"]) == len(cands)


# --- policy behaves like a skater ---

def test_kahneman_is_skater():
    assert isinstance(kahneman(k=1), Skater)


def test_kahneman_accepts_k_and_strength():
    for k in [1, 3]:
        for strength in [1.0, 6.0]:
            f = kahneman(k=k, strength=strength)
            x, _ = f(1.0, None)
            assert len(x) == k
            assert isinstance(x[0], Dist)


def test_kahneman_tracks_fast_level_shift():
    """The underlying process is tracked fast: a step change is caught quickly."""
    f = kahneman(k=1)
    state = None
    random.seed(4)
    for _ in range(300):
        _, state = f(random.gauss(0, 0.5), state)
    for _ in range(15):
        dists, state = f(50.0 + random.gauss(0, 0.5), state)
    assert dists[0].mean > 40.0


def test_kahneman_tracks_trend():
    f = kahneman(k=1)
    state = None
    random.seed(5)
    for t in range(300):
        dists, state = f(float(t) + random.gauss(0, 1), state)
    assert dists[0].mean > 200


def test_kahneman_density_is_finite_and_calibrated():
    f = kahneman(k=2)
    state = None
    random.seed(6)
    for _ in range(200):
        dists, state = f(random.gauss(0, 1), state)
    for d in dists:
        assert d.std > 0
        assert math.isfinite(d.logpdf(0.0))
        assert 0 < d.cdf(0.0) < 1


def test_strength_concentrates_on_fast_slow():
    """A larger strength puts more ensemble weight on the fast/slow block."""
    _, _, groups = _build_candidates(k=1)
    fs = set(groups["fast_slow"])

    def fast_slow_weight(strength, seed=11):
        f = kahneman(k=1, strength=strength)
        state = None
        random.seed(seed)
        # Heteroskedastic: slowly-varying noise scale — the fast/slow
        # candidates should earn weight here.
        for t in range(600):
            sigma = 0.5 + 1.5 * (0.5 + 0.5 * math.sin(2 * math.pi * t / 300))
            _, state = f(random.gauss(0, sigma), state)
        log_w = [state["log_w"][i][0] for i in range(len(state["log_w"]))]
        m = max(log_w)
        w = [math.exp(lw - m) for lw in log_w]
        tot = sum(w)
        return sum(w[i] for i in fs) / tot

    assert fast_slow_weight(8.0) > fast_slow_weight(0.5)
