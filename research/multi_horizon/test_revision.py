import math
import pickle
from copy import deepcopy
from random import Random
from statistics import NormalDist

import pytest

from skaters import Dist

from .revision import ForecastRevision


def _ar_skater(k, phi):
    def step(y, state):
        return [Dist.gaussian(phi**h * y, math.sqrt(sum(phi**(2 * j) for j in range(h))))
                for h in range(1, k + 1)], {"last": y}

    return step


def _mixture_skater(k):
    def step(y, state):
        return [Dist([(0.63, 0.4 * y - 0.5, 0.8), (0.37, 0.4 * y + 1.4, 1.0 + h / 3)])
                for h in range(1, k + 1)], {"last": y}

    return step


@pytest.mark.parametrize("phi", [1.0, 0.7, -0.6, 0.0])
def test_ar_marginals_and_replay(phi):
    k = 5
    base = _ar_skater(k, phi)
    initial, _ = base(0.0, None)
    rhos = [phi**(h - 1) / initial[h - 1].std for h in range(2, k + 1)]
    model = ForecastRevision(k, base=base, correlations=rhos, tail_mass=0.0)
    state = None
    for y in (1.3, -0.9, 0.0, 2.8, 1.1, -1.2):
        fan, state = model(y, state)
        oracle, _ = base(y, None)
        for d, expected in zip(fan, oracle):
            assert d.mean == pytest.approx(expected.mean)
            assert d.std == pytest.approx(expected.std)
            assert d.logpdf(y) == pytest.approx(expected.logpdf(y))

    scores = [0.2, 1.4, -1.2, 0.0, 0.8]
    expected_path = []
    for shock in scores:
        y = phi * y + shock
        expected_path.append(y)
    assert model.decode(scores, state) == pytest.approx(expected_path)
    assert model.encode(expected_path, state) == pytest.approx(scores)


@pytest.mark.parametrize("rho", [-0.7, 0.55])
@pytest.mark.parametrize("tail_mass", [0.0, 0.05])
def test_revised_mixture_averages_to_issued_marginal(rho, tail_mass):
    model = ForecastRevision(2, base=_mixture_skater(2), correlations=(rho,), tail_mass=tail_mass)
    fan, state = model(0.4)
    thresholds = [-1.9, 0.4, 2.8]
    # Gap-free integration splits out the two independent tails.
    sums = [2.0 * tail_mass * fan[1].cdf(y) for y in thresholds]
    width = 1.0 - 2.0 * tail_mass
    n = 256
    for i in range(n):
        arrival = fan[0].quantile(tail_mass + width * (i + 0.5) / n)
        revised, _ = model(arrival, deepcopy(state))
        for j, y in enumerate(thresholds):
            sums[j] += width * revised[0].cdf(y) / n

    assert sums == pytest.approx([fan[1].cdf(y) for y in thresholds], abs=3e-4)
    density, _ = model(0.1, deepcopy(state))
    d = density[0]
    assert d.pdf(0.4) == pytest.approx((d.cdf(0.40001) - d.cdf(0.39999)) / 0.00002, rel=1e-8)
    assert math.isfinite(d.mean) and d.std > 0.0 and d.crps(0.4) > 0.0


def test_learning_waits_for_target_and_uses_old_issue_time_frames():
    model = ForecastRevision(3, base=_mixture_skater(3), alpha=0.1, tail_mass=0.0)
    original, state = model(1.0)
    arrival, target = 2.1, -0.4
    z1 = original[0].probit(arrival)
    z2 = original[1].probit(target)
    after_arrival, state = model(arrival, state)
    assert state["correlations"] == (0.0, 0.0)

    after_label, state = model(target, state)
    assert state["covariance"][0]["mean"] == pytest.approx([0.1 * z1, 0.1 * z2])
    assert state["covariance"][0]["n"] == 1
    assert state["covariance"][1]["n"] == 0
    assert state["correlations"][0] < 0.0
    # The pair matured on this tick and can affect only later revisions.
    assert after_label[0] is after_arrival[1]


def test_round_trip_forks_adaptive_checkpoint():
    model = ForecastRevision(4, base=_mixture_skater(4))
    state = None
    for i in range(24):
        _, state = model(3 * math.sin(i / 3), state)
    assert any(r != 0.0 for r in state["correlations"])

    checkpoint = pickle.dumps(state)
    rng = Random(218)
    path = model.sample_path(state, rng=rng, steps=6)
    scores = model.encode(path, pickle.loads(checkpoint))
    rng.seed(218)
    assert scores == pytest.approx([rng.gauss(0.0, 1.0) for _ in path], abs=1e-11)
    assert model.decode(scores, state) == pytest.approx(path, abs=1e-11)
    assert pickle.dumps(state) == checkpoint


def test_sampled_paths_match_the_adaptive_fan():
    model = ForecastRevision(3, base=_mixture_skater(3))
    state = None
    for i in range(24):
        forecasts, state = model(2 * math.cos(i / 3), state)
    medians = [d.quantile(0.5) for d in forecasts]
    counts = [0] * 3
    rng = Random(474)
    n_paths = 1600
    for _ in range(n_paths):
        path = model.sample_path(state, rng=rng)
        for h, (y, median) in enumerate(zip(path, medians)):
            counts[h] += y <= median
    assert [n / n_paths for n in counts] == pytest.approx([0.5] * 3, abs=0.045)


@pytest.mark.parametrize("score", [-60.0, -12.0, 12.0, 60.0])
@pytest.mark.parametrize("tail_mass", [0.0, 0.025])
def test_tail_rank_round_trip_without_probability_clipping(score, tail_mass):
    model = ForecastRevision(2, base=_mixture_skater(2), correlations=(0.45,), tail_mass=tail_mass)
    _, state = model(1.0)
    fan, state = model(0.8, state)
    y = fan[0].from_probit(score)
    assert fan[0].probit(y) == pytest.approx(score, rel=1e-12)
    assert math.isfinite(fan[0].logpdf(y))


def test_guard_leaves_outstanding_forecasts_intact_on_extreme_arrivals():
    model = ForecastRevision(3, base=_mixture_skater(3), correlations=(0.75, -0.6))
    fan, state = model(0.0)
    extreme = fan[0].from_probit(50.0)
    revised, state = model(extreme, state)
    assert state["innovation"] == pytest.approx(50.0)
    assert revised[:2] == fan[1:]
    assert revised[-1].mean > fan[-1].mean


def test_missing_tick_ages_fan_and_skips_unavailable_pair():
    model = ForecastRevision(2, base=_mixture_skater(2))
    forecasts, state = model(0.0)
    aged, state = model(math.nan, state)
    assert aged[0] is forecasts[1]
    assert state["base"] == {"last": 0.0}
    assert state["innovation"] is None
    assert state["skipped"] == 1
    _, state = model(0.2, state)
    assert state["covariance"][0]["n"] == 0
    _, state = model(0.4, state)
    assert state["covariance"][0]["n"] == 1


def test_default_laplace_base_and_quantile_interface():
    model = ForecastRevision(4)
    state = None
    for i in range(30):
        forecasts, state = model(0.3 * i + math.sin(i), state)
        assert abs(forecasts[0].quantile(0.5)) < 15.0
    assert len(forecasts) == 4
    assert state["covariance"][2]["n"] > 0
    expected = forecasts[0].quantile(0.75)
    assert forecasts[0].cdf(expected) == pytest.approx(0.75, abs=1e-10)
    assert model.decode([NormalDist().inv_cdf(0.75)], state) == pytest.approx([expected])


def test_atom_is_rejected_at_initialization():
    def atomic(y, state):
        return [Dist.gaussian(y, 0.0)], {}

    with pytest.raises(ValueError, match="positive component scales"):
        ForecastRevision(1, base=atomic)(1.0)
