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
from skaters.conjugate import conjugate
from skaters.transform import difference, fractional_difference, standardize, ema_transform
from skaters.bayesian import bayesian_ensemble
from skaters.api import (
    skater,
    brown, holt, hosking, gauss, laplace,
    quickly, slowly, sluggishly, rapidly, ensemble,
)
from skaters.spec import (
    build, name as spec_name, to_json, from_json,
    ema_spec, ensemble_spec, conjugate_spec,
    diff_spec, frac_spec, std_spec,
)

__all__ = [
    "Dist",
    "Skater",
    "leaf",
    "ema",
    "precision_weighted_ensemble",
    "conjugate",
    "difference",
    "fractional_difference",
    "standardize",
    "ema_transform",
    "quickly",
    "slowly",
    "sluggishly",
    "rapidly",
    "ensemble",
    "bayesian_ensemble",
    "skater",
    "brown",
    "holt",
    "hosking",
    "gauss",
    "laplace",
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
