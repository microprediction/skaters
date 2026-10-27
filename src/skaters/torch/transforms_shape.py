"""Shape transforms as torch modules: fractional differencing and the two
signed power families (power_transform, yeo_johnson), delta-method inverses.

Same arithmetic order as :mod:`skaters.transform`; the continuous
hyperparameters (``d``, ``p``, ``lmbda``) are parameters, so the fractional
weights and the delta-method derivatives carry gradients. The exact
pushforward inverse (``exact=True``) is not ported: it builds a table over
:mod:`skaters.pushforward` and raises here.
"""

from __future__ import annotations

import math

import torch

from skaters.torch.dist import TorchDist, DTYPE, _t
from skaters.torch.transform import TorchTransform, _p, _zero, register


def _frac_diff_weights(d: torch.Tensor, window: int) -> list:
    """w[0] = 1, w[k] = -w[k-1] * (d - k + 1) / k, as tensors of ``d``."""
    w = [torch.ones((), dtype=DTYPE)]
    for i in range(1, window):
        w.append(-w[-1] * (d - i + 1) / i)
    return w


class FractionalDifference(TorchTransform):
    reference = "fractional_difference"

    def __init__(self, d: float = 0.4, window: int = 50):
        super().__init__()
        self.d = _p(d)
        self.window = int(window)

    def reference_args(self):
        return {"d": float(self.d), "window": self.window}

    def _weights(self) -> list:
        return _frac_diff_weights(self.d, self.window)

    def forward(self, y, state=None):
        # The reference emits w[0] * y = y on the first call, not 0.
        y = _t(y)
        buf = [] if state is None else list(state["buffer"])
        buf.append(y)
        if len(buf) > self.window:
            buf.pop(0)
        n = len(buf)
        w = self._weights()
        z = _zero()
        for j in range(n):
            z = z + w[j] * buf[n - 1 - j]
        return z, {"buffer": buf}

    def inverse_k(self, dists, state):
        H = len(dists)
        w = self._weights()
        window = self.window
        buf = list(state["buffer"])
        cbuf: list = [None] * len(buf)
        result = []
        for h, d_in in enumerate(dists):
            buf.append(_zero())
            cbuf.append(None)
            n = len(buf)
            shift = _zero()
            coef = [_zero() for _ in range(H)]
            coef[h] = torch.ones((), dtype=DTYPE)
            for j in range(1, min(n, window)):
                shift = shift - w[j] * buf[n - 1 - j]
                cj = cbuf[n - 1 - j]
                if cj is not None:
                    for i in range(h):
                        coef[i] = coef[i] - w[j] * cj[i]
            recovered_mean = d_in.mean + shift
            buf[-1] = recovered_mean
            cbuf[-1] = coef
            total_var = _zero()
            for i in range(h + 1):
                total_var = total_var + coef[i] * coef[i] * dists[i].var
            if bool(total_var > 0):
                std = torch.sqrt(total_var)
            else:
                std = torch.clamp(d_in.std, min=1e-12)
            result.append(TorchDist.gaussian(recovered_mean, std))
            if len(buf) > window:
                buf.pop(0)
                cbuf.pop(0)
        return result


def _not_exact(name: str):
    raise NotImplementedError(
        f"{name}(exact=True) emits the exact pushforward (skaters.pushforward), "
        "which skaters.torch does not port; use exact=False (delta method).")


class PowerTransform(TorchTransform):
    reference = "power_transform"

    def __init__(self, p: float = 0.5, exact: bool = False):
        super().__init__()
        assert 0 < p < 1
        if exact:
            _not_exact("power_transform")
        self.p = _p(p)

    def reference_args(self):
        return {"p": float(self.p), "exact": False}

    def _fwd(self, y):
        return torch.copysign(torch.abs(y) ** self.p, y)

    def _inv(self, yp):
        return torch.copysign(torch.abs(yp) ** (1.0 / self.p), yp)

    def forward(self, y, state=None):
        y = _t(y)
        return self._fwd(y), (state or {})

    def inverse_k(self, dists, state):
        inv_p = 1.0 / self.p
        result = []
        for d in dists:
            ws, ms, ss = [], [], []
            for w, mu, sigma in d.components:
                orig_mean = self._inv(mu)
                abs_mu = torch.abs(mu)
                if bool(abs_mu > 1e-12):
                    deriv = inv_p * abs_mu ** (inv_p - 1)
                else:
                    deriv = inv_p
                orig_std = torch.clamp(sigma * deriv, min=1e-12)
                ws.append(w); ms.append(orig_mean); ss.append(orig_std)
            result.append(TorchDist(ws, ms, ss))
        return result


class YeoJohnson(TorchTransform):
    reference = "yeo_johnson"

    def __init__(self, lmbda: float = 0.0, exact: bool = False):
        super().__init__()
        if exact:
            _not_exact("yeo_johnson")
        self.lmbda = _p(lmbda)

    def reference_args(self):
        return {"lmbda": float(self.lmbda), "exact": False}

    # the L == 0 and L == 2 cases are the reference's closed-form limits,
    # taken on the parameter's float value exactly as the reference does
    def _fwd(self, y):
        L = self.lmbda
        Lf = float(L.detach())
        if bool(y >= 0.0):
            return torch.log1p(y) if Lf == 0.0 else ((y + 1.0) ** L - 1.0) / L
        if Lf == 2.0:
            return -torch.log1p(-y)
        return -(((-y + 1.0) ** (2.0 - L) - 1.0) / (2.0 - L))

    def _inv(self, yp):
        L = self.lmbda
        Lf = float(L.detach())
        if bool(yp >= 0.0):
            if Lf == 0.0:
                return torch.expm1(torch.clamp(yp, max=350.0))
            base = torch.clamp(L * yp + 1.0, min=1e-12)
            return base ** (1.0 / L) - 1.0
        if Lf == 2.0:
            return 1.0 - torch.exp(torch.clamp(-yp, max=350.0))
        base = torch.clamp(-(2.0 - L) * yp + 1.0, min=1e-12)
        return 1.0 - base ** (1.0 / (2.0 - L))

    def _dinv(self, yp):
        L = self.lmbda
        Lf = float(L.detach())
        if bool(yp >= 0.0):
            if Lf == 0.0:
                return torch.exp(torch.clamp(yp, max=350.0))
            base = torch.clamp(L * yp + 1.0, min=1e-12)
            return base ** (1.0 / L - 1.0)
        if Lf == 2.0:
            return torch.exp(torch.clamp(-yp, max=350.0))
        base = torch.clamp(-(2.0 - L) * yp + 1.0, min=1e-12)
        return base ** (1.0 / (2.0 - L) - 1.0)

    def forward(self, y, state=None):
        y = _t(y)
        return self._fwd(y), (state or {})

    def inverse_k(self, dists, state):
        result = []
        for d in dists:
            ws, ms, ss = [], [], []
            for w, mu, sigma in d.components:
                ws.append(w)
                ms.append(self._inv(mu))
                ss.append(torch.clamp(sigma * self._dinv(mu), min=1e-12))
            result.append(TorchDist(ws, ms, ss))
        return result


for _cls in (FractionalDifference, PowerTransform, YeoJohnson):
    register(_cls)
