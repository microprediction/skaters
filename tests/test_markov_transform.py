"""markov_drift: composability, determinism, and lattice sleep."""
import random

from skaters.conjugate import conjugate
from skaters.leaf import leaf
from skaters.markov import markov_drift


def _run(stream):
    f = conjugate(leaf(k=1), markov_drift(), k=1)
    state = None
    out = []
    for y in stream:
        dists, state = f(y, state)
        out.append((round(dists[0].mean, 12), round(dists[0].std, 12)))
    return out


def test_composes_and_is_deterministic():
    r = random.Random(3)
    stream = []
    y = 0.0
    for _ in range(400):
        y += r.gauss(0, 1)
        stream.append(y)
    assert _run(stream) == _run(stream)


def test_sleeps_on_lattice_series():
    stream = [0.0] * 300 + [1.0] + [0.0] * 99
    f = markov_drift()
    fwd, _ = f
    state = None
    for y in stream:
        yp, state = fwd(y, state)
    assert state["shift"] == 0.0  # repeat-dominated: the gate is asleep


def test_forward_inverse_consistency():
    fwd, inv = markov_drift()
    state = None
    r = random.Random(7)
    y = 0.0
    for _ in range(300):
        y += r.gauss(0, 1)
        yp, state = fwd(y, state)
    from skaters.dist import Dist
    d = Dist.gaussian(0.0, 1.0)
    (back,) = inv([d], state)
    assert abs(back.mean - state["shift"]) < 1e-12
