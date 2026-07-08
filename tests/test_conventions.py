"""Tests for the Skater protocol and conventions."""

from skaters.conventions import Skater
from skaters.ema import ema
from skaters.ensemble import precision_weighted_ensemble
from skaters.dist import Dist


def test_ema_satisfies_protocol():
    f = ema(alpha=0.1, k=1)
    assert isinstance(f, Skater)


def test_ensemble_satisfies_protocol():
    f = precision_weighted_ensemble([ema(alpha=0.1, k=1)], k=1)
    assert isinstance(f, Skater)


def test_custom_skater_satisfies_protocol():
    def my_skater(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        return [Dist.gaussian(y, 1.0)], {}
    assert isinstance(my_skater, Skater)


def test_non_callable_fails_protocol():
    assert not isinstance("not a skater", Skater)
    assert not isinstance(42, Skater)


def test_lambda_satisfies_protocol():
    f = lambda y, state: ([Dist.gaussian(y, 1.0)], {})
    assert isinstance(f, Skater)


def test_laplace_state_is_picklable():
    """Skater state must be pure data — checkpoint/restore is how streaming
    systems deploy. Closures belong in the wrapper, never in state."""
    import pickle
    import random
    from skaters import laplace
    f = laplace(3)
    state = None
    random.seed(2)
    ys = [random.gauss(0, 1) for _ in range(120)]
    for y in ys[:80]:
        _, state = f(y, state)
    resumed = pickle.loads(pickle.dumps(state))
    for y in ys[80:]:
        da, state = f(y, state)
        db, resumed = f(y, resumed)
    assert da[0].mean == db[0].mean and da[-1].std == db[-1].std
