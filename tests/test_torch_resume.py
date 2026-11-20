"""Cross-language resume between the reference and the torch port, both
directions, for every parity scenario (gen_vectors.build_scenarios and
build_wrapper_scenarios), as parity/check_torch_resume.py runs it.

Per scenario the reference runs the resume series (gen_resume.py) and is
checkpointed at t = 60, 250 and 530 in the canonical layout (docs/STATE.md).
Forward: torch loads each checkpoint with ``skaters.torch.state_from_json``
and must match the reference's next 20 predictives to 1e-6. Reverse: torch
runs the series from scratch, writes its checkpoints with
``skaters.torch.state_to_json``, and the reference resumes them to the same
tolerance. The torch state must also have exactly the reference's keys.
The reference side is computed here, so no generated file is needed.
"""

import json
import math
import os
import sys

import pytest

torch = pytest.importorskip("torch")

PARITY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "parity")
sys.path.insert(0, PARITY)

from gen_resume import all_scenarios, make_resume_series, TIMES, STEPS  # noqa: E402
from gen_vectors import probe_dist, clean, PROBE, Q_LO, Q_HI  # noqa: E402
from check_torch import build_all_scenarios  # noqa: E402
from check_torch_resume import probes as torch_probes, close  # noqa: E402
from skaters.state import state_to_json as r_to_json, state_from_json as r_from_json  # noqa: E402
from skaters.torch.state import state_to_json as t_to_json, state_from_json as t_from_json  # noqa: E402

SERIES = make_resume_series()
PY = {name: (k, sk) for name, k, sk in all_scenarios()}
TORCH = build_all_scenarios()


def shape(x):
    """Keys and nesting of a canonical state, numbers as one kind."""
    if isinstance(x, dict):
        if x.get("spliced") is True or (len(x) == 1 and "components" in x):
            return "dist"
        return {k: shape(v) for k, v in x.items()}
    if isinstance(x, list):
        return [shape(v) for v in x]
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x if not isinstance(x, str) else "str"
    return "number"


def python_checkpoints(sk):
    """{t: (canonical state, probes of the next STEPS steps)}."""
    out, st = {}, None
    for i, y in enumerate(SERIES[:TIMES[-1]]):
        _, st = sk(y, st)
        if i + 1 in TIMES:
            snap = json.loads(json.dumps(r_to_json(st), allow_nan=False))
            cont, s2 = [], r_from_json(json.loads(json.dumps(snap)))
            for y2 in SERIES[i + 1:i + 1 + STEPS]:
                dists, s2 = sk(y2, s2)
                cont.append([[clean(v) for v in probe_dist(d)] for d in dists])
            out[i + 1] = (snap, cont)
    return out


def torch_checkpoints(sk):
    out, st = {}, None
    with torch.no_grad():
        for i, y in enumerate(SERIES[:TIMES[-1]]):
            _, st = sk(y, st)
            if i + 1 in TIMES:
                out[i + 1] = json.loads(json.dumps(t_to_json(st), allow_nan=False))
    return out


@pytest.mark.parametrize("name", list(PY))
def test_resume_both_directions(name):
    assert name in TORCH, f"no torch builder for {name}"
    k, py = PY[name]
    ts = TORCH[name][1]()
    ref = python_checkpoints(py)
    mine = torch_checkpoints(ts)
    for t, (snap, cont) in ref.items():
        # layout: the torch state is the reference's, key for key
        assert shape(mine[t]) == shape(snap), f"{name}@{t}: torch state layout differs"
        # forward: the reference's checkpoint, resumed in torch
        st = t_from_json(json.loads(json.dumps(snap)))
        with torch.no_grad():
            for j, y in enumerate(SERIES[t:t + STEPS]):
                dists, st = ts(y, st)
                for h, d in enumerate(dists):
                    for a, b in zip(torch_probes(d, PROBE, Q_LO, Q_HI), cont[j][h]):
                        assert close(a, b), f"{name}@{t} forward step {j} h {h}: {float(a)!r} vs {b!r}"
        # reverse: torch's checkpoint, resumed in the reference
        st = r_from_json(mine[t])
        for j, y in enumerate(SERIES[t:t + STEPS]):
            dists, st = py(y, st)
            for h, d in enumerate(dists):
                for a, b in zip(probe_dist(d), cont[j][h]):
                    a = clean(a)
                    ok = (a == b) if isinstance(a, str) or isinstance(b, str) else close(a, b)
                    assert ok, f"{name}@{t} reverse step {j} h {h}: {a!r} vs {b!r}"


def test_learned_state_is_plain_and_resumes():
    """skaters.torch.learned (the training twin) checkpoints through JSON:
    its reference expert's state is read back as the reference's."""
    from skaters.torch.learned import learned
    f = learned(k=1)
    st = None
    with torch.no_grad():
        for y in SERIES[:40]:
            _, st = f(y, st)
        st2 = t_from_json(json.loads(json.dumps(t_to_json(st), allow_nan=False)))
        for y in SERIES[40:50]:
            d1, st = f(y, st)
            d2, st2 = f(y, st2)
            for p in (0.3, -1.0):
                assert abs(float(d1[0].logpdf(p)) - float(d2[0].logpdf(p))) <= 1e-9
            assert abs(float(d1[0].mean) - float(d2[0].mean)) <= 1e-9
    assert not math.isnan(float(d1[0].std))
