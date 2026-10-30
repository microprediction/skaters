"""Multi-scale ensemble in torch: the twin of
:func:`skaters.multiscale.multiscale`, ported as the reference stands today
(including the ``round(h/s)`` coarse-step selection that issue #197
discusses), because agreement with the reference is the point.

``s`` phase-shifted copies of the base skater per decimation stride, one
advanced per tick; each stride's one-coarse-step predictive is scored at
its maturity into an EWMA log score (floored at -20) that sets the stride's
softmax weight; fine horizon ``h`` mixes the eligible strides' coarse
predictives at step ``round(h/s)``. ``forget`` is a parameter; the scores
and weights are tensors. With a single scale the base skater is returned
unwrapped, as in the reference.
"""

from __future__ import annotations

import math

import torch
from torch import nn

from skaters.torch.dist import TorchDist, DTYPE, _t


def _clamp_lp(lp):
    """Reference: lp > 20 -> 20; not (lp >= -20) (incl. NaN) -> -20."""
    if bool(lp > 20.0):
        return torch.as_tensor(20.0, dtype=DTYPE)
    if not bool(lp >= -20.0):
        return torch.as_tensor(-20.0, dtype=DTYPE)
    return lp


def _prune(d, max_components):
    """Prune through the reference merge (no gradient along the merge path)."""
    return TorchDist.from_reference(d.to_reference().prune(max_components))

_LOGPDF_FLOOR = -20.0


class Multiscale(nn.Module):
    def __init__(self, base, k: int, scales, forget: float = 0.99, max_components: int = 20):
        super().__init__()
        self.k = k
        self.scales = scales
        self.forget = nn.Parameter(torch.as_tensor(float(forget), dtype=DTYPE))
        self.max_components = max_components
        self.subs = {s: base(max(1, math.ceil(k / s))) for s in scales}

    def forward(self, y, state=None):
        y = _t(y)
        k, scales = self.k, self.scales
        if state is None:
            state = {
                "t": 0,
                "phase": {s: [None] * s for s in scales},
                "pending": {s: [None] * s for s in scales},
                "latest": {},
                "score": {s: None for s in scales},
            }
        t = state["t"]
        for s in scales:
            ph = t % s
            prev = state["pending"][s][ph]
            if prev is not None:
                lp = prev.logpdf(y)
                if not bool(lp > _LOGPDF_FLOOR):
                    lp = torch.as_tensor(_LOGPDF_FLOOR, dtype=DTYPE)
                m = state["score"][s]
                state["score"][s] = lp if m is None else self.forget * m + (1.0 - self.forget) * lp
            dists, state["phase"][s][ph] = self.subs[s](y, state["phase"][s][ph])
            state["pending"][s][ph] = dists[0]
            state["latest"][s] = dists
        state["t"] = t + 1

        scores = state["score"]
        live = [m for m in scores.values() if m is not None]
        if live:
            top = live[0]
            for m in live[1:]:
                top = torch.maximum(top, m)
        else:
            top = torch.zeros((), dtype=DTYPE)
        out = []
        for h in range(1, k + 1):
            fcs, wts = [], []
            for s in scales:
                if s > h or s not in state["latest"]:
                    continue
                j = max(1, int(h / s + 0.5))
                dists = state["latest"][s]
                if j - 1 >= len(dists):
                    continue
                fcs.append(dists[j - 1])
                m = scores[s]
                wts.append(torch.exp((m if m is not None else top) - top))
            if len(fcs) == 1:
                out.append(fcs[0])
            else:
                d = TorchDist.combine(fcs, wts)
                out.append(_prune(d, self.max_components) if len(d) > self.max_components else d)
        return out, state


def multiscale(base, k: int, scales=None, forget: float = 0.99, max_components: int = 20):
    """Wrap a base factory ``base(k) -> torch skater`` in the multi-scale
    ensemble; with ``scales == [1]`` the base skater is returned unwrapped."""
    if scales is None:
        scales = sorted({1, math.ceil(math.sqrt(k)), k})
    scales = sorted({int(s) for s in scales if 1 <= s <= k})
    assert scales and scales[0] == 1, "scales must include 1"
    if scales == [1]:
        return base(k)
    return Multiscale(base, k, scales, forget=forget, max_components=max_components)
