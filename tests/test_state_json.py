"""A skater is a fold: its state must survive JSON bit-exactly.

The Python twin of parity/roundtrip.mjs. For every exported skater, over a
seeded series, the state is checkpointed through

    state_from_json(json.loads(json.dumps(state_to_json(state))))

at several points, including after laplace's GPD splice is live (warmup
500), and the restored copy is stepped beside the original. On the restore
step and on every step after it, both the predictives and the states must
be equal: the states as JSON text, the predictives float-exactly through
gen_vectors.state_snapshot (some predictives, such as granger's mixture,
are not Dists and have no JSON form). assert_plain_state runs on every step,
so a deque, a non-string key, a tuple, a closure or a non-finite float
anywhere in a state fails the gate. The layout is documented in
docs/STATE.md.

Old Python checkpoints (deques, sticky's float-keyed dict, int-keyed
multiscale and periodicity tables, search's closures) must still resume:
see test_legacy_layouts_resume.
"""

import json
import os
import sys
from collections import deque

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "parity"))

import gen_vectors  # noqa: E402

from skaters import (  # noqa: E402
    Dist, laplace, granger, flesaker, dantzig, multiscale, parade, sticky, homogenize,
    residual_transform, conjugate, leaf, ema, precision_weighted_ensemble,
    bayesian_ensemble, terminal_leaf_ensemble, mahalanobis, zbank, search,
    state_to_json, state_from_json, assert_plain_state, period_detector,
)
from skaters import transform as T  # noqa: E402
from skaters.leaf import scale_mixture_leaf, crps_leaf, garch_leaf, conforming_leaf, ensemble_leaf  # noqa: E402
from skaters.tails import gpdtails, SplicedDist  # noqa: E402
from skaters.anomaly import gpdtail  # noqa: E402

N = 620            # long enough for laplace's default GPD splice (warmup 500)
CHECKPOINTS = (60, 250, 530)
CONTINUE = 20

snap = gen_vectors.state_snapshot


def enc(x) -> str:
    return json.dumps(state_to_json(x), allow_nan=False)


def restore(x):
    return state_from_json(json.loads(enc(x)))


def _c(t, k=1):
    return conjugate(leaf(k=k), t, k=k)


def _every_transform(k=1):
    """conjugate(leaf, t) for every transform in skaters.transform."""
    return [
        ("difference", T.difference()),
        ("fractional_difference", T.fractional_difference(0.4, 30)),
        ("standardize", T.standardize()),
        ("ema_transform", T.ema_transform(0.1)),
        ("ou_transform", T.ou_transform(0.1)),
        ("theta", T.theta(0.1)),
        ("drift", T.drift(0.05, 0.01)),
        ("holt_linear", T.holt_linear(0.1, 0.05)),
        ("garch", T.garch()),
        ("seasonal_difference", T.seasonal_difference(7)),
        ("seasonal_anchor", T.seasonal_anchor(7)),
        ("seasonal_scale", T.seasonal_scale(7)),
        ("seasonal_scale_center", T.seasonal_scale(7, center=True)),
        ("power_transform", T.power_transform(0.5)),
        ("power_transform_exact", T.power_transform(0.5, exact=True)),
        ("yeo_johnson", T.yeo_johnson(0.5)),
        ("yeo_johnson_exact", T.yeo_johnson(0.5, exact=True)),
        ("ar", T.ar(2)),
        ("grouped_ar", T.grouped_ar(8)),
        ("gaussianize", T.gaussianize()),
        ("gaussianize_smooth", T.gaussianize(smooth=True)),
    ]


def _scenarios():
    series = gen_vectors.make_series(n=N, seed=12345)
    repeat = gen_vectors.make_repeat_series(n=N, seed=99)
    gaps = gen_vectors.make_gap_series(n=N, seed=4242)
    short = series[:300]
    positive = [abs(v) + 1.0 for v in series]
    for name, _k, sk in gen_vectors.build_scenarios():
        yield name, sk, series[:300]
    for name, t in _every_transform():
        yield "conjugate_" + name, _c(t), positive if name.startswith("power") else series
    yield "conjugate_log_transform", conjugate(leaf(k=1), T.log_transform(), k=1), positive
    # policies, at full length so the GPD splice is live at the last checkpoint
    yield "laplace", laplace(1), series
    yield "laplace_k3", laplace(3), series
    yield "laplace_likelihood", laplace(1, objective="likelihood"), series
    yield "laplace_gaussian_tails", laplace(1, tails="gaussian"), short
    yield "laplace_repeat", laplace(1), repeat
    yield "laplace_gaps", laplace(1), gaps
    yield "laplace_k3_gaps", laplace(3), gaps
    yield "granger", granger(1), series
    yield "flesaker", flesaker(1, lower=-100.0), series
    yield "dantzig", dantzig(1, expand_interval=50), short
    yield "search_k2", search(k=2, expand_interval=40, max_pool=12), short
    # wrappers
    yield "multiscale_k4", multiscale(lambda kk: _c(T.ema_transform(0.1), kk), 4), short
    yield "parade_spliced", parade(gpdtails(_c(T.ema_transform(0.1)), k=1, nexc=50, warmup=100), 1), series
    yield "parade_laplace_k3", parade(laplace(3), 3), series
    yield "sticky_ema_repeat", sticky(_c(T.ema_transform(0.1)), k=1), repeat
    yield "homogenize", homogenize(_c(T.ema_transform(0.1)), k=1), short
    yield "homogenize_k2_weights", homogenize(_c(T.ema_transform(0.1), 2), k=2, couple="weights"), short
    yield "homogenize_k2_shared", homogenize(_c(T.ema_transform(0.1), 2), k=2, couple="shared"), short
    for model in ("m0", "m1", "m2"):
        yield f"residual_transform_{model}", residual_transform(_c(T.ema_transform(0.1)), model=model), short
    # ensembles and leaves
    yield "pw_ensemble_k2", precision_weighted_ensemble([ema(0.05, k=2), ema(0.2, k=2)], k=2), short
    yield "bayes_ensemble_k2", bayesian_ensemble([ema(0.05, k=2), _c(T.difference(), 2)], k=2), short
    yield "terminal_adaptive", terminal_leaf_ensemble(
        [ema(0.05, k=1), _c(T.difference())], k=1, depths=[0, 1], adaptive_temperature=True), short
    yield "terminal_k3", terminal_leaf_ensemble(
        [ema(0.05, k=3), _c(T.difference(), 3)], k=3, depths=[0, 1], forget=0.99), short
    for nm, lf in (("scale_mixture_leaf", scale_mixture_leaf), ("crps_leaf", crps_leaf),
                   ("garch_leaf", garch_leaf), ("conforming_leaf", conforming_leaf),
                   ("ensemble_leaf", ensemble_leaf)):
        yield nm, lf(k=1), series
    # anomaly heads
    yield "mahalanobis", mahalanobis(laplace(k=2), k=2), short
    yield "zbank", zbank(k=1, strides=(1, 2)), short[:150]
    yield "gpdtail", gpdtail(laplace(k=1), k=1, nexc=50, warmup=100), short


SCENARIOS = list(_scenarios())


@pytest.mark.parametrize("name,skater,series", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_json_roundtrip_is_exact(name, skater, series):
    state = None
    t = 0
    n = len(series)
    checkpoints = [c for c in CHECKPOINTS if c + CONTINUE < n] or [n // 2]
    while t < n:
        _dists, state = skater(series[t], state)
        assert_plain_state(state)
        if t in checkpoints:
            text = enc(state)
            twin = state_from_json(json.loads(text))
            assert enc(twin) == text, f"{name} t={t}: re-encoded restore differs"
            for m in range(1, CONTINUE + 1):
                y = series[t + m]
                da, state = skater(y, state)
                db, twin = skater(y, twin)
                assert snap(da) == snap(db), f"{name} t={t} +{m}: predictive differs after restore"
                assert enc(state) == enc(twin), f"{name} t={t} +{m}: state differs after restore"
            t += CONTINUE
        t += 1


def test_gate_meets_a_spliced_dist_in_state():
    f = laplace(1)
    series = gen_vectors.make_series(n=N, seed=12345)
    state = None
    for y in series[:CHECKPOINTS[-1] + 1]:
        _, state = f(y, state)
    text = enc(state)
    assert '"spliced": true' in text
    back = state_from_json(json.loads(text))
    assert isinstance(back["pending"][-1][0], SplicedDist)


def test_walker_names_the_offending_path():
    with pytest.raises(ValueError, match=r"at \.a\.b\[1\]: non-finite"):
        state_to_json({"a": {"b": [1.0, float("nan")]}})
    with pytest.raises(ValueError, match=r"at \.q: an instance of deque"):
        assert_plain_state({"q": deque([1.0])})
    with pytest.raises(ValueError, match=r"dict key 1\.5"):
        state_to_json({"counts": {1.5: 0.1}})
    with pytest.raises(ValueError, match=r"a function"):
        state_to_json({"f": len})
    with pytest.raises(ValueError, match=r"instance of set"):
        state_to_json({"p": {7}})


def test_dist_encoding_is_exact_and_unrenormalised():
    import random
    rng = random.Random(7)
    for _ in range(300):
        comps = [(rng.random() + 1e-3, rng.gauss(0, 4), 0.1 + rng.random())
                 for _ in range(rng.randint(1, 9))]
        d = Dist(comps)
        back = state_from_json(json.loads(json.dumps(state_to_json(d))))
        assert back.components == d.components
    # a loose hand-written dict is still normalised
    loose = state_from_json({"components": [[1.0, 0.0, 1.0], [3.0, 1.0, 1.0]]})
    assert loose.components[0][0] == 0.25
    # a tuple is written as a list, the canonical sequence
    assert state_to_json({"x": (1, 2.5)}) == {"x": [1, 2.5]}


# ---------------------------------------------------------------------------
# Old Python layouts still resume
# ---------------------------------------------------------------------------

def _to_legacy(o, path=""):
    """Rewrite a canonical state into the layout Python used before the
    canonical one: deques for queues, sticky's float-keyed dict, int-keyed
    multiscale and periodicity tables, granger's tuple pairs. zbank's
    tuple-keyed dict and search's closures are built in their own tests."""
    if isinstance(o, list):
        return [_to_legacy(v, path) for v in o]
    if not isinstance(o, dict) or "components" in o or "spliced" in o:
        return o
    out = {}
    for key, v in o.items():
        v = _to_legacy(v, key)
        if key == "counts" and isinstance(v, list):
            v = {val: w for val, w in v}
        elif key in ("qdist", "mean_q", "queues") and isinstance(v, list):
            v = [deque(q) if not (q and isinstance(q[0], list)) else [deque(x) for x in q] for q in v]
        elif key == "pred_q" or (key == "buf" and "last_r2" in o):
            v = deque(v)
        elif key == "pending" and "pit" in o:
            v = deque(v, maxlen=len(o["pit"]))
        elif key == "pend":
            v = deque((tuple(p) for p in v), maxlen=len(o["z"]))
        elif key in ("phase", "pending", "latest", "score") and "t" in o and isinstance(v, dict) \
                and all(x.isdigit() for x in v):
            v = {int(x): w for x, w in v.items()}
        elif key == "cross":
            v = {int(x): w for x, w in v.items()}
        out[key] = v
    return out


@pytest.mark.parametrize("name,skater,series,stop", [
    ("laplace", laplace(1), gen_vectors.make_series(n=N, seed=12345), 530),
    ("laplace_k3", laplace(3), gen_vectors.make_series(n=300, seed=12345), 120),
    ("laplace_repeat", laplace(1), gen_vectors.make_repeat_series(n=300, seed=99), 150),
    ("granger", granger(1), gen_vectors.make_series(n=300, seed=12345), 150),
    ("garch_leaf", garch_leaf(k=1), gen_vectors.make_series(n=300, seed=12345), 150),
    ("bayes_ensemble_k2", bayesian_ensemble([ema(0.05, k=2), ema(0.2, k=2)], k=2),
     gen_vectors.make_series(n=200, seed=1), 100),
    ("pw_ensemble_k2", precision_weighted_ensemble([ema(0.05, k=2), ema(0.2, k=2)], k=2),
     gen_vectors.make_series(n=200, seed=1), 100),
    ("terminal_adaptive", terminal_leaf_ensemble(
        [ema(0.05, k=1), _c(T.difference())], k=1, depths=[0, 1], adaptive_temperature=True),
     gen_vectors.make_series(n=200, seed=1), 100),
], ids=lambda v: v if isinstance(v, str) else "")
def test_legacy_layouts_resume(name, skater, series, stop):
    state = None
    for y in series[:stop]:
        _, state = skater(y, state)
    legacy = _to_legacy(restore(state))
    for y in series[stop:stop + CONTINUE]:
        da, state = skater(y, state)
        db, legacy = skater(y, legacy)
        assert snap(da) == snap(db), f"{name}: predictive differs after legacy restore"
    # Migration is lazy: a phase copy is rewritten on its own next step, so the
    # states are compared once every copy has stepped.
    assert enc(state) == enc(legacy), f"{name}: state differs after legacy restore"


def test_legacy_zbank_and_periodicity_resume():
    series = gen_vectors.make_series(n=200, seed=3)
    f = zbank(k=1, sigmas=(0.03, 0.003), strides=(1, 2))
    st = None
    for y in series[:80]:
        _, st = f(y, st)
    legacy = restore(st)
    grid = [(sig, s) for sig in (0.03, 0.003) for s in (1, 2)]
    legacy["sub"] = {g: _to_legacy(copies) for g, copies in zip(grid, legacy["sub"])}
    for y in series[80:100]:
        da, st = f(y, st)
        db, legacy = f(y, legacy)
        assert snap(da) == snap(db)
    assert enc(st) == enc(legacy)

    p = period_detector()
    st = None
    for y in series[:80]:
        _, st = p(y, st)
    legacy = _to_legacy(restore(st))
    assert all(isinstance(key, int) for key in legacy["cross"])
    for y in series[80:120]:
        sa, st = p(y, st)
        sb, legacy = p(y, legacy)
        assert sa == sb and enc(st) == enc(legacy)


def test_legacy_search_resumes():
    """A pre-canonical search checkpoint held closures in its pool, a set of
    detected periods, a transform table and deques. It must still resume."""
    from skaters.search import TRANSFORMS, _build_from_recipe
    from skaters.transform import seasonal_difference
    series = [v + 3.0 * ((t % 5) - 2) for t, v in enumerate(gen_vectors.make_series(n=260, seed=5))]
    f = search(k=1, expand_interval=50, max_pool=15)
    st = None
    for y in series[:210]:
        _, st = f(y, st)
    assert st["detected_periods"], "the series should show a period"
    legacy = restore(st)
    periods = legacy["detected_periods"]
    transforms = list(TRANSFORMS) + [(f"seas({p})", lambda p=p: seasonal_difference(p), 2) for p in periods]
    legacy["detected_periods"] = set(periods)
    legacy["transforms"] = transforms
    legacy["buffer"] = deque(legacy["buffer"], maxlen=500)
    for e in legacy["pool"]:
        e["f"] = _build_from_recipe(e["recipe"], 1, transforms)
        e["queues"] = [deque(q) for q in e["queues"]]
    g = search(k=1, expand_interval=50, max_pool=15)     # a fresh process
    for y in series[210:]:
        da, st = f(y, st)
        db, legacy = g(y, legacy)
        assert snap(da) == snap(db)
        assert enc(st) == enc(legacy)
