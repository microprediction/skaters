"""npts_dists issues the h-step forecast for y[j] from origin j-h+1, as the other
arms do. A stand-in NPTSPredictor records the history it is handed, so the test
checks the origin exactly without depending on NPTS's sampling."""
import os
import sys
import types

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))

aa = pytest.importorskip("arm_adapters")
pytest.importorskip("pandas")


@pytest.fixture
def recording_npts(monkeypatch):
    seen = []

    class FakeForecast:
        def __init__(self, last, h):
            self.samples = np.full((50, h), last, dtype=float)

    class FakeNPTS:
        def __init__(self, prediction_length, **kw):
            self.h = prediction_length

        def predict_time_series(self, ts, num_samples):
            seen.append(np.asarray(ts.values, float))
            return FakeForecast(float(ts.values[-1]), self.h)

    mod = types.ModuleType("gluonts.model.npts")
    mod.NPTSPredictor = FakeNPTS
    for name in ("gluonts", "gluonts.model"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "gluonts.model.npts", mod)
    return seen


@pytest.mark.parametrize("h", [1, 3])
def test_history_ends_at_the_forecast_origin(recording_npts, h):
    n = aa.CTX + aa.TEST + 20
    ch = [float(i) for i in range(n)]            # value = index, so the last value names the origin
    out = aa.npts_dists(ch, h)
    assert out is not None and len(out) == aa.TEST
    targets = range(n - aa.TEST, n)
    for j, hist in zip(targets, recording_npts):
        assert hist[-1] == j - h                 # history ends just before origin j-h+1
        assert len(hist) == aa.CTX
