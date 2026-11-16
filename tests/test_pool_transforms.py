"""Untested-transform arms (benchmarks/pool_transforms.py, laplace(+x) in
arm_adapters): hand-computed one-step cases for each new transform, the
no-extras arm reproducing laplace exactly, and every arm running."""
import math
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))

from skaters.dist import Dist

pt = pytest.importorskip("pool_transforms")


def _run(t, ys):
    fwd, inv = t
    st, out = None, []
    for y in ys:
        v, st = fwd(y, st)
        out.append(v)
    return out, st, inv


def _n(mu, sd=1.0):
    return Dist([(1.0, mu, sd)])


def test_integrate_running_level_and_inverse():
    out, st, inv = _run(pt.integrate(), [1.0, 2.0, -0.5])
    assert out == [1.0, 3.0, 2.5]
    d = inv([_n(3.7, 0.4)], st)[0]                      # level 3.7 -> change 1.2
    assert d.mean == pytest.approx(1.2) and d.std == pytest.approx(0.4)


def test_ma1_innovations_and_one_step_mean():
    out, st, inv = _run(pt.ma1(0.5), [1.0, 2.0, 3.0])
    assert out == pytest.approx([1.0, 1.5, 2.25])       # e_t = x_t - 0.5 e_{t-1}
    assert inv([_n(0.0)], st)[0].mean == pytest.approx(1.125)


def test_huber_ema_clips_the_level_update():
    out, st, inv = _run(pt.huber_ema(alpha=0.5, c=1.0, beta=0.5), [10.0, 12.0, 20.0])
    # 12: r=2, first residual unclipped -> level 11, s=2
    # 20: r=9, clipped at c*s=2 -> level 12, s=2+0.5*(9-2)=5.5
    assert out == pytest.approx([0.0, 2.0, 9.0])
    assert st["level"] == pytest.approx(12.0) and st["s"] == pytest.approx(5.5)
    assert inv([_n(0.3)], st)[0].mean == pytest.approx(12.3)


def test_setar1_regime_coefficients():
    out, st, inv = _run(pt.setar1(lam=1.0, ridge=1.0, cap=0.95), [1.0, 2.0, -1.0, 3.0])
    # 2: xp=1 (rise), phi=0 -> 2;   sxy1=2,  sxx1=1
    # -1: xp=2 (rise), phi=2/2=1 capped to .95 -> -1-1.9=-2.9;  sxy1=0, sxx1=5
    # 3: xp=-1 (fall), phi=0 -> 3;  sxy0=-3, sxx0=1
    assert out == pytest.approx([0.0, 2.0, -2.9, 3.0])
    assert st["sxy"] == pytest.approx([-3.0, 0.0]) and st["sxx"] == pytest.approx([1.0, 5.0])
    state = {"sxy": [-1.0, 0.5], "sxx": [3.0, 3.0], "x": -2.0}
    assert inv([_n(0.0)], state)[0].mean == pytest.approx(0.5)   # phi0=-1/4, times -2


def test_h1_only():
    fwd, inv = pt.integrate()
    _, st = fwd(1.0, None)
    with pytest.raises(NotImplementedError):
        inv([_n(0.0), _n(0.0)], st)


def _series(n=160, seed=3):
    rng = random.Random(seed)
    x, out = 0.0, []
    for t in range(n):
        x = 0.6 * x + rng.gauss(0, 1) + 0.8 * math.sin(2 * math.pi * t / 12)
        out.append(x)
    return out


def test_no_extras_reproduces_laplace_exactly():
    aa = pytest.importorskip("arm_adapters")
    from skaters.api import laplace
    f, g = laplace(1), aa.laplace_extra_periods(1, ())
    sf = sg = None
    for y in _series(120):
        df, sf = f(y, sf)
        dg, sg = g(y, sg)
        assert df[0].mean == dg[0].mean and df[0].std == dg[0].std


@pytest.mark.parametrize("name", ["+lou", "+gar", "+ou", "+ma", "+huber", "+ptrend", "+setar", "markov"])
def test_every_arm_runs_and_differs_from_laplace(name):
    aa = pytest.importorskip("arm_adapters")
    from skaters.api import laplace
    f = aa.laplace_extra_periods(1, (), extra=lambda kk: aa._pool_extras(kk)[name])
    g = laplace(1)
    sf = sg = None
    differs = False
    for y in _series():
        df, sf = f(y, sf)
        dg, sg = g(y, sg)
        assert math.isfinite(df[0].logpdf(y + 0.1))
        differs = differs or df[0].mean != dg[0].mean
    assert differs                       # the extra candidates take weight
    assert f"laplace({name})" in aa.make_registry(1)
