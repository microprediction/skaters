"""Fast univariate online time series models that run in Pyodide.

Every skater returns distributional predictions (list[Dist]).
Point forecasts: dist.mean. Uncertainty: dist.std or dist.quantile().
Log-likelihood: dist.logpdf(y_actual).
"""

from skaters.dist import Dist
from skaters.conventions import Skater
from skaters.leaf import leaf, scale_mixture_leaf, crps_leaf
from skaters.ema import ema
from skaters.terminal import terminal_leaf_ensemble
from skaters.ensemble import precision_weighted_ensemble
from skaters.bayesian import bayesian_ensemble
from skaters.conjugate import conjugate
from skaters.transform import (
    difference, fractional_difference, standardize, ema_transform, ou_transform,
    garch, seasonal_difference, power_transform, ar, grouped_ar, drift, holt_linear, theta,
    yeo_johnson,
)
from skaters.search import search
from skaters.periodicity import period_detector, top_periods
from skaters.api import laplace, doob, mean_revert
from skaters.sticky import sticky
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
    "laplace",
    "doob",
    "mean_revert",
    "sticky",
    "period_detector",
    "top_periods",
    # Building blocks
    "leaf",
    "scale_mixture_leaf",
    "crps_leaf",
    "ema",
    "conjugate",
    "difference",
    "fractional_difference",
    "standardize",
    "ema_transform",
    "ou_transform",
    "garch",
    "seasonal_difference",
    "power_transform",
    "yeo_johnson",
    "ar",
    "grouped_ar",
    "drift",
    "holt_linear",
    "theta",
    # Ensembles and search
    "precision_weighted_ensemble",
    "bayesian_ensemble",
    "terminal_leaf_ensemble",
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
