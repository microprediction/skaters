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


class _Const:
    """A stand-in component with a fixed log density."""

    def __init__(self, lp):
        self.lp = lp

    def logpdf(self, x):
        return self.lp


def test_mixture_logpdf_with_infinite_and_nan_components():
    from skaters.granger import MixtureDist
    assert MixtureDist([_Const(math.inf), _Const(-1.0)], [math.log(0.25), math.log(0.75)]).logpdf(0.0) == math.inf
    v = MixtureDist([_Const(float("nan")), _Const(-1.0)], [math.log(0.25), math.log(0.75)]).logpdf(0.0)
    assert abs(v - (math.log(0.75) - 1.0)) < 1e-12
    assert MixtureDist([_Const(-math.inf), _Const(-math.inf)], [0.0, 0.0]).logpdf(0.0) == -math.inf


def test_an_exact_hit_counts_for_the_forecaster_not_against_it():
    from skaters.granger import _score
    assert _score(math.inf) > 0 and _score(float("nan")) < 0 and _score(-math.inf) < 0 and _score(-2.0) == -2.0


def test_leading_and_mid_series_missing_values_are_handled():
    g = granger(1, frequency=available()[0])
    s = None
    ys = [float("nan"), None, 1.0, 1.2, float("nan"), 0.9] + [0.1 * i for i in range(40)]
    for y in ys:
        d, s = g(y, s)
        m = d[0]
        assert math.isfinite(m.mean) and math.isfinite(m.std) and m.std > 0


def test_bad_parameters_are_rejected():
    from skaters.granger import load_params
    P = load_params(available()[0])
    for bad in ({**P, "pi_lap": 0.0}, {**P, "pi_lap": 1.0}, {**P, "granger_format": 2}):
        with pytest.raises(ValueError):
            granger(1, params=bad)


@pytest.mark.parametrize("freq", available())
def test_weights_stay_normalised_and_the_bound_holds_after_an_extreme_step(freq):
    """[0, 0, 0, 2] makes laplace's log density ~ -1e14; the running totals are
    re-centred, so later weights keep full precision."""
    rng = random.Random(12)
    ys = [0.0, 0.0, 0.0, 2.0] + [float(min(6, int(abs(rng.gauss(0, 1.5))))) for _ in range(200)]
    g, f = granger(1, frequency=freq), laplace(1)
    sg = sf = None
    pg = pf = None
    gap = 0.0          # running (granger - laplace) log score, summed per step
    for t, y in enumerate(ys):
        if pg is not None:
            gap += pg.logpdf(y) - pf.logpdf(y)   # per-step difference: one rounding of ~1e-2 at the 1e14 step
        dg, sg = g(y, sg)
        df, sf = f(y, sf)
        pg, pf = dg[0], df[0]
        assert abs(sum(pg.w) - 1.0) < 1e-12
    assert gap >= -math.log(4.0) - 0.05
