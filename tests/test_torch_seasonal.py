"""skaters.torch parity for garch and the seasonal transforms: forward
emissions and every inverse_k component match the reference to 1e-9 on
seeded series, and every parameter carries a finite gradient. Skipped
where torch is not installed."""
import math

import pytest

torch = pytest.importorskip("torch")

from skaters.torch import REGISTRY, from_reference                 # noqa: E402
from skaters.torch.parity import check_parity, gradient_check, random_series  # noqa: E402

TOL = 1e-9

# (reference name, kwargs, series kind)
CASES = [
    ("garch", {}, "ar"),
    ("garch", {}, "seasonal"),
    ("garch", {"omega": 0.05, "alpha": 0.2, "beta": 0.7}, "ar"),
    ("seasonal_difference", {"period": 7}, "seasonal"),
    ("seasonal_difference", {"period": 7}, "ar"),
    ("seasonal_difference", {"period": 12}, "seasonal"),
    ("seasonal_difference", {}, "ar"),
    ("seasonal_anchor", {"period": 7}, "seasonal"),
    ("seasonal_anchor", {"period": 7}, "ar"),
    ("seasonal_anchor", {"period": 12}, "seasonal"),
    ("seasonal_anchor", {"period": 7, "alpha": 0.3, "weight": 0.2}, "seasonal"),
    ("seasonal_scale", {"period": 7}, "seasonal"),
    ("seasonal_scale", {"period": 7}, "ar"),
    ("seasonal_scale", {"period": 7, "center": True}, "seasonal"),
    ("seasonal_scale", {"period": 12, "alpha": 0.1}, "seasonal"),
]


@pytest.mark.parametrize("name,kwargs,kind", CASES, ids=lambda c: str(c))
def test_transform_parity(name, kwargs, kind):
    series = random_series(300, seed=0, kind=kind)
    for k in (1, 3):
        r = check_parity(name, kwargs, series, k=k)
        assert r["forward"] < TOL, (name, kwargs, k, r)
        assert r["inverse"] < TOL, (name, kwargs, k, r)


@pytest.mark.parametrize("name", ["seasonal_difference", "seasonal_anchor"])
def test_horizon_beyond_the_period(name):
    """k > period: anchors recovered within the call carry their variance."""
    series = random_series(300, seed=3, kind="seasonal")
    r = check_parity(name, {"period": 7}, series, k=9)
    assert r["forward"] < TOL, r
    assert r["inverse"] < TOL, r


@pytest.mark.parametrize("name,kwargs,kind", CASES, ids=lambda c: str(c))
def test_transform_gradients(name, kwargs, kind):
    mod = from_reference(name, **kwargs)
    if not list(mod.parameters()):
        return
    grads = gradient_check(name, kwargs, random_series(120, seed=2, kind=kind))
    assert grads and all(g is not None and math.isfinite(g) for g in grads.values()), grads


def test_registry_covers_the_cases():
    assert {c[0] for c in CASES} <= set(REGISTRY)
