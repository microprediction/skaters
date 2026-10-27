"""skaters.torch parity for the shape transforms: fractional differencing,
power_transform and yeo_johnson (delta-method inverses) match the reference
to 1e-9 on seeded series, and their parameters carry finite gradients."""
import math

import pytest

torch = pytest.importorskip("torch")

from skaters.torch import REGISTRY, from_reference                   # noqa: E402
from skaters.torch.parity import check_parity, gradient_check, random_series  # noqa: E402

TOL = 1e-9

# (reference name, kwargs, series kind, zero-mean leaf dists?)
CASES = [
    ("fractional_difference", {"d": 0.2, "window": 30}, "ar", False),
    ("fractional_difference", {"d": 0.4, "window": 30}, "ar", False),
    ("fractional_difference", {}, "ar", False),
    ("power_transform", {"p": 0.5}, "positive", False),
    ("power_transform", {"p": 0.5}, "ar", False),
    ("yeo_johnson", {"lmbda": 0.0}, "ar", False),
    ("yeo_johnson", {"lmbda": 0.0}, "positive", False),
    ("yeo_johnson", {"lmbda": 0.5}, "positive", False),
    ("yeo_johnson", {"lmbda": 0.5}, "ar", False),
]

# gradient cases: yeo_johnson at lmbda=0 takes the closed-form log1p/expm1
# limit, in which the parameter does not appear, so it has no gradient there
GRAD_CASES = [c for c in CASES if not (c[0] == "yeo_johnson" and c[1].get("lmbda") == 0.0)]


@pytest.mark.parametrize("name,kwargs,kind,zm", CASES, ids=lambda c: str(c))
def test_transform_parity(name, kwargs, kind, zm):
    series = random_series(300, seed=0, kind=kind)
    for k in (1, 3):
        r = check_parity(name, kwargs, series, k=k, zero_mean=zm)
        assert r["forward"] < TOL, (name, kwargs, k, r)
        assert r["inverse"] < TOL, (name, kwargs, k, r)


@pytest.mark.parametrize("name,kwargs,kind,zm", GRAD_CASES, ids=lambda c: str(c))
def test_transform_gradients(name, kwargs, kind, zm):
    grads = gradient_check(name, kwargs, random_series(120, seed=2, kind=kind))
    assert grads and all(g is not None and math.isfinite(g) for g in grads.values()), grads


def test_registry_covers_the_cases():
    assert {c[0] for c in CASES} <= set(REGISTRY)


def test_exact_pushforward_is_refused():
    for name in ("power_transform", "yeo_johnson"):
        with pytest.raises(NotImplementedError):
            from_reference(name, exact=True)
