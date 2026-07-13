"""Tests for the multi-scale ensemble (default at k > 1 in laplace)."""

import math
import random
from skaters import laplace, multiscale
from skaters.dist import Dist


def _series(n=300, seed=11):
    random.seed(seed)
    return [math.sin(i / 9.0) * 0.3 + random.gauss(0, 0.1) for i in range(n)]


def test_k1_has_no_wrapper():
    """At k=1 the default scale set is {1}: laplace(1) is single-scale."""
    f, g = laplace(1), laplace(1, scales=[1])
    sf = sg = None
    for y in _series(120):
        df, sf = f(y, sf)
        dg, sg = g(y, sg)
    assert df[0].mean == dg[0].mean
    assert df[0].std == dg[0].std


def test_single_scale_opt_out():
    f = laplace(5, scales=[1])
    x, state = f(1.0, None)
    assert len(x) == 5
    assert "score" not in (state["base"] or {})   # no multi-scale bookkeeping


def test_default_scales_from_k():
    f = laplace(20)
    _, state = f(0.1, None)
    assert sorted(state["base"]["base"]["score"]) == [1, 5, 20]


def test_shapes_and_finiteness():
    f = laplace(20)
    state = None
    for y in _series():
        dists, state = f(y, state)
    assert len(dists) == 20
    for d in dists:
        assert isinstance(d, Dist)
        assert math.isfinite(d.mean)
        assert d.std > 0


def test_h1_matches_single_scale():
    """Horizon 1 is served only by scale 1, whose sub-model sees the raw stream."""
    f, g = laplace(20), laplace(20, scales=[1])
    sf = sg = None
    for y in _series(200):
        df, sf = f(y, sf)
        dg, sg = g(y, sg)
    assert abs(df[0].logpdf(0.05) - dg[0].logpdf(0.05)) < 1e-9


def test_scale_scores_populate():
    f = laplace(20)
    state = None
    for y in _series(150):
        _, state = f(y, state)
    # every scale has been scored (one phase copy steps per tick, so scoring
    # starts after s ticks for scale s)
    assert all(m is not None for m in state["base"]["base"]["score"].values())


def test_coarse_weight_rises_on_fine_noise():
    """A series that is pure noise at the fine scale but smooth at stride 5
    should shift likelihood weight toward the coarse scale relative to a
    series that is smooth at the fine scale."""
    random.seed(3)
    smooth = [math.sin(i / 30.0) for i in range(400)]
    noisy = [x + random.gauss(0, 1.0) for x in smooth]

    def gap(ys):
        f = laplace(5, scales=[1, 5])
        state = None
        for y in ys:
            _, state = f(y, state)
        return state["base"]["base"]["score"][1] - state["base"]["base"]["score"][5]

    assert gap(smooth) > gap(noisy)


def test_multiscale_wrapper_generic_base():
    """multiscale() also wraps arbitrary base factories."""
    from skaters import leaf, conjugate, ema_transform
    f = multiscale(lambda kk: conjugate(leaf(k=kk), ema_transform(0.1), k=kk), k=4)
    state = None
    for y in _series(60):
        dists, state = f(y, state)
    assert len(dists) == 4
