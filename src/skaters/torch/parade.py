"""The prediction parade in torch: the twin of :func:`skaters.parade.parade`.

Pass-through for the forecasts, bookkeeping for the PIT and z of each
matured predictive, and the reference's missing-observation contract: a
non-finite tick never reaches the base, the fan is shifted by one horizon,
and a leading gap emits the wide no-information Gaussian. The PIT and z are
diagnostics and are stored as floats, computed as the reference computes
them (the z through the standard-normal quantile's bisection). The
magnitude gate on the fed observation is applied with tensor ops so it is
the exact identity on ordinary data and keeps the graph.
"""

from __future__ import annotations

import math
from collections import deque

import torch
from torch import nn

from skaters.torch.dist import TorchDist, DTYPE, _t

_STD_NORMAL = TorchDist.gaussian(0.0, 1.0)
_EPS = 1e-12
_NO_INFO_STD = 1e6


def _missing(y) -> bool:
    try:
        return not math.isfinite(float(y))
    except (TypeError, ValueError):
        return True


class Parade(nn.Module):
    """Wrap a k-horizon torch skater with PIT/z bookkeeping."""

    def __init__(self, base, k: int):
        super().__init__()
        self.base = base
        self.k = k

    def forward(self, y, state=None):
        k = self.k
        if state is None:
            state = {"base": None, "pending": deque(maxlen=k),
                     "pit": [None] * k, "z": [None] * k, "skipped": 0}
        pend = state["pending"]
        n = len(pend)
        if _missing(y):
            state["skipped"] = state.get("skipped", 0) + 1
            state["pit"] = [None] * k
            state["z"] = [None] * k
            if not n:
                return [TorchDist.gaussian(0.0, _NO_INFO_STD) for _ in range(k)], state
            prev = pend[-1]
            shifted = [prev[min(h, len(prev) - 1)] for h in range(1, k + 1)]
            pend.append(shifted)
            return shifted, state
        yt = _t(y)
        yv = float(yt.detach())
        pit = [None] * k
        z = [None] * k
        for m in range(1, k + 1):
            if m <= n:
                d = pend[n - m][m - 1]
                u = float(d.cdf(yv))
                if not math.isfinite(u):
                    continue
                u = min(max(u, _EPS), 1.0 - _EPS)
                pit[m - 1] = u
                z[m - 1] = float(_STD_NORMAL.quantile(u))
        y_fed = yt
        if math.isfinite(yv):
            y_fed = torch.clamp(y_fed, -1e60, 1e60)
            if n:
                d1 = pend[-1][0]
                d1 = getattr(d1, "body", d1)
                mp, sp = d1.mean, d1.std
                if math.isfinite(float(mp)) and math.isfinite(float(sp)):
                    w = 1e12 * (1.0 + torch.abs(mp) + sp)
                    y_fed = torch.minimum(torch.maximum(y_fed, mp - w), mp + w)
        dists, state["base"] = self.base(y_fed, state["base"])
        pend.append(list(dists))
        state["pit"] = pit
        state["z"] = z
        return dists, state


def parade(base, k: int) -> Parade:
    """Factory with the reference's name and signature."""
    return Parade(base, k)
