"""Level-and-trend transforms as torch modules: the twins of
``ou_transform``, ``theta``, ``drift`` and ``holt_linear`` in
:mod:`skaters.transform`, same arithmetic order, parameters as tensors.
Held to the reference by ``tests/test_torch_level.py`` at 1e-9.
"""

from __future__ import annotations

import math

import torch

from skaters.torch.dist import TorchDist, DTYPE, _t
from skaters.torch.transform import TorchTransform, _p, _zero, register


def _finite(x) -> bool:
    return bool(torch.isfinite(x))


# ---------------------------------------------------------------------------
# ou_transform: mean reversion toward a running level
# ---------------------------------------------------------------------------

class OU(TorchTransform):
    reference = "ou_transform"

    def __init__(self, kappa: float = 0.1, alpha: float = 0.02):
        super().__init__()
        assert 0.0 < kappa <= 1.0
        assert 0.0 < alpha < 1.0
        self.kappa = _p(kappa)
        self.alpha = _p(alpha)

    def reference_args(self):
        return {"kappa": float(self.kappa), "alpha": float(self.alpha)}

    @property
    def phi(self):
        return 1.0 - self.kappa

    def forward(self, y, state=None):
        y = _t(y)
        if state is None or not _finite(y):
            y0 = y if _finite(y) else _zero()
            return _zero(), {"m": y0, "fc": y0, "y": y0}
        return self._step(y, state)

    def _init_state(self, y):
        return {"m": y, "fc": y, "y": y}

    def _step(self, y, state):
        resid = y - state["fc"]
        if not _finite(resid):
            resid = _zero()
        m = state["m"] + self.alpha * (y - state["m"])
        fc = m + self.phi * (y - m)
        return resid, {"m": m, "fc": fc, "y": y}

    def inverse_k(self, dists, state):
        m, ylast = state["m"], state["y"]
        phi = self.phi
        out = []
        for h, d in enumerate(dists, start=1):
            center = m + (phi ** h) * (ylast - m)
            v_h = d.var
            if bool(v_h > 0.0):
                tot = _zero()
                for i in range(h):
                    tot = tot + (phi ** (2 * (h - 1 - i))) * dists[i].var
                g = torch.sqrt(tot / v_h)
            elif bool(phi < 1.0 - 1e-9):
                g = torch.sqrt((1.0 - phi ** (2 * h)) / (1.0 - phi * phi))
            else:
                g = torch.as_tensor(math.sqrt(h), dtype=DTYPE)
            out.append(d.scale(g).shift(center))
        return out


# ---------------------------------------------------------------------------
# theta: SES + half the running OLS slope
# ---------------------------------------------------------------------------

class Theta(TorchTransform):
    reference = "theta"

    def __init__(self, alpha: float = 0.1):
        super().__init__()
        assert 0 < alpha < 1
        self.alpha = _p(alpha)

    def reference_args(self):
        return {"alpha": float(self.alpha)}

    def _init_state(self, y):
        one = torch.ones((), dtype=DTYPE)
        return {"ses": y, "t": 1, "sum_t": one, "sum_t2": one.clone(),
                "sum_y": y, "sum_ty": y}

    def _step(self, y, state):
        s = dict(state)
        s["t"] += 1
        t = s["t"]
        forecast = s["ses"] + s.get("slope", _zero()) / 2
        residual = y - forecast
        s["ses"] = self.alpha * y + (1 - self.alpha) * s["ses"]
        s["sum_t"] = s["sum_t"] + t
        s["sum_t2"] = s["sum_t2"] + t * t
        s["sum_y"] = s["sum_y"] + y
        s["sum_ty"] = s["sum_ty"] + t * y
        n = t
        denom = n * s["sum_t2"] - s["sum_t"] ** 2
        if bool(torch.abs(denom) > 1e-12):
            slope = (n * s["sum_ty"] - s["sum_t"] * s["sum_y"]) / denom
        else:
            slope = _zero()
        s["slope"] = slope
        return residual, s

    def inverse_k(self, dists, state):
        ses = state["ses"]
        slope = state.get("slope", _zero())
        out = []
        for h, d in enumerate(dists):
            forecast = ses + (h + 1) * slope / 2 + d.mean
            total_var = _zero()
            for j in range(h + 1):
                c = 1.0 if j == 0 else self.alpha
                total_var = total_var + c * c * dists[h - j].var
            if bool(total_var > 0):
                std = torch.sqrt(total_var)
            else:
                std = torch.clamp(d.std, min=1e-12)
            out.append(TorchDist.gaussian(forecast, std))
        return out


# ---------------------------------------------------------------------------
# drift: differencing with a shrunk long-memory drift estimate
# ---------------------------------------------------------------------------

class Drift(TorchTransform):
    reference = "drift"

    def __init__(self, alpha: float = 0.002, shrinkage: float = 0.001):
        super().__init__()
        assert 0 < alpha < 1
        assert 0 <= shrinkage < 1
        self.alpha = _p(alpha)
        self.shrinkage = _p(shrinkage)

    def reference_args(self):
        return {"alpha": float(self.alpha), "shrinkage": float(self.shrinkage)}

    @property
    def decay(self):
        return 1 - self.alpha - self.shrinkage

    def _init_state(self, y):
        return {"last": y, "mu": _zero()}

    def _step(self, y, state):
        dy = y - state["last"]
        residual = dy - state["mu"]
        mu = self.decay * state["mu"] + self.alpha * dy
        return residual, {"last": y, "mu": mu}

    def inverse_k(self, dists, state):
        anchor = state["last"]
        mu = state["mu"]
        rho = self.decay + self.alpha
        out = []
        cumsum_mean = _zero()
        for h, d in enumerate(dists):
            cumsum_mean = cumsum_mean + d.mean
            total_mean = anchor + (h + 1) * mu + cumsum_mean
            total_var = _zero()
            for i in range(h + 1):
                acc = _zero()
                f = torch.ones((), dtype=DTYPE)
                for _ in range(h - i):
                    acc = acc + f
                    f = f * rho
                c = 1.0 + self.alpha * acc
                total_var = total_var + c * c * dists[i].var
            if bool(total_var > 0):
                total_std = torch.sqrt(total_var)
            else:
                total_std = torch.clamp(d.std, min=1e-12)
            out.append(TorchDist.gaussian(total_mean, total_std))
        return out


# ---------------------------------------------------------------------------
# holt_linear: coupled level and trend
# ---------------------------------------------------------------------------

class Holt(TorchTransform):
    reference = "holt_linear"

    def __init__(self, alpha: float = 0.1, beta: float = 0.05):
        super().__init__()
        assert 0 < alpha < 1
        assert 0 < beta < 1
        self.alpha = _p(alpha)
        self.beta = _p(beta)

    def reference_args(self):
        return {"alpha": float(self.alpha), "beta": float(self.beta)}

    def _init_state(self, y):
        return {"level": y, "trend": _zero()}

    def _step(self, y, state):
        l_prev = state["level"]
        b_prev = state["trend"]
        l_new = self.alpha * y + (1 - self.alpha) * (l_prev + b_prev)
        b_new = self.beta * (l_new - l_prev) + (1 - self.beta) * b_prev
        residual = y - (l_prev + b_prev)
        return residual, {"level": l_new, "trend": b_new}

    def inverse_k(self, dists, state):
        level = state["level"]
        trend = state["trend"]
        out = []
        for h, d in enumerate(dists):
            forecast = level + (h + 1) * trend + d.mean
            total_var = _zero()
            for j in range(h + 1):
                c = 1.0 if j == 0 else self.alpha + self.alpha * self.beta * j
                total_var = total_var + c * c * dists[h - j].var
            if bool(total_var > 0):
                std = torch.sqrt(total_var)
            else:
                std = torch.clamp(d.std, min=1e-12)
            out.append(TorchDist.gaussian(forecast, std))
        return out


for _cls in (OU, Theta, Drift, Holt):
    register(_cls)
