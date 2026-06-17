"""Tests for the sticky (zero-inflation) wrapper and the dirac policy."""

import math
import random

from skaters.dist import Dist
from skaters.sticky import sticky
from skaters.api import dirac, skater
from skaters.conventions import Skater
from skaters.leaf import leaf
from skaters.conjugate import conjugate
from skaters.transform import ema_transform


def _run(f, series):
    state = None
    out = []
    for y in series:
        d, state = f(y, state)
        out.append(d[0])
    return out


def _base():
    return conjugate(leaf(1), ema_transform(0.1), 1)


def test_sticky_vanishes_on_continuous_data():
    # No exact repeats -> p stays 0 -> sticky passes the base through unchanged.
    random.seed(0)
    series = [random.gauss(0, 1) for _ in range(200)]
    b = _run(_base(), series)
    s = _run(sticky(_base(), 1), series)
    assert b[-1].components == s[-1].components


def test_sticky_is_still_a_dist():
    d = _run(sticky(skater(1), 1), [3.0] * 50 + [3.0, 4.0, 4.0])[-1]
    assert isinstance(d, Dist)
    assert d.std > 0 and math.isfinite(d.logpdf(4.0))


def test_sticky_spike_on_repeats():
    # Mostly repeating -> a dominant narrow spike at the last value.
    out = _run(sticky(_base(), 1), [5.0] * 60 + [6.0] * 60)
    d = out[-1]
    assert len(d.components) >= 2          # spike + base
    w, m, s = max(d.components, key=lambda c: c[0])
    assert w > 0.5                         # spike carries most of the mass
    assert abs(m - 6.0) < 1e-9             # at the last value
    assert s < 0.05                        # and it is narrow (near-Dirac)


def test_sticky_anchors_at_modal_value_not_last():
    # Mostly 0 with isolated nonzero jumps, ending on a jump. The atom must sit
    # at the modal value (0) -- the lattice attractor -- not the raw last value
    # (0.25), which right after a jump is the least likely value to recur.
    series = [0.25 if i % 17 == 0 else 0.0 for i in range(200)]
    series.append(0.25)                      # force the last value to be a jump
    assert series[-1] == 0.25
    d = _run(sticky(skater(1), 1), series)[-1]
    w, m, s = max(d.components, key=lambda c: c[0])
    assert s < 0.05                          # it is the narrow atom
    assert abs(m - 0.0) < 1e-9               # anchored at the mode, not 0.25


def test_sticky_is_mean_preserving():
    # The projection adds atom mass WITHOUT moving the base ensemble's mean.
    import random
    random.seed(3)
    series, v = [], 5.0
    for _ in range(250):
        if random.random() > 0.85:
            v += random.choice([-0.25, 0.25])
        series.append(round(v, 2))
    base, proj = _base(), sticky(_base(), 1)
    sb = sp = None
    worst = 0.0
    for y in series:
        db, sb = base(y, sb)
        dp, sp = proj(y, sp)
        worst = max(worst, abs(db[0].mean - dp[0].mean))
    assert worst < 1e-9                     # mean is untouched by the atom


def test_sticky_captures_non_consecutive_lattice():
    # A series that revisits {0,1,2} often but NEVER consecutively. A
    # consecutive-repeat gate would see no repeats and vanish; the lattice puts
    # atoms on all three revisited values and assigns the true value high mass.
    random.seed(0)
    vals, last, series = [0.0, 1.0, 2.0], None, []
    for _ in range(400):
        v = random.choice([x for x in [0.0, 1.0, 2.0] if x != last])
        series.append(v)
        last = v
    d = _run(sticky(skater(1), 1), series)[-1]
    atoms = [(w, m) for w, m, s in d.components if s < 0.05]
    assert len(atoms) >= 3                       # an atom on each lattice value
    on_lattice = sum(w for w, m in atoms
                     if min(abs(m - v) for v in vals) < 1e-9)
    assert on_lattice > 0.8                      # most mass sits on the lattice
    # and it makes the lattice values far more likely than a continuous fit
    assert d.logpdf(1.0) > math.log(0.2)


def test_dirac_is_skater_and_runs():
    f = dirac(1)
    assert isinstance(f, Skater)
    state = None
    random.seed(1)
    for _ in range(80):
        d, state = f(random.gauss(0, 1), state)
    assert d[0].std > 0 and math.isfinite(d[0].logpdf(0.0))


def test_dirac_rewards_repetition():
    # On a perfectly sticky series, dirac places a sharp spike at the repeat.
    f = dirac(1)
    state = None
    for _ in range(120):
        d, state = f(2.0, state)
    assert d[0].logpdf(2.0) > 2.0          # the spike makes the repeat very likely
