"""Tests for invertible online transforms."""

import math
import random
from skaters.transform import (
    difference,
    fractional_difference,
    standardize,
    _frac_diff_weights,
    _frac_int_weights,
)
from skaters.dist import Dist


# --- Differencing ---

class TestDifference:

    def test_forward_first_is_zero(self):
        fwd, _ = difference()
        y_prime, state = fwd(10.0, None)
        assert y_prime == 0.0

    def test_forward_computes_deltas(self):
        fwd, _ = difference()
        state = None
        values = [1.0, 3.0, 2.0, 5.0]
        deltas = []
        for y in values:
            dy, state = fwd(y, state)
            deltas.append(dy)
        assert deltas == [0.0, 2.0, -1.0, 3.0]

    def test_inverse_cumsums_from_anchor(self):
        fwd, inv = difference()
        state = None
        for y in [1.0, 3.0, 7.0]:
            _, state = fwd(y, state)
        # Anchor is 7.0, predict changes [1, 2, -1] as Dist objects
        dists_in = [Dist.gaussian(1.0, 0.5), Dist.gaussian(2.0, 0.5), Dist.gaussian(-1.0, 0.5)]
        result = inv(dists_in, state)
        assert abs(result[0].mean - 8.0) < 1e-6
        assert abs(result[1].mean - 10.0) < 1e-6
        assert abs(result[2].mean - 9.0) < 1e-6

    def test_roundtrip_single_step(self):
        """forward then inverse should recover the next value."""
        fwd, inv = difference()
        state = None
        series = [10.0, 12.0, 11.0, 15.0, 13.0]
        for y in series[:-1]:
            _, state = fwd(y, state)
        # The "true" next delta
        dy_true = series[-1] - series[-2]
        # If we predict that delta correctly, inverse should give us series[-1]
        dists_in = [Dist.gaussian(dy_true, 0.1)]
        result = inv(dists_in, state)
        assert abs(result[0].mean - series[-1]) < 1e-6

    def test_online_no_recomputation(self):
        fwd, _ = difference()
        state = None
        for y in range(1000):
            _, state = fwd(float(y), state)
        # State should only hold last value, not the whole history
        assert "last" in state
        assert len(state) == 1

    def test_inverse_returns_dist(self):
        fwd, inv = difference()
        state = None
        for y in [1.0, 2.0, 3.0]:
            _, state = fwd(y, state)
        dists_in = [Dist.gaussian(1.0, 0.5)]
        result = inv(dists_in, state)
        assert isinstance(result[0], Dist)


# --- Fractional differencing ---

class TestFractionalDifference:

    def test_weights_first_is_one(self):
        w = _frac_diff_weights(0.4, 10)
        assert w[0] == 1.0

    def test_weights_decay(self):
        """Weights should decrease in magnitude for d in (0, 1)."""
        w = _frac_diff_weights(0.4, 20)
        for i in range(1, len(w)):
            assert abs(w[i]) < abs(w[i - 1])

    def test_inverse_weights_are_negated_d(self):
        w_fwd = _frac_diff_weights(0.4, 10)
        w_inv = _frac_int_weights(0.4, 10)
        w_neg = _frac_diff_weights(-0.4, 10)
        for a, b in zip(w_inv, w_neg):
            assert abs(a - b) < 1e-12

    def test_d_equals_1_matches_difference(self):
        """Fractional differencing with d=1 should behave like ordinary differencing."""
        fwd_frac, _ = fractional_difference(d=1.0, window=5)
        fwd_diff, _ = difference()
        s_frac = s_diff = None
        series = [10.0, 12.0, 11.0, 15.0, 13.0]
        for y in series:
            y_frac, s_frac = fwd_frac(y, s_frac)
            y_diff, s_diff = fwd_diff(y, s_diff)
        # After enough values, they should match closely
        assert abs(y_frac - y_diff) < 0.5  # not exact due to truncation

    def test_roundtrip_recovers_values(self):
        """Forward then inverse should approximately recover the original."""
        d = 0.3
        window = 30
        fwd, inv = fractional_difference(d=d, window=window)
        state = None
        random.seed(42)

        # Build up state with a random walk
        series = [0.0]
        for _ in range(100):
            series.append(series[-1] + random.gauss(0, 1))

        transformed = []
        for y in series:
            y_p, state = fwd(y, state)
            transformed.append(y_p)

        # Now predict: if we feed the exact transformed values for the
        # next 3 steps, inverse should recover the original values
        future = []
        future_transformed = []
        state_copy = {"buffer": list(state["buffer"])}
        for _ in range(3):
            y_next = series[-1] + random.gauss(0, 1)
            future.append(y_next)
            y_p, state = fwd(y_next, state)
            future_transformed.append(y_p)

        # Create Dist inputs from exact transformed values
        dists_in = [Dist.gaussian(v, 0.001) for v in future_transformed]
        recovered = inv(dists_in, state_copy)
        for orig, rec in zip(future, recovered):
            assert abs(orig - rec.mean) < 1e-3, f"expected {orig}, got {rec.mean}"

    def test_online_buffer_bounded(self):
        fwd, _ = fractional_difference(d=0.4, window=20)
        state = None
        for y in range(1000):
            _, state = fwd(float(y), state)
        assert len(state["buffer"]) <= 20

    def test_forward_is_incremental(self):
        """Each call should process exactly one observation."""
        fwd, _ = fractional_difference(d=0.3, window=10)
        state = None
        random.seed(42)
        results = []
        for _ in range(50):
            y_p, state = fwd(random.gauss(0, 1), state)
            results.append(y_p)
        assert len(results) == 50
        assert all(math.isfinite(r) for r in results)

    def test_small_d_preserves_memory(self):
        """With small d, the transformed series should still be correlated with the original."""
        fwd, _ = fractional_difference(d=0.1, window=50)
        state = None
        # Trending series
        originals = []
        transformed = []
        for i in range(200):
            y = float(i)
            y_p, state = fwd(y, state)
            originals.append(y)
            transformed.append(y_p)
        # With d=0.1, the transform barely changes the series
        # The last transformed value should still be large (trending)
        assert transformed[-1] > 10

    def test_inverse_returns_dist(self):
        fwd, inv = fractional_difference(d=0.3, window=20)
        state = None
        for y in [1.0, 2.0, 3.0, 4.0, 5.0]:
            _, state = fwd(y, state)
        dists_in = [Dist.gaussian(1.0, 0.5)]
        result = inv(dists_in, state)
        assert isinstance(result[0], Dist)


# --- Standardization ---

class TestStandardize:

    def test_forward_first_is_zero(self):
        fwd, _ = standardize()
        y_p, state = fwd(5.0, None)
        assert y_p == 0.0

    def test_stabilizes_to_zero_mean(self):
        """After many observations from N(10, 1), z-scores should be ~0 mean."""
        fwd, _ = standardize(alpha=0.05)
        state = None
        random.seed(42)
        zs = []
        for _ in range(500):
            y_p, state = fwd(random.gauss(10, 1), state)
            zs.append(y_p)
        mean_z = sum(zs[-100:]) / 100
        assert abs(mean_z) < 1.0

    def test_inverse_recovers_scale(self):
        fwd, inv = standardize(alpha=0.05)
        state = None
        random.seed(42)
        for _ in range(200):
            _, state = fwd(random.gauss(50, 5), state)
        # Predicting z=0 as a Dist should map back to ~mu
        dists_in = [Dist.gaussian(0.0, 1.0)]
        result = inv(dists_in, state)
        assert abs(result[0].mean - 50) < 10

    def test_inverse_roundtrip(self):
        fwd, inv = standardize(alpha=0.01)
        state = None
        random.seed(42)
        for _ in range(500):
            _, state = fwd(random.gauss(100, 10), state)
        # A z-score of 1 should map to mu + sigma
        dists_in = [Dist.gaussian(1.0, 0.1)]
        result = inv(dists_in, state)
        assert result[0].mean > 100  # mu + sigma > mu

    def test_online_constant_state_size(self):
        fwd, _ = standardize()
        state = None
        for y in range(10000):
            _, state = fwd(float(y), state)
        assert "mu" in state
        assert "var" in state
        assert len(state) == 2

    def test_inverse_returns_dist(self):
        fwd, inv = standardize()
        state = None
        for y in [1.0, 2.0, 3.0]:
            _, state = fwd(y, state)
        dists_in = [Dist.gaussian(0.0, 1.0)]
        result = inv(dists_in, state)
        assert isinstance(result[0], Dist)
