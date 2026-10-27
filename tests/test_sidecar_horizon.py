"""No-lookahead contract for the sidecar arms at every horizon (#273).

The sidecar arms (~lap, @lap, &lap) adapt a foundation model online. A horizon-h
forecast for target j is issued at j - h, so neither the correction nor the
portfolio weights applied to it may use any observation after j - h.

A stub FM forecasts N(y[t-h], 1) for target t, so it is causal by construction
and any lookahead must come from the sidecar. Perturbing every observation after
an origin o must leave every predictive for a target j <= o + h bit-identical.
The first target issued after o must change, or the perturbation tested nothing.
"""
import os
import random
import sys
from statistics import NormalDist

import pytest

np = pytest.importorskip("numpy")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "benchmarks"))
aa = pytest.importorskip("arm_adapters")

LEVELS = [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
PROBES = [-2.0, -0.5, 0.0, 0.7, 2.5]


def _stub_fm(ch, h):
    n = len(ch)
    return [aa.fs.quantile_dist(LEVELS, [ch[t - h] + NormalDist().inv_cdf(p) for p in LEVELS])
            for t in range(n - aa.fs.TEST, n)]


def _sig(d):
    return tuple([d.quantile(p) for p in (0.05, 0.5, 0.95)] + [d.logpdf(x) for x in PROBES])


SIDECARS = {
    "~lap": lambda h: aa._resid_sandwich(_stub_fm, h),
    "@lap": lambda h: aa.pit_sandwich(_stub_fm, h),
    "&lap": lambda h: aa.portfolio_sandwich(_stub_fm, h=h),
}


@pytest.mark.parametrize("h", [1, 3, 5])
@pytest.mark.parametrize("arm", list(SIDECARS))
def test_sidecar_no_lookahead(arm, h, monkeypatch):
    monkeypatch.setattr(aa, "TEST", 16)
    monkeypatch.setattr(aa, "_RESID_WARM", 24)
    g = random.Random(11)
    ch = [g.gauss(0.0, 1.0) for _ in range(200)]
    n = len(ch)
    lo = n - aa.TEST
    o = lo + 4
    bumped = ch[:o + 1] + [x + 3.0 for x in ch[o + 1:]]
    fn = SIDECARS[arm](h)
    a, b = fn(list(ch)), fn(list(bumped))
    assert a is not None and b is not None and len(a) == len(b) == aa.TEST
    for k in range(len(a)):
        j = lo + k
        if j - h <= o:
            assert _sig(a[k]) == _sig(b[k]), f"{arm} h={h}: target {j} saw data after {o}"
    k_after = o + h + 1 - lo
    assert _sig(a[k_after]) != _sig(b[k_after]), f"{arm} h={h}: perturbation had no effect"
