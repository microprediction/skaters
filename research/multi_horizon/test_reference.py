import math

import pytest

from skaters import Dist, conjugate, log_transform

from .reference import AffineFrame, horizon_conjugate


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


def test_inverse_maps_density_and_quantiles_through_the_same_frozen_frame():
    inner_dist = Dist([(0.4, -1.0, 0.5), (0.6, 2.0, 1.1)])

    def reference(y, state):
        return [Dist.gaussian(10.0, 3.0)] * 3, {}

    def inner(k):
        return lambda y, state: ([inner_dist] * k, {})

    model = horizon_conjugate(reference, inner, k=3)
    state = None
    for y in (7.0, 8.0, 9.0, 11.0):
        fan, state = model(y, state)
    for d in fan:
        for z in (-1.0, 0.5, 2.0):
            y = 10.0 + 3.0 * z
            assert d.cdf(y) == pytest.approx(inner_dist.cdf(z))
            assert d.pdf(y) == pytest.approx(inner_dist.pdf(z) / 3.0)
        assert d.quantile(0.9) == pytest.approx(10.0 + 3.0 * inner_dist.quantile(0.9))


@pytest.mark.parametrize("log_first", [False, True])
def test_conjugation_with_the_existing_log_transform_in_both_orders(log_first):
    def reference(y, state):
        return [Dist.gaussian(5.0, 2.0)] * 3, {}

    def unit(k):
        return lambda y, state: ([Dist.gaussian()] * k, {})

    if log_first:
        model = conjugate(horizon_conjugate(reference, unit, k=3), log_transform(), k=3)
    else:
        def inner(k):
            return conjugate(unit(k), log_transform(), k=k)
        model = horizon_conjugate(reference, inner, k=3)
    state = None
    for y in (10.0, 11.0, 12.0, 13.0):
        fan, state = model(y, state)
    for d in fan:
        for p in (0.1, 0.5, 0.9):
            assert d.cdf(d.quantile(p)) == pytest.approx(p)
        y = d.quantile(0.6)
        delta = 1e-5 * y
        assert d.pdf(y) == pytest.approx((d.cdf(y + delta) - d.cdf(y - delta)) / (2 * delta), rel=1e-6)


@pytest.mark.parametrize("scale", [3.0, -3.0])
def test_affine_frame_has_scalar_and_continuous_predictive_inverses(scale):
    from skaters.pushforward import PushforwardDist

    frame = AffineFrame(10.0, scale)
    assert frame.inverse(frame.forward(1.5)) == pytest.approx(1.5)
    # A table representation stores the exact identity as a general predictive.
    inner = PushforwardDist(Dist.gaussian(), ys=[0.0, 1.0], zs=[0.0, 1.0])
    outer = frame.inverse_dist(inner)
    oracle = Dist.gaussian(10.0, abs(scale))
    assert outer.mean == pytest.approx(oracle.mean)
    assert outer.std == pytest.approx(oracle.std, rel=1e-3)
    for p in (0.1, 0.5, 0.9):
        assert outer.cdf(outer.quantile(p)) == pytest.approx(p)
        assert outer.quantile(p) == pytest.approx(oracle.quantile(p))
    assert outer.logpdf(12.0) == pytest.approx(oracle.logpdf(12.0))
    reflected = outer.affine(-2.0, 7.0)
    assert reflected.mean == pytest.approx(-13.0)
    assert reflected.cdf(reflected.quantile(0.3)) == pytest.approx(0.3)
