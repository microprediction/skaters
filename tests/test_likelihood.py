"""Likelihood tests for the scale-mixture leaf and terminal-leaf ensemble.

Judged the way the package judges everything: held-out predictive
log-likelihood. The scale-mixture leaf should match the Gaussian leaf on
Gaussian data and beat it on heavy tails; wiring it in as the terminal leaf
should carry that gain to the policy output (it does not survive being
mixed inside the pool — that is the whole reason for the terminal design).
"""

import math
import random

from skaters.dist import Dist
from skaters.leaf import leaf, scale_mixture_leaf
from skaters.terminal import terminal_leaf_ensemble
from skaters.conjugate import conjugate
from skaters.transform import ema_transform
from skaters.api import laplace


# --- CRPS correctness (a proper score; kept as a utility) ----------------

def _crps_single_gaussian(mu, sigma, y):
    z = (y - mu) / sigma
    Phi = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    phi = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    return sigma * (z * (2 * Phi - 1) + 2 * phi - 1 / math.sqrt(math.pi))


def test_crps_matches_single_gaussian_formula():
    for mu, sigma, y in [(0, 1, 0), (0, 1, 2.0), (3.0, 2.0, 1.0), (-1, 0.5, 0.4)]:
        assert abs(Dist.gaussian(mu, sigma).crps(y) - _crps_single_gaussian(mu, sigma, y)) < 1e-9


# --- helpers -------------------------------------------------------------

def _student_t(nu, n, seed):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        z = r.gauss(0, 1)
        chi = sum(r.gauss(0, 1) ** 2 for _ in range(nu))
        out.append(z / math.sqrt(chi / nu))
    return out


def _mean_logpdf(make, series, burn=300):
    f = make()
    state, pending = None, None
    tot = 0.0
    n = 0
    for i, y in enumerate(series):
        if pending is not None and i > burn:
            v = pending[0].logpdf(y)
            tot += v if math.isfinite(v) else -20.0
            n += 1
        dists, state = f(y, state)
        pending = dists
    return tot / n


# --- scale-mixture leaf --------------------------------------------------

def test_scale_mixture_is_a_dist_with_zero_means():
    f = scale_mixture_leaf(k=1)
    state = None
    random.seed(0)
    for _ in range(200):
        dists, state = f(random.gauss(0, 1), state)
    d = dists[0]
    assert isinstance(d, Dist)
    assert all(abs(m) < 1e-12 for _, m, _ in d.components)  # discrepancy from N(0,1)


def test_scale_mixture_matches_gaussian_on_gaussian():
    series = [random.Random(1).gauss(0, 1) for _ in range(2500)]
    g = _mean_logpdf(lambda: leaf(1), series)
    sm = _mean_logpdf(lambda: scale_mixture_leaf(1), series)
    assert sm > g - 0.01    # no meaningful likelihood cost on light tails


def test_scale_mixture_beats_gaussian_on_heavy_tails():
    series = _student_t(3, 3000, seed=1)
    g = _mean_logpdf(lambda: leaf(1), series)
    sm = _mean_logpdf(lambda: scale_mixture_leaf(1), series)
    assert sm > g + 0.05    # substantial gain on t3


# --- terminal-leaf ensemble carries the gain -----------------------------

def test_terminal_ensemble_runs_and_is_finite():
    subs = [conjugate(leaf(2), ema_transform(a), 2) for a in (0.05, 0.2)]
    f = terminal_leaf_ensemble(subs, k=2, depths=[1, 1])
    state = None
    random.seed(2)
    for _ in range(120):
        dists, state = f(random.gauss(0, 1), state)
    assert len(dists) == 2
    for d in dists:
        assert d.std > 0 and math.isfinite(d.logpdf(0.0))


def test_terminal_leaf_beats_gaussian_terminal_on_heavy_tails():
    series = _student_t(3, 3000, seed=3)
    subs_g = [conjugate(leaf(1), ema_transform(a), 1) for a in (0.05, 0.2)]
    g = _mean_logpdf(lambda: terminal_leaf_ensemble(
        [conjugate(leaf(1), ema_transform(a), 1) for a in (0.05, 0.2)], leaf_fn=leaf, k=1), series)
    sm = _mean_logpdf(lambda: terminal_leaf_ensemble(
        [conjugate(leaf(1), ema_transform(a), 1) for a in (0.05, 0.2)], k=1), series)
    assert sm > g + 0.05    # the scale-mixture terminal leaf wins, undiluted


def test_laplace_policy_handles_heavy_tails():
    """End to end: the wired-in terminal leaf gives laplace a sane t3 logpdf."""
    series = _student_t(3, 2500, seed=4)
    lp = _mean_logpdf(lambda: laplace(1), series)
    assert -2.0 < lp < -1.6   # ~ -1.93 with the scale-mixture terminal leaf
