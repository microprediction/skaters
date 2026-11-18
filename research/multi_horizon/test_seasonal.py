import math
import pickle
from copy import deepcopy
from random import Random

import pytest

from skaters import Dist, scale_mixture_leaf

from .reference import horizon_conjugate
from .revision import ForecastRevision
from .seasonal import seasonal_reference


@pytest.mark.parametrize("alpha", [1.0, 0.2])
def test_seasonal_reference_repeats_each_phase_at_every_lead(alpha):
    model = seasonal_reference(period=3, k=12, alpha=alpha)
    _, state = model(10.0)
    _, state = model(20.0, state)
    _, state = model(30.0, state)
    issued, state = model(40.0, state)
    phase0 = 10.0 + alpha * 30.0
    assert [d.mean for d in issued] == [20.0, 30.0, phase0] * 4
    _, state = model(-500.0, state)
    assert issued[0].mean == 20.0


def test_last_phase_reference_survives_a_large_change_in_scale():
    model = seasonal_reference(period=1, k=8)
    _, state = model(1e20)
    fan, state = model(1.0, state)
    assert [d.mean for d in fan] == [1.0] * 8


def test_exact_seasonal_pattern_is_removed_seven_cycles_ahead():
    period, k = 24, 168
    pattern = [50 + 20 * math.sin(2 * math.pi * i / period) for i in range(period)]
    reference = seasonal_reference(period, k, scale=2.0)
    model = horizon_conjugate(reference, scale_mixture_leaf, k)
    state = None
    for t in range(k + period + 1):
        fan, state = model(pattern[t % period], state)
    assert state["residuals"] == pytest.approx([0.0] * k, abs=1e-12)
    for h, d in enumerate(fan, 1):
        assert d.mean == pytest.approx(pattern[(t + h) % period])


def test_naive_seasonal_errors_contain_only_noise_at_long_leads():
    period, k = 24, 168
    rng = Random(520)
    noise = [rng.gauss(0.0, 0.2) for _ in range(480)]
    pattern = [80 + 30 * math.sin(2 * math.pi * i / period) for i in range(period)]
    model = horizon_conjugate(seasonal_reference(period, k), scale_mixture_leaf, k)
    state = None
    errors = {h: [] for h in (1, 24, 25, 72, 168)}
    for t, epsilon in enumerate(noise):
        fan, state = model(pattern[t % period] + epsilon, state)
        if t < k:
            continue
        for h in errors:
            anchor = t - period * math.ceil(h / period)
            assert state["residuals"][h - 1] == pytest.approx(epsilon - noise[anchor], abs=2e-14)
            errors[h].append(state["residuals"][h - 1])
    # For a fixed seasonal pattern plus iid noise the two errors have the same
    # population variance, even though the second target is seven cycles out.
    for values in errors.values():
        assert 0.2 < math.sqrt(sum(z * z for z in values) / len(values)) < 0.4


def test_smoothed_reference_error_is_measured_in_its_issued_frame():
    period, k = 4, 17
    alpha, scale = 0.2, 3.0
    model = horizon_conjugate(seasonal_reference(period, k, alpha=alpha, scale=scale),
                              scale_mixture_leaf, k)
    expected = [None] * period
    issued = []
    state = None
    for t in range(100):
        y = 20 * (t % period) + 0.5 * t
        fan, state = model(y, state)
        phase = t % period
        previous = expected[phase]
        expected[phase] = y if previous is None else previous + alpha * (y - previous)
        for h in (1, 4, 17):
            if t >= h:
                loc = issued[t - h][(t % period)]
                assert state["residuals"][h - 1] == pytest.approx((y - loc) / scale)
        issued.append([y if value is None else value for value in expected])
    assert fan[-1].std > 0.0


def test_checkpoint_and_forecasts_do_not_share_a_mutable_seasonal_frame():
    def build():
        return horizon_conjugate(seasonal_reference(3, k=9, alpha=0.2), scale_mixture_leaf, k=9)

    model = build()
    state = None
    for t in range(50):
        issued, state = model(10 * (t % 3) + math.sin(t), state)
    before = [(d.mean, d.std) for d in issued]
    restored = pickle.loads(pickle.dumps(state))
    fresh = build()
    for t in range(50, 70):
        left, state = model(10 * (t % 3) + math.sin(t), state)
        right, restored = fresh(10 * (t % 3) + math.sin(t), restored)
        assert left == right
    assert [(d.mean, d.std) for d in issued] == before


def test_seasonal_calendar_advances_through_leading_and_internal_gaps():
    model = seasonal_reference(3, k=9)
    _, state = model(math.nan)
    _, state = model(math.nan, state)
    for t in range(2, 20):
        _, state = model(10 * (t % 3), state)
    levels = list(state["levels"])
    for _ in range(5):
        _, state = model(math.nan, state)
    assert state["levels"] == levels
    assert state["n"] == 25
    fan, state = model(10 * (25 % 3), state)
    assert [d.mean for d in fan] == [20, 0, 10] * 3


def test_seasonal_transform_can_supply_the_boundary_for_path_revisions():
    period, k = 3, 6
    base = horizon_conjugate(seasonal_reference(period, k), scale_mixture_leaf, k)
    model = ForecastRevision(k, base=base, correlations=[0.0] * (k - 1))
    state = None
    for t in range(30):
        _, state = model(10 * (t % period) + math.sin(t), state)
    checkpoint = deepcopy(state)
    path = model.sample_path(state, rng=Random(17))
    assert model.decode(model.encode(path, state), state) == pytest.approx(path, abs=1e-11)
    assert state["base"]["reference"] == checkpoint["base"]["reference"]


def test_affine_frames_can_be_composed_at_a_fixed_horizon():
    def offset(k):
        def step(y, state):
            return [Dist.gaussian(10.0, 2.0)] * k, {}
        return step

    def unit(k):
        return lambda y, state: ([Dist.gaussian()] * k, {})

    def inner(k):
        return horizon_conjugate(offset(k), unit, k)

    model = horizon_conjugate(offset(3), inner, k=3)
    state = None
    for _ in range(10):
        fan, state = model(30.0, state)
    assert [d.mean for d in fan] == [30.0] * 3
    assert [d.std for d in fan] == [4.0] * 3


@pytest.mark.parametrize("kwargs", [
    {"period": 0, "k": 3}, {"period": 3, "k": 0}, {"period": 3.5, "k": 3},
    {"period": 3, "k": 3, "alpha": 0}, {"period": 3, "k": 3, "alpha": 1.1},
    {"period": 3, "k": 3, "scale": 0}, {"period": 3, "k": 3, "scale": math.inf},
])
def test_invalid_seasonal_parameters(kwargs):
    with pytest.raises(ValueError):
        seasonal_reference(**kwargs)
