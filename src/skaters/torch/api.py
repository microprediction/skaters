"""The named forecasters in torch: ``laplace`` assembled exactly as
:mod:`skaters.api` assembles it, from the torch twins of its parts.

    laplace(k) = parade(gpdtails(multiscale(kk -> sticky(trunk(kk)))))

with ``trunk`` the likelihood-weighted candidate pool over the torch leaf
(:mod:`skaters.torch.pool`), ``sticky`` the lattice projection, ``gpdtails``
the tail splice and ``parade`` the PIT/z reader. Held to the reference by
``parity/check_torch.py`` on the standard vectors (``pol_laplace``,
``pol_laplace_k3``, the gap scenarios), so a learned model initialised here
is laplace by the same check the other ports pass.
"""

from __future__ import annotations

from functools import partial


def _objective_leaf(objective: str, scale_alpha: float = 0.03):
    from skaters.torch.leaf import crps_leaf, scale_mixture_leaf
    if objective == "crps":
        return partial(crps_leaf, scale_alpha=scale_alpha)
    if objective == "likelihood":
        return partial(scale_mixture_leaf, scale_alpha=scale_alpha)
    raise ValueError(f"objective must be 'crps' or 'likelihood', got {objective!r}")


def laplace_single_scale(k, objective="crps", sticky=True, leaf=None, scale_alpha=0.03):
    """Torch twin of ``api._laplace_single_scale``: the trunk at one clock,
    with the lattice projection when ``sticky``."""
    from skaters.torch.leaf import leaf as torch_leaf
    from skaters.torch.pool import build_pool
    from skaters.torch.trunk import TerminalLeafEnsemble
    skaters, depths, modules = build_pool(k, leaf_fn=torch_leaf)
    f = TerminalLeafEnsemble(
        skaters, k=k,
        leaf_fn=leaf if leaf is not None else _objective_leaf(objective, scale_alpha),
        learning_rate=0.8, complexity_penalty=0.005, depths=depths, max_components=20, forget=0.99)
    f.candidate_modules = modules
    if sticky:
        from skaters.torch.sticky import sticky as _project
        f = _project(f, k=k)
    return f


def laplace(k: int = 1, objective: str = "crps", sticky: bool = True, leaf=None,
            scales=None, scale_alpha: float = 0.03, tails: str = "gpd"):
    """The torch ``laplace``; same signature and defaults as the reference."""
    from skaters.torch.multiscale import multiscale
    from skaters.torch.parade import parade as _parade
    assert tails in ("gpd", "gaussian")
    f = multiscale(lambda kk: laplace_single_scale(kk, objective, sticky, leaf, scale_alpha),
                   k, scales=scales)
    if tails == "gpd":
        from skaters.torch.tails import gpdtails as _gpdtails
        f = _gpdtails(f, k=k)
    f = _parade(f, k=k)
    return f


def dantzig(k: int = 1, **kwargs):
    from skaters.torch.search import search
    return search(k=k, **kwargs)
