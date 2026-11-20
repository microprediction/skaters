"""skaters.torch: the differentiable port, a full implementation of the
library on torch tensors.

The reference package has no dependencies; this subpackage needs ``torch``
(``pip install skaters[torch]``) and is imported only on request, so
``import skaters`` stays dependency-free.

    from skaters.torch import laplace, from_reference
    f = laplace(k=1)                                   # the same model, tensors inside
    dists, state = f(y, None)                          # list[TorchDist]
    loss = -dists[0].logpdf(y_next)                    # differentiable in every parameter

It is held to the reference by the same parity vectors the JavaScript,
Rust, R and Julia ports pass (``parity/check_torch.py``, 1e-6 on every
scenario including ``laplace`` at k=1 and k=3, the repeat-series lattice
and the missing-observation rules), and module by module at 1e-9 by the
tests in ``tests/test_torch_*.py``. Continuous hyperparameters are
``nn.Parameter`` tensors and gradients flow from a log score at the output
through the tail splice, the lattice projection, the trunk's weights and
every transform.
"""

from skaters.torch.dist import TorchDist
from skaters.torch.transform import TorchTransform, REGISTRY, from_reference, register
import skaters.torch.sticky  # noqa: F401
import skaters.torch.parade  # noqa: F401
import skaters.torch.tails  # noqa: F401
import skaters.torch.transforms_seasonal  # noqa: F401
import skaters.torch.transforms_shape  # noqa: F401
import skaters.torch.transforms_ar  # noqa: F401
import skaters.torch.transforms_level  # noqa: F401
import skaters.torch.runstats  # noqa: F401
import skaters.torch.leaf  # noqa: F401
import skaters.torch.ema  # noqa: F401
import skaters.torch.ensemble  # noqa: F401
import skaters.torch.bayesian  # noqa: F401
import skaters.torch.multiscale  # noqa: F401
import skaters.torch.periodicity  # noqa: F401
import skaters.torch.search  # noqa: F401
import skaters.torch.learned  # noqa: F401
import skaters.torch.spec  # noqa: F401

from skaters.torch.trunk import TerminalLeafEnsemble, terminal_leaf_ensemble
from skaters.torch.pool import pool_spec, build_pool
from skaters.torch.api import laplace, dantzig, flesaker
from skaters.torch.granger import granger
from skaters.torch.learned import learned, LearnedLaplace
from skaters.torch.leaf import leaf, scale_mixture_leaf, crps_leaf, garch_leaf
from skaters.torch.ema import ema
from skaters.torch.ensemble import precision_weighted_ensemble
from skaters.torch.bayesian import bayesian_ensemble
from skaters.torch.conjugate import conjugate
from skaters.torch.search import search
from skaters.torch.periodicity import period_detector, top_periods
from skaters.torch.multiscale import multiscale
from skaters.torch.parade import parade
from skaters.torch.sticky import sticky
from skaters.torch.residual_transform import residual_transform, ResidualDiagnostics, CorrectedDist
from skaters.torch.homogenize import (homogenize, make_candidates as homogenize_candidates,
                                      HomogenizedDist)
from skaters.torch.state import state_to_json, state_from_json, assert_plain_state
from skaters.torch.spec import (
    build, name as spec_name, to_json, from_json,
    ema_spec, ensemble_spec, conjugate_spec, diff_spec, frac_spec, std_spec,
)
from skaters.conventions import Skater

Dist = TorchDist          # the reference's name for the predictive type


def _transform_factory(name: str):
    def factory(*args, **kwargs):
        return REGISTRY[name](*args, **kwargs)
    factory.__name__ = factory.__qualname__ = name
    factory.__doc__ = f"The torch module matching ``skaters.{name}`` (same arguments)."
    return factory


difference = _transform_factory("difference")
fractional_difference = _transform_factory("fractional_difference")
standardize = _transform_factory("standardize")
ema_transform = _transform_factory("ema_transform")
ou_transform = _transform_factory("ou_transform")
garch = _transform_factory("garch")
seasonal_difference = _transform_factory("seasonal_difference")
power_transform = _transform_factory("power_transform")
ar = _transform_factory("ar")
grouped_ar = _transform_factory("grouped_ar")
drift = _transform_factory("drift")
holt_linear = _transform_factory("holt_linear")
theta = _transform_factory("theta")
yeo_johnson = _transform_factory("yeo_johnson")
log_transform = _transform_factory("log_transform")

__all__ = ["learned", "LearnedLaplace", "TorchDist", "TorchTransform", "REGISTRY", "from_reference", "register",
           "TerminalLeafEnsemble", "pool_spec", "build_pool", "laplace", "dantzig", "flesaker",
           # the reference's exported surface, on tensors
           "Dist", "Skater", "granger", "leaf", "scale_mixture_leaf", "crps_leaf", "garch_leaf", "ema", "conjugate",
           "difference", "fractional_difference", "standardize", "ema_transform", "ou_transform",
           "garch", "seasonal_difference", "power_transform", "yeo_johnson", "log_transform",
           "ar", "grouped_ar", "drift", "holt_linear", "theta",
           "precision_weighted_ensemble", "bayesian_ensemble", "terminal_leaf_ensemble",
           "multiscale", "parade", "sticky", "search", "period_detector", "top_periods",
           "residual_transform", "ResidualDiagnostics", "CorrectedDist",
           "homogenize", "homogenize_candidates", "HomogenizedDist",
           "state_to_json", "state_from_json", "assert_plain_state",
           "build", "spec_name", "to_json", "from_json",
           "ema_spec", "ensemble_spec", "conjugate_spec", "diff_spec", "frac_spec", "std_spec"]
