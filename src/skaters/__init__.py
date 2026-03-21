"""Fast univariate online time series models that run in Pyodide."""

from skaters.conventions import Skater
from skaters.ema import ema
from skaters.envelope import envelope
from skaters.calibrated import calibrated_envelope
from skaters.ensemble import precision_weighted_ensemble
from skaters.conjugate import conjugate
from skaters.transform import difference, fractional_difference, standardize
from skaters.spec import (
    build, name as spec_name, to_json, from_json,
    ema_spec, ensemble_spec, conjugate_spec, envelope_spec, calibrated_spec,
    diff_spec, frac_spec, std_spec,
)
from skaters.api import (
    quickly, slowly, sluggishly, rapidly,
    ensemble, ensemble_with_envelope, ensemble_calibrated,
)

__all__ = [
    "Skater",
    "ema",
    "envelope",
    "calibrated_envelope",
    "precision_weighted_ensemble",
    "conjugate",
    "difference",
    "fractional_difference",
    "standardize",
    "quickly",
    "slowly",
    "sluggishly",
    "rapidly",
    "ensemble",
    "ensemble_with_envelope",
    "ensemble_calibrated",
    "build",
    "spec_name",
    "to_json",
    "from_json",
    "ema_spec",
    "ensemble_spec",
    "conjugate_spec",
    "envelope_spec",
    "calibrated_spec",
    "diff_spec",
    "frac_spec",
    "std_spec",
]
