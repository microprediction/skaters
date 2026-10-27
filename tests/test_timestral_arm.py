"""Timestral benchmark arm (#282): the decile subset of the 21 native levels
and the explicit forecast settings. The model itself is only exercised when
the timestral package is installed (the .venv-timestral environment)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))

aa = pytest.importorskip("arm_adapters")


def test_decile_subset_indexes_the_native_levels():
    picked = [aa.LEVELS21[i] for i in aa._Q9_IN_21]
    assert picked == aa.LEVELS9
    assert len(aa.LEVELS21) == 21 and aa.LEVELS21[0] == 0.01 and aa.LEVELS21[-1] == 0.99


def test_every_size_is_pinned():
    assert set(aa.TIMESTRAL_REVISIONS) == {"5M", "28M", "123M", "209M"}
    assert all(len(sha) == 40 for sha in aa.TIMESTRAL_REVISIONS.values())


def test_registry_exposes_the_arms():
    reg = aa.make_registry(1)
    for name in ("Timestral-5M", "Timestral-28M", "Timestral-123M", "Timestral-209M",
                 "Timestral-5M(q21)", "Timestral-28M(q21)", "Timestral-123M(q21)",
                 "Timestral-209M(q21)"):
        assert name in reg


def test_5m_forecast_is_sound_on_signed_changes():
    pytest.importorskip("timestral")
    rng = np.random.default_rng(0)
    ctx = rng.standard_normal((2, 128)).astype(np.float32)   # signed, mean zero
    q = aa.timestral_quantiles_from_contexts(ctx, h=1, size="5M")
    assert q.shape == (2, 21)
    assert np.all(np.diff(q, axis=1) >= 0)
    # the nonnegativity clip is off: a zero-mean context must get a negative lower tail
    assert np.all(q[:, 0] < 0)
