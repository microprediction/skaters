"""Fast univariate online time series models that run in Pyodide.

Every skater returns distributional predictions (list[Dist]).
Point forecasts: dist.mean. Uncertainty: dist.std or dist.quantile().
Log-likelihood: dist.logpdf(y_actual).
"""

from skaters.dist import Dist
from skaters.conventions import Skater
from skaters.leaf import leaf
from skaters.ema import ema
from skaters.ensemble import precision_weighted_ensemble
from skaters.bayesian import bayesian_ensemble
from skaters.conjugate import conjugate
from skaters.transform import (
    difference, fractional_difference, standardize, ema_transform,
    garch, seasonal_difference, power_transform, ar, grouped_ar, drift, holt_linear, theta,
)
from skaters.search import search
from skaters.periodicity import period_detector, top_periods
from skaters.api import skater, holt, hosking, laplace, samuelson, wald, dantzig
from skaters.spec import (
    build, name as spec_name, to_json, from_json,
    ema_spec, ensemble_spec, conjugate_spec,
    diff_spec, frac_spec, std_spec,
)

__all__ = [
    # Types
    "Dist",
    "Skater",
    # Search policies (the main user API)
    "skater",
    "holt",
    "hosking",
    "laplace",
    "samuelson",
    "wald",
    "dantzig",
    "period_detector",
    "top_periods",
    # Building blocks
    "leaf",
    "ema",
    "conjugate",
    "difference",
    "fractional_difference",
    "standardize",
    "ema_transform",
    "garch",
    "seasonal_difference",
    "power_transform",
    "ar",
    "grouped_ar",
    "drift",
    "holt_linear",
    "theta",
    # Ensembles and search
    "precision_weighted_ensemble",
    "bayesian_ensemble",
    "search",
    # Spec system
    "build",
    "spec_name",
    "to_json",
    "from_json",
    "ema_spec",
    "ensemble_spec",
    "conjugate_spec",
    "diff_spec",
    "frac_spec",
    "std_spec",
]
