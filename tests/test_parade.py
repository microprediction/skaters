"""Tests for the prediction parade (PIT/z calibration state)."""

import math
import random
from skaters import laplace, parade, leaf


def test_shapes_and_warmup():
    f = laplace(3)
    state = None
    d, state = f(0.1, state)
    assert state["pit"] == [None, None, None]     # nothing matured yet
    d, state = f(0.2, state)
    assert state["pit"][0] is not None and state["pit"][1] is None
    d, state = f(0.3, state)
    d, state = f(0.4, state)
    assert all(v is not None for v in state["pit"])
    assert all(v is not None for v in state["z"])
    assert len(state["pit"]) == len(state["z"]) == 3


def test_pass_through():
    """The wrapper must not change the forecasts."""
    random.seed(2)
    ys = [random.gauss(0, 1) for _ in range(80)]
    g = leaf(k=2)
    f = parade(leaf(k=2), k=2)
    sg = sf = None
    for y in ys:
        dg, sg = g(y, sg)
        df, sf = f(y, sf)
    assert dg[0].mean == df[0].mean and dg[1].std == df[1].std


def test_roughly_uniform_and_normal():
    random.seed(7)
    f = laplace(1)
    state = None
    us, zs = [], []
    for i in range(700):
        _, state = f(random.gauss(0, 1), state)
        if i >= 100 and state["pit"][0] is not None:
            us.append(state["pit"][0])
            zs.append(state["z"][0])
    n = len(us)
    assert abs(sum(us) / n - 0.5) < 0.05                       # PIT mean ~ 1/2
    assert abs(sum(1 for u in us if u < 0.5) / n - 0.5) < 0.07  # median ~ 1/2
    zbar = sum(zs) / n
    zstd = math.sqrt(sum((z - zbar) ** 2 for z in zs) / n)
    assert abs(zbar) < 0.15
    assert 0.7 < zstd < 1.3


def test_horizon_alignment():
    """z at horizon m must resolve against the prediction made m steps ago:
    an outlier registers as surprising at every matured horizon at once."""
    random.seed(11)
    f = laplace(3)
    state = None
    for _ in range(200):
        _, state = f(random.gauss(0, 0.1), state)
    _, state = f(25.0, state)                    # a screaming outlier
    assert all(z is not None and z > 4 for z in state["z"])


def test_no_infinities_on_extreme_inputs():
    """Outliers, constants, and huge jumps must never yield infinite z."""
    f = laplace(2)
    state = None
    stream = [0.0] * 30 + [1e12, -1e12, 0.0, 5.0] + [3.3] * 20 + [float(10 ** 9)]
    for y in stream:
        _, state = f(y, state)
        for z in state["z"]:
            if z is not None:
                assert math.isfinite(z)
                assert abs(z) <= 7.05             # the documented clamp bound
        for u in state["pit"]:
            if u is not None:
                assert 0.0 < u < 1.0
