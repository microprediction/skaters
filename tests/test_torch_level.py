"""skaters.torch parity for the level-and-trend transforms (ou_transform,
theta, drift, holt_linear): 1e-9 against the reference on seeded series,
forward emissions and every inverse_k component, plus finite gradients."""
import math

import pytest

torch = pytest.importorskip("torch")

from skaters.torch import REGISTRY, from_reference                       # noqa: E402
from skaters.torch.parity import check_parity, gradient_check, random_series  # noqa: E402

TOL = 1e-9

CASES = [
    ("ou_transform", {"kappa": 0.1, "alpha": 0.02}, "ar", False),
    ("ou_transform", {"kappa": 1.0, "alpha": 0.02}, "ar", False),
    ("ou_transform", {"kappa": 0.1, "alpha": 0.02}, "positive", True),
    ("theta", {"alpha": 0.1}, "ar", False),
    ("theta", {"alpha": 0.05}, "ar", False),
    ("theta", {"alpha": 0.3}, "seasonal", False),
    ("drift", {"alpha": 0.002, "shrinkage": 0.001}, "ar", False),
    ("drift", {"alpha": 0.05, "shrinkage": 0.01}, "ar", False),
    ("drift", {"alpha": 0.002, "shrinkage": 0.0}, "positive", False),
    ("holt_linear", {"alpha": 0.1, "beta": 0.05}, "ar", False),
    ("holt_linear", {"alpha": 0.3, "beta": 0.1}, "ar", False),
    ("holt_linear", {"alpha": 0.1, "beta": 0.02}, "seasonal", False),
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
    assert list(mod.parameters())
    grads = gradient_check(name, kwargs, random_series(120, seed=2, kind=kind))
    assert grads and all(g is not None and math.isfinite(g) for g in grads.values()), grads


def test_registry_covers_the_cases():
    assert {c[0] for c in CASES} <= set(REGISTRY)
