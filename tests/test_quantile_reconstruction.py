"""The decile-to-density reconstructions are not calibration-preserving (#261).

A quantile-only model is scored through a reconstruction of its nine deciles.
Fed the exact deciles of a standard normal, the local reconstruction
(quantile_dist) covers about 0.81 with its own central-90% interval and the
wide one about 0.88. These numbers pin that artifact so that no page can
describe the reconstruction's coverage as a model-native interval without the
figure being on record.
"""
import os
import sys
from statistics import NormalDist

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))

LEVELS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def _central90(recon):
    truth = NormalDist()
    q = [truth.inv_cdf(p) for p in LEVELS]
    d = recon(LEVELS, q)
    lo, hi = d.quantile(0.05), d.quantile(0.95)
    return truth.cdf(hi) - truth.cdf(lo)


def test_local_reconstruction_undercovers_a_calibrated_source():
    fs = pytest.importorskip("foundation_study")
    cov = _central90(fs.quantile_dist)
    assert 0.80 < cov < 0.82, cov


def test_wide_reconstruction_also_undercovers_a_calibrated_source():
    nz = pytest.importorskip("nozzles")
    cov = _central90(nz.nozzle_wide)
    assert 0.87 < cov < 0.89, cov
