"""Benchmark-side sinh-arcsinh transform: inverse undoes forward, causal,
identity at (0, 1), json-safe state."""
import copy
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))
from shash import shash  # noqa: E402
from skaters.dist import Dist  # noqa: E402


def _feed(fwd, ys):
    st = None
    out = []
    for y in ys:
        yp, st = fwd(y, st)
        out.append(yp)
    return out, st


def test_inverse_maps_the_next_forward_value_back():
    rng = random.Random(3)
    ys = [rng.gauss(0, 1) ** 3 for _ in range(200)]
    for e, d in [(0.0, 0.7), (0.3, 1.0), (-0.3, 1.4)]:
        fwd, inv = shash(e, d)
        _, st = _feed(fwd, ys)
        y_next = 1.7
        yp, _ = fwd(y_next, copy.deepcopy(st))   # forward uses the state BEFORE y_next
        back = inv([Dist.gaussian(yp, 1e-9)], st)[0].mean
        assert abs(back - y_next) < 1e-6, (e, d, back)


def test_identity_after_standardization():
    """(epsilon, delta) = (0, 1): the output is the causal z-score."""
    rng = random.Random(4)
    ys = [rng.gauss(2, 3) for _ in range(100)]
    fwd, _ = shash(0.0, 1.0, alpha=0.02, warmup=20)
    st = None
    for t, y in enumerate(ys):
        before = copy.deepcopy(st)
        yp, st = fwd(y, st)
        if t > 20:
            z = (y - before["m"]) / math.sqrt(before["v"])
            assert abs(yp - z) < 1e-9


def test_causal():
    rng = random.Random(5)
    ys = [rng.gauss(0, 1) for _ in range(120)]
    fwd, _ = shash(0.3, 0.8)
    a, _ = _feed(fwd, ys)
    fwd2, _ = shash(0.3, 0.8)
    b, _ = _feed(fwd2, ys[:80] + [v * 50 for v in ys[80:]])
    assert a[:80] == b[:80]


def test_state_json_round_trip():
    fwd, inv = shash(-0.3, 1.2)
    _, st = _feed(fwd, [math.sin(i / 4.0) for i in range(60)])
    st2 = json.loads(json.dumps(st))
    d = [Dist.gaussian(0.2, 0.5)]
    assert [x.mean for x in inv(d, st)] == [x.mean for x in inv(d, st2)]


def test_inverse_maps_back_at_the_end_of_warmup():
    """After exactly `warmup` points the next forward transforms, so the inverse must too."""
    rng = random.Random(4)
    for n in (19, 20, 21):
        fwd, inv = shash(0.3, 1.2, warmup=20)
        _, st = _feed(fwd, [rng.gauss(0, 1) ** 3 for _ in range(n)])
        y_next = 1.7
        yp, _ = fwd(y_next, copy.deepcopy(st))
        back = inv([Dist.gaussian(yp, 1e-9)], st)[0].mean
        assert abs(back - y_next) < 1e-6, n
