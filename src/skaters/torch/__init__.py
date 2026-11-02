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
import skaters.torch.spec  # noqa: F401

from skaters.torch.trunk import TerminalLeafEnsemble
from skaters.torch.pool import pool_spec, build_pool
from skaters.torch.api import laplace, dantzig

__all__ = ["TorchDist", "TorchTransform", "REGISTRY", "from_reference", "register",
           "TerminalLeafEnsemble", "pool_spec", "build_pool", "laplace", "dantzig"]
