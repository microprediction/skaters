"""skaters.torch parity for the shape transforms: fractional differencing,
power_transform and yeo_johnson (delta-method and exact inverses),
log_transform and gaussianize match the reference to 1e-9 on seeded series,
and their parameters carry finite gradients."""
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
    ("power_transform", {"p": 0.5, "exact": True}, "ar", False),
    ("yeo_johnson", {"lmbda": 0.5, "exact": True}, "ar", False),
    ("yeo_johnson", {"lmbda": 0.0, "exact": True}, "positive", False),
    ("log_transform", {}, "positive", False),
    ("log_transform", {"upper": 40.0}, "ar", False),
    ("gaussianize", {}, "ar", False),
    ("gaussianize", {"smooth": True}, "seasonal", False),
    ("gaussianize", {"max_knots": 15, "guard": "delete", "slope_cap": 1.5}, "ar", False),
    ("gaussianize", {"max_knots": 15, "guard": "emin", "slope_cap": 1.5}, "ar", False),
]

# gradient cases: yeo_johnson at lmbda=0 takes the closed-form log1p/expm1
# limit, in which the parameter does not appear, so it has no gradient there
# log_transform and gaussianize have no continuous parameter
GRAD_CASES = [c for c in CASES if not (c[0] == "yeo_johnson" and c[1].get("lmbda") == 0.0)
              and c[0] not in ("log_transform", "gaussianize")]


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


def test_exact_inverse_is_a_pushforward():
    from skaters.torch.pushforward import TorchPushforwardDist
    from skaters.torch.dist import TorchDist
    for name, kw in (("power_transform", {"p": 0.5}), ("yeo_johnson", {"lmbda": 0.5})):
        t = from_reference(name, exact=True, **kw)
        _, st = t(1.0, None)
        d = t.inverse_k([TorchDist.gaussian(0.3, 0.8)], st)[0]
        assert isinstance(d, TorchPushforwardDist)


def test_power_transform_gradient_is_finite_at_exact_zero():
    """An exact zero (a repeated value in the level series) must not turn the
    exponent's gradient into NaN: d/dp |y|**p at 0 is 0 * log(0) in autograd.
    Found on the weekly granger training run, where it voided a quarter of the
    windows; values are unchanged by the fix."""
    from skaters.torch.transforms_shape import PowerTransform
    t = PowerTransform(0.5)
    ys = torch.tensor([0.0, 0.0, 1.7, -0.3, 0.0, 2.5], dtype=torch.float64)
    out = torch.stack([t._fwd(y) for y in ys])
    back = torch.stack([t._inv(v) for v in out])
    (out.sum() + back.sum()).backward()
    assert torch.isfinite(t.p.grad).all()
    p = float(t.p.detach())
    expect = [math.copysign(abs(float(y)) ** p, float(y)) for y in ys]
    assert [float(v) for v in out] == expect
    assert torch.allclose(back, ys)
