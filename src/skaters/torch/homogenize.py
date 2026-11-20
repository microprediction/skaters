"""Homogenized scale-mixture correction in torch: the twin of
:mod:`skaters.homogenize`.

The candidate pool (each candidate's filter state ``q``, its discounted
log-weight and its guard run) is driven by matured PITs and is pure float
bookkeeping, so it runs on the reference's own functions on Python floats:
it is a constant in the graph. The state layout is the reference's key for
key (docs/STATE.md): ``base``, ``raw``, ``pending``, ``cell`` and
``correction``.

What is differentiable is the corrected predictive, :class:`TorchHomogenizedDist`.
Its ``logpdf`` and ``cdf`` are torch expressions in the base predictive's
cdf and density at ``z = Phi^-1(F(y))``. The normal quantile is the
reference's bisection on the float value, with its first-order dependence on
``F(y)`` attached through the implicit derivative ``1 / phi(z)``, so the value
is the reference's exactly and the gradient is the true one. ``quantile``,
the moments and ``crps`` run on the reference :class:`HomogenizedDist` built
from the detached base, as :class:`TorchSplicedDist` and the pushforward
do, so they carry no gradient and cannot drift from the reference.
"""

from __future__ import annotations

import math

import torch
from torch import nn

import importlib

ref = importlib.import_module("skaters.homogenize")  # the module, not the exported function
from skaters.homogenize import make_candidates, candidate_weights, cell_step  # noqa: F401
from skaters.torch.dist import DTYPE, _t

__all__ = ["homogenize", "make_candidates", "TorchHomogenizedDist", "HomogenizedDist",
           "Homogenize", "cell_step", "candidate_weights"]

_EPS = ref._EPS
_SQRT2 = math.sqrt(2.0)
_LOG_SQRT2PI = ref._LOG_SQRT2PI
_INV_SQRT2PI = 1.0 / math.sqrt(2.0 * math.pi)


def _floats(x):
    """The same nesting with every 0-d tensor replaced by its float."""
    if isinstance(x, torch.Tensor):
        return float(x.detach())
    if isinstance(x, list):
        return [_floats(v) for v in x]
    if isinstance(x, dict):
        return {key: _floats(v) for key, v in x.items()}
    return x


def _phi_inv_t(u):
    """Phi^-1 on a 0-d tensor: the reference's value (Dist bisection on the
    float) plus a value-zero term carrying the derivative 1 / phi(z)."""
    uf = float(u.detach())
    z = ref._phi_inv(uf)
    zt = torch.as_tensor(z, dtype=DTYPE)
    if not math.isfinite(z) or not u.requires_grad:
        return zt
    dens = _INV_SQRT2PI * math.exp(-0.5 * z * z)
    if dens <= 0.0:
        return zt
    return zt + (u - u.detach()) / dens


def _logg_t(z, correction):
    """``homogenize.logg`` on a tensor z: log-sum-exp over the pooled
    (weight, scale) pairs, in the reference's order."""
    terms = []
    for w, s in zip(correction["weights"], correction["scales"]):
        if w <= 0.0:
            continue
        zs = z / s
        terms.append(math.log(w) - math.log(s) + (-0.5 * zs * zs - _LOG_SQRT2PI))
    if not terms:
        return torch.as_tensor(-math.inf, dtype=DTYPE)
    tt = torch.stack([t.reshape(()) for t in terms])
    best = torch.max(tt).detach()
    return best + torch.log(torch.sum(torch.exp(tt - best)))


class TorchHomogenizedDist:
    """The base torch predictive reshaped by a pooled scale-mixture correction
    (``{"weights": [...], "scales": [...]}`` of floats)."""

    __slots__ = ("base", "correction", "_ref")

    def __init__(self, base, correction: dict):
        self.base = base
        self.correction = correction
        self._ref = None

    def to_reference(self) -> ref.HomogenizedDist:
        if self._ref is None:
            self._ref = ref.HomogenizedDist(self.base.to_reference(), self.correction)
        return self._ref

    def _z(self, y):
        u = torch.clamp(_t(self.base.cdf(y)), _EPS, 1.0 - _EPS)
        return _phi_inv_t(u)

    def cdf(self, y):
        z = self._z(_t(y))
        total = torch.zeros((), dtype=DTYPE)
        for w, s in zip(self.correction["weights"], self.correction["scales"]):
            total = total + w * (0.5 * (1.0 + torch.erf(z / s / _SQRT2)))
        return torch.clamp(total, _EPS, 1.0 - _EPS)

    def logpdf(self, y):
        y = _t(y)
        z = self._z(y)
        return _t(self.base.logpdf(y)) + _logg_t(z, self.correction) - (-0.5 * z * z - _LOG_SQRT2PI)

    def pdf(self, y):
        lp = self.logpdf(y)
        if bool(lp > -700.0):
            return torch.exp(lp)
        return torch.zeros((), dtype=DTYPE)

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
        return torch.as_tensor(self.to_reference().crps(float(_t(x).detach())), dtype=DTYPE)

    def __repr__(self) -> str:
        return f"TorchHomogenizedDist(components={len(self.correction['weights'])}, base={self.base!r})"


HomogenizedDist = TorchHomogenizedDist


def _plain(s: dict) -> None:
    """A state restored from JSON holds tensors where the pool keeps floats:
    convert the pool's parts back, in place."""
    cells = s["cell"]
    for j, c in enumerate(cells):
        if c is not None and isinstance(c["dynamic"][0]["q"], torch.Tensor):
            cells[j] = _floats(c)
    corr = s["correction"]
    for j, c in enumerate(corr):
        if c is not None and c["weights"] and isinstance(c["weights"][0], torch.Tensor):
            corr[j] = _floats(c)


class Homogenize(nn.Module):
    """Wrap a k-horizon torch skater with the homogenized correction."""

    def __init__(self, base, candidates=None, k: int = 1, couple: str = "none", lam: float = 0.25):
        super().__init__()
        assert k >= 1
        assert couple in ("none", "weights", "state", "shared")
        self.base = base
        self.candidates = candidates if candidates is not None else make_candidates()
        self.k = k
        self.couple = couple
        self.lam = float(lam)

    def forward(self, y, state=None):
        k, couple, candidates = self.k, self.couple, self.candidates
        yt = _t(y)
        yv = float(yt.detach())
        if state is None:
            state = {"base": None, "raw": None, "pending": [],
                     "cell": [None] * k, "correction": [None] * k}
        s = state
        _plain(s)

        pend = s["pending"]
        n = len(pend)
        with torch.no_grad():
            for m in range(1, k + 1):
                if m > n:
                    continue
                d_m = pend[n - m][m - 1]
                u = ref._clamp01(float(d_m.cdf(yv)))
                z = ref._phi_inv(u)
                if not (z == z):
                    continue
                slot = 0 if couple == "shared" else m - 1
                corr, s["cell"][slot] = ref.cell_step(z, s["cell"][slot], candidates)
                if couple == "shared":
                    for j in range(k):
                        s["correction"][j] = corr
                else:
                    s["correction"][m - 1] = corr

            if couple in ("weights", "state"):
                ref._couple(s["cell"], couple, self.lam, candidates)
                for m in range(k):
                    if s["cell"][m] is not None:
                        s["correction"][m] = ref._pool(candidates, s["cell"][m]["dynamic"])

        dists, s["base"] = self.base(yt, s["base"])
        s["raw"] = dists[0]
        pend.append(list(dists))
        if len(pend) > k:
            pend.pop(0)

        out = []
        for m in range(1, k + 1):
            d = dists[m - 1] if m - 1 < len(dists) else dists[-1]
            corr = s["correction"][m - 1]
            out.append(d if corr is None else TorchHomogenizedDist(d, corr))
        return out, s


def homogenize(base, candidates: tuple | None = None, k: int = 1,
               couple: str = "none", lam: float = 0.25) -> Homogenize:
    """Factory with the reference's name and signature."""
    return Homogenize(base, candidates=candidates, k=k, couple=couple, lam=lam)
