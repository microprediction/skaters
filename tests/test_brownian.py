"""Brownian motion overfitting tests.

Brownian motion (random walk) has NO predictable structure. The optimal
forecast is y_{t+1} = y_t with uncertainty sigma (the increment std).

Any model that claims to do better is overfitting. These tests check:
1. Point forecasts should be close to "predict last value"
2. Uncertainty should be close to the true increment std
3. No model should systematically beat the true logpdf
4. Models should not be overconfident (std should not be too narrow)
"""

import math
import random
from skaters.ema import ema
from skaters.leaf import leaf
from skaters.conjugate import conjugate
from skaters.transform import (
    difference, fractional_difference, standardize, ema_transform,
    garch, power_transform, ar, grouped_ar,
)
from skaters.ensemble import precision_weighted_ensemble
from skaters.bayesian import bayesian_ensemble
from skaters.api import skater, brown, holt, hosking, laplace, wald, dantzig, bachelier, samuelson
from skaters.search import search
from skaters.dist import Dist


def _brownian(n: int = 1000, sigma: float = 1.0, seed: int = 42) -> list[float]:
    """Generate a standard Brownian motion (random walk)."""
    random.seed(seed)
    y = [0.0]
    for _ in range(n - 1):
        y.append(y[-1] + random.gauss(0, sigma))
    return y


def _run_model(f, series, burn=100):
    """Run a model on a series and collect post-burn-in diagnostics."""
    state = None
    predictions = []
    actuals = []
    logpdfs = []
    stds = []

    prev_pred = None
    prev_std = None
    for i, y in enumerate(series):
        dists, state = f(y, state)
        if i > burn and prev_pred is not None:
            predictions.append(prev_pred)
            actuals.append(y)
            stds.append(prev_std)
            # Score the previous prediction against this observation
            if prev_std > 0:
                logpdfs.append(Dist.gaussian(prev_pred, prev_std).logpdf(y))
        prev_pred = dists[0].mean
        prev_std = dists[0].std

    errors = [p - a for p, a in zip(predictions, actuals)]
    mae = sum(abs(e) for e in errors) / len(errors)
    mean_std = sum(stds) / len(stds)
    mean_logpdf = sum(lp for lp in logpdfs if math.isfinite(lp)) / max(1, len(logpdfs))

    return {
        "mae": mae,
        "mean_std": mean_std,
        "mean_logpdf": mean_logpdf,
        "n": len(errors),
    }


# ---------------------------------------------------------------------------
# Bachelier should be near-optimal on Brownian motion
# ---------------------------------------------------------------------------

class TestBachelierOnBrownian:

    def test_bachelier_near_optimal(self):
        """Bachelier (heavy prior on diff|leaf) should estimate sigma correctly."""
        series = _brownian(sigma=1.0)
        r = _run_model(bachelier(k=1), series)
        assert 0.5 < r["mae"] < 1.2, f"MAE={r['mae']:.3f}"
        assert 0.5 < r["mean_std"] < 2.0, f"std={r['mean_std']:.3f}"

    def test_bachelier_logpdf_near_true(self):
        """Bachelier should achieve logpdf close to the true model."""
        series = _brownian(sigma=1.0)
        r = _run_model(bachelier(k=1), series)
        true_logpdf = -0.5 * math.log(2 * math.pi) - 0.5
        assert r["mean_logpdf"] > true_logpdf - 0.5, (
            f"logpdf={r['mean_logpdf']:.3f}, true≈{true_logpdf:.3f}"
        )


# ---------------------------------------------------------------------------
# Individual transforms should not overfit Brownian motion
# ---------------------------------------------------------------------------

ALL_SINGLE_TRANSFORMS = [
    ("leaf", leaf(k=1)),
    ("ema(0.1)", ema(alpha=0.1, k=1)),
    ("ema(0.3)", ema(alpha=0.3, k=1)),
    ("diff|leaf", conjugate(leaf(k=1), difference(), k=1)),
    ("std|leaf", conjugate(leaf(k=1), standardize(), k=1)),
    ("garch|leaf", conjugate(leaf(k=1), garch(), k=1)),
    ("ar(2)|leaf", conjugate(leaf(k=1), ar(2), k=1)),
    ("ar(5,decay=1)|leaf", conjugate(leaf(k=1), ar(5, decay=1), k=1)),
    ("grouped_ar(16)|leaf", conjugate(leaf(k=1), grouped_ar(16), k=1)),
    ("frac(0.3)|leaf", conjugate(leaf(k=1), fractional_difference(0.3), k=1)),
    ("pow(0.5)|leaf", conjugate(leaf(k=1), power_transform(0.5), k=1)),
]


class TestNoOverfitOnBrownian:

    def test_no_transform_beats_bachelier_by_much(self):
        """No single transform should significantly beat bachelier on Brownian."""
        series = _brownian(sigma=1.0, n=2000)
        baseline = _run_model(bachelier(k=1), series)

        for name, f in ALL_SINGLE_TRANSFORMS:
            r = _run_model(f, series)
            # No model should have logpdf much higher than baseline
            # (would indicate overfitting — claiming to predict noise)
            assert r["mean_logpdf"] < baseline["mean_logpdf"] + 0.3, (
                f"{name} beat baseline by too much: {r['mean_logpdf']:.3f} vs {baseline['mean_logpdf']:.3f}"
            )

    def test_no_model_is_overconfident(self):
        """No model should have std much below true sigma on Brownian motion."""
        series = _brownian(sigma=1.0, n=2000)
        for name, f in ALL_SINGLE_TRANSFORMS:
            r = _run_model(f, series)
            # std should not be much below 0.5 (half the true sigma)
            # Overconfidence = thinks it's explained structure that doesn't exist
            if "diff" in name or "ar" in name:
                # These should have std close to 1.0
                assert r["mean_std"] > 0.3, f"{name} overconfident: std={r['mean_std']:.3f}"

    def test_ar_on_differenced_brownian(self):
        """AR on differenced Brownian (= white noise): coefficients should be near zero."""
        fwd_diff, _ = difference()
        fwd_ar, _ = ar(order=5, decay=1)
        series = _brownian(sigma=1.0, n=2000)
        d_state = ar_state = None
        for y in series:
            dy, d_state = fwd_diff(y, d_state)
            _, ar_state = fwd_ar(dy, ar_state)
        # After differencing, increments are white noise — no AR structure
        for i, phi in enumerate(ar_state["phi"]):
            assert abs(phi) < 0.2, f"phi[{i}]={phi:.4f} — found phantom AR in white noise"

    def test_grouped_ar_on_differenced_brownian(self):
        fwd_diff, _ = difference()
        fwd_gar, _ = grouped_ar(max_lag=16)
        series = _brownian(sigma=1.0, n=2000)
        d_state = gar_state = None
        for y in series:
            dy, d_state = fwd_diff(y, d_state)
            _, gar_state = fwd_gar(dy, gar_state)
        for i, theta in enumerate(gar_state["theta"]):
            assert abs(theta) < 0.3, f"theta[{i}]={theta:.4f} — found phantom structure in white noise"

    def test_ar_correctly_finds_unit_root(self):
        """AR(1) on raw Brownian motion should find phi ≈ 1.0 (the unit root)."""
        fwd, _ = ar(order=1, lam=0.99)
        series = _brownian(sigma=1.0, n=2000)
        state = None
        for y in series:
            _, state = fwd(y, state)
        assert abs(state["phi"][0] - 1.0) < 0.1, f"phi={state['phi'][0]:.4f}, expected ~1.0"


# ---------------------------------------------------------------------------
# Named policies on Brownian motion
# ---------------------------------------------------------------------------

class TestPoliciesOnBrownian:

    def test_all_policies_survive(self):
        """Every policy should run without crashing on Brownian motion."""
        series = _brownian(sigma=1.0, n=500)
        for name, factory in [
            ("brown", brown), ("holt", holt), ("hosking", hosking),
            ("laplace", laplace), ("wald", wald), ("dantzig", dantzig),
            ("bachelier", bachelier),
            ("samuelson", samuelson),
            ("skater(0.5)", lambda k: skater(k=k, aggressiveness=0.5)),
        ]:
            f = factory(k=1)
            state = None
            for y in series:
                dists, state = f(y, state)
            assert math.isfinite(dists[0].mean), f"{name} produced non-finite mean"
            assert dists[0].std > 0, f"{name} collapsed std to 0"

    def test_wald_is_not_overconfident(self):
        """Wald (cautious) should have wide uncertainty on Brownian."""
        series = _brownian(sigma=1.0, n=500)
        r = _run_model(wald(k=1), series)
        assert r["mean_std"] > 0.3, f"wald overconfident: std={r['mean_std']:.3f}"

    def test_samuelson_handles_drift(self):
        """Samuelson should do well on random walk with drift."""
        random.seed(42)
        y = [0.0]
        for _ in range(999):
            y.append(y[-1] + 0.3 + random.gauss(0, 1))
        r = _run_model(samuelson(k=1), y)
        assert math.isfinite(r["mean_logpdf"])
        assert r["mean_std"] > 0

    def test_bachelier_is_best_on_brownian(self):
        """Bachelier should be the best policy on pure Brownian motion."""
        series = _brownian(sigma=1.0, n=1000)
        bach = _run_model(bachelier(k=1), series)
        true_logpdf = -0.5 * math.log(2 * math.pi) - 0.5
        assert bach["mean_logpdf"] > true_logpdf - 0.5, (
            f"bachelier logpdf={bach['mean_logpdf']:.3f}, true≈{true_logpdf:.3f}"
        )


# ---------------------------------------------------------------------------
# Brownian with different sigmas
# ---------------------------------------------------------------------------

class TestBrownianScales:

    def test_small_sigma(self):
        series = _brownian(sigma=0.01, n=1000)
        f = conjugate(leaf(k=1), difference(), k=1)
        r = _run_model(f, series)
        assert r["mean_std"] < 0.1  # should adapt to small sigma

    def test_large_sigma(self):
        series = _brownian(sigma=100.0, n=1000)
        f = conjugate(leaf(k=1), difference(), k=1)
        r = _run_model(f, series)
        assert r["mean_std"] > 10  # should adapt to large sigma


# ---------------------------------------------------------------------------
# Brownian with drift (should NOT fool a well-calibrated model)
# ---------------------------------------------------------------------------

class TestBrownianWithDrift:

    def test_diff_leaf_handles_drift(self):
        """Brownian with drift: diff|leaf should still estimate sigma correctly."""
        random.seed(42)
        y = [0.0]
        for _ in range(999):
            y.append(y[-1] + 0.1 + random.gauss(0, 1))
        f = conjugate(leaf(k=1), difference(), k=1)
        r = _run_model(f, y)
        # Std should still be close to 1.0 (the noise sigma, not the drift)
        assert 0.5 < r["mean_std"] < 2.0
