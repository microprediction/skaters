"""Torch twins of the volatility and seasonal transforms: ``garch``,
``seasonal_difference``, ``seasonal_anchor`` and ``seasonal_scale``.

Same arithmetic order as :mod:`skaters.transform`; continuous
hyperparameters are ``nn.Parameter`` tensors, periods stay ints, ring
buffers and per-phase arrays are Python lists of 0-d tensors so gradients
flow through recovered values and phase EMAs. Held to the reference by
``tests/test_torch_seasonal.py`` at 1e-9.
"""

from __future__ import annotations

import torch

from skaters.torch.dist import TorchDist, DTYPE, _t
from skaters.torch.transform import TorchTransform, _p, _zero, register


def _f(x) -> torch.Tensor:
    """Float or tensor -> 0-d float64 tensor."""
    return _t(x)


# ---------------------------------------------------------------------------
# garch:  z_t = (y_t - mu_t) / sigma_t,  sigma_t^2 = omega + alpha dev^2 + beta sigma^2
# ---------------------------------------------------------------------------

class GARCH(TorchTransform):
    reference = "garch"

    def __init__(self, omega: float = 0.01, alpha: float = 0.1, beta: float = 0.85,
                 mean_alpha: float = 0.05, eps: float = 1e-8):
        super().__init__()
        assert omega > 0
        assert alpha >= 0
        assert beta >= 0
        self.omega = _p(omega)
        self.alpha = _p(alpha)
        self.beta = _p(beta)
        self.mean_alpha = _p(mean_alpha)
        self.eps = float(eps)

    def reference_args(self):
        return {"omega": float(self.omega), "alpha": float(self.alpha),
                "beta": float(self.beta), "mean_alpha": float(self.mean_alpha),
                "eps": self.eps}

    def _init_state(self, y):
        persist = self.alpha + self.beta
        if bool(persist < 1):
            var0 = self.omega / (1 - persist)
        else:
            var0 = self.omega / self.eps
        return {"var": var0, "last_dev": _zero(), "mu": y}

    def _step(self, y, state):
        eps = self.eps
        mu = state["mu"]
        dev = y - mu
        var = self.omega + self.alpha * state["last_dev"] ** 2 + self.beta * state["var"]
        sigma = torch.sqrt(var) if bool(var > eps * eps) else torch.as_tensor(eps, dtype=DTYPE)
        z = dev / sigma
        mu_new = mu + self.mean_alpha * dev
        return z, {"var": var, "last_dev": dev, "mu": mu_new}

    def inverse_k(self, dists, state):
        var = state["var"]
        sigma = torch.sqrt(var) if bool(var > 1e-16) else torch.as_tensor(1e-8, dtype=DTYPE)
        return [d.affine(sigma, state["mu"]) for d in dists]


# ---------------------------------------------------------------------------
# seasonal_difference:  z_t = y_t - y_{t-s}
# ---------------------------------------------------------------------------

class SeasonalDifference(TorchTransform):
    reference = "seasonal_difference"

    def __init__(self, period: int = 12):
        super().__init__()
        assert period >= 1
        self.period = int(period)

    def reference_args(self):
        return {"period": self.period}

    def _init_state(self, y):
        return {"buffer": [y]}

    def _step(self, y, state):
        period = self.period
        buf = list(state["buffer"])
        if len(buf) >= period:
            z = y - buf[-period]
        else:
            z = _zero()
        buf.append(y)
        if len(buf) > 2 * period:
            buf.pop(0)
        return z, {"buffer": buf}

    def inverse_k(self, dists, state):
        period = self.period
        buf = list(state["buffer"])
        recovered_means = []
        recovered_vars = []
        result = []
        for h in range(len(dists)):
            lag_idx = h - period
            if lag_idx < 0:
                buf_idx = len(buf) - period + h
                anchor_mean = buf[buf_idx] if 0 <= buf_idx < len(buf) else _zero()
                anchor_var = _zero()
            else:
                anchor_mean = recovered_means[lag_idx]
                anchor_var = recovered_vars[lag_idx]
            recovered_means.append(dists[h].mean + anchor_mean)
            recovered_vars.append(dists[h].var + anchor_var)
            if bool(anchor_var > 0.0):
                av = anchor_var
                am = anchor_mean
                result.append(dists[h].map(lambda m, s: m + am,
                                           lambda m, s: torch.sqrt(s * s + av)))
            else:
                result.append(dists[h].shift(anchor_mean))
        return result


# ---------------------------------------------------------------------------
# seasonal_anchor:  z_t = y_t - (w phaseEMA + (1-w) y_{t-s})
# ---------------------------------------------------------------------------

class SeasonalAnchor(TorchTransform):
    reference = "seasonal_anchor"

    def __init__(self, period: int, alpha: float = 0.2, weight: float = 0.5):
        super().__init__()
        assert period >= 1
        assert 0 < alpha < 1
        assert 0.0 <= weight <= 1.0
        self.period = int(period)
        self.alpha = _p(alpha)
        self.weight = _p(weight)

    def reference_args(self):
        return {"period": self.period, "alpha": float(self.alpha), "weight": float(self.weight)}

    def _anchor(self, ema, snaive):
        w = self.weight
        return (w * ema + (1.0 - w) * snaive) if ema is not None else snaive

    def _init_state(self, y):
        return {"ema": [None] * self.period, "buffer": [y], "n": 1}

    def _step(self, y, state):
        period = self.period
        buf = list(state["buffer"])
        ema = list(state["ema"])
        p = state["n"] % period
        snaive = buf[-period] if len(buf) >= period else buf[-1]
        z = y - self._anchor(ema[p], snaive)
        e = ema[p]
        ema[p] = y if e is None else e + self.alpha * (y - e)
        buf.append(y)
        if len(buf) > 2 * period:
            buf.pop(0)
        return z, {"ema": ema, "buffer": buf, "n": state["n"] + 1}

    def inverse_k(self, dists, state):
        period = self.period
        alpha = self.alpha
        weight = self.weight
        buf = state["buffer"]
        H = len(dists)
        recovered_means = []
        rec_resp = []
        ema_resp = [[0.0] * H for _ in range(period)]
        out = []
        for h in range(H):
            p = (state["n"] + h) % period
            lag_idx = h - period
            if lag_idx < 0:
                buf_idx = len(buf) - period + h
                snaive = buf[buf_idx] if 0 <= buf_idx < len(buf) else buf[-1]
                sn_resp = None
            else:
                snaive = recovered_means[lag_idx]
                sn_resp = rec_resp[lag_idx]
            e = state["ema"][p]
            a_mean = self._anchor(e, snaive)
            a_resp = [0.0] * H
            for i in range(h):
                sn = sn_resp[i] if sn_resp is not None else 0.0
                a_resp[i] = (weight * ema_resp[p][i] + (1.0 - weight) * sn) if e is not None else sn
            a_var = 0.0
            for i in range(h):
                a_var = a_var + a_resp[i] * a_resp[i] * dists[i].var
            r = list(a_resp)
            r[h] = 1.0
            recovered_means.append(dists[h].mean + a_mean)
            rec_resp.append(r)
            if e is None:
                ema_resp[p] = list(r)
            else:
                ema_resp[p] = [(1.0 - alpha) * ema_resp[p][i] + alpha * r[i] for i in range(H)]
            if bool(_f(a_var) > 0.0):
                av = _f(a_var)
                am = a_mean
                out.append(dists[h].map(lambda m, s: m + am,
                                        lambda m, s: torch.sqrt(s * s + av)))
            else:
                out.append(dists[h].shift(a_mean))
        return out


# ---------------------------------------------------------------------------
# seasonal_scale:  z_t = (y_t - mu_{p(t)}) / sigma_{p(t)}
# ---------------------------------------------------------------------------

class SeasonalScale(TorchTransform):
    reference = "seasonal_scale"
    K0 = 3.0                                     # shrinkage prior strength (visits)

    def __init__(self, period: int, alpha: float = 0.05, center: bool = False,
                 eps: float = 1e-8):
        super().__init__()
        assert period >= 1
        assert 0 < alpha < 1
        self.period = int(period)
        self.alpha = _p(alpha)
        self.center = bool(center)
        self.eps = float(eps)

    def reference_args(self):
        return {"period": self.period, "alpha": float(self.alpha),
                "center": self.center, "eps": self.eps}

    @property
    def a_g(self):
        return self.alpha / self.period

    def _vg(self, var_g, n):
        updates = n - 1
        if updates <= 0:
            return 0.0
        return var_g / (1.0 - (1.0 - self.a_g) ** updates)

    def _maxeps(self, x):
        e2 = self.eps * self.eps
        if isinstance(x, torch.Tensor):
            return torch.clamp(x, min=e2)
        return torch.as_tensor(max(x, e2), dtype=DTYPE)

    def _phase_stats(self, mu, var, vis, mu_g, var_g, n, p):
        w = vis[p] / (vis[p] + self.K0)
        vp = self._maxeps(var[p])
        vg = self._maxeps(self._vg(var_g, n))
        var_eff = torch.exp(w * torch.log(vp) + (1.0 - w) * torch.log(vg))
        mu_eff = (w * mu[p] + (1.0 - w) * mu_g) if self.center else _zero()
        return mu_eff, torch.sqrt(var_eff)

    def _init_state(self, y):
        period = self.period
        return {"mu_g": y, "var_g": _zero(),
                "mu": [_zero() for _ in range(period)], "var": [_zero() for _ in range(period)],
                "vis": [0] * period, "n": 1}

    def _step(self, y, state):
        period = self.period
        alpha = self.alpha
        a_g = self.a_g
        mu = list(state["mu"]); var = list(state["var"]); vis = list(state["vis"])
        mu_g = state["mu_g"]; var_g = state["var_g"]; n = state["n"]
        p = n % period
        mu_eff, _ = self._phase_stats(mu, var, vis, mu_g, var_g, n, p)
        dg = y - mu_g
        mu_g = mu_g + a_g * dg
        var_g = (1 - a_g) * var_g + a_g * dg * dg
        if vis[p] == 0:
            mu[p] = y
            var[p] = _f(self._vg(var_g, n))
        else:
            dp = y - mu[p]
            mu[p] = mu[p] + alpha * dp
            var[p] = (1 - alpha) * var[p] + alpha * dp * dp
        vis[p] += 1
        n += 1
        _, sigma = self._phase_stats(mu, var, vis, mu_g, var_g, n, p)
        z = (y - mu_eff) / sigma
        return z, {"mu_g": mu_g, "var_g": var_g, "mu": mu, "var": var, "vis": vis, "n": n}

    def inverse_k(self, dists, state):
        out = []
        for h in range(len(dists)):
            mu_eff, sigma = self._phase_stats(state["mu"], state["var"], state["vis"],
                                              state["mu_g"], state["var_g"], state["n"],
                                              (state["n"] + h) % self.period)
            out.append(dists[h].affine(sigma, mu_eff))
        return out


for _cls in (GARCH, SeasonalDifference, SeasonalAnchor, SeasonalScale):
    register(_cls)
