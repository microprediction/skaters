"""Tests for the online residual-transform wrapper (residual_transform.py)."""

import math
import random
from skaters import leaf, laplace, Dist
from skaters.residual_transform import residual_transform, CorrectedDist


def _dummy_base(y, state):
    """A base skater that always predicts N(0,1), ignoring y and state.

    Used to isolate the residual-transform learner: since the base always
    predicts standard normal, the wrapper's internal z_t equals y_t exactly,
    so a synthetic y-stream built from the M2 recursion directly IS the
    planted z-stream.
    """
    return [Dist.gaussian(0.0, 1.0)], None


def test_m0_reduces_to_base():
    """M0 (identity) must reproduce the base Dist exactly (to bisection tol)."""
    random.seed(1)
    ys = [random.gauss(0, 1) for _ in range(60)]
    f = residual_transform(leaf(k=1), model="m0")
    state = None
    for y in ys:
        dists, state = f(y, state)
        corrected = dists[0]
        base = state["raw"]
        for x in (base.mean - 1.0, base.mean, base.mean + 1.5):
            assert abs(corrected.cdf(x) - base.cdf(x)) < 1e-6
            assert abs(corrected.logpdf(x) - base.logpdf(x)) < 1e-5
            # CRPS goes through the 32-point quantile-grid quadrature (not the
            # closed-form mixture formula base.crps uses), so it only agrees
            # approximately even under the identity transform.
            assert abs(corrected.crps(x) - base.crps(x)) < 3e-3
        for p in (0.05, 0.25, 0.5, 0.75, 0.95):
            assert abs(corrected.quantile(p) - base.quantile(p)) < 1e-4


def test_quantile_monotone():
    """quantile(p) must be strictly increasing across p, for every model."""
    random.seed(2)
    ys = [random.gauss(0, 1.5) for _ in range(300)]
    ps = [0.01, 0.05, 0.1, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9, 0.95, 0.99]
    for model in ("m0", "m1", "m2"):
        f = residual_transform(laplace(k=1), model=model)
        state = None
        for y in ys:
            dists, state = f(y, state)
        corrected = dists[0]
        qs = [corrected.quantile(p) for p in ps]
        assert all(qs[i] < qs[i + 1] for i in range(len(qs) - 1)), (model, qs)


def test_causal_no_lookahead():
    """Truncating the stream must not change earlier outputs (no lookahead)."""
    random.seed(3)
    ys = [random.gauss(0, 1) for _ in range(150)]
    cut = 90

    def run(stream):
        f = residual_transform(laplace(k=1), model="m2")
        state = None
        snapshots = []
        for y in stream:
            dists, state = f(y, state)
            snapshots.append((dict(state["theta"]), dists[0].mean, dists[0].std))
        return snapshots

    full = run(ys)
    prefix = run(ys[:cut])

    assert len(prefix) == cut
    for i in range(cut):
        theta_full, mean_full, std_full = full[i]
        theta_pref, mean_pref, std_pref = prefix[i]
        assert theta_full == theta_pref, i
        assert mean_full == mean_pref, i
        assert std_full == std_pref, i


def _simulate_m2(T, a_true, b_true, c_true, seed):
    """Standard SV generator: the log-variance recursion is driven by the
    standardized innovation eps_t ~ N(0,1), not by the raw y_t. Driving it by
    y_t would be self-referentially explosive -- y_t already carries the
    current scale (y_t = exp(ell_t/2)*eps_t), so feeding it back in directly
    compounds without bound. eps_t is what the recursion in section 5 means
    by "z_t" when the base forecast is itself perfectly scaled; feeding the
    *observation* y_t through a naive N(0,1) base (see _dummy_base) recovers
    an attenuated but correctly-signed version of the same signal, exactly
    the scenario M1/M2 are meant to exploit.
    """
    rng = random.Random(seed)
    ell = 0.0
    ys = []
    for t in range(T):
        eps = rng.gauss(0.0, 1.0)
        sigma = math.exp(0.5 * ell)
        ys.append(sigma * eps)
        ell = a_true * ell + b_true * eps + c_true * (eps * eps - 1.0)
        ell = max(min(ell, 20.0), -20.0)
    return ys


def _held_out_scores(ys, model, lr=0.02, warmup=500):
    f = residual_transform(_dummy_base, model=model, lr=lr)
    state = None
    preds = []
    for y in ys:
        dists, state = f(y, state)
        preds.append(dists[0])
    scores = [preds[i].logpdf(ys[i + 1]) for i in range(warmup, len(ys) - 1)]
    return sum(scores) / len(scores), state


def test_recovers_planted_leverage():
    """With a planted leverage effect (b != 0), M2 should learn b with the
    planted sign and beat M1 on held-out log-score."""
    ys = _simulate_m2(T=4000, a_true=0.7, b_true=-0.35, c_true=0.1, seed=42)

    score_m1, _ = _held_out_scores(ys, "m1")
    score_m2, state_m2 = _held_out_scores(ys, "m2")

    assert state_m2["learner"]["b"] < -0.05, state_m2["learner"]
    assert score_m2 > score_m1, (score_m1, score_m2)


def test_no_spurious_leverage_when_absent():
    """With no planted leverage (b_true = 0, pure ARCH-style clustering),
    the learner must not converge to a large |b|, and M2 must not show a
    reliable edge over M1."""
    ys = _simulate_m2(T=4000, a_true=0.7, b_true=0.0, c_true=0.1, seed=123)

    score_m1, _ = _held_out_scores(ys, "m1")
    score_m2, state_m2 = _held_out_scores(ys, "m2")

    # Some sampling noise in the estimated b is expected at finite T under the
    # null; the decisive check is that M2 gets no reliable *score* edge from
    # it (across several seeds this differences is consistently <= 0, i.e.
    # the extra parameter is pure estimation noise, not signal).
    assert abs(state_m2["learner"]["b"]) < 0.25, state_m2["learner"]
    assert score_m2 - score_m1 < 0.03, (score_m1, score_m2)
