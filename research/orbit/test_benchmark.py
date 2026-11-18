import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmarks"))

from research.orbit.benchmark import orbit_dists, orbit_extras


def test_candidate_is_an_ordinary_depth_one_chain():
    [(candidate, depth)] = orbit_extras(1)
    assert depth == 1
    state = None
    for i in range(12):
        dists, state = candidate(math.sin(i), state)
    assert len(dists) == 1
    assert set(state) == {"s_state", "t_state"}
    assert state["t_state"]["n"] == 12


@pytest.mark.parametrize("k", [1, 3])
def test_research_pool_hook_without_an_extra_reproduces_default_laplace(k):
    from arm_adapters import laplace_extra_periods
    from skaters.api import laplace
    baseline = laplace(k=k)
    hook = laplace_extra_periods(k=k, periods=())
    a = b = None
    for i in range(32):
        da, a = baseline(math.sin(i / 5.0), a)
        db, b = hook(math.sin(i / 5.0), b)
        for left, right in zip(da, db):
            assert left.mean == right.mean
            assert left.var == right.var
            assert left.quantile(0.9) == right.quantile(0.9)


@pytest.mark.parametrize("pooled", [False, True])
def test_canonical_adapter_scores_the_matured_target(pooled, monkeypatch):
    import foundation_study
    monkeypatch.setattr(foundation_study, "TEST", 4)
    if pooled:
        import arm_adapters
        monkeypatch.setattr(arm_adapters, "TEST", 4)
    ch = [math.sin(i / 4.0) for i in range(20)]
    out = orbit_dists(ch, h=1, pooled=pooled)
    assert len(out) == 4
    assert all(math.isfinite(d.logpdf(y)) for d, y in zip(out, ch[-4:]))


@pytest.mark.parametrize("h", [1, 3])
def test_standalone_adapter_uses_the_origin_h_ticks_earlier(h, monkeypatch):
    import foundation_study
    from skaters.dist import Dist
    from research.orbit import benchmark
    monkeypatch.setattr(foundation_study, "TEST", 4)

    def known(k):
        def step(y, state):
            return [Dist.gaussian(100.0 * y + j, 1.0) for j in range(k)], {}
        return [(step, 1)]

    monkeypatch.setattr(benchmark, "orbit_extras", known)
    ch = list(range(20))
    out = benchmark.orbit_dists(ch, h=h, pooled=False)
    assert [d.mean for d in out] == [100.0 * ch[i - h] + h - 1 for i in range(16, 20)]
