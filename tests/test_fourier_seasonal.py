"""The benchmark-side Fourier seasonal transform: causal, exact on a pure
harmonic, and a state that round-trips through json."""
import copy
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))
from fourier_seasonal import fourier_seasonal  # noqa: E402
from skaters.dist import Dist  # noqa: E402

P = 365.25 / 7


def test_recovers_a_pure_harmonic_after_warmup():
    fwd, inv = fourier_seasonal(P, harmonics=2, forget=1.0)
    st = None
    resid = []
    for t in range(400):
        y = 2.0 + 3.0 * math.sin(2 * math.pi * t / P) - 1.0 * math.cos(4 * math.pi * t / P)
        yp, st = fwd(y, st)
        if t > 300:
            resid.append(abs(yp))
    # the RLS prior (delta) regularises the early fit; by four periods it is negligible
    assert max(resid) < 1e-3, max(resid)        # amplitude 3: recovered to 0.03%
    # the inverse forecasts the next value of the harmonic exactly
    nxt = 2.0 + 3.0 * math.sin(2 * math.pi * 400 / P) - 1.0 * math.cos(4 * math.pi * 400 / P)
    d = inv([Dist.gaussian(0.0, 1.0)], st)[0]
    assert abs(d.mean - nxt) < 1e-3


def test_forward_is_causal():
    rng = random.Random(1)
    ys = [math.sin(2 * math.pi * t / P) + 0.3 * rng.gauss(0, 1) for t in range(200)]
    fwd, _ = fourier_seasonal(P)
    st = None
    out_a = []
    for y in ys:
        yp, st = fwd(y, st); out_a.append(yp)
    st = None
    ys_b = ys[:150] + [v + 100.0 for v in ys[150:]]
    out_b = []
    for y in ys_b:
        yp, st = fwd(y, st); out_b.append(yp)
    assert out_a[:150] == out_b[:150]


def test_state_round_trips_through_json():
    fwd, inv = fourier_seasonal(P)
    st = None
    for t in range(120):
        _, st = fwd(math.cos(t / 3.0), st)
    st2 = json.loads(json.dumps(st))
    a = inv([Dist.gaussian(0.0, 1.0)] * 3, copy.deepcopy(st))
    b = inv([Dist.gaussian(0.0, 1.0)] * 3, st2)
    assert [x.mean for x in a] == [x.mean for x in b]
