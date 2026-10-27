"""Gaussian mixture distribution on torch tensors: the differentiable twin of
:class:`skaters.dist.Dist`.

Same object, same arithmetic, different substrate: a mixture is three
float64 tensors ``w``, ``m``, ``s`` of equal length, and every query
(``pdf``, ``logpdf``, ``cdf``, ``crps``, moments, ``affine``) is a torch
expression, so gradients flow from a log score back to whatever produced the
components. Weights are normalised by their sum; a std of 0 is a point mass,
as in the reference. ``quantile`` is the reference bisection and carries no
gradient.

``to_reference`` / ``from_reference`` convert to and from the pure-Python
``Dist`` so the parity suite can compare the two ports component by
component.
"""

from __future__ import annotations

import math

import torch

_SQRT2 = math.sqrt(2.0)
_LOG_SQRT2PI = 0.5 * math.log(2.0 * math.pi)
DTYPE = torch.float64


def _t(x, dtype=DTYPE) -> torch.Tensor:
    if isinstance(x, torch.Tensor):
        return x.to(dtype)
    return torch.as_tensor(float(x), dtype=dtype)


class TorchDist:
    """A weighted mixture of Gaussians with tensor components."""

    __slots__ = ("w", "m", "s")

    def __init__(self, w, m, s, *, _trusted: bool = False):
        w = _stack(w); m = _stack(m); s = _stack(s)
        if not (w.shape == m.shape == s.shape) or w.ndim != 1 or w.numel() == 0:
            raise ValueError("TorchDist needs equal-length 1-D weight, mean and std tensors")
        if _trusted:
            self.w, self.m, self.s = w, m, s
            return
        total = w.sum()
        if not bool(torch.isfinite(total)) or not bool(total > 0):
            raise ValueError("total component weight must be positive")
        self.w, self.m, self.s = w / total, m, s

    # --- constructors ---------------------------------------------------

    @staticmethod
    def gaussian(mean=0.0, std=1.0) -> "TorchDist":
        return TorchDist([_t(mean) * 0 + 1.0], [_t(mean)], [_t(std)], _trusted=True)

    @staticmethod
    def from_components(components) -> "TorchDist":
        """From ``[(w, m, s), ...]`` of floats or 0-d tensors (normalised)."""
        return TorchDist([c[0] for c in components], [c[1] for c in components],
                         [c[2] for c in components])

    @staticmethod
    def from_reference(d) -> "TorchDist":
        """Exact copy of a :class:`skaters.dist.Dist` (weights kept bit for bit)."""
        w = [c[0] for c in d.components]; m = [c[1] for c in d.components]; s = [c[2] for c in d.components]
        return TorchDist(w, m, s, _trusted=True)

    def to_reference(self):
        from skaters.dist import Dist
        return Dist.trusted([(float(a), float(b), float(c)) for a, b, c in
                             zip(self.w.detach(), self.m.detach(), self.s.detach())])

    @staticmethod
    def combine(dists, weights=None) -> "TorchDist":
        n = len(dists)
        if n == 0:
            raise ValueError("combine needs at least one distribution")
        if weights is None:
            weights = [1.0 / n] * n
        wt = _stack(weights)
        total = wt.sum()
        parts_w, parts_m, parts_s = [], [], []
        for d, wo in zip(dists, wt):
            parts_w.append(wo / total * d.w); parts_m.append(d.m); parts_s.append(d.s)
        return TorchDist(torch.cat(parts_w), torch.cat(parts_m), torch.cat(parts_s))

    # --- queries ----------------------------------------------------------

    @property
    def components(self):
        """``[(w, m, s), ...]`` as 0-d tensors (reference-shaped)."""
        return list(zip(self.w, self.m, self.s))

    def _z(self, x):
        x = _t(x)
        return (x - self.m) / self.s

    def logpdf(self, x) -> torch.Tensor:
        """Log density, log-sum-exp over components. Point masses (s == 0)
        carry no density anywhere except exactly at their atom, as in the
        reference, where they contribute 0 to the sum."""
        x = _t(x)
        live = self.s > 0
        s = torch.where(live, self.s, torch.ones_like(self.s))
        z = (x - self.m) / s
        logw = torch.where(self.w > 0, torch.log(torch.clamp(self.w, min=1e-300)),
                           torch.full_like(self.w, -float("inf")))
        terms = logw - 0.5 * z * z - torch.log(s) - _LOG_SQRT2PI
        terms = torch.where(live, terms, torch.full_like(terms, -float("inf")))
        return torch.logsumexp(terms, dim=0)

    def pdf(self, x) -> torch.Tensor:
        return torch.exp(self.logpdf(x))

    def cdf(self, x) -> torch.Tensor:
        x = _t(x)
        live = self.s > 0
        s = torch.where(live, self.s, torch.ones_like(self.s))
        phi = 0.5 * (1.0 + torch.erf((x - self.m) / (s * _SQRT2)))
        step = (x >= self.m).to(DTYPE)
        return torch.sum(self.w * torch.where(live, phi, step))

    def crps(self, x) -> torch.Tensor:
        """Closed-form CRPS of a Gaussian mixture (Grimit et al. 2006)."""
        x = _t(x)
        t1 = torch.sum(self.w * _abs_expectation(self.m - x, self.s))
        sij = torch.sqrt(self.s[:, None] ** 2 + self.s[None, :] ** 2)
        t2 = torch.sum(self.w[:, None] * self.w[None, :] * _abs_expectation(self.m[:, None] - self.m[None, :], sij))
        return t1 - 0.5 * t2

    @property
    def mean(self) -> torch.Tensor:
        return torch.sum(self.w * self.m)

    @property
    def var(self) -> torch.Tensor:
        mu = self.mean
        return torch.sum(self.w * (self.s * self.s + (self.m - mu) * (self.m - mu)))

    @property
    def std(self) -> torch.Tensor:
        v = self.var
        return torch.where(v > 0, torch.sqrt(torch.clamp(v, min=0.0)), torch.zeros_like(v))

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100) -> torch.Tensor:
        """Inverse CDF by the reference bisection; no gradient."""
        if not 0 < p < 1:
            raise ValueError(f"quantile needs 0 < p < 1, got {p}")
        with torch.no_grad():
            mu = float(self.mean); sigma = math.sqrt(max(float(self.var), 0.0))
            lo = mu - 8 * sigma; hi = mu + 8 * sigma
            width = max(16 * sigma, 1e-12)
            for _ in range(120):
                if float(self.cdf(lo)) <= p:
                    break
                lo -= width; width *= 2.0
            else:
                raise ArithmeticError(f"could not bracket quantile p={p} from below")
            width = max(16 * sigma, 1e-12)
            for _ in range(120):
                if float(self.cdf(hi)) >= p:
                    break
                hi += width; width *= 2.0
            else:
                raise ArithmeticError(f"could not bracket quantile p={p} from above")
            for _ in range(max_iter):
                mid = 0.5 * (lo + hi)
                if float(self.cdf(mid)) < p:
                    lo = mid
                else:
                    hi = mid
                if hi - lo < tol:
                    break
            return torch.as_tensor(0.5 * (lo + hi), dtype=DTYPE)

    # --- transform support -----------------------------------------------

    def shift(self, delta) -> "TorchDist":
        return TorchDist(self.w, self.m + _t(delta), self.s, _trusted=True)

    def scale(self, factor) -> "TorchDist":
        f = _t(factor)
        return TorchDist(self.w, self.m * f, self.s * torch.abs(f), _trusted=True)

    def affine(self, a, b) -> "TorchDist":
        a = _t(a); b = _t(b)
        return TorchDist(self.w, a * self.m + b, torch.abs(a) * self.s, _trusted=True)

    def map(self, fn_m, fn_s) -> "TorchDist":
        """Component-wise ``(m, s) -> (fn_m(m, s), fn_s(m, s))``, weights kept."""
        return TorchDist(self.w, fn_m(self.m, self.s), fn_s(self.m, self.s), _trusted=True)

    def __len__(self) -> int:
        return int(self.w.numel())

    def __repr__(self) -> str:
        return f"TorchDist({self.to_reference().components})"


def _stack(xs) -> torch.Tensor:
    if isinstance(xs, torch.Tensor):
        return xs.to(DTYPE).reshape(-1)
    return torch.stack([_t(x).reshape(()) for x in xs]) if len(xs) else torch.empty(0, dtype=DTYPE)


def _abs_expectation(m, s):
    """E|N(m, s^2)| = m (2 Phi(m/s) - 1) + 2 s phi(m/s), with the s -> 0 limit |m|."""
    live = s > 0
    ss = torch.where(live, s, torch.ones_like(s))
    z = m / ss
    phi = torch.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    big_phi = 0.5 * (1.0 + torch.erf(z / _SQRT2))
    val = m * (2.0 * big_phi - 1.0) + 2.0 * ss * phi
    return torch.where(live, val, torch.abs(m))
