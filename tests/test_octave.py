"""Benchmark-side octave standardize: exact affine inverse, causal, a scale
that moves faster after a volatility jump than the medium estimate alone."""
import copy
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))
from octave import octave_standardize  # noqa: E402
from skaters.dist import Dist  # noqa: E402


def _feed(fwd, ys, st=None):
    out = []
    for y in ys:
        yp, st = fwd(y, st)
        out.append(yp)
    return out, st


def test_inverse_undoes_forward():
    rng = random.Random(1)
    fwd, inv = octave_standardize()
    _, st = _feed(fwd, [rng.gauss(0, 2) for _ in range(150)])
    y_next = 3.3
    yp, _ = fwd(y_next, copy.deepcopy(st))
    assert abs(inv([Dist.gaussian(yp, 1e-9)], st)[0].mean - y_next) < 1e-9


def test_causal_and_json_safe():
    rng = random.Random(2)
    ys = [rng.gauss(0, 1) for _ in range(120)]
    fwd, inv = octave_standardize()
    a, st = _feed(fwd, ys)
    b, _ = _feed(fwd, ys[:90] + [v * 30 for v in ys[90:]])
    assert a[:90] == b[:90]
    st2 = json.loads(json.dumps(st))
    d = [Dist.gaussian(0.1, 0.4)]
    assert [x.mean for x in inv(d, st)] == [x.mean for x in inv(d, st2)]


def test_scale_tracks_a_volatility_jump_faster_than_the_medium_estimate():
    rng = random.Random(3)
    ys = [rng.gauss(0, 1) for _ in range(300)] + [rng.gauss(0, 4) for _ in range(15)]
    fwd, inv = octave_standardize()
    _, st = _feed(fwd, ys)
    s_oct = inv([Dist.gaussian(0.0, 1.0)], st)[0].std
    s_mid = math.sqrt(st["vm"])
    assert s_oct > s_mid, (s_oct, s_mid)
