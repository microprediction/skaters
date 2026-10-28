"""The torch trunk (pool + terminal-leaf ensemble) against the reference
``api._laplace_single_scale`` without the lattice projection: same series,
every horizon, every component, at 1e-9. And gradients from a log score at
the output reach a candidate's transform parameter and the mixing policy."""
import math

import pytest

torch = pytest.importorskip("torch")

from skaters.api import _build_candidates, _laplace_single_scale      # noqa: E402
from skaters.torch.pool import pool_spec, laplace_single_scale         # noqa: E402
from skaters.torch.parity import random_series                         # noqa: E402

TOL = 1e-9


def test_pool_spec_matches_the_reference_pool_shape():
    for k in (1, 3):
        cands, depths, groups = _build_candidates(k)
        spec = pool_spec(k)
        assert len(spec) == len(cands)
        assert [d for _, d in spec] == depths
        # group membership by index, where the reference names them
        assert [c[0][0] for c in (spec[i][0] for i in groups["diff"])] == ["difference"] * len(groups["diff"])
        assert all(spec[i][0][0][0] == "drift" for i in groups["drift"])
        assert all(spec[i][0][1][0] == "standardize" for i in groups["fast_slow"])
        assert all(spec[i][0][0][0] == "yeo_johnson" for i in groups["coordinate"])


def _worst(ref_f, tor_f, series, k):
    s1 = s2 = None
    worst = 0.0
    with torch.no_grad():
        for y in series:
            d1, s1 = ref_f(y, s1)
            d2, s2 = tor_f(y, s2)
            assert len(d1) == len(d2) == k
            for a, b in zip(d1, d2):
                bc = b.to_reference().components
                assert len(a.components) == len(bc), (len(a.components), len(bc))
                for (w1, m1, v1), (w2, m2, v2) in zip(a.components, bc):
                    worst = max(worst, abs(w1 - w2), abs(m1 - m2), abs(v1 - v2))
    return worst


@pytest.mark.parametrize("k", [1, 3])
@pytest.mark.parametrize("kind,seed", [("ar", 21), ("seasonal", 22), ("positive", 23)])
def test_trunk_matches_reference_single_scale(k, kind, seed):
    series = random_series(200, seed=seed, kind=kind)
    ref_f = _laplace_single_scale(k, "crps", False, None, 0.03)
    tor_f = laplace_single_scale(k, 0.03)
    assert _worst(ref_f, tor_f, series, k) < TOL


def test_gradients_reach_transforms_and_policy():
    k = 1
    series = random_series(90, seed=24)
    trunk = laplace_single_scale(k)
    state = None
    loss = torch.zeros((), dtype=torch.float64)
    for t, y in enumerate(series[:-1]):
        dists, state = trunk(y, state)
        if t >= 20:
            loss = loss - dists[0].logpdf(series[t + 1])
    loss.backward()
    assert trunk.learning_rate.grad is not None and math.isfinite(float(trunk.learning_rate.grad))
    assert trunk.forget.grad is not None and math.isfinite(float(trunk.forget.grad))
    # the first EMA candidate's rate (pool index 1) must carry a finite gradient
    ema = trunk.candidate_modules[1][0]
    assert ema.alpha.grad is not None and math.isfinite(float(ema.alpha.grad))
    assert float(ema.alpha.grad) != 0.0
