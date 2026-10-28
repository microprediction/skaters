"""Residual leaves as torch modules: the twins of :mod:`skaters.leaf`.

Each factory returns an ``nn.Module`` skater, ``forward(y, state=None) ->
(list[TorchDist], state)``, with the reference's arithmetic in the
reference's order. Continuous hyperparameters (``gamma``, ``scale_alpha``,
``eta``) are ``nn.Parameter`` tensors; the fixed scale dictionaries and the
GARCH refit grid are constants, exactly as in the reference. Mixture weights
are normalised the way :class:`skaters.dist.Dist` normalises them (a
compensated sum of the weights), so the two ports agree to float64
round-off.

Held to the reference by ``tests/test_torch_leaf.py``.
"""

from __future__ import annotations

import bisect
import math
from collections import deque

import torch
from torch import nn

from skaters.leaf import FINE, _SCALE_BASIS, _GARCH_AB_GRID, _GARCH_OMEGA_MULT
from skaters.torch.dist import TorchDist, DTYPE, _t
from skaters.torch.runstats import running_var_init, running_var_update, running_var_get
from skaters.torch.transforms_ar import _psum

__all__ = ["leaf", "scale_mixture_leaf", "crps_leaf", "garch_leaf", "conforming_leaf",
           "ensemble_leaf", "Leaf", "ScaleMixtureLeaf", "CrpsLeaf", "GarchLeaf",
           "ConformingLeaf", "EnsembleLeaf"]

_S2 = math.sqrt(2.0)
_INV = 1.0 / math.sqrt(2.0 * math.pi)
_A0 = 2.0 * _INV


def _p(value: float) -> nn.Parameter:
    return nn.Parameter(torch.as_tensor(float(value), dtype=DTYPE))


def _zero() -> torch.Tensor:
    return torch.zeros((), dtype=DTYPE)


def _c(value: float) -> torch.Tensor:
    return torch.as_tensor(float(value), dtype=DTYPE)


def _dist(ws, ms, ss) -> TorchDist:
    """``Dist([(w, m, s), ...])``: weights divided by their compensated sum."""
    total = _psum(ws)
    return TorchDist([w / total for w in ws], list(ms), list(ss), _trusted=True)


def _scale_or_bootstrap(var, y):
    """``sqrt(var)`` when finite and positive, else ``max(|y|, 1e-8)``."""
    if bool(torch.isfinite(var)) and bool(var > 0):
        return torch.sqrt(var)
    return torch.clamp(torch.abs(y), min=1e-8)


def _rate(param, n: int):
    """``param if param > 1/n else 1/n`` (Welford-like early rate)."""
    inv = 1.0 / n
    return param if bool(param > inv) else _c(inv)


# ---------------------------------------------------------------------------
# leaf: centred Gaussian, Welford variance
# ---------------------------------------------------------------------------

class Leaf(nn.Module):
    def __init__(self, k: int = 1):
        super().__init__()
        self.k = k

    def forward(self, y, state=None):
        y = _t(y)
        if state is None:
            state = {"var": running_var_init()}
        state["var"] = running_var_update(state["var"], y)
        _, var = running_var_get(state["var"])
        std = _scale_or_bootstrap(var, y)
        d = TorchDist.gaussian(0.0, std)
        return [d] * self.k, state


def leaf(k: int = 1) -> Leaf:
    return Leaf(k)


# ---------------------------------------------------------------------------
# scale_mixture_leaf: fixed scale dictionary, likelihood-EM weights
# ---------------------------------------------------------------------------

class ScaleMixtureLeaf(nn.Module):
    def __init__(self, k: int = 1, gamma: float = 0.02, scale_alpha: float = 0.01,
                 scales: tuple = _SCALE_BASIS):
        super().__init__()
        self.k = k
        self.gamma = _p(gamma)
        self.scale_alpha = _p(scale_alpha)
        self.C = tuple(float(c) for c in scales)
        self.one_idx = min(range(len(self.C)), key=lambda i: abs(self.C[i] - 1.0))

    def _fresh(self):
        w = [_c(1e-6) for _ in self.C]
        w[self.one_idx] = _c(1.0)
        return {"v": _zero(), "w": w, "n": 0}

    def forward(self, y, state=None):
        y = _t(y)
        C, K = self.C, len(self.C)
        if state is None:
            state = self._fresh()
        state["n"] += 1
        a = _rate(self.scale_alpha, state["n"])
        state["v"] = (1 - a) * state["v"] + a * y * y
        var = state["v"]
        sigma = _scale_or_bootstrap(var, y)
        z = y / sigma
        w = state["w"]
        dens = [w[i] * torch.exp(-0.5 * z * z / (C[i] * C[i])) / C[i] for i in range(K)]
        total = _psum(dens)
        if bool(total > 0):
            g = _rate(self.gamma, state["n"])
            state["w"] = [(1 - g) * w[i] + g * dens[i] / total for i in range(K)]
        d = _dist(state["w"], [_zero()] * K, [C[i] * sigma for i in range(K)])
        return [d] * self.k, state


def scale_mixture_leaf(k: int = 1, gamma: float = 0.02, scale_alpha: float = 0.01,
                       scales: tuple = _SCALE_BASIS) -> ScaleMixtureLeaf:
    return ScaleMixtureLeaf(k, gamma, scale_alpha, scales)


# ---------------------------------------------------------------------------
# crps_leaf: same form, exponentiated-gradient weights on the mixture CRPS
# ---------------------------------------------------------------------------

def _Phi(x):
    return 0.5 * (1.0 + torch.erf(x / _S2))


def _phi(x):
    return torch.exp(-0.5 * x * x) * _INV


def _abs_normal(m, s: float):
    """E|N(m, s^2)| for a tensor ``m`` and a float scale ``s``."""
    if s <= 0:
        return torch.abs(m)
    z = m / s
    return m * (2.0 * _Phi(z) - 1.0) + 2.0 * s * _phi(z)


class CrpsLeaf(nn.Module):
    def __init__(self, k: int = 1, eta: float = 1.0, scale_alpha: float = 0.01, scales: tuple = FINE):
        super().__init__()
        self.k = k
        self.eta = _p(eta)
        self.scale_alpha = _p(scale_alpha)
        self.C = tuple(float(c) for c in scales)
        K = len(self.C)
        self.B = [[math.sqrt(self.C[a] * self.C[a] + self.C[b] * self.C[b]) * _A0 for b in range(K)]
                  for a in range(K)]
        self.one_idx = min(range(K), key=lambda i: abs(self.C[i] - 1.0))

    def _fresh(self):
        w = [_c(1e-6) for _ in self.C]
        w[self.one_idx] = _c(1.0)
        return {"v": _zero(), "w": w, "n": 0}

    def forward(self, y, state=None):
        y = _t(y)
        C, K, B = self.C, len(self.C), self.B
        if state is None:
            state = self._fresh()
        state["n"] += 1
        a = _rate(self.scale_alpha, state["n"])
        state["v"] = (1 - a) * state["v"] + a * y * y
        sig = _scale_or_bootstrap(state["v"], y)
        z = y / sig
        w = state["w"]
        g = [_abs_normal(-z, C[c]) - _psum(w[j] * B[c][j] for j in range(K)) for c in range(K)]
        gm = _psum(g) / K
        e = [-self.eta * (g[c] - gm) for c in range(K)]
        emax = e[0]
        for x in e[1:]:
            emax = torch.maximum(emax, x)
        nw = [w[c] * torch.exp(e[c] - emax) for c in range(K)]
        Z = _psum(nw)
        if not (bool(Z > 0.0) and bool(torch.isfinite(Z))):
            nw = list(w)
            Z = _psum(nw)
        state["w"] = [x / Z for x in nw]
        d = _dist(state["w"], [_zero()] * K, [C[c] * sig for c in range(K)])
        return [d] * self.k, state


def crps_leaf(k: int = 1, eta: float = 1.0, scale_alpha: float = 0.01, scales: tuple = FINE) -> CrpsLeaf:
    return CrpsLeaf(k, eta, scale_alpha, scales)


# ---------------------------------------------------------------------------
# garch_leaf: GARCH(1,1) conditional variance, scale-mixture tails
# ---------------------------------------------------------------------------

class GarchLeaf(nn.Module):
    """The ``(alpha, beta, omega)`` refit is a grid argmin over the residual
    window; the selection is made on detached floats with the reference's own
    arithmetic (so the choice is identical), and the chosen ``omega`` is then
    rebuilt from the tensor window variance so gradients flow through it."""

    def __init__(self, k: int = 1, gamma: float = 0.02, refit_every: int = 40,
                 min_obs: int = 80, window: int = 400, scales: tuple = _SCALE_BASIS):
        super().__init__()
        self.k = k
        self.gamma = _p(gamma)
        self.refit_every, self.min_obs, self.window = refit_every, min_obs, window
        self.C = tuple(float(c) for c in scales)
        self.one_idx = min(range(len(self.C)), key=lambda i: abs(self.C[i] - 1.0))

    def _fresh(self):
        w = [_c(1e-6) for _ in self.C]
        w[self.one_idx] = _c(1.0)
        return {"h": _zero(), "s2": _zero(), "n": 0, "omega": _zero(), "alpha": _c(0.05),
                "beta": _c(0.90), "buf": deque(maxlen=self.window), "w": w, "last_r2": _zero()}

    def forward(self, y, state=None):
        y = _t(y)
        C, K = self.C, len(self.C)
        s = state if state is not None else self._fresh()
        s["n"] += 1
        a0 = _rate(_c(0.02), s["n"])
        s["s2"] = (1 - a0) * s["s2"] + a0 * y * y
        if bool(s["s2"] <= 0):
            s["s2"] = torch.clamp(y * y, min=1e-12)

        if s["n"] == 1:
            h = s["s2"]
        else:
            h = s["omega"] + s["alpha"] * s["last_r2"] + s["beta"] * s["h"]
        if bool(h <= 1e-300):
            h = s["s2"]
        s["h"] = h
        s["last_r2"] = y * y
        s["buf"].append(y)

        if s["n"] >= self.min_obs and s["n"] % self.refit_every == 0 and len(s["buf"]) >= self.min_obs:
            resid = list(s["buf"])
            s2_t = _psum(r * r for r in resid) / len(resid)
            if bool(s2_t > 0):
                rf = [float(r.detach()) for r in resid]
                s2 = sum(r * r for r in rf) / len(rf)
                best = None
                best_v = float("inf")
                for (al, be) in _GARCH_AB_GRID:
                    base = (1.0 - al - be) * s2
                    for c in _GARCH_OMEGA_MULT:
                        om = base * c if base * c > 1e-12 else 1e-12
                        hh = om / (1.0 - al - be)
                        v = 0.0
                        prev = None
                        for r in rf:
                            if prev is not None:
                                hh = om + al * (prev * prev) + be * hh
                                if hh <= 1e-300:
                                    hh = 1e-300
                            v += math.log(hh) + (r * r) / hh
                            prev = r
                        if v < best_v:
                            best_v, best = v, (al, be, c)
                al, be, c = best
                base_t = (1.0 - al - be) * s2_t
                om_t = base_t * c if bool(base_t * c > 1e-12) else _c(1e-12)
                s["omega"], s["alpha"], s["beta"] = om_t, _c(al), _c(be)

        sigma = _scale_or_bootstrap(h, y)
        z = y / sigma
        w = s["w"]
        dens = [w[i] * torch.exp(-0.5 * z * z / (C[i] * C[i])) / C[i] for i in range(K)]
        total = _psum(dens)
        if bool(total > 0):
            g = _rate(self.gamma, s["n"])
            s["w"] = [(1 - g) * w[i] + g * dens[i] / total for i in range(K)]

        h_next = s["omega"] + s["alpha"] * y * y + s["beta"] * h
        if not (bool(torch.isfinite(h_next)) and bool(h_next > 1e-300)):
            h_next = s["s2"]
        sigma_next = torch.sqrt(h_next)
        d = _dist(s["w"], [_zero()] * K, [C[i] * sigma_next for i in range(K)])
        return [d] * self.k, s


def garch_leaf(k: int = 1, gamma: float = 0.02, refit_every: int = 40,
               min_obs: int = 80, window: int = 400, scales: tuple = _SCALE_BASIS) -> GarchLeaf:
    return GarchLeaf(k, gamma, refit_every, min_obs, window, scales)


# ---------------------------------------------------------------------------
# conforming_leaf: smoothed empirical law with a reference component
# ---------------------------------------------------------------------------

class _Keyed:
    """Sort key so ``bisect.insort`` orders 0-d tensors by value."""
    __slots__ = ("t", "v")

    def __init__(self, t):
        self.t = t
        self.v = float(t.detach())

    def __lt__(self, other):
        return self.v < other.v


class ConformingLeaf(nn.Module):
    def __init__(self, k: int = 1, max_centers: int = 96, ref_weight: float = 0.01, warmup: int = 30):
        super().__init__()
        self.k = k
        self.max_centers, self.warmup = max_centers, warmup
        self.ref_weight = _p(ref_weight)

    def forward(self, y, state=None):
        y = _t(y)
        if state is None:
            state = {"vals": [], "n": 0, "mu": _zero(), "m2": _zero()}
        bisect.insort(state["vals"], _Keyed(y))
        state["n"] += 1
        n = state["n"]
        d0 = y - state["mu"]
        state["mu"] = state["mu"] + d0 / n
        state["m2"] = state["m2"] + d0 * (y - state["mu"])
        var = state["m2"] / (n - 1) if n > 1 else torch.clamp(y * y, min=1e-12)
        std = torch.sqrt(var) if bool(var > 0) else torch.clamp(torch.abs(y), min=1e-8)

        if n < self.warmup:
            return [TorchDist.gaussian(0.0, std)] * self.k, state

        vals = state["vals"]
        m = min(self.max_centers, n)
        centers = [vals[min(n - 1, int((i + 0.5) * n / m))].t for i in range(m)]
        std_pos = std if bool(std > 0) else _c(1.0)
        h = torch.maximum(torch.maximum(1.06 * std * n ** (-0.2), 1e-8 * std_pos), _c(1e-12))
        w_body = (1.0 - self.ref_weight) / m
        ws = [w_body] * m + [self.ref_weight]
        ms = list(centers) + [_zero()]
        ss = [h] * m + [std]
        return [_dist(ws, ms, ss)] * self.k, state


def conforming_leaf(k: int = 1, max_centers: int = 96, ref_weight: float = 0.01,
                    warmup: int = 30) -> ConformingLeaf:
    return ConformingLeaf(k, max_centers, ref_weight, warmup)


# ---------------------------------------------------------------------------
# ensemble_leaf: score-weighted conforming + scale-mixture
# ---------------------------------------------------------------------------

class EnsembleLeaf(nn.Module):
    def __init__(self, k: int = 1, max_centers: int = 96, ref_weight: float = 0.01,
                 eta: float = 0.8, forget: float = 0.995, warmup: int = 30):
        super().__init__()
        self.k = k
        self.eta = _p(eta)
        self.forget = _p(forget)
        self.conf = ConformingLeaf(1, max_centers, ref_weight, warmup)
        self.mixl = ScaleMixtureLeaf(1)

    def forward(self, y, state=None):
        y = _t(y)
        if state is None:
            state = {"conf": None, "mix": None, "lw": [_zero(), _zero()], "pend": [None, None]}
        lw = list(state["lw"])
        for i, pend in enumerate(state["pend"]):
            if pend is not None:
                lp = pend.logpdf(y)
                if bool(lp > 20.0):
                    lp = _c(20.0)
                elif not bool(lp >= -20.0):
                    lp = _c(-20.0)
                lw[i] = self.forget * lw[i] + self.eta * lp
        state["lw"] = lw
        dc, state["conf"] = self.conf(y, state["conf"])
        dm, state["mix"] = self.mixl(y, state["mix"])
        state["pend"] = [dc[0], dm[0]]
        mx = torch.maximum(lw[0], lw[1])
        ws = [torch.exp(v - mx) for v in lw]
        d = _combine([dc[0], dm[0]], ws)
        return [d] * self.k, state


def _combine(dists, weights) -> TorchDist:
    """``Dist.combine``: outer weights over their compensated sum, then the
    ``Dist`` constructor's compensated normalisation."""
    w_total = _psum(weights)
    ws, ms, ss = [], [], []
    for d, wo in zip(dists, weights):
        for wi, m, s in zip(d.w, d.m, d.s):
            ws.append(wo / w_total * wi); ms.append(m); ss.append(s)
    return _dist(ws, ms, ss)


def ensemble_leaf(k: int = 1, max_centers: int = 96, ref_weight: float = 0.01,
                  eta: float = 0.8, forget: float = 0.995, warmup: int = 30) -> EnsembleLeaf:
    return EnsembleLeaf(k, max_centers, ref_weight, eta, forget, warmup)
