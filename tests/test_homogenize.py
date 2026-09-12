"""Tests for the homogenize wrapper (homogenize.py): the online homogenized
scale-mixture correction, composed onto a real base skater's predictive
Dist. The pure z-space mechanics (exact pooling, Huber changepoint escape,
no-regret on iid data, regime tracking) are already thoroughly tested
against the original benchmark module in test_cell_model.py; these tests
cover what's new here -- the ported z-space core plus the Dist-composition
layer (HomogenizedDist) -- and include one direct consistency check against
the benchmark original to guard against transcription drift.
"""
import math
import os
import random
import sys

from skaters import Dist, laplace
from skaters.homogenize import homogenize, make_candidates, cell_step, HomogenizedDist

_HOMOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "benchmarks", "homogenization")
sys.path.insert(0, os.path.normpath(_HOMOG))
import cell_model as cm_bench  # noqa: E402


def _dummy_base(y, state):
    """Always predicts N(0,1): isolates the correction, since z_t == y_t
    exactly (same idiom as test_residual_transform.py)."""
    return [Dist.gaussian(0.0, 1.0)], None


def test_matches_benchmark_cell_model():
    """The ported pure z-space core (cell_step/make_candidates) must agree
    exactly with the original benchmarks/homogenization/cell_model.py on
    the same z-stream and candidate grid -- guards against transcription
    errors when copying into the library module."""
    rng = random.Random(7)
    zs = [rng.gauss(0.0, 1.0) for _ in range(400)]
    lib_candidates = make_candidates()
    bench_candidates = cm_bench.make_candidates()
    lib_state = bench_state = None
    for z in zs:
        lib_corr, lib_state = cell_step(z, lib_state, lib_candidates)
        bench_corr, bench_state = cm_bench.cell_step(z, bench_state, bench_candidates)
        assert lib_corr["weights"] == bench_corr["weights"]
        assert lib_corr["scales"] == bench_corr["scales"]


def test_causal_no_lookahead():
    """Truncating the stream must not change earlier outputs (no lookahead)."""
    random.seed(3)
    ys = [random.gauss(0, 1) for _ in range(150)]
    cut = 90

    def run(stream):
        f = homogenize(laplace(k=1))
        state = None
        snapshots = []
        for y in stream:
            dists, state = f(y, state)
            snapshots.append((dists[0].mean, dists[0].std))
        return snapshots

    full = run(ys)
    prefix = run(ys[:cut])
    assert len(prefix) == cut
    assert full[:cut] == prefix


def test_quantile_monotone_and_roundtrips_cdf():
    """quantile(p) must be strictly increasing, and cdf(quantile(p)) ~= p,
    for a HomogenizedDist with a genuinely non-trivial (non-identity) pooled
    correction."""
    random.seed(2)
    ys = [random.gauss(0, 1.5) for _ in range(600)]
    f = homogenize(laplace(k=1))
    state = None
    for y in ys:
        dists, state = f(y, state)
    corrected = dists[0]

    ps = [0.01, 0.05, 0.1, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9, 0.95, 0.99]
    qs = [corrected.quantile(p) for p in ps]
    assert all(qs[i] < qs[i + 1] for i in range(len(qs) - 1)), qs
    for p, q in zip(ps, qs):
        assert abs(corrected.cdf(q) - p) < 1e-6, (p, q, corrected.cdf(q))


def test_no_regret_on_iid_null():
    """On iid N(0,1) data the correction must not pay a meaningful log-score
    tax relative to the (already correct) base forecast."""
    zs, _ = _gen_iid_gaussian(6000, seed=1)
    f = homogenize(_dummy_base)
    state = None
    scores_raw, scores_corrected = [], []
    for t, z in enumerate(zs):
        dists, state = f(z, state)
        if t >= 500 and t + 1 < len(zs):
            nxt = zs[t + 1]
            scores_raw.append(state["raw"].logpdf(nxt))
            scores_corrected.append(dists[0].logpdf(nxt))
    mean_delta = sum(scores_corrected) / len(scores_corrected) - sum(scores_raw) / len(scores_raw)
    assert mean_delta > -0.01, mean_delta


def test_improves_on_two_state_volatility():
    """On two-state Markov-switching volatility, homogenize must beat the
    (mis-specified, constant-variance) base forecast on held-out log-score."""
    zs = _gen_two_state_sv(6000, seed=3)
    f = homogenize(_dummy_base)
    state = None
    scores_raw, scores_corrected = [], []
    for t, z in enumerate(zs):
        dists, state = f(z, state)
        if t >= 1000 and t + 1 < len(zs):
            nxt = zs[t + 1]
            scores_raw.append(state["raw"].logpdf(nxt))
            scores_corrected.append(dists[0].logpdf(nxt))
    mean_raw = sum(scores_raw) / len(scores_raw)
    mean_corrected = sum(scores_corrected) / len(scores_corrected)
    assert mean_corrected > mean_raw + 0.05, (mean_raw, mean_corrected)


def _gen_iid_gaussian(T, seed):
    rng = random.Random(seed)
    return [rng.gauss(0.0, 1.0) for _ in range(T)], None


def _gen_two_state_sv(T, seed, sigma_lo=0.6, sigma_hi=1.8, p_switch=0.02):
    rng = random.Random(seed)
    y = 0
    sig = {0: sigma_lo, 1: sigma_hi}
    zs = []
    for _ in range(T):
        if rng.random() < p_switch:
            y = 1 - y
        zs.append(sig[y] * rng.gauss(0.0, 1.0))
    return zs
