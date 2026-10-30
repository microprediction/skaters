"""Bayesian model-averaging ensemble in torch: the twin of
:func:`skaters.bayesian.bayesian_ensemble`.

Per sub-model and horizon, the predictive issued h+1 steps ago is scored at
the current observation (log density clamped to [-20, 20]) and shrunk by
the learning rate less a depth penalty into a running log-weight; the
horizon's predictive is the softmax-weighted exact mixture, pruned to
``max_components``. Same arithmetic as the reference. ``learning_rate``,
``complexity_penalty`` and the prior log-weights are parameters; the
log-weights are tensors, so gradients reach the sub-models through both the
mixing weights and the scored predictives. Pruning goes through the
reference merge (no gradient along the merge path), as in the trunk.
"""

from __future__ import annotations

from collections import deque

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


class BayesianEnsemble(nn.Module):
    def __init__(self, skaters, k: int = 1, learning_rate: float = 0.5, complexity_penalty: float = 0.0,
                 depths=None, prior_log_weights=None, max_components: int = 20):
        super().__init__()
        n = len(skaters)
        assert n > 0
        assert 0 < learning_rate <= 1
        assert complexity_penalty >= 0
        self.skaters = list(skaters)
        self.n, self.k = n, k
        self.depths = list(depths) if depths is not None else [0] * n
        self.max_components = max_components
        self.learning_rate = nn.Parameter(torch.as_tensor(float(learning_rate), dtype=DTYPE))
        self.complexity_penalty = nn.Parameter(torch.as_tensor(float(complexity_penalty), dtype=DTYPE))
        prior = prior_log_weights if prior_log_weights is not None else [0.0] * n
        self.prior_log_weights = nn.Parameter(torch.as_tensor([float(p) for p in prior], dtype=DTYPE))

    def forward(self, y, state=None):
        y = _t(y)
        n, k = self.n, self.k
        if state is None:
            state = {
                "sub": [None] * n,
                "queues": [[deque() for _ in range(k)] for _ in range(n)],
                "log_w": [[self.prior_log_weights[i] for _ in range(k)] for i in range(n)],
                "n_obs": 0,
            }
        state["n_obs"] += 1
        all_dists = []
        for i, f in enumerate(self.skaters):
            di, state["sub"][i] = f(y, state["sub"][i])
            all_dists.append(di)
        for i in range(n):
            for h in range(k):
                q = state["queues"][i][h]
                q.append(all_dists[i][h])
                if len(q) > h + 1:
                    lp = _clamp_lp(q.popleft().logpdf(y))
                    state["log_w"][i][h] = (state["log_w"][i][h]
                                            + self.learning_rate * lp
                                            - self.complexity_penalty * self.depths[i])
        combined = []
        for h in range(k):
            lw = torch.stack([_t(state["log_w"][i][h]).reshape(()) for i in range(n)])
            max_lw = torch.max(lw)
            if bool(torch.isfinite(max_lw)):
                weights = torch.exp(lw - max_lw)
            else:
                weights = torch.ones(n, dtype=DTYPE)
            dist = TorchDist.combine([all_dists[i][h] for i in range(n)], weights)
            if len(dist) > self.max_components:
                dist = _prune(dist, self.max_components)
            combined.append(dist)
        return combined, state


def bayesian_ensemble(skaters, k: int = 1, learning_rate: float = 0.5, complexity_penalty: float = 0.0,
                      depths=None, prior_log_weights=None, max_components: int = 20) -> BayesianEnsemble:
    return BayesianEnsemble(skaters, k=k, learning_rate=learning_rate, complexity_penalty=complexity_penalty,
                            depths=depths, prior_log_weights=prior_log_weights, max_components=max_components)
