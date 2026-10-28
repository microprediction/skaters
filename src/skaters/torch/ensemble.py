"""Precision-weighted ensemble in torch: the twin of
:func:`skaters.ensemble.precision_weighted_ensemble`.

Each sub-skater's point forecast (the mixture mean) is queued per horizon
and resolved against the observation it targeted; Welford running statistics
of the errors give a mean squared error per sub-model and horizon, and the
horizon's predictive is the exact mixture of the sub-predictives weighted by
``1 / max(mse, floor)`` (``floor`` while a sub-model is immature). Same
arithmetic as the reference; the error statistics are tensors, so a log
score at the output differentiates through the weights into the sub-models.
The running statistics of :mod:`skaters.runstats` are inlined here on
tensors (Welford's update, sample variance, ``mse = mean^2 + var``).
"""

from __future__ import annotations

from collections import deque

import torch
from torch import nn

from skaters.torch.dist import TorchDist, DTYPE, _t


def _running_var_init():
    return {"n": 0, "mean": torch.zeros((), dtype=DTYPE), "m2": torch.zeros((), dtype=DTYPE)}


def _running_var_update(state, x):
    n = state["n"] + 1
    delta = x - state["mean"]
    mean = state["mean"] + delta / n
    delta2 = x - mean
    m2 = state["m2"] + delta * delta2
    return {"n": n, "mean": mean, "m2": m2}


def _running_mse_get(state):
    """``mean^2 + var`` of the errors, or None while fewer than two have
    resolved (the reference returns inf there)."""
    if state["n"] < 2:
        return None
    var = state["m2"] / (state["n"] - 1)
    if not bool(torch.isfinite(var)):
        return None
    return state["mean"] * state["mean"] + var


class PrecisionWeightedEnsemble(nn.Module):
    def __init__(self, skaters, k: int = 1, floor: float = 1e-6):
        super().__init__()
        assert len(skaters) > 0
        self.skaters = list(skaters)
        self.n = len(skaters)
        self.k = k
        self.floor = nn.Parameter(torch.as_tensor(float(floor), dtype=DTYPE))

    def forward(self, y, state=None):
        y = _t(y)
        n, k = self.n, self.k
        if state is None:
            state = {
                "sub": [None] * n,
                "queues": [[deque() for _ in range(k)] for _ in range(n)],
                "stats": [[_running_var_init() for _ in range(k)] for _ in range(n)],
            }
        all_dists = []
        for i, f in enumerate(self.skaters):
            di, state["sub"][i] = f(y, state["sub"][i])
            all_dists.append(di)
        for i in range(n):
            for h in range(k):
                q = state["queues"][i][h]
                q.append(all_dists[i][h].mean)
                if len(q) > h + 1:
                    error = y - q.popleft()
                    state["stats"][i][h] = _running_var_update(state["stats"][i][h], error)
        combined = []
        for h in range(k):
            weights = []
            for i in range(n):
                mse = _running_mse_get(state["stats"][i][h])
                if mse is None:
                    weights.append(self.floor)
                else:
                    weights.append(1.0 / torch.maximum(mse, self.floor))
            combined.append(TorchDist.combine([all_dists[i][h] for i in range(n)], weights))
        return combined, state


def precision_weighted_ensemble(skaters, k: int = 1, floor: float = 1e-6) -> PrecisionWeightedEnsemble:
    return PrecisionWeightedEnsemble(skaters, k=k, floor=floor)
