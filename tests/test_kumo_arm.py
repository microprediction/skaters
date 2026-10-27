"""Kumo Tabular benchmark arm (#294): pins, level indexing, and a soundness
check of the regressor and classifier arms on a synthetic change series.
The model runs only where structured-data-models is installed (.venv-kumo)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))

aa = pytest.importorskip("arm_adapters")


def test_pins_and_levels():
    assert len(aa.KUMO_MODEL_REVISION) == 40
    assert len(aa.LEVELS99) == 99 and aa.LEVELS99[0] == 0.01 and aa.LEVELS99[-1] == 0.99
    # the 21 levels index the right native quantile columns (q010 ... q990)
    cols = [int(round(p * 1000)) - 1 for p in aa.LEVELS21]
    assert cols[0] == 9 and cols[10] == 499 and cols[-1] == 989


def test_registry_exposes_the_arms():
    reg = aa.make_registry(1)
    for name in ("Kumo-large-reg(q21)", "Kumo-large-reg(q99)", "Kumo-small-reg(q21)",
                 "Kumo-small-reg(q99)", "Kumo-large-clf8", "Kumo-small-clf8"):
        assert name in reg


def _ar1(n, seed=0):
    rng = np.random.default_rng(seed)
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.5 * y[t - 1] + rng.standard_normal()
    return list(y)


def test_small_regressor_arm_is_sound():
    pytest.importorskip("sdm")
    ch = _ar1(aa.CTX + aa.TEST + 20)
    q = aa.kumo_reg_quantiles(ch, h=1, size="small")
    assert q.shape == (aa.TEST, 999)
    assert np.all(np.isfinite(q)) and np.all(np.diff(q, axis=1) >= 0)
    assert np.all(q[:, 9] < 0) and np.all(q[:, 989] > 0)      # signed tails on a zero-mean series
    dists = aa.kumo_dists(ch, 1, "small", "reg(q21)")
    assert len(dists) == aa.TEST
    y = ch[-aa.TEST:]
    lp = [d.logpdf(v) for d, v in zip(dists, y)]
    assert all(np.isfinite(lp)) and np.mean(lp) > -3.0
    d99 = aa.kumo_dists(ch, 1, "small", "reg(q99)")
    assert abs(d99[0].quantile(0.5) - dists[0].quantile(0.5)) < 0.2


def test_small_classifier_arm_is_sound():
    pytest.importorskip("sdm")
    ch = _ar1(aa.CTX + aa.TEST + 20, seed=1)
    dists = aa.kumo_dists(ch, 1, "small", "clf8")
    assert len(dists) == aa.TEST
    lp = [d.logpdf(v) for d, v in zip(dists, ch[-aa.TEST:])]
    assert all(np.isfinite(lp))
