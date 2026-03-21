"""Fast univariate online time series models that run in Pyodide."""

from skaters.conventions import Skater
from skaters.ema import ema
from skaters.envelope import envelope
from skaters.ensemble import precision_weighted_ensemble
from skaters.api import (
    quickly, slowly, sluggishly, rapidly,
    ensemble, ensemble_with_envelope,
)

__all__ = [
    "Skater",
    "ema",
    "envelope",
    "precision_weighted_ensemble",
    "quickly",
    "slowly",
    "sluggishly",
    "rapidly",
    "ensemble",
    "ensemble_with_envelope",
]
