"""Convenience constructors for common skater configurations."""

from __future__ import annotations
from skaters.ema import ema
from skaters.ensemble import precision_weighted_ensemble


def rapidly(k: int = 1):
    """EMA with alpha=0.3 — reacts fast to changes."""
    return ema(alpha=0.3, k=k)


def quickly(k: int = 1):
    """EMA with alpha=0.1 — moderate reactivity."""
    return ema(alpha=0.1, k=k)


def slowly(k: int = 1):
    """EMA with alpha=0.05 — smooth, slow-moving."""
    return ema(alpha=0.05, k=k)


def sluggishly(k: int = 1):
    """EMA with alpha=0.01 — very slow adaptation."""
    return ema(alpha=0.01, k=k)


def ensemble(k: int = 1):
    """Precision-weighted ensemble of EMA models at different speeds."""
    return precision_weighted_ensemble(
        skaters=[rapidly(k), quickly(k), slowly(k), sluggishly(k)],
        k=k,
    )
