"""flesaker / log_transform: forecasts never cross the bound, the pushforward is
the exact change of variables (closed-form log-normal checks for the floor,
a shifted floor and a ceiling), the state is laplace's own, and exact=True
transforms accept laplace's tail-spliced predictive once the splice is live."""
import math
import random

import pytest

from skaters import Dist, conjugate, flesaker, laplace, log_transform
from skaters.tails import SplicedDist
from skaters.transform import power_transform, yeo_johnson


def _rate(n, seed=7, scale=0.05):
    rng = random.Random(seed)
    x, out = 0.0, []
    for _ in range(n):
        x += 0.05 * (-x) + 0.2 * rng.gauss(0.0, 1.0)
        out.append(scale * math.exp(x))
    return out


def _run(f, ys):
    state = None
    for y in ys:
        dists, state = f(y, state)
    return dists, state


# 1,500 ticks: laplace's GPD splice needs matured PITs and exceedances before
# it replaces the plain Dist, which happens somewhere past 1,000 on this series
N_SPLICED = 1500


def test_lower_bound_holds_at_every_horizon_once_spliced():
    dists, _ = _run(flesaker(k=3), _rate(N_SPLICED))
    for d in dists:
        assert isinstance(d.inner, SplicedDist)
        assert d.quantile(1e-4) > 0.0
        assert d.cdf(0.0) < 1e-9
        assert d.mean > 0.0 and d.std > 0.0


def test_upper_bound_and_shifted_lower_bound():
    ys = [1.0 - y for y in _rate(150)]
    for d in _run(flesaker(k=2, upper=1.0), ys)[0]:
        assert d.quantile(1 - 1e-4) < 1.0
    for d in _run(flesaker(lower=-3.0), [y - 3.0 for y in _rate(150)])[0]:
        assert d.quantile(1e-4) > -3.0


def test_state_is_laplaces_own():
    _, state = _run(flesaker(), _rate(80))
    assert state["pit"][0] is not None and 0.0 <= state["pit"][0] <= 1.0
    assert state["z"][0] is not None
    assert "s_state" not in state and "t_state" not in state


def test_missing_values_pass_through():
    ys = [None] + _rate(60)
    ys[30] = float("nan")
    dists, state = _run(flesaker(), ys)
    composed, wrapped_state = _run(conjugate(laplace(), log_transform(), k=1), ys)
    assert dists[0].quantile(0.5) > 0.0
    assert dists[0].quantile(0.5) == composed[0].quantile(0.5)
    assert state["skipped"] == 2
    assert state["pit"][0] == wrapped_state["s_state"]["pit"][0]
    d = flesaker()(None, None)[0][0]
    assert d.quantile(0.1) > 0.0
    assert d.mean == d.std == math.inf


def test_observation_on_the_bound_raises():
    forward, _ = log_transform()
    with pytest.raises(ValueError):
        forward(0.0, None)
    forward, _ = log_transform(upper=2.0)
    with pytest.raises(ValueError):
        forward(2.5, None)
    with pytest.raises(ValueError):
        log_transform(lower=0.0, upper=1.0)
    for bound in (math.inf, -math.inf, math.nan):
        with pytest.raises(ValueError, match="finite bound"):
            log_transform(lower=bound)


def _lognormal_logpdf(y, m, s):
    return -math.log(y * s * math.sqrt(2 * math.pi)) - (math.log(y) - m) ** 2 / (2 * s * s)


@pytest.mark.parametrize("lower", [0.0, -3.0, 2.5])
def test_floor_pushforward_is_lognormal_closed_form(lower):
    """N(m, s) in log(y - lower) space is lower + LogNormal(m, s): logpdf (with
    Jacobian), median and moments against the closed form."""
    m, s = math.log(0.2), 0.4
    _, inverse_k = log_transform(lower=lower)
    d = inverse_k([Dist([(1.0, m, s)])], {})[0]
    for x in (0.08, 0.2, 0.5):
        logpdf = _lognormal_logpdf(x, m, s)
        assert d.logpdf(lower + x) == pytest.approx(logpdf, abs=1e-12)
        assert d.pdf(lower + x) == pytest.approx(math.exp(logpdf), rel=1e-12)
    assert d.quantile(0.5) == pytest.approx(lower + math.exp(m), abs=1e-9)
    mean_gap = math.exp(m + s * s / 2)
    assert d.mean == pytest.approx(lower + mean_gap, rel=1e-12)
    assert d.std == pytest.approx(mean_gap * math.sqrt(math.expm1(s * s)), rel=1e-12)


def test_ceiling_pushforward_is_mirrored_lognormal():
    """Under upper=b the map is y = b - exp(-z): N(m, s) in z gives
    b - LogNormal(-m, s). Check logpdf, median and mean."""
    b, m, s = 1.0, 2.0, 0.3
    _, inverse_k = log_transform(upper=b)
    d = inverse_k([Dist([(1.0, m, s)])], {})[0]
    for x in (0.05, 0.135, 0.3):            # gap below the ceiling
        assert d.logpdf(b - x) == pytest.approx(_lognormal_logpdf(x, -m, s), abs=1e-12)
    assert d.quantile(0.5) == pytest.approx(b - math.exp(-m), rel=1e-6)
    assert d.mean == pytest.approx(b - math.exp(-m + s * s / 2), rel=1e-6)
    assert d.quantile(1 - 1e-6) < b


@pytest.mark.parametrize("direction", [1, -1])
def test_support_and_crps_for_shifted_bound(direction):
    b, m, s = 3.0, -0.5, 0.8
    bound = {"lower" if direction == 1 else "upper": b}
    _, inverse_k = log_transform(**bound)
    d = inverse_k([Dist.gaussian(direction * m, s)], {})[0]
    for x in (b, b - 0.25 * direction):
        assert d.cdf(x) == (0.0 if direction == 1 else 1.0)
        assert d.logpdf(x) == -math.inf
        assert d.pdf(x) == 0.0
    mean_gap = math.exp(m + s * s / 2)
    boundary_crps = mean_gap * math.erfc(s / 2)
    assert d.crps(b) == pytest.approx(boundary_crps, rel=5e-4)
    assert d.crps(b - 0.25 * direction) == pytest.approx(d.crps(b) + 0.25, abs=1e-12)
    gap = math.exp(m)
    # At the median, the absolute-error term is mean_gap * (2 * Phi(s) - 1).
    median_crps = mean_gap * (math.erf(s / math.sqrt(2)) - math.erf(s / 2))
    assert d.crps(b + direction * gap) == pytest.approx(median_crps, rel=5e-4)


@pytest.mark.parametrize("direction", [1, -1])
def test_quantile_rounding_stays_inside_the_bound(direction):
    bound = {"lower" if direction == 1 else "upper": 3.0}
    _, inverse_k = log_transform(**bound)
    d = inverse_k([Dist.gaussian(-50.0 * direction, 1.0)], {})[0]
    assert d.quantile(0.5) == math.nextafter(3.0, direction * math.inf)


def test_large_quantiles_and_moments_across_float_range():
    _, inverse_k = log_transform()
    d = inverse_k([Dist.gaussian(705.0, 1.0)], {})[0]
    assert d.quantile(0.5) == pytest.approx(math.exp(705.0), rel=1e-9)
    assert d.mean == pytest.approx(math.exp(705.5), rel=1e-12)
    assert d.std == pytest.approx(math.exp(705.5) * math.sqrt(math.expm1(1.0)), rel=1e-12)
    assert d.var == math.inf
    assert d.crps(0.0) == pytest.approx(math.exp(705.5) * math.erfc(0.5), rel=5e-4)
    d = inverse_k([Dist.gaussian(800.0, 1.0)], {})[0]
    assert d.quantile(0.5) == d.mean == d.std == math.inf


def test_shifted_inverse_can_recover_from_an_overflowing_gap():
    forward, inverse_k = log_transform(lower=-1.4e308)
    z, _ = forward(1.2e308, None)
    d = inverse_k([Dist.gaussian(z, 0.1)], {})[0]
    assert d.quantile(0.5) == pytest.approx(1.2e308, rel=1e-9)


def test_subnormal_query_has_a_finite_log_density():
    y, s = 1e-310, 1.0
    z = math.log(y)
    inner = Dist.gaussian(z - 15.0, s)
    d = log_transform()[1]([inner], {})[0]
    lp = inner.logpdf(z) - z
    assert d.logpdf(y) == pytest.approx(lp, abs=1e-12)
    assert d.pdf(y) == pytest.approx(math.exp(lp), rel=1e-12)
    assert all(math.isnan(query(math.nan)) for query in (d.cdf, d.pdf, d.logpdf, d.crps))


def test_yeo_johnson_zero_allows_values_below_minus_one():
    _, inverse_k = yeo_johnson(0.0, exact=True)
    d = inverse_k([Dist.gaussian(-2.0, 1.0)], {})[0]
    assert 0.0 < d.cdf(-1.0) < 1.0
    assert d.quantile(0.5) == pytest.approx(1.0 - math.sqrt(5.0))


@pytest.mark.parametrize("transform", [yeo_johnson(0.0, exact=True),
                                      power_transform(0.5, exact=True)])
def test_exact_transform_accepts_spliced_laplace(transform):
    """exact=True used to read d.components, which laplace's SplicedDist
    lacks; on origin/main this raised AttributeError once the splice was on."""
    d = _run(conjugate(laplace(), transform, k=1), _rate(N_SPLICED))[0][0]
    assert isinstance(d.inner, SplicedDist)
    assert d.quantile(0.1) < d.quantile(0.5) < d.quantile(0.9)
    assert math.isfinite(d.mean) and d.std > 0.0


def test_spliced_moments_are_plausible():
    """Quantile-grid mean/std for a spliced inner: the mean lies inside
    (q01, q99) and the std is of the order of the interquartile range."""
    d = _run(flesaker(), _rate(N_SPLICED))[0][0]
    assert d.quantile(0.01) < d.mean < d.quantile(0.99)
    iqr = d.quantile(0.75) - d.quantile(0.25)
    assert 0.3 * iqr < d.std < 3.0 * iqr
    assert math.isfinite(d.crps(0.0))
    assert d.crps(-0.25) == pytest.approx(d.crps(0.0) + 0.25, abs=1e-12)
    assert len(d) == 1
    approx = Dist.combine([d])
    assert approx.mean == pytest.approx(d.mean)
    assert approx.std == pytest.approx(d.std)
    _, inverse_k = yeo_johnson(0.0, exact=True)
    nested = inverse_k([d], {})[0]
    assert nested.quantile(0.5) == pytest.approx(math.expm1(d.quantile(0.5)))


def test_hand_composition_matches_flesaker():
    ys = _rate(120)
    a = _run(flesaker(), ys)[0][0]
    b = _run(conjugate(laplace(), log_transform(lower=0.0), k=1), ys)[0][0]
    for p in (0.05, 0.5, 0.95):
        assert a.quantile(p) == b.quantile(p)


def test_name_carries_the_bound():
    assert flesaker(k=2).__name__ == "flesaker(k=2, lower=0.0)"
    assert flesaker(upper=1.0).__name__ == "flesaker(k=1, upper=1.0)"
