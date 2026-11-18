import pytest
from pathlib import Path

from skaters import Dist

from . import benchmark


def test_benchmark_scores_the_forecast_issued_h_ticks_before_the_target(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "benchmarks"))
    from foundation_study import TEST

    def factory(reference, inner, k):
        def step(y, state):
            count = 0 if state is None else state
            return [Dist.gaussian(count * 100 + j) for j in range(1, k + 1)], count + 1
        return step

    monkeypatch.setattr(benchmark, "horizon_conjugate", factory)
    h, n = 5, TEST + 100
    dists = benchmark.seasonal_dists([float(i) for i in range(n)], h, alpha=0.2)
    assert len(dists) == TEST
    assert [d.mean for d in dists] == pytest.approx([(t - h) * 100 + h for t in range(n - TEST, n)])
