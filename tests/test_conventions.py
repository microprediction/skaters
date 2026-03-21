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
