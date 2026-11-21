"""Cross-language resume: a checkpoint written by one port resumes in the other.

docs/STATE.md fixes one JSON layout for skater state, with Python as the
reference. For every exported skater the JS port reproduces, over a seeded
series:

1. Python runs the stream and writes ``state_to_json(state)`` at t = 60, 250
   and 530 (those that leave 20 steps to run), plus the probes of the next 20
   outputs.
2. ``parity/state_resume.mjs`` loads each Python checkpoint with
   ``stateFromJSON``, steps 20, and must match Python's probes to 1e-6. It also
   runs the stream itself and checks that its own state at each checkpoint has
   exactly Python's key layout. It writes its own checkpoints and probes.
3. Python loads each JS checkpoint with ``state_from_json``, steps 20, and must
   match the JS probes (and its own) to 1e-6.

The registry here and ``parity/state_resume.mjs`` must use the same names.
Skipped if Node is not installed.
"""

import json
import math
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "parity"))

import gen_vectors  # noqa: E402

from skaters import (  # noqa: E402
    laplace, granger, flesaker, dantzig, multiscale, parade, sticky, homogenize,
    residual_transform, conjugate, leaf, ema, precision_weighted_ensemble,
    bayesian_ensemble, terminal_leaf_ensemble, search, state_to_json, state_from_json,
)
from skaters import transform as T  # noqa: E402
from skaters.leaf import scale_mixture_leaf, crps_leaf, garch_leaf  # noqa: E402
from skaters.tails import gpdtails  # noqa: E402

N = 620
CHECKPOINTS = (60, 250, 530)
CONTINUE = 20
PROBE = 0.3
ATOL = RTOL = 1e-6


def _c(t, k=1):
    return conjugate(leaf(k=k), t, k=k)


def _series():
    series = gen_vectors.make_series(n=N, seed=12345)
    return {
        "series": series,
        "short": series[:300],
        "positive": [abs(v) + 1.0 for v in series],
        "repeat": gen_vectors.make_repeat_series(n=N, seed=99),
        "gaps": gen_vectors.make_gap_series(n=N, seed=4242),
    }


def _parity_scenario(name):
    """A fresh instance of a parity scenario (gen_vectors), by name."""
    for n, _k, sk in gen_vectors.build_scenarios() + gen_vectors.build_wrapper_scenarios():
        if n == name:
            return sk
    raise KeyError(name)


def _registry():
    """name -> (factory, series key). Every exported skater JS has."""
    out = {n: (lambda n=n: _parity_scenario(n), "short")
           for n, _k, _sk in gen_vectors.build_scenarios() + gen_vectors.build_wrapper_scenarios()}
    extra = {
        "conjugate_seasonal_anchor": (lambda: _c(T.seasonal_anchor(7)), "series"),
        "conjugate_ar_default": (lambda: _c(T.ar(2)), "series"),
        "conjugate_power_positive": (lambda: _c(T.power_transform(0.5)), "positive"),
        "conjugate_log_transform": (lambda: _c(T.log_transform()), "positive"),
        "laplace": (lambda: laplace(1), "series"),
        "laplace_k3": (lambda: laplace(3), "series"),
        "laplace_likelihood": (lambda: laplace(1, objective="likelihood"), "series"),
        "laplace_gaussian_tails": (lambda: laplace(1, tails="gaussian"), "short"),
        "laplace_scales": (lambda: laplace(4, scales=[1, 2]), "short"),
        "laplace_garch_leaf": (lambda: laplace(1, leaf=garch_leaf), "series"),
        "laplace_repeat": (lambda: laplace(1), "repeat"),
        "laplace_gaps": (lambda: laplace(1), "gaps"),
        "laplace_k3_gaps": (lambda: laplace(3), "gaps"),
        "granger": (lambda: granger(1), "series"),
        "flesaker": (lambda: flesaker(1, lower=-100.0), "series"),
        "dantzig": (lambda: dantzig(1, expand_interval=50), "short"),
        "search_k2": (lambda: search(k=2, expand_interval=40, max_pool=12), "short"),
        "multiscale_k4": (lambda: multiscale(lambda kk: _c(T.ema_transform(0.1), kk), 4), "short"),
        "parade_spliced": (lambda: parade(gpdtails(_c(T.ema_transform(0.1)), k=1, nexc=50, warmup=100), 1),
                           "series"),
        "sticky_ema_repeat": (lambda: sticky(_c(T.ema_transform(0.1)), k=1), "repeat"),
        "homogenize_laplace": (lambda: homogenize(laplace(1)), "series"),
        "residual_transform_laplace": (lambda: residual_transform(laplace(1)), "series"),
        "pw_ensemble_k2": (lambda: precision_weighted_ensemble([ema(0.05, k=2), ema(0.2, k=2)], k=2), "short"),
        "bayes_ensemble_k2": (lambda: bayesian_ensemble(
            [ema(0.05, k=2), _c(T.difference(), 2)], k=2, learning_rate=0.5, complexity_penalty=0.0), "short"),
        "terminal_k3": (lambda: terminal_leaf_ensemble(
            [ema(0.05, k=3), _c(T.difference(), 3)], k=3, depths=[0, 1], forget=0.99), "short"),
        "scale_mixture_leaf_long": (lambda: scale_mixture_leaf(k=1), "series"),
        "crps_leaf_long": (lambda: crps_leaf(k=1), "series"),
        "garch_leaf_long": (lambda: garch_leaf(k=1), "series"),
    }
    out.update(extra)
    return out


REGISTRY = _registry()


def _clean(x):
    if x != x:
        return "nan"
    if x == math.inf:
        return "inf"
    if x == -math.inf:
        return "-inf"
    return x


def _decode(x):
    return {"nan": math.nan, "inf": math.inf, "-inf": -math.inf}.get(x, x) if isinstance(x, str) else x


def _probe(dists):
    return [[_clean(v) for v in (d.mean, d.std, d.logpdf(PROBE), d.cdf(PROBE),
                                 d.quantile(0.1), d.quantile(0.9), d.crps(PROBE))] for d in dists]


def _close(a, b):
    a, b = _decode(a), _decode(b)
    if a != a and b != b:
        return True
    if not (math.isfinite(a) and math.isfinite(b)):
        return a == b
    return abs(a - b) <= ATOL + RTOL * abs(b)


def _compare(got, want, where):
    bad = []
    for m, (gs, ws) in enumerate(zip(got, want)):
        assert len(gs) == len(ws), f"{where} +{m + 1}: {len(gs)} horizons, want {len(ws)}"
        for h, (g, w) in enumerate(zip(gs, ws)):
            for j, (a, b) in enumerate(zip(g, w)):
                if not _close(a, b):
                    bad.append(f"{where} +{m + 1} h={h} probe{j}: {a!r} vs {b!r}")
    return bad


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_checkpoint_resumes_across_ports(name, tmp_path):
    factory, key = REGISTRY[name]
    series = _series()[key]
    n = len(series)
    checkpoints = [c for c in CHECKPOINTS if c + CONTINUE < n]

    # 1. Python checkpoints and the next CONTINUE outputs.
    f = factory()
    state = None
    py = []
    for t, y in enumerate(series[:max(checkpoints) + CONTINUE + 1]):
        _, state = f(y, state)
        if t in checkpoints:
            text = json.dumps(state_to_json(state), allow_nan=False)
            probes = []
            for y2 in series[t + 1:t + 1 + CONTINUE]:
                d, state = f(y2, state)
                probes.append(_probe(d))
            py.append({"t": t, "state": json.loads(text), "probes": probes})
            # the original stream carries on from t + CONTINUE: rewind
            state = state_from_json(json.loads(text))
    py_path = tmp_path / "py.json"
    js_path = tmp_path / "js.json"
    py_path.write_text(json.dumps({"name": name, "series": [_clean(v) for v in series],
                                   "probe": PROBE, "continue": CONTINUE, "checkpoints": py},
                                  allow_nan=False))

    # 2. JS resumes Python's checkpoints and writes its own.
    result = subprocess.run(
        ["node", os.path.join(ROOT, "parity", "state_resume.mjs"), str(py_path), str(js_path)],
        capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, f"{name}: JS resume from Python failed\n{result.stdout}\n{result.stderr}"

    # 3. Python resumes JS's checkpoints.
    js = json.loads(js_path.read_text())
    bad = []
    for cp, mine in zip(js["checkpoints"], py):
        assert cp["t"] == mine["t"]
        f = factory()
        state = state_from_json(cp["state"])
        t = cp["t"]
        got = []
        for y2 in series[t + 1:t + 1 + CONTINUE]:
            d, state = f(y2, state)
            got.append(_probe(d))
        bad += _compare(got, cp["probes"], f"{name} t={t} python-from-js vs js")
        bad += _compare(got, mine["probes"], f"{name} t={t} python-from-js vs python")
    assert not bad, "\n".join(bad[:10])
