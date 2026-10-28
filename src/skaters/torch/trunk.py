"""The trunk in torch: :func:`skaters.terminal.terminal_leaf_ensemble` with
tensor weights and tensor means, so a log score at the output differentiates
through the mixing weights into every candidate's transform parameters.

Same arithmetic as the reference: each candidate's one-step predictive is
queued and scored against the next observation (log density clamped to
[-20, 20]); log-evidence accumulates with ``forget`` and ``learning_rate``
less a depth penalty; weights are the softmax of the accumulated evidence;
the combined mean per horizon is the weighted mean of candidate means; the
residual of the combined mean issued h+1 steps earlier updates a terminal
leaf (the reference ``crps_leaf``, a constant in the graph); the output is
that leaf's predictive shifted by the combined mean. During warm-up, before
the leaf has a residual, the candidate mixture is issued, as in the
reference.

Two things are deliberately not learnable in this pass: the terminal leaf
and the lattice/tail wrappers, which stay in the reference (``laplace`` is
``multiscale(_laplace_single_scale)`` plus ``_project`` and ``_gpdtails``;
this module is the ``terminal_leaf_ensemble`` inside, at one scale).
``learning_rate``, ``forget`` and ``complexity_penalty`` are parameters so
the mixing policy itself can be trained; ``prior_log_weights`` likewise.
"""

from __future__ import annotations

import math
from collections import deque

import torch
from torch import nn

from skaters.leaf import crps_leaf
from skaters.torch.dist import TorchDist, DTYPE, _t

_LOGPDF_LO, _LOGPDF_HI = -20.0, 20.0


def _clamp_lp(lp):
    """Reference: lp > 20 -> 20; not (lp >= -20) (incl. NaN) -> -20."""
    if bool(lp > _LOGPDF_HI):
        return torch.as_tensor(_LOGPDF_HI, dtype=DTYPE)
    if not bool(lp >= _LOGPDF_LO):
        return torch.as_tensor(_LOGPDF_LO, dtype=DTYPE)
    return lp


class TerminalLeafEnsemble(nn.Module):
    """Likelihood-weighted mean trunk with a terminal reference leaf."""

    def __init__(self, skaters, k: int = 1, leaf_fn=crps_leaf, learning_rate: float = 0.5,
                 complexity_penalty: float = 0.0, depths=None, prior_log_weights=None,
                 max_components: int = 20, forget: float = 1.0):
        super().__init__()
        n = len(skaters)
        assert n > 0
        self.skaters = list(skaters)
        self.k = k
        self.leaf_fn = leaf_fn
        self.n = n
        self.depths = list(depths) if depths is not None else [0] * n
        self.max_components = max_components
        self.learning_rate = nn.Parameter(torch.as_tensor(float(learning_rate), dtype=DTYPE))
        self.complexity_penalty = nn.Parameter(torch.as_tensor(float(complexity_penalty), dtype=DTYPE))
        self.forget = nn.Parameter(torch.as_tensor(float(forget), dtype=DTYPE))
        prior = prior_log_weights if prior_log_weights is not None else [0.0] * n
        self.prior_log_weights = nn.Parameter(torch.as_tensor([float(p) for p in prior], dtype=DTYPE))
        # one reference terminal leaf per horizon; closures live here, not in state
        self.tleafs = [leaf_fn(k=1) for _ in range(k)]

    def forward(self, y, state=None):
        y = _t(y)
        n, k = self.n, self.k
        if state is None:
            state = {
                "sub": [None] * n,
                "qdist": [deque() for _ in range(n)],
                "log_w": [self.prior_log_weights[i] for i in range(n)],
                "leaf_state": [None] * k,
                "leaf_pred": [None] * k,
                "mean_q": [deque() for _ in range(k)],
            }
        all_dists = []
        for i, f in enumerate(self.skaters):
            di, state["sub"][i] = f(y, state["sub"][i])
            all_dists.append(di)

        # weight update from the resolved one-step predictive
        log_w = list(state["log_w"])
        for i in range(n):
            q = state["qdist"][i]
            if q:
                lp = _clamp_lp(q.popleft().logpdf(y))
                log_w[i] = (self.forget * log_w[i] + self.learning_rate * lp
                            - self.complexity_penalty * self.depths[i])
            q.append(all_dists[i][0])
        state["log_w"] = log_w
        lw = torch.stack([_t(v).reshape(()) for v in log_w])
        max_lw = torch.max(lw)
        w = torch.exp(lw - max_lw)
        tot = torch.sum(w)

        combined = []
        for h in range(k):
            means = torch.stack([all_dists[i][h].mean.reshape(()) for i in range(n)])
            mu_h = torch.sum(w * means) / tot
            mq = state["mean_q"][h]
            if len(mq) >= h + 1:
                r = float(y.detach()) - float(mq.popleft().detach())     # leaf sees a constant residual
                ld, state["leaf_state"][h] = self.tleafs[h](r, state["leaf_state"][h])
                state["leaf_pred"][h] = ld[0]
            if state["leaf_pred"][h] is not None:
                pred = TorchDist.from_reference(state["leaf_pred"][h]).shift(mu_h)
            else:
                pred = TorchDist.combine([all_dists[i][h] for i in range(n)], w)
                if len(pred) > self.max_components:
                    pred = _prune(pred, self.max_components)
            combined.append(pred)
            mq.append(mu_h)
        return combined, state


def _prune(d: TorchDist, max_components: int) -> TorchDist:
    """Warm-up only: prune through the reference (no gradient through the
    merge path), keeping weights/means/stds as the reference computes them."""
    return TorchDist.from_reference(d.to_reference().prune(max_components))
