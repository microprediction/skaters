"""gibrat / log_transform: forecasts never cross the bound, the pushforward is
the exact change of variables (closed-form log-normal checks for the floor,
a shifted floor and a ceiling), the state is laplace's own, and exact=True
transforms accept laplace's tail-spliced predictive once the splice is live."""
import math
import random

import pytest

from skaters import Dist, conjugate, gibrat, laplace, log_transform
from skaters.tails import SplicedDist
from skaters.transform import yeo_johnson


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
    dists, _ = _run(gibrat(k=3), _rate(N_SPLICED))
    for d in dists:
        assert isinstance(d.inner, SplicedDist)
        assert d.quantile(1e-4) > 0.0
        assert d.cdf(0.0) < 1e-9
        assert d.mean > 0.0 and d.std > 0.0


def test_upper_bound_and_shifted_lower_bound():
    ys = [1.0 - y for y in _rate(150)]
    for d in _run(gibrat(k=2, upper=1.0), ys)[0]:
        assert d.quantile(1 - 1e-4) < 1.0
    for d in _run(gibrat(lower=-3.0), [y - 3.0 for y in _rate(150)])[0]:
        assert d.quantile(1e-4) > -3.0


def test_state_is_laplaces_own():
    _, state = _run(gibrat(), _rate(80))
    assert state["pit"][0] is not None and 0.0 <= state["pit"][0] <= 1.0
    assert state["z"][0] is not None
    assert "s_state" not in state and "t_state" not in state


def test_missing_values_pass_through():
    ys = _rate(60)
    ys[30] = float("nan")
    dists, state = _run(gibrat(), ys)
    assert dists[0].quantile(0.5) > 0.0
    assert state["pit"][0] is not None


def test_observation_on_the_bound_raises():
    forward, _ = log_transform()
    with pytest.raises(ValueError):
        forward(0.0, None)
    forward, _ = log_transform(upper=2.0)
    with pytest.raises(ValueError):
        forward(2.5, None)
    with pytest.raises(ValueError):
        log_transform(lower=0.0, upper=1.0)


def _lognormal_logpdf(y, m, s):
    return -math.log(y * s * math.sqrt(2 * math.pi)) - (math.log(y) - m) ** 2 / (2 * s * s)


@pytest.mark.parametrize("lower", [0.0, -3.0, 2.5])
def test_floor_pushforward_is_lognormal_closed_form(lower):
    """N(m, s) in log(y - lower) space is lower + LogNormal(m, s): logpdf (with
    Jacobian), median and mean against the closed form. Tolerance on the
    logpdf is the 400-knot table's Jacobian."""
    m, s = math.log(0.2), 0.4
    _, inverse_k = log_transform(lower=lower)
    d = inverse_k([Dist([(1.0, m, s)])], {})[0]
    for x in (0.08, 0.2, 0.5):
        assert d.logpdf(lower + x) == pytest.approx(_lognormal_logpdf(x, m, s), abs=1e-3)
    assert d.quantile(0.5) == pytest.approx(lower + math.exp(m), rel=1e-6)
    assert d.mean == pytest.approx(lower + math.exp(m + s * s / 2), rel=1e-6)


def test_ceiling_pushforward_is_mirrored_lognormal():
    """Under upper=b the map is y = b - exp(-z): N(m, s) in z gives
    b - LogNormal(-m, s). Check logpdf, median and mean."""
    b, m, s = 1.0, 2.0, 0.3
    _, inverse_k = log_transform(upper=b)
    d = inverse_k([Dist([(1.0, m, s)])], {})[0]
    for x in (0.05, 0.135, 0.3):            # gap below the ceiling
        assert d.logpdf(b - x) == pytest.approx(_lognormal_logpdf(x, -m, s), abs=1e-3)
    assert d.quantile(0.5) == pytest.approx(b - math.exp(-m), rel=1e-6)
    assert d.mean == pytest.approx(b - math.exp(-m + s * s / 2), rel=1e-6)
    assert d.quantile(1 - 1e-6) < b


def test_table_window_clips_at_exp_overflow():
    """An inner predictive far up in log space must not flatten the table."""
    _, inverse_k = log_transform()
    d = inverse_k([Dist([(1.0, 800.0, 1.0)])], {})[0]
    assert math.isfinite(d.mean) and d.std > 0.0


def test_exact_yeo_johnson_accepts_spliced_laplace():
    """exact=True used to read d.components, which laplace's SplicedDist
    lacks; on origin/main this raised AttributeError once the splice was on."""
    d = _run(conjugate(laplace(), yeo_johnson(0.0, exact=True), k=1), _rate(N_SPLICED))[0][0]
    assert isinstance(d.inner, SplicedDist)
    assert d.quantile(0.1) < d.quantile(0.5) < d.quantile(0.9)
    assert d.quantile(0.001) > -1.0
    assert math.isfinite(d.mean) and d.std > 0.0


def test_spliced_moments_are_plausible():
    """Quantile-grid mean/std for a spliced inner: the mean lies inside
    (q01, q99) and the std is of the order of the interquartile range."""
    d = _run(gibrat(), _rate(N_SPLICED))[0][0]
    assert d.quantile(0.01) < d.mean < d.quantile(0.99)
    iqr = d.quantile(0.75) - d.quantile(0.25)
    assert 0.3 * iqr < d.std < 3.0 * iqr


def test_hand_composition_matches_gibrat():
    ys = _rate(120)
    a = _run(gibrat(), ys)[0][0]
    b = _run(conjugate(laplace(), log_transform(lower=0.0), k=1), ys)[0][0]
    for p in (0.05, 0.5, 0.95):
        assert a.quantile(p) == b.quantile(p)


def test_name_carries_the_bound():
    assert gibrat(k=2).__name__ == "gibrat(k=2, lower=0.0)"
    assert gibrat(upper=1.0).__name__ == "gibrat(k=1, upper=1.0)"
