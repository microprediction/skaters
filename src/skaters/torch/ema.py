"""The EMA skater in torch: the twin of :mod:`skaters.ema`,
``ema(alpha, k) = conjugate(leaf(k), ema_transform(alpha))``, as an
``nn.Module`` so ``alpha`` is a registered parameter."""

from __future__ import annotations

from torch import nn

from skaters.torch.conjugate import conjugate
from skaters.torch.leaf import Leaf
from skaters.torch.transform import EMA


class EmaSkater(nn.Module):
    def __init__(self, alpha: float = 0.05, k: int = 1):
        super().__init__()
        self.k = k
        self.transform = EMA(alpha)
        self.leaf = Leaf(k)
        self._f = conjugate(self.leaf, self.transform, k=k)

    def forward(self, y, state=None):
        return self._f(y, state)


def ema(alpha: float = 0.05, k: int = 1) -> EmaSkater:
    return EmaSkater(alpha, k)
