"""The torch homogenize against the reference at 1e-9: every predictive of
every horizon probed side by side, for each couple mode and a small
candidate grid, plus the state layout and a checkpoint that crosses ports
in both directions."""

import json
import math
import random

import pytest

torch = pytest.importorskip("torch")

from skaters.conjugate import conjugate as r_conjugate
from skaters.homogenize import homogenize as r_homogenize, make_candidates
from skaters.leaf import leaf as r_leaf
from skaters.state import state_from_json as r_from_json, state_to_json as r_to_json
from skaters.transform import ema_transform
from skaters.torch.conjugate import conjugate as t_conjugate
from skaters.torch.homogenize import homogenize as t_homogenize, TorchHomogenizedDist
from skaters.torch.leaf import leaf as t_leaf
from skaters.torch.state import state_from_json as t_from_json, state_to_json as t_to_json
from skaters.torch.transform import from_reference

TOL = 1e-9
SMALL = make_candidates(rho_grid=(0.0, 0.9), gain_grid=(0.1,), delta_grid=(0.0, 0.5))

CASES = [
    ("k1", 1, {}),
    ("k1_small_grid", 1, {"candidates": SMALL}),
    ("k2_weights", 2, {"couple": "weights"}),
    ("k2_state_lam", 2, {"couple": "state", "lam": 0.5}),
    ("k2_shared", 2, {"couple": "shared"}),
    ("k3_none", 3, {}),
    ("k3_weights", 3, {"couple": "weights"}),
    ("k3_state", 3, {"couple": "state"}),
    ("k3_shared", 3, {"couple": "shared"}),
]


def series(n=160, seed=11):
    rng = random.Random(seed)
    lvl, out = 0.0, []
    for t in range(n):
        lvl = 0.95 * lvl + rng.gauss(0, 0.4)
        # heavy-tailed noise so the scale-mixture pool has something to correct
        e = rng.gauss(0, 1.0) * (3.0 if rng.random() < 0.1 else 1.0)
        out.append(lvl + 1.5 * math.sin(2 * math.pi * t / 7) + e)
    return out


def build(k, kw):
    ref = r_homogenize(r_conjugate(r_leaf(k=k), ema_transform(0.1), k=k), k=k, **kw)
    tor = t_homogenize(t_conjugate(t_leaf(k=k), from_reference("ema_transform", alpha=0.1), k=k), k=k, **kw)
    return ref, tor


def probes(d, x=0.3):
    return [float(v) for v in (d.mean, d.std, d.logpdf(x), d.cdf(x),
                               d.quantile(0.1), d.quantile(0.9), d.crps(x))]


def assert_close(a, b, label):
    for i, (x, y) in enumerate(zip(a, b)):
        if math.isnan(x) and math.isnan(y):
            continue
        assert abs(x - y) <= TOL + TOL * abs(y), f"{label} probe {i}: torch {x!r} ref {y!r}"


def shape(x):
    """Keys, nesting and value kinds of a canonical state (numbers merged)."""
    if isinstance(x, dict):
        return {key: shape(v) for key, v in x.items()}
    if isinstance(x, list):
        return [shape(v) for v in x]
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return type(x).__name__
    if isinstance(x, int):
        return "int"
    return "number"


@pytest.mark.parametrize("label,k,kw", CASES, ids=[c[0] for c in CASES])
def test_matches_reference(label, k, kw):
    ref, tor = build(k, kw)
    rs = ts = None
    corrected = 0
    with torch.no_grad():
        for t, y in enumerate(series()):
            rd, rs = ref(y, rs)
            td, ts = tor(y, ts)
            assert len(rd) == len(td) == k
            for h, (a, b) in enumerate(zip(td, rd)):
                assert type(a).__name__.endswith(type(b).__name__)
                corrected += isinstance(a, TorchHomogenizedDist)
                assert_close(probes(a), probes(b), f"{label} t={t} h={h}")
    assert corrected > 0
    # same layout, same values
    rj, tj = r_to_json(rs), t_to_json(ts)
    assert shape(rj) == shape(tj)
    assert rj["cell"][0]["n"] == tj["cell"][0]["n"]


def test_logpdf_is_differentiable():
    T = from_reference("ema_transform", alpha=0.1)
    tor = t_homogenize(t_conjugate(t_leaf(k=1), T, k=1), k=1)
    st = None
    with torch.no_grad():
        for y in series(80):
            _, st = tor(y, st)
    dists, st = tor(0.2, st)
    d = dists[0]
    assert isinstance(d, TorchHomogenizedDist)
    d.logpdf(0.5).backward(retain_graph=True)
    assert T.alpha.grad is not None and float(T.alpha.grad) != 0.0
    y = torch.tensor(0.5, dtype=torch.float64, requires_grad=True)
    d.logpdf(y).backward()
    # d logpdf / dy against a finite difference
    h = 1e-6
    fd = (float(d.logpdf(0.5 + h)) - float(d.logpdf(0.5 - h))) / (2 * h)
    assert abs(float(y.grad) - fd) < 1e-5


@pytest.mark.parametrize("label,k,kw", [CASES[0], CASES[1], CASES[3], CASES[8]],
                         ids=[CASES[i][0] for i in (0, 1, 3, 8)])
def test_resume_across_ports(label, k, kw):
    ref, tor = build(k, kw)
    ys = series()
    cut, steps = 120, 20
    rs = ts = None
    with torch.no_grad():
        for y in ys[:cut]:
            _, rs = ref(y, rs)
            _, ts = tor(y, ts)
        # torch checkpoint resumed in the reference, reference checkpoint in torch
        r_from_t = r_from_json(json.loads(json.dumps(t_to_json(ts), allow_nan=False)))
        t_from_r = t_from_json(json.loads(json.dumps(r_to_json(rs), allow_nan=False)))
        for j, y in enumerate(ys[cut:cut + steps]):
            rd, rs = ref(y, rs)
            ad, r_from_t = ref(y, r_from_t)
            bd, t_from_r = tor(y, t_from_r)
            for h in range(k):
                want = probes(rd[h])
                assert_close(probes(ad[h]), want, f"{label} py<-torch step {j} h {h}")
                assert_close(probes(bd[h]), want, f"{label} torch<-py step {j} h {h}")
