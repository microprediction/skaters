"""TimeH2O benchmark arm (#298): pins, registry, reconstruction choice, and a
soundness check of the forecasts on signed changes. The checkpoints are gated
(non-commercial licence); the model tests skip when the weights cannot be
downloaded with the stored Hugging Face token."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))

aa = pytest.importorskip("arm_adapters")


def test_pins_are_recorded():
    assert set(aa.TIMEH2O_REVISIONS) == {"v1", "v1-tiny"}
    assert all(len(sha) == 40 for sha in aa.TIMEH2O_REVISIONS.values())


def test_registry_exposes_the_arms():
    reg = aa.make_registry(1)
    for name in ("TimeH2O-v1", "TimeH2O-v1(wide)", "TimeH2O-v1-tiny", "TimeH2O-v1-tiny(wide)"):
        assert name in reg


def _quantiles_or_skip(ctx, size):
    pytest.importorskip("h2ofm")
    try:
        return aa.timeh2o_quantiles_from_contexts(ctx, h=1, size=size)
    except Exception as e:  # noqa: BLE001
        if "gated" in str(e).lower() or "403" in str(e) or "restricted" in str(e).lower():
            pytest.skip(f"TimeH2O weights not accessible: {str(e)[:80]}")
        raise


def test_tiny_forecast_is_sound_on_signed_changes():
    rng = np.random.default_rng(0)
    ctx = rng.standard_normal((3, 128)).astype(np.float32)     # signed, mean zero
    q = _quantiles_or_skip(ctx, "v1-tiny")
    assert q.shape == (3, 9)
    assert np.all(np.isfinite(q)) and np.all(np.diff(q, axis=1) >= 0)
    assert np.all(q[:, 0] < 0)                                  # no nonnegativity clip
    one = _quantiles_or_skip(ctx[:1], "v1-tiny")
    assert np.abs(one[0] - q[0]).max() < 1e-4                   # batched equals single
    aa._timeh2o_memo.clear()
    again = _quantiles_or_skip(ctx, "v1-tiny")
    assert np.array_equal(q, again)                             # deterministic


def test_tight_and_wide_arms_share_one_forecast_and_differ_in_spread():
    import nozzles
    rng = np.random.default_rng(1)
    n = aa.CTX + aa.TEST + 10
    ch = list(rng.standard_normal(n))
    tight = aa.timeh2o_dists(ch, 1, "v1-tiny")
    if tight is None:
        pytest.skip("TimeH2O weights not accessible")
    wide = aa.timeh2o_dists(ch, 1, "v1-tiny", recon=nozzles.nozzle_wide)
    assert len(tight) == len(wide) == aa.TEST
    assert abs(float(tight[0].quantile(0.5)) - float(wide[0].quantile(0.5))) < 0.05
    assert wide[0].std > tight[0].std
