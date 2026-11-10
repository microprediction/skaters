"""Foundation-model arms added for #329: Chronos-2, TTM-R3, Moirai 2.0,
TinyCast and Toto 2.0 (TiRex-2 has its own test). Pins and registry always
run; each model's soundness check runs only in the venv that has its package
(benchmarks/<slug>_requirements.lock) and skips elsewhere."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))

aa = pytest.importorskip("arm_adapters")

ARMS = ("Chronos-2", "TTM-R3", "Moirai-2.0-small", "TinyCast", "TinyCast(flip)",
        "Toto2-4m", "Toto2-22m", "Toto2-313m", "Toto2-1B", "Toto2-2.5B")


def test_pins_are_recorded():
    pins = [aa.CHRONOS2_MODEL_REVISION, aa.TTM3_MODEL_REVISION, aa.TINYCAST_MODEL_REVISION,
            aa.TINYCAST_SOURCE_COMMIT, aa.TOTO2_REPO_COMMIT, aa.TIREX2_MODEL_REVISION,
            *aa.MOIRAI2_REVISIONS.values(), *aa.TOTO2_REVISIONS.values()]
    assert all(len(sha) == 40 for sha in pins)
    assert set(aa.TOTO2_REVISIONS) == {"4m", "22m", "313m", "1B", "2.5B"}


def test_registry_exposes_the_arms():
    reg = aa.make_registry(1)
    for name in ARMS:
        assert name in reg


def test_lock_files_are_present():
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks")
    for slug in ("chronos2", "ttm3", "moirai2", "tinycast", "toto2", "tirex2_0_5"):
        path = os.path.join(here, f"{slug}_requirements.lock")
        with open(path) as fh:
            head = fh.readline()
        assert head.startswith("#") and "#329" in head


def _signed_contexts(n=3, seed=0):
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, aa.CTX)).astype(np.float32)     # signed, mean zero


@pytest.mark.parametrize("package,fn,kw", [
    ("chronos", "chronos2_quantiles_from_contexts", {}),
    ("tsfm_public", "ttm3_quantiles_from_contexts", {}),
    ("uni2ts", "moirai2_quantiles_from_contexts", {"size": "small"}),
    ("tinycast", "tinycast_quantiles_from_contexts", {}),
    ("toto2", "toto2_quantiles_from_contexts", {"size": "4m"}),
])
def test_forecast_is_sound_on_signed_changes(package, fn, kw):
    pytest.importorskip(package)
    f = getattr(aa, fn)
    ctx = _signed_contexts()
    q = f(ctx, h=1, **kw)
    assert q.shape[0] == 3 and q.shape[1] in (9, 21)
    assert np.all(np.isfinite(q)) and np.all(np.diff(q, axis=1) >= 0)
    assert np.all(q[:, 0] < 0)                                  # no nonnegativity clip
    one = f(ctx[:1], h=1, **kw)
    assert np.abs(one[0] - q[0]).max() < 1e-3 * (q[0, -1] - q[0, 0])   # batched equals single
    q3 = f(ctx, h=3, **kw)
    assert q3.shape == q.shape and np.all(np.isfinite(q3))
