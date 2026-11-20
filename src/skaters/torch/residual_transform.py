"""Online residual-transform wrapper in torch: the twin of
:mod:`skaters.residual_transform`.

The wrapper reads the base skater's matured PIT residual ``z_t``, updates a
small online scale learner (M1) or scale and leverage learner (M2), and
reshapes the next base predictive through the residual model ``H_t``:

    F~_t(y) = H_t(Phi^-1(F_t(y)))

The learner is bookkeeping driven by matured residuals, as the GPD tail fit
is in :mod:`skaters.torch.tails`: it runs on Python floats with the
reference's own functions, so it cannot drift from the reference, and it is
a constant in the graph. What is differentiable is the corrected
predictive, :class:`TorchCorrectedDist`: ``cdf`` and ``logpdf`` are torch
expressions in the base predictive (its cdf and density) and in ``theta``
when theta holds tensors. The normal quantile ``Phi^-1`` takes its value
from the reference bisection and its derivative from the implicit function
theorem, so values match the reference exactly and gradients are exact.
``quantile``, ``mean``, ``var``, ``std`` and ``crps`` run on the reference
:class:`skaters.residual_transform.CorrectedDist` built from the same base
predictive and theta on floats, and carry no gradient.

State has exactly the reference's layout: ``base``, ``raw``, ``z``,
``learner`` (``None`` for m0, else ``{ell, a, c, ea, ec, g2a, g2c}`` plus
``b``, ``eb``, ``g2b`` for m2) and ``theta``. A state restored by
:func:`skaters.torch.state.state_from_json` holds 0-d tensors where the
reference holds floats; the learner is converted back to floats on entry.
"""

from __future__ import annotations

import math

import torch

import skaters.residual_transform  # noqa: F401  (the package re-exports the factory under this name)
import sys as _sys

ref = _sys.modules["skaters.residual_transform"]
from skaters.residual_transform import ResidualDiagnostics  # noqa: F401  (float diagnostic, re-exported)
from skaters.torch.dist import DTYPE, _t

__all__ = ["residual_transform", "TorchCorrectedDist", "CorrectedDist", "ResidualDiagnostics"]

_EPS = ref._EPS
_LOG_SQRT2PI = ref._LOG_SQRT2PI
_SQRT2 = math.sqrt(2.0)


def _f(x) -> float:
    return float(x.detach()) if isinstance(x, torch.Tensor) else float(x)


def _std_cdf_t(z):
    """Standard normal cdf, the reference ``Dist.gaussian(0, 1).cdf``."""
    return 0.5 * (1.0 + torch.erf(z / _SQRT2))


def _phi_inv_t(u):
    """Standard normal quantile of a 0-d tensor: the value is the reference
    bisection (``ref._phi_inv``), the derivative is ``1 / phi(z)``."""
    z0 = ref._phi_inv(_f(u))
    if not u.requires_grad:
        return torch.as_tensor(z0, dtype=DTYPE)
    dens = math.exp(-0.5 * z0 * z0 - _LOG_SQRT2PI)
    return torch.as_tensor(z0, dtype=DTYPE) + (u - u.detach()) / dens


def _clamp01_t(u):
    return torch.clamp(u, _EPS, 1.0 - _EPS)


def _sigma(theta):
    return torch.exp(0.5 * _t(theta["ell"]))


class TorchCorrectedDist:
    """The torch base predictive ``base`` reshaped by the residual model
    ``model`` ("m0" identity, else Gaussian shift-scale) with ``theta``."""

    __slots__ = ("base", "model", "theta", "_ref")

    def __init__(self, base, model: str, theta: dict):
        self.base = base
        self.model = model
        self.theta = theta
        self._ref = None

    # --- the reference twin (floats) ------------------------------------

    def to_reference(self) -> ref.CorrectedDist:
        if self._ref is None:
            family = ref.IDENTITY_FAMILY if self.model == "m0" else ref.GAUSSIAN_SHIFT_SCALE_FAMILY
            self._ref = ref.CorrectedDist(self.base.to_reference(), family,
                                          {key: _f(v) for key, v in self.theta.items()})
        return self._ref

    # --- differentiable queries -----------------------------------------

    def _z(self, y):
        return _phi_inv_t(_clamp01_t(_t(self.base.cdf(y))))

    def _h_cdf(self, z):
        if self.model == "m0":
            return _std_cdf_t(z)
        return _std_cdf_t((z - _t(self.theta["m"])) / _sigma(self.theta))

    def _h_logpdf(self, z):
        if self.model == "m0":
            return -0.5 * z * z - _LOG_SQRT2PI
        sigma = _sigma(self.theta)
        zz = (z - _t(self.theta["m"])) / sigma
        return -0.5 * zz * zz - torch.log(sigma) - _LOG_SQRT2PI

    def cdf(self, y):
        return self._h_cdf(self._z(_t(y)))

    def logpdf(self, y):
        y = _t(y)
        z = self._z(y)
        return _t(self.base.logpdf(y)) + self._h_logpdf(z) + 0.5 * z * z + _LOG_SQRT2PI

    def pdf(self, y):
        lp = self.logpdf(y)
        return torch.exp(lp) if _f(lp) > -700.0 else torch.zeros((), dtype=DTYPE)

    # --- reference-twin queries (no gradient) ----------------------------

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 2100):
        return torch.as_tensor(self.to_reference().quantile(p, tol=tol, max_iter=max_iter), dtype=DTYPE)

    @property
    def mean(self):
        return torch.as_tensor(self.to_reference().mean, dtype=DTYPE)

    @property
    def var(self):
        return torch.as_tensor(self.to_reference().var, dtype=DTYPE)

    @property
    def std(self):
        return torch.as_tensor(self.to_reference().std, dtype=DTYPE)

    def crps(self, x):
        return torch.as_tensor(self.to_reference().crps(_f(_t(x))), dtype=DTYPE)

    def __repr__(self) -> str:
        return f"TorchCorrectedDist(model={self.model}, theta={self.theta!r}, base={self.base!r})"


CorrectedDist = TorchCorrectedDist


def _learner_floats(learner):
    if learner is None:
        return None
    return {key: _f(v) for key, v in learner.items()}


def residual_transform(base, model: str = "m2", lr: float = 0.01, k: int = 1):
    """Torch twin of :func:`skaters.residual_transform.residual_transform`:
    same signature, same state layout, predictives are
    :class:`TorchCorrectedDist`."""
    assert k == 1, "residual_transform currently supports k=1 only"
    assert model in ref._MODELS, f"model must be one of {ref._MODELS}, got {model!r}"
    learn_b = model == "m2"
    lr = float(lr)

    def _skater(y, state=None):
        yt = _t(y)
        if state is None:
            learner0 = None if model == "m0" else ref._init_scale_learner(learn_b)
            state = {
                "base": None,
                "raw": None,
                "z": None,
                "learner": learner0,
                "theta": ref._theta_of(model, learner0 or {}),
            }
        elif model != "m0" and state["learner"] is not None:
            state["learner"] = _learner_floats(state["learner"])   # a restored state holds tensors

        z = None
        if state["raw"] is not None:
            with torch.no_grad():
                u = ref._clamp01(_f(state["raw"].cdf(yt)))
            z = ref._phi_inv(u)
            if model != "m0":
                state["learner"] = ref._update_scale_learner(state["learner"], z, lr, learn_b)
        state["z"] = z

        dists, state["base"] = base(yt, state["base"])
        f_t = dists[0]
        state["raw"] = f_t

        theta = ref._theta_of(model, state["learner"] if model != "m0" else {})
        state["theta"] = theta
        return [TorchCorrectedDist(f_t, model, theta)], state

    _skater.__name__ = f"residual_transform({getattr(base, '__name__', '?')}, model={model})"
    return _skater
