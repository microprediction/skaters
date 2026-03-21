"""Skater convention: an online univariate model is a callable:

    x, state = f(y, state)

where:
    y:     float             - new observation
    state: dict | None       - prior state (None on first call)
    x:     list[float]       - point forecasts for horizons 1..k
    state: dict              - updated state (pass back next call)

Skaters only predict. Uncertainty estimation is handled separately
by the Envelope (see envelope.py), which wraps any skater and tracks
empirical forecast errors per horizon.
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class Skater(Protocol):
    def __call__(self, y: float, state: dict | None) -> tuple[list[float], dict]:
        ...
