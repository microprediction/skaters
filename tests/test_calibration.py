"""Calibration and proper-scoring tests.

These check the things that actually matter for a distributional forecaster
and that the rest of the suite doesn't: CRPS correctness, and that conformal
recalibration brings interval coverage to nominal on miscalibrated data.
"""

import math
import random

from skaters.dist import Dist
from skaters.leaf import leaf, heavy_leaf
from skaters.conformal import conformal
from skaters.conjugate import conjugate
from skaters.transform import ema_transform


# --- CRPS ---------------------------------------------------------------

def _crps_single_gaussian(mu, sigma, y):
    """Analytic CRPS of a single Gaussian (Gneiting & Raftery 2007)."""
    z = (y - mu) / sigma
    Phi = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    phi = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    return sigma * (z * (2 * Phi - 1) + 2 * phi - 1 / math.sqrt(math.pi))


def test_crps_matches_single_gaussian_formula():
    for mu, sigma, y in [(0, 1, 0), (0, 1, 2.0), (3.0, 2.0, 1.0), (-1, 0.5, 0.4)]:
        d = Dist.gaussian(mu, sigma)
        assert abs(d.crps(y) - _crps_single_gaussian(mu, sigma, y)) < 1e-9


def test_crps_nonnegative_and_proper():
    d = Dist.gaussian(0.0, 1.0)
    assert d.crps(0.0) >= 0
    # A worse observation (further from the forecast) scores worse.
    assert d.crps(0.0) < d.crps(1.0) < d.crps(4.0)


def test_crps_matches_numerical_integral_for_mixture():
    d = Dist([(0.6, -1.0, 0.5), (0.4, 2.0, 1.0)])
    y = 0.3
    # CRPS = ∫ (F(t) - 1{t>=y})^2 dt, integrated numerically.
    lo, hi, steps = -12.0, 12.0, 24000
    dt = (hi - lo) / steps
    approx = 0.0
    for i in range(steps):
        t = lo + (i + 0.5) * dt
        diff = d.cdf(t) - (1.0 if t >= y else 0.0)
        approx += diff * diff * dt
    assert abs(d.crps(y) - approx) < 1e-3


# --- heavy leaf ---------------------------------------------------------

def test_heavy_leaf_is_variance_matched_and_leptokurtic():
    f = heavy_leaf(k=1, excess_kurtosis=6.0)
    state = None
    random.seed(0)
    for _ in range(400):
        dists, state = f(random.gauss(0, 2.0), state)
    d = dists[0]
    assert len(d) == 2                      # scale mixture
    assert abs(d.mean) < 1e-9               # centred
    assert 1.6 < d.std < 2.4                # variance ~ matched to data
    # Heavier tails than a Gaussian of the same std: more mass beyond 3 sigma.
    s = d.std
    tail = 1 - d.cdf(3 * s)
    gauss_tail = 1 - 0.5 * (1 + math.erf(3 / math.sqrt(2)))
    assert tail > gauss_tail


# --- conformal calibration ----------------------------------------------

def _student_t(nu, n, seed):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        z = r.gauss(0, 1)
        chi = sum(r.gauss(0, 1) ** 2 for _ in range(nu))
        out.append(z / math.sqrt(chi / nu))
    return out


def _coverage(skater_factory, series, level, burn=300):
    f = skater_factory()
    state, pending = None, None
    covered = n = 0
    lo_p, hi_p = (1 - level) / 2, 1 - (1 - level) / 2
    for i, y in enumerate(series):
        if pending is not None and i > burn:
            d = pending[0]
            if d.quantile(lo_p) <= y <= d.quantile(hi_p):
                covered += 1
            n += 1
        dists, state = f(y, state)
        pending = dists
    return covered / n


def _gaussian_base():
    # Fast Gaussian base: EMA level + Gaussian leaf.
    return conjugate(leaf(k=1), ema_transform(0.1), k=1)


def test_gaussian_base_miscalibrated_on_heavy_tails():
    series = _student_t(3, 2000, seed=1)
    c50 = _coverage(_gaussian_base, series, 0.5)
    assert c50 > 0.6   # a Gaussian over-covers the centre of t3 data


def test_conformal_fixes_heavy_tail_coverage():
    series = _student_t(3, 2000, seed=1)
    base50 = _coverage(_gaussian_base, series, 0.5)
    conf50 = _coverage(lambda: conformal(_gaussian_base(), k=1), series, 0.5)
    # Conformal pulls the 50% interval back toward nominal.
    assert conf50 < base50 - 0.05
    assert 0.43 <= conf50 <= 0.60


def test_conformal_keeps_calibration_on_gaussian():
    random.seed(2)
    series = [random.gauss(0, 1) for _ in range(2000)]
    for level in (0.5, 0.95):
        cov = _coverage(lambda: conformal(_gaussian_base(), k=1), series, level)
        assert abs(cov - level) < 0.06


def test_conformal_passthrough_before_min_obs():
    f = conformal(_gaussian_base(), k=1, min_obs=50)
    state = None
    random.seed(3)
    for _ in range(20):
        dists, state = f(random.gauss(0, 1), state)
    # Before min_obs, output is the (single-Gaussian) base prediction.
    assert len(dists[0]) == 1
