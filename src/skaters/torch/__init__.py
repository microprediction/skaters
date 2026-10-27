"""skaters.torch: the differentiable port.

The reference package has no dependencies; this subpackage needs ``torch``
(``pip install skaters[torch]``) and is imported only on request, so
``import skaters`` stays dependency-free.

    from skaters.torch import TorchDist, from_reference
    T = from_reference("ema_transform", alpha=0.05)   # an nn.Module
    z, state = T(y, None)
    dists = T.inverse_k(dists_z, state)

Every transform here is held to the reference by the parity suite in
:mod:`skaters.torch.parity` (``check_parity``) at 1e-9 over seeded series,
and every parameter carries a gradient (``gradient_check``).
"""

from skaters.torch.dist import TorchDist
from skaters.torch.transform import TorchTransform, REGISTRY, from_reference, register
import skaters.torch.transforms_seasonal  # noqa: F401
import skaters.torch.transforms_shape  # noqa: F401
import skaters.torch.transforms_ar  # noqa: F401
import skaters.torch.transforms_level  # noqa: F401

__all__ = ["TorchDist", "TorchTransform", "REGISTRY", "from_reference", "register"]
