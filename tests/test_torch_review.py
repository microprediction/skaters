"""Regression tests for the #302 review findings: gradients survive pruning at
every horizon, sub-modules are visible to ``parameters()``, a deepcopy of the
search state keeps pointing at the live transform modules, the weight
recursion keeps a bounded graph, and the tensor prune follows the reference's
merge path. Skipped where torch is absent."""
import copy
import math
import random

import pytest

torch = pytest.importorskip("torch")

from skaters.dist import Dist                                   # noqa: E402
from skaters.ema import ema                                     # noqa: E402
from skaters.torch import laplace, TorchDist                    # noqa: E402
from skaters.torch.ema import ema as torch_ema                  # noqa: E402
from skaters.torch.ensemble import precision_weighted_ensemble  # noqa: E402
from skaters.torch.bayesian import bayesian_ensemble            # noqa: E402
from skaters.torch.multiscale import multiscale                 # noqa: E402
from skaters.torch.search import search                         # noqa: E402

SERIES = [0.2, 0.8, -0.3, 0.4, 1.1, 0.1, -0.5, 0.9, 0.3, -0.2, 0.6, 0.0]


def test_laplace_k3_every_horizon_keeps_a_gradient_path():
    """The reviewer's reproduction: after the 20-component pruning cap the
    later horizons used to come back detached."""
    f = laplace(k=3)
    state = None
    for y in SERIES:
        dists, state = f(y, state)
    flags = [bool(d.logpdf(0.6).requires_grad) for d in dists]
    assert flags == [True, True, True], flags
    loss = -sum(d.logpdf(0.6) for d in dists)
    loss.backward()
    grads = [p.grad for p in f.parameters() if p.grad is not None]
    assert grads and all(bool(torch.isfinite(g).all()) for g in grads)


def test_laplace_parameters_include_the_transform_modules():
    f = laplace(k=1)
    names = [n for n, _ in f.named_parameters()]
    assert any("candidate_modules" in n for n in names), names[:10]
    assert len(names) > 10, len(names)


def test_ensemble_wrappers_register_module_sub_skaters():
    e1, e2 = torch_ema(0.05, k=1), torch_ema(0.2, k=1)
    p1, p2 = next(e1.parameters()), next(e2.parameters())
    pw = precision_weighted_ensemble([e1, e2], k=1)
    assert any(p is p1 for p in pw.parameters())
    be = bayesian_ensemble([e1, e2], k=1)
    assert any(p is p2 for p in be.parameters())
    ms = multiscale(lambda kk: torch_ema(0.1, k=kk), k=2, scales=(1, 2))
    subs = [m for m in ms.sub_modules.values()]
    assert subs and all(any(p is q for q in ms.parameters()) for m in subs for p in m.parameters())


def test_search_state_deepcopy_shares_the_live_modules():
    f = search(k=1)
    state = None
    with torch.no_grad():              # the restore leg runs under no_grad, as the parity checker does
        for y in SERIES:
            _, state = f(y, state)
    copied = copy.deepcopy(state)
    for a, b in zip(state["pool"], copied["pool"]):
        assert a["mods"] is b["mods"]
        for m1, m2 in zip(a["mods"], b["mods"]):
            assert m1 is m2


def test_search_log_weights_do_not_accumulate_the_graph():
    """With the carried term detached, a log weight's graph depends on the
    latest step only: its value has no grad_fn chain into earlier steps."""
    f = search(k=1)
    state = None
    for y in SERIES:
        _, state = f(y, state)
    lw = state["pool"][0]["log_w"][0]
    if lw.requires_grad:
        # walking the graph from this tensor must not reach more than one logpdf
        seen, frontier, depth = set(), [lw.grad_fn], 0
        while frontier and depth < 200:
            nxt = []
            for fn in frontier:
                if fn is None or fn in seen:
                    continue
                seen.add(fn)
                nxt.extend(nf for nf, _ in fn.next_functions)
            frontier, depth = nxt, depth + 1
        assert depth < 200, "autograd graph of a log weight spans the whole stream"


def test_torch_prune_matches_the_reference_merge_path():
    rng = random.Random(7)
    for _ in range(20):
        n = rng.randint(21, 40)
        comps = [(rng.random() + 1e-3, rng.gauss(0, 1), 0.1 + rng.random()) for _ in range(n)]
        ref = Dist(comps).prune(20)
        tor = TorchDist.from_components(comps).prune(20)
        assert len(ref.components) == len(tor) == 20
        for (w1, m1, s1), (w2, m2, s2) in zip(ref.components, tor.to_reference().components):
            assert math.isclose(w1, w2, rel_tol=0, abs_tol=1e-12)
            assert math.isclose(m1, m2, rel_tol=0, abs_tol=1e-12)
            assert math.isclose(s1, s2, rel_tol=0, abs_tol=1e-12)


def test_torch_prune_keeps_gradients_through_merged_components():
    m = torch.nn.Parameter(torch.linspace(-1.0, 1.0, 25, dtype=torch.float64))
    d = TorchDist(torch.ones(25, dtype=torch.float64) / 25, m, torch.full((25,), 0.3, dtype=torch.float64))
    pruned = d.prune(20)
    lp = pruned.logpdf(0.1)
    assert lp.requires_grad
    lp.backward()
    assert m.grad is not None and bool(torch.isfinite(m.grad).all()) and float(m.grad.abs().sum()) > 0
