"""Tests for Bayesian model averaging ensemble."""

import math
import random
from skaters.bayesian import bayesian_ensemble
from skaters.ema import ema
from skaters.conjugate import conjugate
from skaters.transform import difference, ema_transform
from skaters.leaf import leaf
from skaters.dist import Dist


# --- Basic mechanics ---

def test_returns_list_of_dist():
    f = bayesian_ensemble([ema(alpha=0.1, k=1)], k=1)
    x, state = f(1.0, None)
    assert isinstance(x, list)
    assert isinstance(x[0], Dist)


def test_returns_k_predictions():
    for k in [1, 3, 5]:
        f = bayesian_ensemble([ema(alpha=0.1, k=k)], k=k)
        x, _ = f(1.0, None)
        assert len(x) == k


def test_single_model_passes_through():
    """Bayesian ensemble of one should match the model's mean."""
    inner = ema(alpha=0.2, k=1)
    ens = bayesian_ensemble([ema(alpha=0.2, k=1)], k=1)
    s_inner = s_ens = None
    random.seed(42)
    for _ in range(50):
        y = random.gauss(0, 1)
        x_inner, s_inner = inner(y, s_inner)
        x_ens, s_ens = ens(y, s_ens)
    assert abs(x_inner[0].mean - x_ens[0].mean) < 1e-6


def test_state_tracks_log_weights():
    f = bayesian_ensemble([ema(alpha=0.1, k=1), ema(alpha=0.3, k=1)], k=1)
    state = None
    random.seed(42)
    for _ in range(50):
        _, state = f(random.gauss(0, 1), state)
    assert "log_w" in state
    assert len(state["log_w"]) == 2


# --- Log-likelihood weighting ---

def test_favors_well_calibrated_model():
    """A well-calibrated model should accumulate more weight than a bad one."""
    random.seed(42)
    k = 1
    # Good model: EMA that tracks well
    good = ema(alpha=0.3, k=k)
    # Bad model: always predicts 100 with tight std (overconfident and wrong)
    def bad_model(y, state):
        return [Dist.gaussian(100.0, 0.1)], state or {}
    bad_model.__name__ = "bad"

    f = bayesian_ensemble([good, bad_model], k=k, learning_rate=0.5)
    state = None
    for _ in range(100):
        _, state = f(random.gauss(5.0, 1.0), state)

    # Good model should have much higher log weight
    assert state["log_w"][0][0] > state["log_w"][1][0]


def test_punishes_overconfidence():
    """An overconfident model (small std) that's wrong should lose weight fast."""
    random.seed(42)
    k = 1
    # Modest model: predicts 0 with reasonable std
    def modest(y, state):
        return [Dist.gaussian(0.0, 5.0)], state or {}
    modest.__name__ = "modest"

    # Overconfident: predicts 0 with tiny std (will be wrong often)
    def overconfident(y, state):
        return [Dist.gaussian(0.0, 0.01)], state or {}
    overconfident.__name__ = "overconfident"

    f = bayesian_ensemble([modest, overconfident], k=k, learning_rate=1.0)
    state = None
    for _ in range(50):
        _, state = f(random.gauss(0, 1), state)

    # Overconfident should have much lower weight
    assert state["log_w"][0][0] > state["log_w"][1][0]


def test_punishes_underconfidence():
    """A model with unnecessarily wide std should lose to a tighter one."""
    random.seed(42)
    k = 1
    # Tight and correct
    def tight(y, state):
        return [Dist.gaussian(0.0, 1.2)], state or {}
    tight.__name__ = "tight"

    # Needlessly wide
    def wide(y, state):
        return [Dist.gaussian(0.0, 100.0)], state or {}
    wide.__name__ = "wide"

    f = bayesian_ensemble([tight, wide], k=k, learning_rate=1.0)
    state = None
    for _ in range(200):
        _, state = f(random.gauss(0, 1), state)

    assert state["log_w"][0][0] > state["log_w"][1][0]


# --- Learning rate (shrinkage) ---

def test_learning_rate_slows_concentration():
    """Lower learning rate should keep weights closer to uniform."""
    random.seed(42)
    k = 1
    models = [ema(alpha=0.1, k=k), ema(alpha=0.3, k=k)]

    f_fast = bayesian_ensemble([ema(alpha=0.1, k=k), ema(alpha=0.3, k=k)], k=k, learning_rate=1.0)
    f_slow = bayesian_ensemble([ema(alpha=0.1, k=k), ema(alpha=0.3, k=k)], k=k, learning_rate=0.1)
    s_fast = s_slow = None

    for _ in range(200):
        y = random.gauss(0, 1)
        _, s_fast = f_fast(y, s_fast)
        _, s_slow = f_slow(y, s_slow)

    # The spread of log weights should be smaller with lower learning rate
    spread_fast = abs(s_fast["log_w"][0][0] - s_fast["log_w"][1][0])
    spread_slow = abs(s_slow["log_w"][0][0] - s_slow["log_w"][1][0])
    assert spread_slow < spread_fast


def test_learning_rate_adapts_to_regime_change():
    """Lower learning rate should recover faster from a regime change."""
    random.seed(42)
    k = 1

    # Model A: predicts 0
    def model_a(y, state):
        return [Dist.gaussian(0.0, 2.0)], state or {}
    model_a.__name__ = "a"

    # Model B: predicts 50
    def model_b(y, state):
        return [Dist.gaussian(50.0, 2.0)], state or {}
    model_b.__name__ = "b"

    f = bayesian_ensemble([model_a, model_b], k=k, learning_rate=0.3)
    state = None

    # Phase 1: data near 0 (model A wins)
    for _ in range(100):
        _, state = f(random.gauss(0, 1), state)
    assert state["log_w"][0][0] > state["log_w"][1][0]

    # Phase 2: data near 50 (model B should catch up)
    for _ in range(200):
        _, state = f(random.gauss(50, 1), state)
    assert state["log_w"][1][0] > state["log_w"][0][0]


# --- Complexity penalty ---

def test_complexity_penalty_favors_simpler():
    """With complexity penalty, a simpler model should get a boost."""
    random.seed(42)
    k = 1
    # Both models are identical EMAs, but we declare different depths
    models = [ema(alpha=0.1, k=k), ema(alpha=0.1, k=k)]

    f = bayesian_ensemble(
        models, k=k,
        complexity_penalty=0.1,
        depths=[1, 3],  # second model declared as "deeper"
    )
    state = None
    for _ in range(100):
        _, state = f(random.gauss(0, 1), state)

    # Simpler (depth=1) should have higher log weight
    assert state["log_w"][0][0] > state["log_w"][1][0]


def test_complexity_penalty_zero_is_neutral():
    """With λ=0, depth shouldn't matter."""
    random.seed(42)
    k = 1
    models = [ema(alpha=0.1, k=k), ema(alpha=0.1, k=k)]

    f = bayesian_ensemble(
        models, k=k,
        complexity_penalty=0.0,
        depths=[1, 5],
    )
    state = None
    for _ in range(100):
        _, state = f(random.gauss(0, 1), state)

    # Weights should be equal (same model, no penalty)
    assert abs(state["log_w"][0][0] - state["log_w"][1][0]) < 1e-6


def test_deep_model_can_overcome_penalty():
    """A deep model that actually captures structure should win despite penalty."""
    random.seed(42)
    k = 1
    # Trending data: diff+ema should beat plain ema
    shallow = ema(alpha=0.1, k=k)
    deep = conjugate(ema(alpha=0.1, k=k), difference(), k=k)

    f = bayesian_ensemble(
        [shallow, deep], k=k,
        learning_rate=0.5,
        complexity_penalty=0.01,  # mild penalty
        depths=[1, 2],
    )
    state = None
    level = 0.0
    for _ in range(500):
        level += 0.5 + random.gauss(0, 0.5)  # strong trend
        _, state = f(level, state)

    # Deep model should win despite penalty because trend is real structure
    assert state["log_w"][1][0] > state["log_w"][0][0]


# --- Pruning ---

def test_prune_bounds_components():
    """Combined Dist should not exceed max_components."""
    k = 1
    models = [ema(alpha=a, k=k) for a in [0.01, 0.05, 0.1, 0.2, 0.3, 0.5]]
    f = bayesian_ensemble(models, k=k, max_components=5)
    state = None
    random.seed(42)
    for _ in range(100):
        x, state = f(random.gauss(0, 1), state)
    assert len(x[0]) <= 5


# --- Composition ---

def test_bayesian_with_mixed_transforms():
    """Bayesian ensemble of models with different transforms."""
    k = 1
    models = [
        ema(alpha=0.1, k=k),
        conjugate(ema(alpha=0.1, k=k), difference(), k=k),
        conjugate(leaf(k=k), ema_transform(0.3), k=k),
    ]
    f = bayesian_ensemble(models, k=k, depths=[1, 2, 1])
    state = None
    random.seed(42)
    for _ in range(200):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)
    assert x[0].std > 0


def test_multihorizon():
    k = 3
    f = bayesian_ensemble(
        [ema(alpha=0.1, k=k), ema(alpha=0.3, k=k)], k=k
    )
    state = None
    random.seed(42)
    for _ in range(50):
        x, state = f(random.gauss(0, 1), state)
    assert len(x) == 3
    assert all(math.isfinite(d.mean) for d in x)


def test_many_observations_stable():
    k = 1
    f = bayesian_ensemble(
        [ema(alpha=0.05, k=k), ema(alpha=0.3, k=k)], k=k,
        learning_rate=0.3,
    )
    state = None
    random.seed(42)
    for _ in range(10_000):
        x, state = f(random.gauss(0, 1), state)
    assert math.isfinite(x[0].mean)
    assert x[0].std > 0


def test_logpdf_of_ensemble_is_finite():
    """The ensemble's combined Dist should produce finite logpdf."""
    f = bayesian_ensemble(
        [ema(alpha=0.1, k=1), ema(alpha=0.3, k=1)], k=1,
    )
    state = None
    random.seed(42)
    for _ in range(100):
        x, state = f(random.gauss(0, 1), state)
    lp = x[0].logpdf(0.0)
    assert math.isfinite(lp)
