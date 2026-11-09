"""granger: the guarantee against laplace, checkpoint-restore, and the mixture's
own consistency, on every shipped parameter set (no torch needed; parity
against the torch training twin is parity/check_granger.py)."""
import math
import pickle
import random

import pytest

from skaters import laplace
from skaters.granger import available, granger


def _stream(n=260, seed=5):
    rng = random.Random(seed)
    out = []
    for t in range(n):
        vol = 4.0 if (t // 60) % 2 else 1.0
        out.append(rng.gauss(0.0, vol) + (0.5 if t > n // 2 else 0.0))
    return out


@pytest.mark.parametrize("freq", available())
def test_never_more_than_log4_behind_laplace(freq):
    g, f = granger(1, frequency=freq), laplace(1)
    sg = sf = None
    pg = pf = None
    total_g = total_f = 0.0
    for y in _stream():
        if pg is not None:
            total_g += pg.logpdf(y)
            total_f += pf.logpdf(y)
            assert total_g >= total_f - math.log(4.0) - 1e-9
        dg, sg = g(y, sg)
        df, sf = f(y, sf)
        pg, pf = dg[0], df[0]


@pytest.mark.parametrize("freq", available())
def test_checkpoint_restore_is_identical(freq):
    g = granger(1, frequency=freq)
    ys = _stream(160, seed=8)
    s = None
    for y in ys[:80]:
        _, s = g(y, s)
    s2 = pickle.loads(pickle.dumps(s))
    for y in ys[80:]:
        a, s = g(y, s)
        b, s2 = g(y, s2)
        assert a[0].logpdf(y) == b[0].logpdf(y) and a[0].mean == b[0].mean


def test_mixture_quantile_and_cdf_agree():
    g = granger(1, frequency=available()[0])
    s = None
    for y in _stream(120, seed=9):
        d, s = g(y, s)
    m = d[0]
    for p in (0.05, 0.5, 0.95):
        assert abs(m.cdf(m.quantile(p)) - p) < 1e-6


def test_horizon_above_one_is_refused():
    with pytest.raises(ValueError):
        granger(3)


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node not installed")
def test_js_port_matches_python():
    """The JS port (docs/js/skaters/granger.mjs) against this package, 1e-6."""
    import os
    import subprocess
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, PYTHONPATH=os.path.join(root, "src"))
    subprocess.run([sys.executable, os.path.join(root, "parity", "gen_granger_vectors.py")],
                   check=True, env=env, capture_output=True)
    r = subprocess.run(["node", os.path.join(root, "parity", "check_granger.mjs")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
