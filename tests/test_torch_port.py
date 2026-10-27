"""skaters.torch parity: every ported transform matches the reference to
1e-9 on seeded series (forward emissions and every inverse_k component), the
TorchDist queries match Dist, and every parameter carries a finite gradient.
Skipped where torch is not installed."""
import math
import random

import pytest

torch = pytest.importorskip("torch")

from skaters.dist import Dist                                   # noqa: E402
from skaters.torch import TorchDist, REGISTRY, from_reference   # noqa: E402
from skaters.torch.parity import (check_parity, gradient_check,  # noqa: E402
                                  random_series, random_dists)

TOL = 1e-9

# (reference name, kwargs, series kind, zero-mean leaf dists?)
CASES = [
    ("difference", {}, "ar", False),
    ("standardize", {}, "ar", False),
    ("standardize", {"alpha": 0.2}, "ar", False),
    ("ema_transform", {"alpha": 0.05}, "ar", False),
    ("ema_transform", {"alpha": 0.3}, "ar", False),
]


@pytest.mark.parametrize("name,kwargs,kind,zm", CASES, ids=lambda c: str(c))
def test_transform_parity(name, kwargs, kind, zm):
    series = random_series(300, seed=0, kind=kind)
    for k in (1, 3):
        r = check_parity(name, kwargs, series, k=k, zero_mean=zm)
        assert r["forward"] < TOL, (name, kwargs, k, r)
        assert r["inverse"] < TOL, (name, kwargs, k, r)


@pytest.mark.parametrize("name,kwargs,kind,zm", CASES, ids=lambda c: str(c))
def test_transform_gradients(name, kwargs, kind, zm):
    mod = from_reference(name, **kwargs)
    if not list(mod.parameters()):
        return
    grads = gradient_check(name, kwargs, random_series(120, seed=2, kind=kind))
    assert grads and all(g is not None and math.isfinite(g) for g in grads.values()), grads


def test_registry_covers_the_cases():
    assert {c[0] for c in CASES} <= set(REGISTRY)


def test_torchdist_matches_dist():
    rng = random.Random(5)
    for _ in range(50):
        d = random_dists(1, rng)[0]
        t = TorchDist.from_reference(d)
        for x in (-2.0, -0.3, 0.0, 0.7, 3.5):
            assert abs(float(t.logpdf(x)) - d.logpdf(x)) < 1e-10
            assert abs(float(t.cdf(x)) - d.cdf(x)) < 1e-12
            assert abs(float(t.crps(x)) - d.crps(x)) < 1e-10
        assert abs(float(t.mean) - d.mean) < 1e-12
        assert abs(float(t.var) - d.var) < 1e-12
        for p in (0.05, 0.5, 0.95):
            assert abs(float(t.quantile(p)) - d.quantile(p)) < 1e-8
        a = t.affine(1.7, -0.4).to_reference(); b = d.affine(1.7, -0.4)
        assert all(abs(x - y) < 1e-12 for c1, c2 in zip(a.components, b.components) for x, y in zip(c1, c2))


def test_torchdist_point_mass_and_combine():
    d = Dist([(0.5, 0.0, 0.0), (0.5, 1.0, 1.0)])
    t = TorchDist.from_reference(d)
    assert abs(float(t.cdf(0.5)) - d.cdf(0.5)) < 1e-12
    assert abs(float(t.logpdf(2.0)) - d.logpdf(2.0)) < 1e-10
    c = TorchDist.combine([t, TorchDist.gaussian(3.0, 0.5)], [0.25, 0.75]).to_reference()
    r = Dist.combine([d, Dist.gaussian(3.0, 0.5)], [0.25, 0.75])
    assert all(abs(x - y) < 1e-12 for c1, c2 in zip(c.components, r.components) for x, y in zip(c1, c2))


def test_logpdf_gradient_reaches_components():
    m = torch.tensor(0.3, dtype=torch.float64, requires_grad=True)
    s = torch.tensor(1.2, dtype=torch.float64, requires_grad=True)
    t = TorchDist([1.0], [m], [s])
    t.logpdf(0.9).backward()
    assert math.isfinite(float(m.grad)) and math.isfinite(float(s.grad))
