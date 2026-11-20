"""Causality, path inversion, recurrence, and ordinary chain integration."""

from copy import deepcopy
import math
import pickle
import random

import pytest

from skaters.conjugate import conjugate
from skaters.dist import Dist
from skaters.leaf import leaf
from skaters.parade import parade
from skaters.transform import ema_transform, log_transform

from research.orbit import OrbitTransform, orbit_transform


def train(transform, values):
    state = None
    residuals = []
    for y in values:
        z, state = transform.forward(y, state)
        residuals.append(z)
    return residuals, state


def sine(i):
    return 10.0 + 3.0 * math.sin(2.0 * math.pi * i / 64.0)


@pytest.mark.parametrize("split", [0, 1, 4, 19, 100])
def test_exact_path_roundtrip_and_no_state_mutation(split):
    rng = random.Random(712)
    ys = [sine(i) + rng.gauss(0.0, 0.2) for i in range(180)]
    transform = orbit_transform(memory=64)
    _, state = train(transform, ys[:split])
    saved = pickle.dumps(state)
    future_residuals = []
    live = deepcopy(state)
    for y in ys[split:]:
        z, live = transform.forward(y, live)
        future_residuals.append(z)
    restored = transform.inverse_path(future_residuals, state)
    assert restored == pytest.approx(ys[split:], abs=2e-10)
    assert pickle.dumps(state) == saved


def test_transform_is_a_causal_translation_before_learning_label():
    transform = orbit_transform()
    _, state = train(transform, [sine(i) for i in range(320)])
    before = deepcopy(state)
    center = transform.center(state)
    z, state = transform.forward(123.0, state)
    assert z == 123.0 - center
    feature, label, tick = state["archive"][-1]
    assert feature == before["feature"]
    assert label == 123.0 - before["history"][-1]
    assert tick == before["n"] - 1
    z2, _ = transform.forward(123.25, deepcopy(before))
    assert z2 - z == pytest.approx(0.25)


def test_first_value_is_retained_and_archive_is_bounded():
    transform = orbit_transform(memory=17)
    z, state = transform.forward(42.0, None)
    assert z == 42.0
    assert transform.inverse_path([z], None) == [42.0]
    for i in range(200):
        _, state = transform.forward(float(i), state)
    assert len(state["archive"]) == 17
    assert len(state["history"]) == 5


def test_long_memory_removes_an_orbit_without_a_period_parameter():
    long = orbit_transform(memory=512)
    short = orbit_transform(memory=16)
    ys = [sine(i) for i in range(896)]
    zl, state = train(long, ys)
    zs, _ = train(short, ys)
    assert max(abs(z) for z in zl[640:]) < 1e-9
    assert sum(z * z for z in zl[640:]) < 1e-10 * sum(z * z for z in zs[640:])
    # Two full turns ahead. The SAME map advances its state along this path.
    assert long.inverse_path([0.0] * 128, state) == pytest.approx(
        [sine(i) for i in range(896, 1024)], abs=1e-8)


def test_same_level_has_different_motion_on_rising_and_falling_visits():
    transform = orbit_transform()
    state = None
    moves = {}
    for i in range(833):
        _, state = transform.forward(sine(i), state)
        if i in (800, 832):
            moves[i] = transform.center(state) - sine(i)
    # Both observations are 10. The delayed slopes distinguish the branches.
    assert sine(800) == pytest.approx(sine(832))
    assert moves[800] < -0.29
    assert moves[832] > 0.29


def test_nonsinusoidal_orbit_at_an_unconfigured_period():
    def wave(i):
        theta = 2.0 * math.pi * i / 63.0
        return 4.0 + 2.0 * math.sin(theta) + 0.8 * math.sin(3.0 * theta + 0.3)

    transform = orbit_transform()
    _, state = train(transform, [wave(i) for i in range(882)])
    assert transform.inverse_path([0.0] * 126, state) == pytest.approx(
        [wave(i) for i in range(882, 1008)], abs=1e-8)


def test_conditional_center_learns_nonperiodic_nonlinear_motion():
    # The chaotic logistic map supplies recurrence without a seasonal clock.
    transform = orbit_transform()
    state = None
    value = 0.1234
    errors = []
    changes = []
    for i in range(1024):
        previous = value
        value = 3.9 * value * (1.0 - value)
        z, state = transform.forward(value, state)
        if i >= 768:
            errors.append(z * z)
            changes.append((value - previous) ** 2)
    assert sum(errors) < 0.04 * sum(changes)


def test_one_step_distribution_inverse_preserves_the_full_mixture():
    transform = orbit_transform()
    _, state = train(transform, [sine(i) for i in range(320)])
    dist = Dist([(0.3, -1.0, 0.2), (0.7, 2.0, 1.3)])
    center = transform.center(state)
    inv = transform.inverse_k([dist], state)[0]
    for p in (0.01, 0.1, 0.5, 0.9, 0.99):
        assert inv.quantile(p) == pytest.approx(dist.quantile(p) + center, abs=1e-7)
    for y in (-2.0, 0.0, 3.0):
        assert inv.cdf(y + center) == pytest.approx(dist.cdf(y))
        assert inv.pdf(y + center) == pytest.approx(dist.pdf(y))


@pytest.mark.parametrize("phi", [0.0, 0.7, -0.6, 1.0])
def test_distribution_rollout_against_linear_independent_innovation_oracle(phi):
    class LinearCenter(OrbitTransform):
        def center(self, state):
            return phi * state["history"][-1] if state and state["history"] else 0.0

    transform = LinearCenter(memory=8, paths=4096)
    _, state = train(transform, [2.0])
    means = [0.3, -0.8, 1.1]
    variances = [0.4, 1.7, 0.8]
    dists = [Dist.gaussian(m, math.sqrt(v)) for m, v in zip(means, variances)]
    saved = pickle.dumps(state)
    out = transform.inverse_k(dists, state)
    mean, variance = 2.0, 0.0
    for d, m, v in zip(out, means, variances):
        mean = phi * mean + m
        variance = phi * phi * variance + v
        # Antithetic Gaussian draws give exact linear means; variances are MC.
        assert d.mean == pytest.approx(mean, abs=1e-12)
        assert d.var == pytest.approx(variance, rel=0.07)
    assert pickle.dumps(state) == saved


def test_distribution_approximation_is_deterministic_and_prefix_consistent():
    transform = orbit_transform(paths=12)
    _, state = train(transform, [sine(i) for i in range(96)])
    dists = [Dist([(0.2, -0.5, 0.1), (0.8, 0.2, 0.6)])] * 5
    saved = pickle.dumps(state)
    short = transform.inverse_k(dists[:3], state)
    long = transform.inverse_k(dists, state)
    repeat = transform.inverse_k(dists, state)
    assert [d.components for d in short] == [d.components for d in long[:3]]
    assert [d.components for d in long] == [d.components for d in repeat]
    assert pickle.dumps(state) == saved


def test_checkpoint_restore_with_reconstructed_transform():
    left = orbit_transform(memory=48, paths=4)
    right = orbit_transform(memory=48, paths=4)
    _, a = train(left, [sine(i) for i in range(100)])
    b = pickle.loads(pickle.dumps(a))
    for i in range(100, 140):
        za, a = left.forward(sine(i), a)
        zb, b = right.forward(sine(i), b)
        assert za == zb
    assert a == b


@pytest.mark.parametrize("scale, offset", [(7.0, 123.0), (-3.0, -17.0)])
def test_learned_center_respects_a_change_of_units_and_origin(scale, offset):
    transform = orbit_transform()
    ys = [sine(i) for i in range(160)]
    _, a = train(transform, ys)
    _, b = train(transform, [scale * y + offset for y in ys])
    assert transform.center(b) == pytest.approx(scale * transform.center(a) + offset)


@pytest.mark.parametrize("order", [0, 1])
@pytest.mark.parametrize("existing", [ema_transform, log_transform])
def test_composes_with_an_existing_transform_in_either_order(order, existing):
    k = 3
    other = existing(0.1) if existing == ema_transform else existing(lower=-100.0)
    transforms = [orbit_transform(memory=32, paths=4), other]
    if order:
        transforms.reverse()
    f = leaf(k=k)
    for transform in transforms:
        f = conjugate(f, transform, k=k)
    state = None
    for i in range(48):
        dists, state = f(sine(i), state)
    assert len(dists) == k
    assert all(math.isfinite(d.mean) and math.isfinite(d.var) for d in dists)


def test_exact_translation_of_an_existing_nonlinear_predictive():
    _, inv = log_transform()
    dist = inv([Dist.gaussian(0.2, 0.3)], {})[0]
    transform = orbit_transform(paths=4)
    _, state = train(transform, [sine(i) for i in range(64)])
    center = transform.center(state)
    out = transform.inverse_k([dist, dist], state)
    for p in (0.01, 0.5, 0.99):
        y = dist.quantile(p)
        assert out[0].quantile(p) == pytest.approx(y + center)
        assert out[0].cdf(y + center) == pytest.approx(p)
        assert out[0].pdf(y + center) == pytest.approx(dist.pdf(y))


def test_parade_handles_missing_observations_and_freezes_transform():
    f = parade(conjugate(leaf(k=2), orbit_transform(paths=4), k=2), k=2)
    _, state = f(2.0, None)
    before = pickle.dumps(state["base"])
    dists, state = f(float("nan"), state)
    assert pickle.dumps(state["base"]) == before
    assert len(dists) == 2
    assert state["skipped"] == 1
    dists, _ = f(3.0, state)
    assert all(math.isfinite(d.mean) for d in dists)


@pytest.mark.parametrize("kwargs", [
    {"memory": 0}, {"neighbors": -1}, {"paths": 1}, {"paths": 3},
    {"lags": ()}, {"lags": (0, 1)}, {"lags": (4, 1)}, {"lags": (1, 1)},
    {"alpha": 0.0}, {"alpha": float("nan")}, {"forget": 1.1},
])
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        orbit_transform(**kwargs)
