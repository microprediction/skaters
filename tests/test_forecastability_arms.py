"""No-lookahead contract for the #250 forecastability arms.

Perturbing every observation after an origin o must leave every predictive
issued at or before o bit-identical, for each arm and horizon. A predictive for
target j is issued at j - h, so targets j <= o + h are covered. The first target
issued after o must change, or the perturbation tested nothing.
"""
import os
import random
import sys

import pytest

np = pytest.importorskip("numpy")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "benchmarks"))
aa = pytest.importorskip("arm_adapters")

ARMS = ["laplace", "unc", "cps", "cpsz", "unc(250)", "cps(250)", "cpsz(250)",
        "lap_grid", "lap_conf"]
PROBES = [-2.0, -0.5, 0.0, 0.7, 2.5]


def _sig(d):
    return tuple([d.quantile(p) for p in (0.05, 0.5, 0.95)] + [d.logpdf(x) for x in PROBES])


@pytest.mark.parametrize("h", [1, 3])
@pytest.mark.parametrize("arm", ARMS)
def test_no_lookahead(arm, h, monkeypatch):
    monkeypatch.setattr(aa, "TEST", 12)
    g = random.Random(7)
    ch = [g.gauss(0.0, 1.0) for _ in range(300)]
    n = len(ch)
    lo = n - aa.TEST
    o = lo + 4
    bumped = ch[:o + 1] + [x + 3.0 for x in ch[o + 1:]]
    fn = aa.make_registry(h)[arm]
    a, b = fn(list(ch)), fn(list(bumped))
    assert a is not None and b is not None and len(a) == len(b) == aa.TEST
    for k in range(len(a)):
        j = lo + k
        if j - h <= o:
            assert _sig(a[k]) == _sig(b[k]), f"{arm} h={h}: target {j} saw data after {o}"
    k_after = o + h + 1 - lo
    assert _sig(a[k_after]) != _sig(b[k_after]), f"{arm} h={h}: perturbation had no effect"
