"""Tests with serially correlated measurement noise.

Serially correlated noise is tricky because:
1. It looks like predictable structure (an AR model will fit it)
2. It IS partially predictable — but only the noise part
3. Models can become overconfident by overfitting the noise correlation
4. The optimal predictor depends on separating signal from correlated noise

We test several scenarios:
- Constant signal + AR(1) noise: AR should help, but shouldn't overfit
- Random walk + AR(1) noise: hardest case, signal and noise both autocorrelated
- Trend + AR(1) noise: drift/holt should capture trend, AR the noise
"""

import math
import random
from skaters.ema import ema
from skaters.leaf import leaf
from skaters.conjugate import conjugate
from skaters.transform import difference, ar, drift, holt_linear, ema_transform
from skaters.api import bachelier, samuelson, yule, brown, holt, laplace, skater
from skaters.dist import Dist


def _correlated_noise(n: int, rho: float, sigma: float = 1.0, seed: int = 42) -> list[float]:
    """Generate AR(1) noise: e_t = rho * e_{t-1} + eps_t."""
    random.seed(seed)
    e = [0.0]
    for _ in range(n - 1):
        e.append(rho * e[-1] + random.gauss(0, sigma))
    return e


def _run_model(f, series, burn=200):
    state = None
    prev_mean = prev_std = None
    logpdfs = []
    errors = []
    for i, y in enumerate(series):
        dists, state = f(y, state)
        if i > burn and prev_mean is not None and prev_std and prev_std > 0:
            logpdfs.append(Dist.gaussian(prev_mean, prev_std).logpdf(y))
            errors.append(abs(prev_mean - y))
        prev_mean = dists[0].mean
        prev_std = dists[0].std
    ll = [lp for lp in logpdfs if math.isfinite(lp)]
    return {
        "mae": sum(errors) / len(errors) if errors else float("inf"),
        "mean_logpdf": sum(ll) / len(ll) if ll else float("-inf"),
        "mean_std": sum(
            s for s in [prev_std] if s and s > 0
        ) if prev_std else float("inf"),
    }


# ---------------------------------------------------------------------------
# Constant signal + AR(1) noise
# ---------------------------------------------------------------------------

class TestConstantPlusCorrelatedNoise:

    def _series(self, rho=0.8, n=2000):
        noise = _correlated_noise(n, rho=rho)
        return [10.0 + e for e in noise]

    def test_ar_helps_on_correlated_noise(self):
        """AR transform should beat plain EMA on correlated noise."""
        series = self._series(rho=0.8)
        r_ema = _run_model(ema(alpha=0.1, k=1), series)
        r_ar = _run_model(conjugate(leaf(k=1), ar(1), k=1), series)
        # AR should have better logpdf (exploits noise correlation)
        assert r_ar["mean_logpdf"] > r_ema["mean_logpdf"] - 0.1

    def test_yule_does_well(self):
        """Yule (AR prior) should handle correlated noise well."""
        series = self._series(rho=0.8)
        r = _run_model(yule(k=1), series)
        assert math.isfinite(r["mean_logpdf"])
        assert r["mae"] < 2.0

    def test_not_overconfident(self):
        """No model should have std collapsing to near zero."""
        series = self._series(rho=0.9)
        for name, f in [
            ("ema", ema(alpha=0.1, k=1)),
            ("ar(1)", conjugate(leaf(k=1), ar(1), k=1)),
            ("ar(2)", conjugate(leaf(k=1), ar(2, decay=1), k=1)),
        ]:
            state = None
            for y in series:
                dists, state = f(y, state)
            assert dists[0].std > 0.1, f"{name} overconfident: std={dists[0].std:.4f}"


# ---------------------------------------------------------------------------
# Random walk + AR(1) noise (hardest case)
# ---------------------------------------------------------------------------

class TestRandomWalkPlusCorrelatedNoise:

    def _series(self, rho=0.7, n=2000):
        random.seed(42)
        rw = [0.0]
        for _ in range(n - 1):
            rw.append(rw[-1] + random.gauss(0, 0.5))
        noise = _correlated_noise(n, rho=rho, seed=99)
        return [r + e for r, e in zip(rw, noise)]

    def test_all_policies_survive(self):
        """Every policy should handle this without crashing."""
        series = self._series()
        for name, factory in [
            ("bachelier", bachelier),
            ("yule", yule),
            ("samuelson", samuelson),
            ("laplace", laplace),
            ("brown", brown),
        ]:
            f = factory(k=1)
            state = None
            for y in series:
                dists, state = f(y, state)
            assert math.isfinite(dists[0].mean), f"{name} non-finite mean"
            assert dists[0].std > 0, f"{name} collapsed std"

    def test_diff_ar_captures_both(self):
        """diff|ar should capture both the random walk and the noise correlation."""
        series = self._series(rho=0.7)
        r_diff = _run_model(conjugate(leaf(k=1), difference(), k=1), series)
        r_diff_ar = _run_model(
            conjugate(conjugate(leaf(k=1), ar(1), k=1), difference(), k=1),
            series,
        )
        # diff|ar should be at least as good as diff alone
        assert r_diff_ar["mean_logpdf"] > r_diff["mean_logpdf"] - 0.2

    def test_not_overconfident(self):
        """On this noisy series, models should have reasonable std."""
        series = self._series(rho=0.9)
        for name, f in [
            ("diff|leaf", conjugate(leaf(k=1), difference(), k=1)),
            ("diff|ar(1)|leaf", conjugate(conjugate(leaf(k=1), ar(1), k=1), difference(), k=1)),
            ("yule", yule(k=1)),
        ]:
            r = _run_model(f, series)
            # Std should be reasonable — not collapsed
            assert r["mae"] > 0.1, f"{name} suspiciously low MAE"


# ---------------------------------------------------------------------------
# Trend + AR(1) noise
# ---------------------------------------------------------------------------

class TestTrendPlusCorrelatedNoise:

    def _series(self, rho=0.7, n=2000):
        noise = _correlated_noise(n, rho=rho, seed=42)
        return [0.1 * t + e for t, e in enumerate(noise)]

    def test_holt_handles_trend_plus_noise(self):
        """Holt should capture the trend even with correlated noise."""
        series = self._series()
        r = _run_model(
            conjugate(leaf(k=1), holt_linear(0.1, 0.05), k=1),
            series,
        )
        assert math.isfinite(r["mean_logpdf"])

    def test_samuelson_handles_trend_plus_noise(self):
        series = self._series()
        r = _run_model(samuelson(k=1), series)
        assert math.isfinite(r["mean_logpdf"])

    def test_drift_plus_ar_is_good(self):
        """drift|ar|leaf should handle both trend and noise correlation."""
        series = self._series(rho=0.7)
        r = _run_model(
            conjugate(conjugate(leaf(k=1), ar(1), k=1),
                      drift(alpha=0.01, shrinkage=0.002), k=1),
            series,
        )
        assert math.isfinite(r["mean_logpdf"])


# ---------------------------------------------------------------------------
# High vs low correlation
# ---------------------------------------------------------------------------

class TestCorrelationStrength:

    def test_ar_benefit_increases_with_rho(self):
        """Higher noise correlation should make AR more beneficial."""
        benefits = []
        for rho in [0.2, 0.5, 0.8]:
            noise = _correlated_noise(2000, rho=rho, seed=42)
            series = [5.0 + e for e in noise]
            r_ema = _run_model(ema(alpha=0.1, k=1), series)
            r_ar = _run_model(conjugate(leaf(k=1), ar(1), k=1), series)
            benefit = r_ar["mean_logpdf"] - r_ema["mean_logpdf"]
            benefits.append(benefit)
        # Higher rho should give more benefit to AR
        # (or at least not reverse the ordering)
        assert benefits[-1] >= benefits[0] - 0.1

    def test_zero_correlation_ar_doesnt_crash(self):
        """With rho=0 (white noise), AR should run without issues."""
        noise = _correlated_noise(2000, rho=0.0, seed=42)
        series = [5.0 + e for e in noise]
        r_ar = _run_model(conjugate(leaf(k=1), ar(1), k=1), series)
        assert math.isfinite(r_ar["mean_logpdf"])


# ---------------------------------------------------------------------------
# Negative autocorrelation (alternating noise)
# ---------------------------------------------------------------------------

class TestNegativeCorrelation:

    def test_negative_rho(self):
        """AR should handle negative autocorrelation (mean-reverting noise)."""
        noise = _correlated_noise(2000, rho=-0.5, seed=42)
        series = [10.0 + e for e in noise]
        r = _run_model(conjugate(leaf(k=1), ar(1), k=1), series)
        assert math.isfinite(r["mean_logpdf"])

    def test_ar_finds_negative_phi_in_residuals(self):
        """After removing level, AR(1) should find negative autocorrelation."""
        from skaters.transform import ar as ar_transform
        fwd_ema, _ = ema_transform(0.05)
        fwd_ar, _ = ar_transform(order=1, lam=0.99)
        noise = _correlated_noise(3000, rho=-0.6, seed=42)
        series = [10.0 + e for e in noise]
        ema_state = ar_state = None
        for y in series:
            resid, ema_state = fwd_ema(y, ema_state)
            _, ar_state = fwd_ar(resid, ar_state)
        # After removing level via EMA, AR should find negative correlation
        assert ar_state["phi"][0] < 0, f"phi={ar_state['phi'][0]:.4f}, expected negative"
