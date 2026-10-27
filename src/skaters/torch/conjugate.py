"""Conjugation in torch: wrap an inner skater in a torch transform, exactly as
:func:`skaters.conjugate.conjugate` wraps the reference closures.

    f = conjugate(inner, T, k)        # T a TorchTransform, inner a skater
    dists, state = f(y, state)        # list[TorchDist]

The inner skater may itself be a torch conjugation (stacking "all the way
down") or a reference skater such as :func:`skaters.leaf.leaf`, which
emits :class:`skaters.dist.Dist`; :func:`reference_skater` adapts the latter
so its outputs enter the torch graph as constants (the leaf is not
differentiated in this pass; the transforms around it are).
"""

from __future__ import annotations

from skaters.torch.dist import TorchDist, _t


def reference_skater(skater):
    """Adapt a reference skater ``(y, state) -> (list[Dist], state)`` so it
    takes a float or 0-d tensor and returns TorchDist constants."""
    def run(y, state=None):
        dists, state = skater(float(_t(y).detach()), state)
        return [TorchDist.from_reference(d) for d in dists], state
    run.__name__ = f"reference({getattr(skater, '__name__', '?')})"
    return run


def conjugate(skater, transform, k: int = 1):
    """Conjugate a skater with a torch transform (same contract as the
    reference ``conjugate``: forward, predict in the transformed space,
    invert the k predictives)."""
    def _conjugated(y, state=None):
        if state is None:
            state = {"t_state": None, "s_state": None}
        z, state["t_state"] = transform(y, state["t_state"])
        dists_z, state["s_state"] = skater(z, state["s_state"])
        assert len(dists_z) == k, (
            f"conjugate(k={k}) wraps a skater emitting {len(dists_z)} horizons")
        return transform.inverse_k(dists_z, state["t_state"]), state
    _conjugated.__name__ = f"conjugate({getattr(skater, '__name__', '?')})"
    return _conjugated
