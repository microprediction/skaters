import math

import pytest

from skaters import Dist

from .reference import horizon_conjugate


def _reference(k):
    def step(y, state):
        return [Dist.gaussian(10 * y + h, 1 + h) for h in range(1, k + 1)], {"last": y}

    return step


def _inner(k):
    def step(z, state):
        return [Dist.gaussian(100 * h + z, h) for h in range(1, k + 1)], {"last": z}

    return step


def test_each_inner_skater_consumes_residuals_in_the_original_frame():
    k = 3
    reference = _reference(k)
    model = horizon_conjugate(reference, _inner, k)
    state = None
    stream = [4.0, 5.0, 9.0, 1.2, 12.2, 14.0]

    for t, y in enumerate(stream):
        fan, state = model(y, state)
        for h in range(1, k + 1):
            d = fan[h - 1]
            if t < h:
                assert state["residuals"][h - 1] is None
                assert d == reference(y, None)[0][h - 1]
                continue
            scale = 1 + h
            z = (y - 10 * stream[t - h] - h) / scale
            assert state["inner"][h - 1]["last"] == pytest.approx(z)
            assert state["residuals"][h - 1] == pytest.approx(z)
            assert d.mean == pytest.approx(10 * y + h + scale * (100 * h + z))
            assert d.std == pytest.approx(scale * h)


def test_random_walk_is_a_standard_normal_problem_at_every_lead():
    k, drift, sigma = 6, 0.3, 2.4

    def reference(y, state):
        return [Dist.gaussian(y + h * drift, sigma * math.sqrt(h)) for h in range(1, k + 1)], {}

    def standard_normal(k):
        return lambda z, state: ([Dist.gaussian()] * k, {})

    model = horizon_conjugate(reference, standard_normal, k)
    state = None
    stream = [6.5, 4.0, 5.5, 6.4, 6.2, 7.0, 5.3, 5.6, 4.4, 9.0]
    for t, y in enumerate(stream):
        fan, state = model(y, state)
        for h in range(1, min(t, k) + 1):
            z = (y - stream[t - h] - h * drift) / (sigma * math.sqrt(h))
            assert state["residuals"][h - 1] == pytest.approx(z)
            assert fan[h - 1] == reference(y, None)[0][h - 1]


def test_missing_tick_is_rejected_before_retiming_a_model():
    from .seasonal import seasonal_reference

    model = horizon_conjugate(seasonal_reference(2, k=2), _inner, k=2)
    state = None
    for y in (5.0, 9.0, 6.0, 8.0):
        _, state = model(y, state)
    reference_before = list(state["reference"]["levels"])
    inner_before = [dict(s) for s in state["inner"]]
    with pytest.raises(ValueError, match="finite observation"):
        model(math.nan, state)
    assert state["reference"]["levels"] == reference_before
    assert state["reference"]["n"] == 4
    assert state["inner"] == inner_before
