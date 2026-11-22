"""The torch residual_transform against the reference, at 1e-9: every
predictive's probes over a 300-point series for m0, m1, m2 and m2 with
lr=0.05, the state layout, and resume across the two ports through JSON."""

import json
import math
import random

import pytest

torch = pytest.importorskip("torch")

from skaters.conjugate import conjugate as r_conjugate  # noqa: E402
from skaters.leaf import leaf as r_leaf  # noqa: E402
from skaters.transform import ema_transform  # noqa: E402
from skaters.residual_transform import residual_transform as r_residual  # noqa: E402
from skaters.state import state_to_json as r_to_json, state_from_json as r_from_json  # noqa: E402
from skaters.torch.conjugate import conjugate as t_conjugate  # noqa: E402
from skaters.torch.leaf import leaf as t_leaf  # noqa: E402
from skaters.torch.transform import from_reference  # noqa: E402
from skaters.torch.residual_transform import residual_transform as t_residual  # noqa: E402
from skaters.torch.state import state_to_json as t_to_json, state_from_json as t_from_json  # noqa: E402

TOL = 1e-9
CASES = [("m0", 0.01), ("m1", 0.01), ("m2", 0.01), ("m2", 0.05)]


def series(n=300, seed=31):
    rng = random.Random(seed)
    lvl, out = 0.0, []
    for t in range(n):
        lvl = 0.95 * lvl + rng.gauss(0, 0.4)
        scale = 1.0 + 0.8 * (t % 50 > 35)
        out.append(lvl + 1.5 * math.sin(2 * math.pi * t / 7) + scale * rng.gauss(0, 1.0))
    return out


def make_ref(model, lr):
    return r_residual(r_conjugate(r_leaf(k=1), ema_transform(0.1), k=1), model=model, lr=lr)


def make_torch(model, lr):
    return t_residual(t_conjugate(t_leaf(k=1), from_reference("ema_transform", alpha=0.1), k=1),
                      model=model, lr=lr)


def probes(d, x):
    return [float(v) for v in (d.mean, d.std, d.logpdf(x), d.cdf(x),
                               d.quantile(0.1), d.quantile(0.9), d.crps(x))]


def close(a, b):
    return abs(a - b) <= TOL + TOL * abs(b)


def keys_shape(x):
    """Keys and nesting, numbers collapsed to 'num' (tensor or float alike)."""
    if isinstance(x, dict):
        return {k: keys_shape(v) for k, v in x.items()}
    if isinstance(x, list):
        return [keys_shape(v) for v in x]
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x if not isinstance(x, str) else "str"
    return "num"


@pytest.mark.parametrize("model,lr", CASES)
def test_matches_reference(model, lr):
    ys = series()
    fr, ft = make_ref(model, lr), make_torch(model, lr)
    sr = st = None
    for i, y in enumerate(ys):
        dr, sr = fr(y, sr)
        with torch.no_grad():
            dt, st = ft(y, st)
        x = ys[i + 1] if i + 1 < len(ys) else y
        for a, b in zip(probes(dt[0], x), probes(dr[0], x)):
            assert close(a, b), (model, lr, i, a, b)
        assert (st["z"] is None) == (sr["z"] is None)
        if sr["z"] is not None:
            assert close(float(st["z"]), sr["z"])
    # layout: same keys and nesting as the reference
    assert keys_shape(t_to_json(st)) == keys_shape(r_to_json(sr))


@pytest.mark.parametrize("model,lr", CASES)
def test_resume_across_ports(model, lr):
    ys = series()
    cut, steps = 150, 20
    fr, ft = make_ref(model, lr), make_torch(model, lr)
    sr = st = None
    for y in ys[:cut]:
        _, sr = fr(y, sr)
        with torch.no_grad():
            _, st = ft(y, st)
    # torch checkpoint resumed by the reference, reference checkpoint by torch
    r_from_t = r_from_json(json.loads(json.dumps(t_to_json(st), allow_nan=False)))
    t_from_r = t_from_json(json.loads(json.dumps(r_to_json(sr), allow_nan=False)))
    for y in ys[cut:cut + steps]:
        d_ref, sr = fr(y, sr)
        d_a, r_from_t = fr(y, r_from_t)
        with torch.no_grad():
            d_b, t_from_r = ft(y, t_from_r)
        expect = probes(d_ref[0], y)
        for a, b in zip(probes(d_a[0], y), expect):
            assert close(a, b), ("torch->ref", model, a, b)
        for a, b in zip(probes(d_b[0], y), expect):
            assert close(a, b), ("ref->torch", model, a, b)


def test_logpdf_differentiable():
    """A log score differentiates into the transform parameter under the base."""
    ys = series(80)
    ft = make_torch("m2", 0.01)
    st = None
    for y in ys[:-1]:
        d, st = ft(y, st)
    lp = d[0].logpdf(ys[-1])
    ema_alpha = None
    # the EMA alpha parameter, reached through the conjugate closure
    for cell in ft.__closure__ or ():
        obj = cell.cell_contents
        if callable(obj) and getattr(obj, "__closure__", None):
            for c2 in obj.__closure__:
                v = c2.cell_contents
                if hasattr(v, "alpha") and isinstance(v.alpha, torch.nn.Parameter):
                    ema_alpha = v.alpha
    assert ema_alpha is not None
    (g,) = torch.autograd.grad(lp, ema_alpha)
    assert math.isfinite(float(g)) and float(g) != 0.0
