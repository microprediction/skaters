"""skaters.torch twins of periodicity, search and spec against the reference:
the detector reproduces the parity vectors' periodicity entry exactly, the
search and spec scenarios match the reference predictive by predictive on
the standard probes at 1e-9 through several expand/prune cycles, and a log
score at search's output reaches a transform parameter inside the pool."""
import json
import math
import os

import pytest

torch = pytest.importorskip("torch")

import skaters.periodicity as rp                                   # noqa: E402
import importlib                                                   # noqa: E402
rs = importlib.import_module("skaters.search")   # the package re-exports the function under the module name
import skaters.spec as rspec                                       # noqa: E402
import skaters.torch.periodicity as tp                             # noqa: E402
ts = importlib.import_module("skaters.torch.search")               # noqa: E402
import skaters.torch.spec as tspec                                 # noqa: E402
from skaters.torch.parity import random_series                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
VECTORS = os.path.join(os.path.dirname(HERE), "parity", "vectors.json")
TOL = 1e-9
PROBE, Q_LO, Q_HI = 0.3, 0.1, 0.9


def _probe(d):
    return [float(d.mean), float(d.std), float(d.logpdf(PROBE)), float(d.cdf(PROBE)),
            float(d.quantile(Q_LO)), float(d.quantile(Q_HI)), float(d.crps(PROBE))]


def _worst(ref_f, tor_f, series, k, burn=0):
    s1 = s2 = None
    worst = 0.0
    with torch.no_grad():
        for i, y in enumerate(series):
            d1, s1 = ref_f(y, s1)
            d2, s2 = tor_f(y, s2)
            assert len(d1) == len(d2) == k
            if i < burn:
                continue
            for a, b in zip(d1, d2):
                for x, z in zip(_probe(a), _probe(b)):
                    if math.isinf(x) and math.isinf(z) and (x > 0) == (z > 0):
                        continue
                    worst = max(worst, abs(x - z))
    return worst


# ---------------------------------------------------------------- periodicity

def test_period_detector_reproduces_the_parity_vectors():
    vec = json.load(open(VECTORS))
    series, burn = vec["series"], vec["burn"]
    pd = tp.period_detector()
    st = None
    out = []
    with torch.no_grad():
        for i, y in enumerate(series):
            scores, st = pd(y, st)
            if i >= burn:
                out.append([[L, float(acf)] for L, acf in scores])
    expected = vec["periodicity"]
    assert len(out) == len(expected)
    for got, exp in zip(out, expected):
        assert [g[0] for g in got] == [e[0] for e in exp]          # same lags, same order
        for g, e in zip(got, exp):
            assert abs(g[1] - float(e[1])) < TOL


@pytest.mark.parametrize("kind,seed", [("seasonal", 1), ("ar", 2), ("positive", 3)])
def test_period_detector_matches_reference(kind, seed):
    series = random_series(260, seed=seed, kind=kind)
    r, t = rp.period_detector(), tp.period_detector()
    s1 = s2 = None
    with torch.no_grad():
        for y in series:
            a, s1 = r(y, s1)
            b, s2 = t(y, s2)
            assert [L for L, _ in a] == [L for L, _ in b]
            for (_, x), (_, z) in zip(a, b):
                assert abs(x - float(z)) < TOL
            assert rp.top_periods(a) == tp.top_periods(b)


# ---------------------------------------------------------------- spec

def _spec_cases():
    conj = rspec.conjugate_spec(rspec.ensemble_spec(rspec.ema_spec(0.01, 1), rspec.ema_spec(0.1, 1), k=1),
                                rspec.diff_spec())
    return [("spec_diff_ensemble", conj, 1), ("spec_ema", rspec.ema_spec(0.05, 1), 1),
            ("spec_frac_std", rspec.conjugate_spec(rspec.conjugate_spec(rspec.ema_spec(0.1, 2), rspec.std_spec(0.05)),
                                                   rspec.frac_spec(0.3, 20)), 2)]


@pytest.mark.parametrize("name,spec,k", _spec_cases(), ids=lambda c: c if isinstance(c, str) else "")
@pytest.mark.parametrize("kind,seed", [("ar", 4), ("seasonal", 5)])
def test_spec_build_matches_reference(name, spec, k, kind, seed):
    series = random_series(220, seed=seed, kind=kind)
    ref_f, tor_f = rspec.build(spec), tspec.build(spec)
    assert tor_f.__name__ == ref_f.__name__ == rspec.name(spec)
    assert _worst(ref_f, tor_f, series, k) < TOL


# ---------------------------------------------------------------- search

@pytest.mark.parametrize("kind,seed", [("ar", 6), ("seasonal", 7), ("positive", 8)])
def test_search_default_matches_reference(kind, seed):
    """expand_interval=50 as the parity scenario; 300 steps = five cycles."""
    series = random_series(300, seed=seed, kind=kind)
    ref_f = rs.search(k=1, expand_interval=50)
    tor_f = ts.search(k=1, expand_interval=50)
    assert _worst(ref_f, tor_f, series, 1) < TOL


def test_search_k2_matches_reference():
    series = random_series(160, seed=9, kind="ar")
    assert _worst(rs.search(k=2, expand_interval=50), ts.search(k=2, expand_interval=50), series, 2) < TOL


def test_search_pool_recipes_track_the_reference():
    series = random_series(160, seed=10, kind="seasonal")
    ref_f, tor_f = rs.search(k=1, expand_interval=50), ts.search(k=1, expand_interval=50)
    s1 = s2 = None
    with torch.no_grad():
        for y in series:
            _, s1 = ref_f(y, s1)
            _, s2 = tor_f(y, s2)
    assert [e["recipe"] for e in s1["pool"]] == [e["recipe"] for e in s2["pool"]]
    assert s1["detected_periods"] == s2["detected_periods"]
    assert len(s1["pool"]) > 1


def test_gradient_reaches_a_transform_inside_the_pool():
    series = random_series(120, seed=11, kind="ar")
    f = ts.search(k=1, expand_interval=50)
    state = None
    loss = torch.zeros((), dtype=torch.float64)
    for t, y in enumerate(series[:-1]):
        dists, state = f(y, state)
        if t >= 60:
            loss = loss - dists[0].logpdf(series[t + 1])
    loss.backward()
    grads = []
    for e in state["pool"]:
        for m in e["mods"]:
            for p in m.parameters():
                if p.grad is not None:
                    grads.append(float(p.grad))
    assert grads, "no transform parameter received a gradient"
    assert all(math.isfinite(g) for g in grads)
    assert any(g != 0.0 for g in grads)
