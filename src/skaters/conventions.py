"""Skater convention: an online univariate model is a callable:

    dists, state = f(y, state)

where:
    y:      float             - new observation
    state:  dict | None       - prior state (None on first call)
    dists:  list[Dist]        - distributional forecasts for horizons 1..k
    state:  dict              - updated state (pass back next call)

Every skater returns full distributional predictions. Point forecasts
are just dist.mean. Uncertainty is dist.std or dist.quantile().
Log-likelihood is dist.logpdf(y_actual).

A skater is always a tree of transforms with a distributional leaf
at the bottom. The leaf estimates the residual distribution; the
transforms propagate it back to the original space.
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable
from skaters.dist import Dist


@runtime_checkable
class Skater(Protocol):
    def __call__(self, y: float, state: dict | None) -> tuple[list[Dist], dict]:
        ...
