"""laplace's candidate pool, rebuilt in torch.

:func:`pool_spec` lists the pool of :func:`skaters.api._build_candidates` as
transform chains (outer first) with depths, in the reference's order;
:func:`build_pool` instantiates it as torch conjugations over the reference
leaf; :func:`laplace_single_scale` is the torch twin of
``api._laplace_single_scale(k, "crps", sticky=False, None, scale_alpha)``:
the trunk at one scale, without the lattice projection and the tail splice
(those wrappers stay in the reference for now).

At the reference's parameter values the twin reproduces the reference to
float64 round-off; see ``tests/test_torch_trunk.py``.
"""

from __future__ import annotations

from functools import partial

from skaters.leaf import leaf as reference_leaf, crps_leaf
from skaters.torch.conjugate import conjugate, reference_skater
from skaters.torch.transform import from_reference
from skaters.torch.trunk import TerminalLeafEnsemble


def pool_spec(k: int = 1):
    """``[(chain, depth), ...]``; a chain is ``[(name, kwargs), ...]`` outer first."""
    spec = [([], 0)]
    for a in (0.01, 0.05, 0.1, 0.3):
        spec.append(([("ema_transform", {"alpha": a})], 1))
    spec.append(([("difference", {})], 1))
    for a, s in ((0.05, 0.01), (0.01, 0.002), (0.002, 0.001), (0.0005, 0.0002)):
        spec.append(([("drift", {"alpha": a, "shrinkage": s})], 1))
    for a in (0.05, 0.1, 0.3):
        spec.append(([("theta", {"alpha": a})], 1))
    spec.append(([("ar", {"order": 1})], 1))
    spec.append(([("ar", {"order": 2, "decay": 1})], 1))
    for a, b in ((0.1, 0.02), (0.1, 0.05), (0.3, 0.1)):
        spec.append(([("holt_linear", {"alpha": a, "beta": b})], 1))
    for p in (7, 12, 24):
        spec.append(([("seasonal_difference", {"period": p})], 1))
    for p in (7, 12, 24):
        spec.append(([("seasonal_anchor", {"period": p})], 1))
    for p in (7, 12, 24):
        for a in (0.05, 0.1):
            spec.append(([("seasonal_difference", {"period": p}), ("ema_transform", {"alpha": a})], 2))
    for a in (0.05, 0.1, 0.3):
        spec.append(([("difference", {}), ("ema_transform", {"alpha": a})], 2))
    for a in (0.05, 0.1):
        spec.append(([("standardize", {}), ("ema_transform", {"alpha": a})], 2))
    for d in (0.2, 0.4):
        spec.append(([("fractional_difference", {"d": d, "window": 30}), ("ema_transform", {"alpha": 0.1})], 2))
    for ad, sd in ((0.002, 0.001), (0.0005, 0.0002)):
        for ae in (0.05, 0.1):
            spec.append(([("drift", {"alpha": ad, "shrinkage": sd}), ("ema_transform", {"alpha": ae})], 2))
    spec.append(([("drift", {"alpha": 0.001, "shrinkage": 0.0005}), ("holt_linear", {"alpha": 0.1, "beta": 0.05})], 2))
    spec.append(([("garch", {}), ("ema_transform", {"alpha": 0.1})], 2))
    spec.append(([("power_transform", {"p": 0.5}), ("ema_transform", {"alpha": 0.1})], 2))
    trackers = [("ema_transform", {"alpha": 0.3}), ("ema_transform", {"alpha": 0.5}),
                ("holt_linear", {"alpha": 0.4, "beta": 0.2}), ("ar", {"order": 1}),
                ("drift", {"alpha": 0.05, "shrinkage": 0.01}), ("difference", {})]
    for scale_alpha in (0.02, 0.05):
        for tracker in trackers:
            spec.append(([tracker, ("standardize", {"alpha": scale_alpha})], 2))
    for L in (0.0, 0.5):
        for inner in (("difference", {}), ("ema_transform", {"alpha": 0.1})):
            spec.append(([("yeo_johnson", {"lmbda": L}), inner], 2))
    if k > 1:
        for L in (0.0, 0.5):
            for kappa in (0.03, 0.1, 0.3):
                spec.append(([("yeo_johnson", {"lmbda": L}), ("ou_transform", {"kappa": kappa, "alpha": 0.02})], 2))
    return spec


def build_candidate(chain, k: int, leaf_fn=reference_leaf):
    """A torch conjugation chain over the reference leaf; returns the skater
    and the list of transform modules (outer first) for parameter access."""
    inner = leaf_fn(k=k)
    # a torch leaf (nn.Module) is used as is; a reference leaf is adapted
    from torch import nn
    f = inner if isinstance(inner, nn.Module) else reference_skater(inner)
    mods = []
    for name, kw in reversed(chain):            # inner first
        m = from_reference(name, **kw)
        mods.insert(0, m)
        f = conjugate(f, m, k=k)
    return f, mods


def build_pool(k: int = 1, leaf_fn=reference_leaf):
    """``(skaters, depths, modules)`` for laplace's pool at horizon ``k``."""
    skaters, depths, modules = [], [], []
    for chain, depth in pool_spec(k):
        f, mods = build_candidate(chain, k, leaf_fn)
        skaters.append(f); depths.append(depth); modules.append(mods)
    return skaters, depths, modules


def laplace_single_scale(k: int = 1, scale_alpha: float = 0.03):
    """Torch twin of ``api._laplace_single_scale(k, "crps", sticky=False, None, scale_alpha)``."""
    skaters, depths, modules = build_pool(k)
    trunk = TerminalLeafEnsemble(skaters, k=k, leaf_fn=partial(crps_leaf, scale_alpha=scale_alpha),
                                 learning_rate=0.8, complexity_penalty=0.005, depths=depths,
                                 max_components=20, forget=0.99)
    trunk.candidate_modules = modules
    return trunk
