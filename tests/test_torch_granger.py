"""The torch granger against the reference at 1e-9: the mixture's probes over
a stream (both experts, the gate and the Aggregating-Algorithm weights), the
state layout, resume across the two ports through JSON in both directions,
and a gradient from the log score into the gate and the trained transforms."""

import json
import math
import random

import pytest

torch = pytest.importorskip("torch")

from skaters.granger import granger as r_granger  # noqa: E402
from skaters.state import state_to_json as r_to_json, state_from_json as r_from_json  # noqa: E402
from skaters.torch.granger import granger as t_granger  # noqa: E402
from skaters.torch.state import state_to_json as t_to_json, state_from_json as t_from_json  # noqa: E402

TOL = 1e-9
N = 90


def series(n=N + 20, seed=8):
    rng = random.Random(seed)
    lvl, out = 0.0, []
    for t in range(n):
        lvl = 0.95 * lvl + rng.gauss(0, 0.4)
        out.append(lvl + 1.5 * math.sin(2 * math.pi * t / 12) + rng.gauss(0, 0.8))
    return out


def probes(d):
    return [float(v) for v in (d.mean, d.std, d.logpdf(0.3), d.cdf(0.3), d.logpdf(2.5),
                               d.quantile(0.1), d.quantile(0.9), d.crps(0.3))]


def assert_close(a, b, where):
    for x, y in zip(a, b):
        assert abs(x - y) <= TOL * (1.0 + abs(y)), f"{where}: torch {x!r} reference {y!r}"


def keys(x):
    if isinstance(x, dict):
        if "components" in x or x.get("spliced"):
            return "dist"
        return {k: keys(v) for k, v in x.items()}
    if isinstance(x, list):
        return [keys(v) for v in x]
    return type(x).__name__ if not isinstance(x, (int, float)) or isinstance(x, bool) else "number"


@pytest.fixture(scope="module")
def runs():
    ys = series()
    r, t = r_granger(1, "monthly"), t_granger(1, "monthly")
    a = b = None
    out = []
    with torch.no_grad():
        for i, y in enumerate(ys[:N]):
            dr, a = r(y, a)
            dt, b = t(y, b)
            out.append((probes(dt[0]), probes(dr[0])))
    return ys, r, t, a, b, out


def test_granger_matches_reference(runs):
    _, _, _, _, _, out = runs
    for i, (pt, pr) in enumerate(out):
        assert_close(pt, pr, f"step {i}")


def test_granger_state_layout_is_the_reference_layout(runs):
    _, _, _, a, b, _ = runs
    ra, tb = r_to_json(a), t_to_json(b)
    assert keys(ra) == keys(tb)


def test_granger_resumes_across_ports(runs):
    ys, r, t, a, b, _ = runs
    tail = ys[N:]
    ref_cont, st = [], r_from_json(json.loads(json.dumps(r_to_json(a))))
    for y in tail:
        d, st = r(y, st)
        ref_cont.append(probes(d[0]))
    # torch checkpoint -> Python
    st = r_from_json(json.loads(json.dumps(t_to_json(b))))
    for j, y in enumerate(tail):
        d, st = r(y, st)
        assert_close(probes(d[0]), ref_cont[j], f"torch->python step {j}")
    # Python checkpoint -> torch
    st = t_from_json(json.loads(json.dumps(r_to_json(a))))
    with torch.no_grad():
        for j, y in enumerate(tail):
            d, st = t(y, st)
            assert_close(probes(d[0]), ref_cont[j], f"python->torch step {j}")


def test_gradient_reaches_gate_and_transforms():
    ys = series(70, seed=3)
    f = t_granger(1, "weekly")
    st = None
    loss = torch.zeros((), dtype=torch.float64)
    for i, y in enumerate(ys[:-1]):
        d, st = f(y, st)
        if i >= 40:
            loss = loss - d[0].logpdf(ys[i + 1])
    loss.backward()
    g = f.gate.l2_bias.grad
    assert g is not None and bool(torch.isfinite(g).all()) and float(g.abs().sum()) > 0
    grads = [p.grad for p in f.trunk.candidate_modules.parameters() if p.grad is not None]
    assert grads and any(float(x.abs().sum()) > 0 for x in grads)
