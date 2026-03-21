"""Tests for online covariance estimators."""

import math
import random
from skaters.cov.running import running_cov
from skaters.cov.ema_cov import ema_cov
from skaters.cov.shrinkage import ledoit_wolf_cov


class TestRunningCov:

    def test_first_obs(self):
        mean, cov, state = running_cov([1.0, 2.0], None)
        assert mean == [1.0, 2.0]
        assert all(c == 0.0 for c in cov)

    def test_known_covariance(self):
        """Two identical series should have perfect correlation."""
        state = None
        random.seed(42)
        for _ in range(1000):
            x = random.gauss(0, 1)
            mean, cov, state = running_cov([x, x], state)
        # Diagonal should be ~1, off-diagonal should be ~1
        assert abs(cov[0] - cov[3]) < 0.1  # var_1 ≈ var_2
        assert abs(cov[1] - cov[0]) < 0.1  # cov ≈ var

    def test_uncorrelated(self):
        state = None
        random.seed(42)
        for _ in range(5000):
            mean, cov, state = running_cov(
                [random.gauss(0, 1), random.gauss(0, 1)], state
            )
        assert abs(cov[1]) < 0.1  # off-diagonal near zero

    def test_3d(self):
        state = None
        random.seed(42)
        for _ in range(100):
            mean, cov, state = running_cov(
                [random.gauss(0, 1), random.gauss(5, 2), random.gauss(-1, 0.5)], state
            )
        assert len(mean) == 3
        assert len(cov) == 9


class TestEmaCov:

    def test_first_obs(self):
        mean, cov, state = ema_cov([1.0, 2.0], None)
        assert mean == [1.0, 2.0]

    def test_adapts_to_change(self):
        """EMA cov should adapt when correlation changes."""
        state = None
        random.seed(42)
        # Phase 1: correlated
        for _ in range(500):
            x = random.gauss(0, 1)
            _, cov1, state = ema_cov([x, x + random.gauss(0, 0.1)], state, alpha=0.02)
        assert cov1[1] > 0  # positive correlation

        # Phase 2: uncorrelated
        for _ in range(500):
            _, cov2, state = ema_cov(
                [random.gauss(0, 1), random.gauss(0, 1)], state, alpha=0.02
            )
        assert abs(cov2[1]) < abs(cov1[1])  # correlation should decrease


class TestLedoitWolf:

    def test_shrinkage_toward_identity(self):
        """With high shrinkage, off-diagonal should be near zero."""
        state = None
        random.seed(42)
        for _ in range(500):
            x = random.gauss(0, 1)
            _, cov, state = ledoit_wolf_cov(
                [x, x], state, shrinkage=0.99
            )
        # Heavy shrinkage → off-diagonal near zero
        assert abs(cov[1]) < abs(cov[0]) * 0.1

    def test_no_shrinkage_preserves_correlation(self):
        state = None
        random.seed(42)
        for _ in range(500):
            x = random.gauss(0, 1)
            _, cov, state = ledoit_wolf_cov(
                [x, x + random.gauss(0, 0.1)], state, shrinkage=0.0
            )
        # No shrinkage → should see correlation
        assert cov[1] > 0

    def test_correlations_bounded(self):
        """Correlations should never exceed [-1, 1]."""
        state = None
        random.seed(42)
        for _ in range(1000):
            y = [random.gauss(0, 1), random.gauss(0, 1)]
            _, _, state = ledoit_wolf_cov(y, state)
        for i in range(2):
            for j in range(2):
                assert abs(state["corr"][i * 2 + j]) <= 1.0 + 1e-10
