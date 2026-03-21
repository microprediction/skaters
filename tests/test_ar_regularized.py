"""Tests for Minnesota prior and grouped AR."""

import copy
import math
import random
from skaters.transform import ar, grouped_ar, _build_groups
from skaters.conjugate import conjugate
from skaters.leaf import leaf
from skaters.transform import difference
from skaters.dist import Dist


# ---------------------------------------------------------------------------
# Minnesota prior (decay parameter on ar())
# ---------------------------------------------------------------------------

class TestMinnesotaPrior:

    def test_decay_zero_is_uniform(self):
        """decay=0 should be identical to standard ridge."""
        fwd_std, _ = ar(order=3, ridge=1.0, decay=0)
        fwd_minn, _ = ar(order=3, ridge=1.0, decay=0)
        s1 = s2 = None
        random.seed(42)
        for _ in range(100):
            y = random.gauss(0, 1)
            _, s1 = fwd_std(y, s1)
            _, s2 = fwd_minn(y, s2)
        for i in range(3):
            assert abs(s1["phi"][i] - s2["phi"][i]) < 1e-10

    def test_decay_shrinks_distant_lags(self):
        """With decay>0, distant lag coefficients should be smaller."""
        random.seed(42)
        fwd_no, _ = ar(order=5, lam=0.99, decay=0)
        fwd_yes, _ = ar(order=5, lam=0.99, decay=2)
        s_no = s_yes = None
        # Feed AR(1) data — only lag 1 should matter
        y = 0.0
        for _ in range(1000):
            y = 0.5 * y + random.gauss(0, 1)
            _, s_no = fwd_no(y, s_no)
            _, s_yes = fwd_yes(y, s_yes)
        # With strong Minnesota prior, distant lags should be closer to zero
        assert abs(s_yes["phi"][4]) < abs(s_no["phi"][4]) + 0.1

    def test_minnesota_still_learns_lag1(self):
        """Even with strong decay, lag 1 should still be estimated well."""
        random.seed(42)
        fwd, _ = ar(order=5, lam=0.99, decay=2)
        state = None
        y = 0.0
        for _ in range(2000):
            y = 0.7 * y + random.gauss(0, 0.5)
            _, state = fwd(y, state)
        assert abs(state["phi"][0] - 0.7) < 0.15

    def test_minnesota_roundtrip(self):
        fwd, inv = ar(order=3, decay=1)
        state = None
        random.seed(42)
        series = [random.gauss(0, 1) for _ in range(200)]
        for y in series[:150]:
            _, state = fwd(y, state)
        state_snap = copy.deepcopy(state)
        y_next = series[150]
        y_p, _ = fwd(y_next, copy.deepcopy(state_snap))
        recovered = inv([Dist.gaussian(y_p, 1e-6)], state_snap)
        assert abs(recovered[0].mean - y_next) < 0.01

    def test_composable_with_diff(self):
        k = 1
        f = conjugate(conjugate(leaf(k=k), ar(3, decay=1), k=k), difference(), k=k)
        state = None
        random.seed(42)
        for _ in range(200):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0].mean)


# ---------------------------------------------------------------------------
# Grouped AR
# ---------------------------------------------------------------------------

class TestGroupedAR:

    def test_build_groups_small(self):
        g = _build_groups(4)
        assert g == [0, 1, 1, 2]  # lag0→g0, lag1-2→g1, lag3→g2

    def test_build_groups_8(self):
        g = _build_groups(8)
        # 1 + 2 + 4 + 1 = 8
        assert g == [0, 1, 1, 2, 2, 2, 2, 3]

    def test_build_groups_16(self):
        g = _build_groups(16)
        n_groups = max(g) + 1
        # 1 + 2 + 4 + 8 + 1 = 16, so 5 groups
        assert n_groups == 5

    def test_fewer_params_than_lags(self):
        g = _build_groups(64)
        n_groups = max(g) + 1
        assert n_groups < 64
        assert n_groups == 7  # 1+2+4+8+16+32+1

    def test_forward_returns_finite(self):
        fwd, _ = grouped_ar(max_lag=8)
        state = None
        random.seed(42)
        for _ in range(100):
            y_p, state = fwd(random.gauss(0, 1), state)
        assert math.isfinite(y_p)

    def test_coefficients_adapt(self):
        """On AR(1) data, grouped_ar should learn that lag 1 (group 0) dominates."""
        random.seed(42)
        fwd, _ = grouped_ar(max_lag=8, lam=0.99)
        state = None
        y = 0.0
        for _ in range(2000):
            y = 0.6 * y + random.gauss(0, 1)
            _, state = fwd(y, state)
        # Group 0 (lag 1) should have the largest coefficient
        assert abs(state["theta"][0]) > abs(state["theta"][-1])

    def test_residuals_reduce_variance(self):
        random.seed(42)
        fwd, _ = grouped_ar(max_lag=8)
        state = None
        y = 0.0
        raw = []
        resid = []
        for i in range(1000):
            y = 0.7 * y + random.gauss(0, 1)
            raw.append(y)
            y_p, state = fwd(y, state)
            if i > 50:
                resid.append(y_p)
        raw_var = sum(x ** 2 for x in raw) / len(raw)
        resid_var = sum(x ** 2 for x in resid) / len(resid)
        assert resid_var < raw_var

    def test_inverse_returns_dist(self):
        fwd, inv = grouped_ar(max_lag=8)
        state = None
        random.seed(42)
        for _ in range(50):
            _, state = fwd(random.gauss(0, 1), state)
        result = inv([Dist.gaussian(0.0, 1.0)], state)
        assert isinstance(result[0], Dist)
        assert result[0].std > 0

    def test_bijection_k1(self):
        fwd, inv = grouped_ar(max_lag=8)
        state = None
        random.seed(42)
        series = [random.gauss(0, 1) for _ in range(200)]
        for y in series[:150]:
            _, state = fwd(y, state)
        state_snap = copy.deepcopy(state)
        y_next = series[150]
        y_p, _ = fwd(y_next, copy.deepcopy(state_snap))
        recovered = inv([Dist.gaussian(y_p, 1e-6)], state_snap)
        assert abs(recovered[0].mean - y_next) < 0.01

    def test_bijection_k3(self):
        fwd, inv = grouped_ar(max_lag=16)
        state = None
        random.seed(42)
        series = [random.gauss(0, 1) for _ in range(200)]
        for y in series[:180]:
            _, state = fwd(y, state)
        state_snap = copy.deepcopy(state)
        future = series[180:183]
        transformed = []
        fwd_state = copy.deepcopy(state_snap)
        for y in future:
            y_p, fwd_state = fwd(y, fwd_state)
            transformed.append(y_p)
        dists_in = [Dist.gaussian(y_p, 1e-6) for y_p in transformed]
        recovered = inv(dists_in, state_snap)
        for h in range(3):
            assert abs(recovered[h].mean - future[h]) < 0.05

    def test_composable_with_diff(self):
        k = 1
        f = conjugate(conjugate(leaf(k=k), grouped_ar(16), k=k), difference(), k=k)
        state = None
        random.seed(42)
        for _ in range(300):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0].mean)

    def test_long_run_stable(self):
        f = conjugate(leaf(k=1), grouped_ar(16), k=1)
        state = None
        random.seed(42)
        for _ in range(5000):
            x, state = f(random.gauss(0, 1), state)
        assert math.isfinite(x[0].mean)
        assert abs(x[0].mean) < 100
