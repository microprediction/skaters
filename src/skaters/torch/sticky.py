"""Lattice projection in torch: the twin of :func:`skaters.sticky.sticky`.

The recency-weighted value table is plain float data, exactly as in the
reference (its arithmetic is independent of any tensor), so atom weights,
threshold and mass cap are computed with the same Python floats and the
same builtin ``sum``. The body enters through its tensor moments: the
recentering shift ``delta = P (mu - atom_mean) / (1 - P)`` and the spike
width ``spike_frac * std`` carry gradients into the base predictive. Lattice
atoms are the same near-Dirac Gaussians the reference emits.
"""

from __future__ import annotations

import torch
from torch import nn

from skaters.torch.dist import TorchDist, DTYPE, _t


class Sticky(nn.Module):
    """Wrap a torch skater with mean-preserving lattice atoms."""

    def __init__(self, base, k: int = 1, propensity_alpha: float = 0.05,
                 spike_frac: float = 0.005, thresh_mult: float = 1.8,
                 max_atoms: int = 6, prune_eps: float = 1e-6):
        super().__init__()
        self.base = base
        self.k = k
        self.propensity_alpha = float(propensity_alpha)
        self.spike_frac = float(spike_frac)
        self.thresh_mult = float(thresh_mult)
        self.max_atoms = int(max_atoms)
        self.prune_eps = float(prune_eps)

    def forward(self, y, state=None):
        yt = _t(y)
        yv = float(yt.detach())                       # the exact value, as the table key
        if state is None:
            state = {"base": None, "counts": {}}

        dists, state["base"] = self.base(yt, state["base"])

        c = state["counts"]
        a = self.propensity_alpha
        for key in list(c):
            c[key] *= (1.0 - a)
            if c[key] < self.prune_eps:
                del c[key]
        c[yv] = c.get(yv, 0.0) + a

        thr = self.thresh_mult * a
        atoms = sorted(((v, w) for v, w in c.items() if w > thr),
                       key=lambda t: -t[1])[:self.max_atoms]

        out = []
        for d in dists:
            if not atoms:
                out.append(d)
                continue
            sw = sum(w for _, w in atoms)
            P = min(sw, 0.999)
            pc = 1.0 - P
            atom_mean = sum(w * v for v, w in atoms) / sw
            spike_std = torch.clamp(self.spike_frac * d.std, min=1e-9)
            n_at = len(atoms)
            if pc <= 1e-9:
                w_at = torch.as_tensor([w / sw for _, w in atoms], dtype=DTYPE)
                m_at = torch.as_tensor([v for v, _ in atoms], dtype=DTYPE)
                out.append(TorchDist(w_at, m_at, spike_std.expand(n_at)))
                continue
            mu = d.mean
            delta = P * (mu - atom_mean) / pc
            w_at = torch.as_tensor([P * (w / sw) for _, w in atoms], dtype=DTYPE)
            m_at = torch.as_tensor([v for v, _ in atoms], dtype=DTYPE)
            out.append(TorchDist(torch.cat([w_at, pc * d.w]),
                                 torch.cat([m_at, d.m + delta]),
                                 torch.cat([spike_std.expand(n_at), d.s])))
        return out, state


def sticky(base, k: int = 1, **kwargs) -> Sticky:
    """Factory with the reference's name and signature."""
    return Sticky(base, k=k, **kwargs)
