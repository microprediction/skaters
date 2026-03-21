"""Convenience constructors for common skater configurations."""

from __future__ import annotations
from skaters.ema import ema
from skaters.ensemble import precision_weighted_ensemble
from skaters.envelope import envelope
from skaters.calibrated import calibrated_envelope


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


def ensemble_with_envelope(k: int = 1, decay: float | None = None):
    """Precision-weighted ensemble wrapped with an empirical error envelope."""
    return envelope(ensemble(k=k), k=k, decay=decay)


def ensemble_calibrated(k: int = 1, target: float = 0.6827):
    """Precision-weighted ensemble with self-calibrating uncertainty bands.

    This is the recommended default — good predictions with ±1σ bands
    that auto-tune to match the target coverage probability.
    """
    return calibrated_envelope(ensemble(k=k), k=k, target=target)
