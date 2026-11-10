"""Conformal time-series arms: each check has an answer known in advance."""
import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))
import conformal_arms as ca  # noqa: E402
from skaters.dist import Dist  # noqa: E402

TAU = ca.LEVELS


def test_aci_long_run_coverage_holds_on_a_shifting_sequence():
    """Gibbs-Candes: |mean(1{u<=a}) - tau| <= (max(a1,1-a1)+gamma)/(gamma T) for every sequence."""
    rng = np.random.default_rng(0)
    lv = ca._Levels("aci")
    hits = np.zeros_like(TAU)
    T = 6000
    for t in range(T):
        u = rng.uniform() ** (0.3 if (t // 500) % 2 else 3.0)       # regimes far from uniform
        hits += (u <= lv.levels())
        lv.update(u)
    bound = (1.0 + ca.GAMMA) / (ca.GAMMA * T)
    assert np.all(np.abs(hits / T - TAU) <= bound + 1e-12)


def test_roll_recovers_the_quantiles_of_a_miscalibrated_base():
    """Base N(0,1), data N(0,4): u = Phi(y) has a known law; roll's levels are its quantiles."""
    rng = np.random.default_rng(1)
    lv = ca._Levels("roll")
    for _ in range(ca.CAL):
        y = rng.normal(0.0, 2.0)
        lv.update(0.5 * (1.0 + math.erf(y / math.sqrt(2.0))))
    a = lv.levels()
    # the tau-quantile of u is Phi(2 * z_tau)
    z = np.array([math.sqrt(2.0) * _erfinv(2 * t - 1) for t in TAU])
    exact = np.array([0.5 * (1.0 + math.erf(2 * zz / math.sqrt(2.0))) for zz in z])
    mid = (TAU > 0.1) & (TAU < 0.9)
    assert np.max(np.abs(a[mid] - exact[mid])) < 0.12


def test_identity_wrapper_is_the_base_exactly():
    d = Dist([(0.6, 1.0, 2.0), (0.4, -3.0, 0.5)])
    g = ca.wrap([d] * ca.TEST, [0.0] * ca.TEST, "id")[-1]
    for x in (-4.0, -1.0, 0.3, 2.5):
        assert abs(g.logpdf(x) - d.logpdf(x)) < 1e-9     # the strict-increase nudge on the knots
        assert abs(g.cdf(x) - d.cdf(x)) < 1e-9
    for p in (0.05, 0.5, 0.9):
        assert abs(g.quantile(p) - d.quantile(p)) < 1e-9


def test_recalibrated_quantiles_hit_the_chosen_base_levels_and_density_integrates():
    d = Dist.gaussian(0.0, 1.0)
    a = np.clip(ca.LEVELS ** 1.7, 1e-6, None)               # an arbitrary monotone level map
    g = ca.Recalibrated(d, a)
    for t, ai in zip(ca.LEVELS, a):
        assert abs(g.quantile(t) - d.quantile(ai)) < 1e-9
        assert abs(g.cdf(d.quantile(ai)) - t) < 1e-6
    xs = np.linspace(-9, 9, 36001)
    mass = np.trapezoid(np.exp([g.logpdf(x) for x in xs]), xs)
    assert abs(mass - 1.0) < 1e-3


def test_crps_by_quantile_integral_matches_the_base():
    d = Dist.gaussian(0.5, 1.5)
    g = ca.Recalibrated(d, ca.LEVELS)
    for y in (-2.0, 0.5, 3.0):
        assert abs(g.crps(y) - d.crps(y)) < 0.01


def test_histogram_system_on_iid_normals_matches_normal_quantiles():
    rng = random.Random(3)
    ch = [rng.gauss(0.0, 1.0) for _ in range(1100)]
    ds = ca.histogram_dists(ch)
    assert len(ds) == ca.TEST
    med = np.median([d.quantile(0.5) for d in ds])
    hi = np.median([d.quantile(0.95) for d in ds])
    assert abs(med) < 0.25 and abs(hi - 1.645) < 0.45


def test_laplace_base_with_calibration_steps_scores_the_same_window():
    import arm_adapters as aa
    rng = random.Random(4)
    ch = [rng.gauss(0.0, 1.0) for _ in range(400)]
    a = aa.laplace_dists(ch, 1)
    b = aa.laplace_dists(ch, 1, nsteps=ca.CAL + ca.TEST)[-ca.TEST:]
    assert [x.mean for x in a] == [x.mean for x in b]


def _erfinv(x):
    # Giles' approximation is enough for a test tolerance; refine with two Newton steps
    w = -math.log((1.0 - x) * (1.0 + x))
    if w < 5:
        w -= 2.5
        p = 2.81022636e-08
        for c in (3.43273939e-07, -3.5233877e-06, -4.39150654e-06, 0.00021858087, -0.00125372503,
                  -0.00417768164, 0.246640727, 1.50140941):
            p = c + p * w
    else:
        w = math.sqrt(w) - 3
        p = -0.000200214257
        for c in (0.000100950558, 0.00134934322, -0.00367342844, 0.00573950773, -0.0076224613,
                  0.00943887047, 1.00167406, 2.83297682):
            p = c + p * w
    y = p * x
    for _ in range(2):
        y -= (math.erf(y) - x) / (2 / math.sqrt(math.pi) * math.exp(-y * y))
    return y
