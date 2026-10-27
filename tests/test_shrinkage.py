"""Tests for skaters.cov.shrinkage.ledoit_wolf_cov."""

import random
import pytest
from skaters.cov.shrinkage import ledoit_wolf_cov

np = pytest.importorskip("numpy")


def _min_eig(cov, n):
    return float(np.linalg.eigvalsh(np.array(cov).reshape(n, n)).min())


def test_three_observation_reproduction_is_psd():
    """skaters#224: this exact three-observation sequence at shrinkage=0.1
    used to produce an indefinite matrix (min eigenvalue ~-0.035)."""
    state = None
    for y in ([2.0, 0.0, 0.0],
              [2.0, -2.0, 1.0],
              [-1.0, -2.0, -1.0]):
        _, cov, state = ledoit_wolf_cov(y, state, alpha=0.05, shrinkage=0.1)

    v = [-2.0, 2.0, 3.0]
    quad = sum(v[i] * cov[3 * i + j] * v[j] for i in range(3) for j in range(3))
    assert quad >= -1e-9
    assert _min_eig(cov, 3) >= -1e-9


@pytest.mark.parametrize("shrinkage", [0.0, 0.05, 0.1, 0.3, 0.5, 0.9])
def test_stays_psd_across_random_sequences(shrinkage):
    random.seed(0)
    for _ in range(20):
        n = random.choice([2, 3, 4, 5])
        state = None
        for _ in range(random.randint(2, 20)):
            y = [random.gauss(0, random.choice([0.1, 1, 10])) for _ in range(n)]
            _, cov, state = ledoit_wolf_cov(y, state, alpha=0.05, shrinkage=shrinkage)
        assert _min_eig(cov, n) >= -1e-8


def test_diagonal_is_unchanged_by_shrinkage():
    """Shrinking toward the diagonal must leave the diagonal itself alone --
    only off-diagonal entries move toward zero."""
    n = 3
    state_raw = state_shrunk = None
    random.seed(1)
    ys = [[random.gauss(0, 1) for _ in range(n)] for _ in range(10)]
    for y in ys:
        _, cov_raw, state_raw = ledoit_wolf_cov(y, state_raw, shrinkage=0.0)
        _, cov_shrunk, state_shrunk = ledoit_wolf_cov(y, state_shrunk, shrinkage=0.7)
    for i in range(n):
        assert cov_raw[i * n + i] == pytest.approx(cov_shrunk[i * n + i], rel=1e-9)


def test_zero_shrinkage_matches_plain_ema_cov():
    from skaters.cov.ema_cov import ema_cov
    random.seed(2)
    n = 3
    state_lw = state_ema = None
    for _ in range(15):
        y = [random.gauss(0, 1) for _ in range(n)]
        mean_lw, cov_lw, state_lw = ledoit_wolf_cov(y, state_lw, shrinkage=0.0)
        mean_ema, cov_ema, state_ema = ema_cov(y, state_ema)
    assert mean_lw == pytest.approx(mean_ema, rel=1e-9)
    assert cov_lw == pytest.approx(cov_ema, rel=1e-9)
