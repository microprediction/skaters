"""skaters.torch parity for the autoregressive transforms (ar, grouped_ar):
forward emissions and every inverse_k component within 1e-9 of the
reference on seeded series, and finite gradients for the float parameters.
Skipped where torch is not installed."""
import math

import pytest

torch = pytest.importorskip("torch")

from skaters.torch import REGISTRY, from_reference                 # noqa: E402
from skaters.torch.parity import check_parity, gradient_check, random_series  # noqa: E402

TOL = 1e-9

CASES = [
    ("ar", {"order": 1}, "ar", False),
    ("ar", {"order": 2, "decay": 1}, "ar", False),
    ("ar", {}, "ar", False),
    ("grouped_ar", {"max_lag": 8}, "ar", False),
    ("grouped_ar", {"max_lag": 16}, "ar", False),
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
