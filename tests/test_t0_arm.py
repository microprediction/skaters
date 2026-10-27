"""t0-gamma benchmark arm (#287): pinned revisions, explicit inference switches,
native 21 levels. The checkpoint is exercised only where tfc-t0 is installed
(the .venv-t0 environment)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))

aa = pytest.importorskip("arm_adapters")


def test_pins_are_recorded():
    assert len(aa.T0_MODEL_REVISION) == 40 and len(aa.T0_SOURCE_COMMIT) == 40
    assert aa.T0_MODEL_ID == "theforecastingcompany/t0-gamma"


def test_registry_exposes_the_arms():
    reg = aa.make_registry(1)
    for name in ("t0-gamma(q21)", "t0-gamma", "t0-gamma(q21+sym)"):
        assert name in reg


def test_gamma_forecast_is_sound_on_signed_changes():
    pytest.importorskip("t0")
    rng = np.random.default_rng(0)
    ctx = rng.standard_normal((3, 128)).astype(np.float32)      # signed, mean zero
    q = aa.t0_quantiles_from_contexts(ctx, h=1)
    assert q.shape == (3, 21)
    assert np.all(np.isfinite(q))
    assert np.all(np.diff(q, axis=1) >= 0)
    assert np.all(q[:, 0] < 0)                                   # no nonnegativity clip
    # integer-valued history must not trigger integer snapping of the forecast
    qi = aa.t0_quantiles_from_contexts(np.round(ctx * 3), h=1)
    assert not np.allclose(qi, np.round(qi))
    # batched equals single, and permuting the batch only permutes the rows
    one = aa.t0_quantiles_from_contexts(ctx[:1], h=1)
    assert np.abs(one[0] - q[0]).max() < 1e-4
    perm = aa.t0_quantiles_from_contexts(ctx[::-1], h=1)
    assert np.abs(perm[::-1] - q).max() < 1e-4


def test_horizon_two_uses_the_second_step():
    pytest.importorskip("t0")
    rng = np.random.default_rng(1)
    ctx = rng.standard_normal((2, 128)).astype(np.float32)
    q1 = aa.t0_quantiles_from_contexts(ctx, h=1)
    q2 = aa.t0_quantiles_from_contexts(ctx, h=2)
    assert q1.shape == q2.shape == (2, 21)
    assert not np.allclose(q1, q2)
