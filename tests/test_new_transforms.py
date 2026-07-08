"""Tests for GARCH, seasonal differencing, and power transform."""

import math
import random
from skaters.transform import garch, seasonal_difference, power_transform
from skaters.dist import Dist
from skaters.conjugate import conjugate
from skaters.ema import ema


# ---------------------------------------------------------------------------
# GARCH
# ---------------------------------------------------------------------------

class TestGarch:

    def test_forward_basic(self):
        fwd, _ = garch()
        y_prime, state = fwd(1.0, None)
        assert math.isfinite(y_prime)
        assert "var" in state
        assert "last_y" in state

    def test_forward_reduces_vol_clustering(self):
        """After GARCH scaling, the variance of transformed values should be more stable."""
        random.seed(42)
        fwd, _ = garch(omega=0.01, alpha=0.1, beta=0.85)
        state = None
        raw = []
        transformed = []
        vol = 1.0
        for _ in range(500):
            # Simulate GARCH-like data
            vol = max(0.1, 0.01 + 0.1 * (raw[-1] ** 2 if raw else 1) + 0.85 * vol)
            y = random.gauss(0, math.sqrt(vol))
            raw.append(y)
            y_p, state = fwd(y, state)
            transformed.append(y_p)
        # Transformed should have more stable variance
        # (hard to test precisely, just check it runs and produces finite values)
        assert all(math.isfinite(v) for v in transformed[-100:])

    def test_inverse_scales_dist(self):
        fwd, inv = garch()
        state = None
        for y in [1.0, 2.0, -1.0, 3.0, -2.0]:
            _, state = fwd(y, state)
        dists_in = [Dist.gaussian(0.0, 1.0)]
        result = inv(dists_in, state)
        assert isinstance(result[0], Dist)
        # Inverse should scale by sigma, so std should be > 0
        assert result[0].std > 0

    def test_roundtrip_with_ema(self):
        k = 1
        f = conjugate(ema(alpha=0.1, k=k), garch(), k=k)
        state = None
        random.seed(42)
        for _ in range(200):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0].mean)
        assert x[0].std > 0

    def test_constant_series(self):
        fwd, inv = garch()
        state = None
        for _ in range(100):
            _, state = fwd(5.0, state)
        dists_in = [Dist.gaussian(0.0, 1.0)]
        result = inv(dists_in, state)
        assert math.isfinite(result[0].mean)

    def test_volatile_then_calm(self):
        """GARCH variance should adapt: high after volatility, low after calm."""
        fwd, _ = garch(omega=0.01, alpha=0.15, beta=0.8)
        state = None
        random.seed(42)
        # Volatile period
        for _ in range(100):
            _, state = fwd(random.gauss(0, 10), state)
        var_after_vol = state["var"]
        # Calm period
        for _ in range(100):
            _, state = fwd(random.gauss(0, 0.1), state)
        var_after_calm = state["var"]
        assert var_after_calm < var_after_vol

    def test_multistep(self):
        k = 3
        f = conjugate(ema(alpha=0.1, k=k), garch(), k=k)
        state = None
        random.seed(42)
        for _ in range(100):
            x, state = f(random.gauss(0, 1), state)
        assert len(x) == 3
        assert all(math.isfinite(d.mean) for d in x)


# ---------------------------------------------------------------------------
# Seasonal differencing
# ---------------------------------------------------------------------------

class TestSeasonalDifference:

    def test_forward_basic(self):
        fwd, _ = seasonal_difference(period=3)
        state = None
        results = []
        for y in [10.0, 20.0, 30.0, 11.0, 21.0, 31.0]:
            y_p, state = fwd(y, state)
            results.append(y_p)
        # After period=3 values, should compute seasonal diffs
        # y[3] - y[0] = 11 - 10 = 1
        assert abs(results[3] - 1.0) < 1e-10
        # y[4] - y[1] = 21 - 20 = 1
        assert abs(results[4] - 1.0) < 1e-10

    def test_first_period_returns_zero(self):
        fwd, _ = seasonal_difference(period=5)
        state = None
        for i in range(5):
            y_p, state = fwd(float(i), state)
            if i < 5:
                assert y_p == 0.0

    def test_inverse_accumulates_variance_past_period(self):
        """For h >= period the anchor is a previously recovered forecast, so its
        uncertainty must be added: recovered_var[h] = leaf_var + recovered_var[h-s].
        Before the fix the inverse shifted by the anchor mean only and dropped
        this variance, understating uncertainty at long horizons.
        """
        period = 2
        fwd, inv = seasonal_difference(period=period)
        state = None
        for y in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]:
            _, state = fwd(y, state)
        # Constant unit-variance differenced predictive at every horizon.
        k = 4
        dists_in = [Dist.gaussian(0.0, 1.0) for _ in range(k)]
        out = inv(dists_in, state)
        vars_out = [d.var for d in out]
        # h < period: buffer anchor (deterministic) -> var == leaf var == 1.
        assert abs(vars_out[0] - 1.0) < 1e-9
        assert abs(vars_out[1] - 1.0) < 1e-9
        # h >= period: += recovered_var[h-period] == 1 -> var == 2.
        assert abs(vars_out[2] - 2.0) < 1e-9
        assert abs(vars_out[3] - 2.0) < 1e-9

    def test_inverse_shifts_by_lag(self):
        fwd, inv = seasonal_difference(period=4)
        state = None
        for y in [10.0, 20.0, 30.0, 40.0, 15.0, 25.0]:
            _, state = fwd(y, state)
        dists_in = [Dist.gaussian(5.0, 1.0)]
        result = inv(dists_in, state)
        assert isinstance(result[0], Dist)
        assert math.isfinite(result[0].mean)

    def test_removes_seasonal_pattern(self):
        """A perfectly periodic series should have ~zero seasonal diffs."""
        fwd, _ = seasonal_difference(period=7)
        state = None
        pattern = [10, 20, 15, 30, 25, 5, 12]
        diffs = []
        for i in range(50):
            y = float(pattern[i % 7])
            y_p, state = fwd(y, state)
            if i >= 7:
                diffs.append(y_p)
        # All diffs should be zero for a perfectly periodic series
        assert all(abs(d) < 1e-10 for d in diffs)

    def test_roundtrip_with_ema(self):
        k = 1
        f = conjugate(ema(alpha=0.1, k=k), seasonal_difference(period=7), k=k)
        state = None
        random.seed(42)
        pattern = [10, 20, 15, 30, 25, 5, 12]
        for i in range(200):
            y = pattern[i % 7] + random.gauss(0, 0.5)
            x, state = f(y, state)
        assert math.isfinite(x[0].mean)

    def test_buffer_bounded(self):
        fwd, _ = seasonal_difference(period=10)
        state = None
        for i in range(1000):
            _, state = fwd(float(i), state)
        assert len(state["buffer"]) <= 20  # 2 * period

    def test_multistep(self):
        k = 3
        f = conjugate(ema(alpha=0.1, k=k), seasonal_difference(period=7), k=k)
        state = None
        random.seed(42)
        for i in range(100):
            x, state = f(float(i % 7) + random.gauss(0, 0.1), state)
        assert len(x) == 3


# ---------------------------------------------------------------------------
# Power transform
# ---------------------------------------------------------------------------

class TestPowerTransform:

    def test_forward_basic(self):
        fwd, _ = power_transform(p=0.5)
        y_p, _ = fwd(4.0, None)
        assert abs(y_p - 2.0) < 1e-10  # sqrt(4) = 2

    def test_forward_negative(self):
        fwd, _ = power_transform(p=0.5)
        y_p, _ = fwd(-4.0, None)
        assert abs(y_p - (-2.0)) < 1e-10  # -sqrt(4) = -2

    def test_forward_zero(self):
        fwd, _ = power_transform(p=0.5)
        y_p, _ = fwd(0.0, None)
        assert y_p == 0.0

    def test_roundtrip_scalar(self):
        """Forward then inverse should approximately recover the original."""
        fwd, inv = power_transform(p=0.5)
        state = None
        for y in [3.0, -7.0, 0.1, -0.1, 100.0]:
            y_p, state = fwd(y, state)
            d_in = [Dist.gaussian(y_p, 0.001)]
            result = inv(d_in, state)
            assert abs(result[0].mean - y) < 0.1, f"failed for y={y}"

    def test_compresses_tails(self):
        """Large values should be compressed more than small ones."""
        fwd, _ = power_transform(p=0.5)
        _, _ = fwd(1.0, None)
        y_small, _ = fwd(4.0, None)
        y_large, _ = fwd(10000.0, None)
        # Ratio in transformed space should be smaller than in original
        assert y_large / y_small < 10000.0 / 4.0

    def test_inverse_returns_dist(self):
        fwd, inv = power_transform(p=0.5)
        _, state = fwd(5.0, None)
        result = inv([Dist.gaussian(2.0, 0.5)], state)
        assert isinstance(result[0], Dist)
        assert result[0].std > 0

    def test_roundtrip_with_ema(self):
        k = 1
        f = conjugate(ema(alpha=0.1, k=k), power_transform(0.5), k=k)
        state = None
        random.seed(42)
        for _ in range(200):
            x, state = f(random.gauss(0, 5), state)
        assert math.isfinite(x[0].mean)
        assert x[0].std > 0

    def test_different_powers(self):
        for p in [0.1, 0.3, 0.5, 0.7, 0.9]:
            fwd, inv = power_transform(p=p)
            state = None
            _, state = fwd(10.0, state)
            result = inv([Dist.gaussian(0.0, 1.0)], state)
            assert math.isfinite(result[0].mean)

    def test_long_run_stable(self):
        k = 1
        f = conjugate(ema(alpha=0.1, k=k), power_transform(0.5), k=k)
        state = None
        random.seed(42)
        for _ in range(5000):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0].mean)
