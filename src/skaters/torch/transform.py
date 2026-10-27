"""Invertible online transforms as torch modules: the learnable twin of
:mod:`skaters.transform`.

Every reference transform is a closure pair ``(forward, inverse_k)`` over a
dict of floats. Here each is a :class:`TorchTransform`, an ``nn.Module``
whose parameters (an EMA rate, a Holt pair, a Yeo-Johnson lambda) are
tensors, whose state is a dict of 0-d tensors, and whose two methods keep
the reference's arithmetic order so that at the reference's parameter
values the two ports agree to float64 round-off. The parity suite
(:mod:`skaters.torch.parity`) checks that claim transform by transform;
nothing here is trusted until it passes.

Contract, identical to the reference:

    z, state = T.forward(y, state)        # state None on the first call
    dists    = T.inverse_k(dists_z, state)

``y`` may be a float or a 0-d tensor; ``dists_z`` is a list of
:class:`TorchDist`. Branches on state (cold starts, degenerate variances)
are taken on tensor values exactly where the reference branches on floats,
so the chosen branch is differentiable and the branch set is the same.

Parameter learning: a transform is created from floats (``EMA(0.05)``) and
its parameters are ``nn.Parameter`` tensors; ``requires_grad`` is on by
default. :func:`from_reference` builds the module that matches a reference
factory call, so ``epoch zero`` of any learned model is the reference.
"""

from __future__ import annotations

import math

import torch
from torch import nn

from skaters.torch.dist import TorchDist, DTYPE, _t


def _p(value: float) -> nn.Parameter:
    return nn.Parameter(torch.as_tensor(float(value), dtype=DTYPE))


def _zero() -> torch.Tensor:
    return torch.zeros((), dtype=DTYPE)


class TorchTransform(nn.Module):
    """Base: subclasses implement ``_init_state``, ``_step`` and ``inverse_k``."""

    #: name of the reference factory in skaters.transform
    reference = ""

    def forward(self, y, state=None):
        y = _t(y)
        if state is None:
            return _zero(), self._init_state(y)
        return self._step(y, state)

    def _init_state(self, y) -> dict:
        raise NotImplementedError

    def _step(self, y, state):
        raise NotImplementedError

    def inverse_k(self, dists, state):
        raise NotImplementedError

    def reference_args(self) -> dict:
        """Keyword arguments reproducing this module with the reference factory."""
        return {}


# ---------------------------------------------------------------------------
# difference:  z_t = y_t - y_{t-1}
# ---------------------------------------------------------------------------

class Difference(TorchTransform):
    reference = "difference"

    def _init_state(self, y):
        return {"last": y}

    def _step(self, y, state):
        return y - state["last"], {"last": y}

    def inverse_k(self, dists, state):
        anchor = state["last"]
        out = []
        cumsum_mean = _zero()
        cumsum_var = _zero()
        for d in dists:
            cumsum_mean = cumsum_mean + d.mean
            cumsum_var = cumsum_var + d.var
            if bool(cumsum_var > 0):
                std = torch.sqrt(cumsum_var)
            else:
                std = torch.clamp(d.std, min=1e-12)
            out.append(TorchDist.gaussian(anchor + cumsum_mean, std))
        return out


# ---------------------------------------------------------------------------
# standardize:  z_t = (y_t - mu_t) / sigma_t
# ---------------------------------------------------------------------------

class Standardize(TorchTransform):
    reference = "standardize"

    def __init__(self, alpha: float = 0.05, eps: float = 1e-8):
        super().__init__()
        self.alpha = _p(alpha)
        self.eps = float(eps)

    def reference_args(self):
        return {"alpha": float(self.alpha), "eps": self.eps}

    def _init_state(self, y):
        return {"mu": y, "var": _zero()}

    def _step(self, y, state):
        mu, var = state["mu"], state["var"]
        diff = y - mu
        eps = self.eps
        if bool(var > eps * eps):
            sigma = torch.sqrt(var)
        else:
            ad = torch.abs(diff)
            sigma = ad if bool(ad > eps) else torch.as_tensor(eps, dtype=DTYPE)
        z = diff / sigma
        mu_new = mu + self.alpha * diff
        var_new = (1 - self.alpha) * var + self.alpha * diff * diff
        return z, {"mu": mu_new, "var": var_new}

    def inverse_k(self, dists, state):
        mu, var = state["mu"], state["var"]
        sigma = torch.sqrt(var) if bool(var > 1e-16) else torch.as_tensor(1e-8, dtype=DTYPE)
        return [d.affine(sigma, mu) for d in dists]


# ---------------------------------------------------------------------------
# ema_transform:  z_t = y_t - level_t
# ---------------------------------------------------------------------------

class EMA(TorchTransform):
    reference = "ema_transform"

    def __init__(self, alpha: float = 0.05):
        super().__init__()
        assert 0 < alpha < 1
        self.alpha = _p(alpha)

    def reference_args(self):
        return {"alpha": float(self.alpha)}

    def _init_state(self, y):
        return {"level": y}

    def _step(self, y, state):
        residual = y - state["level"]
        level = state["level"] + self.alpha * residual
        return residual, {"level": level}

    def inverse_k(self, dists, state):
        level = state["level"]
        out = []
        add = _zero()
        for d in dists:
            if bool(add > 0):
                out.append(d.map(lambda m, s: m + level, lambda m, s: torch.sqrt(s * s + add)))
            else:
                out.append(d.shift(level))
            add = add + self.alpha * self.alpha * d.var
        return out


# ---------------------------------------------------------------------------
# registry: reference factory name -> module class
# ---------------------------------------------------------------------------

REGISTRY: dict[str, type[TorchTransform]] = {}


def register(cls: type[TorchTransform]) -> type[TorchTransform]:
    REGISTRY[cls.reference] = cls
    return cls


for _cls in (Difference, Standardize, EMA):
    register(_cls)


def from_reference(name: str, **kwargs) -> TorchTransform:
    """The module matching ``skaters.transform.<name>(**kwargs)``."""
    if name not in REGISTRY:
        raise KeyError(f"no torch port of transform {name!r}; have {sorted(REGISTRY)}")
    return REGISTRY[name](**kwargs)
