"""Exact pushforward in torch: the twin of :mod:`skaters.pushforward`.

:class:`TorchPushforwardDist` holds a torch predictive in the transformed
z-coordinate and a monotone map given as torch callables, so ``logpdf``,
``cdf`` and ``quantile`` are torch expressions through the change of
variables and differentiate in whatever produced the map (a Yeo-Johnson
lambda, a power) and the inner predictive. CRPS, the moments and the
moment-matched ``components`` run on the reference
:class:`skaters.pushforward.PushforwardDist` built from the same table and
the same maps on floats (as ``TorchDist.quantile`` runs the reference
search), so they carry no gradient and cannot drift from the reference.
"""

from __future__ import annotations

import bisect
import math

import torch

from skaters import pushforward as ref
from skaters.dist import Dist
from skaters.torch.dist import TorchDist, DTYPE, _t


def _f(x) -> float:
    return float(x.detach()) if isinstance(x, torch.Tensor) else float(x)


def _on_floats(fn):
    """A torch map as a float map (for the reference twin)."""
    if fn is None:
        return None
    return lambda *args: _f(fn(*(_t(a) for a in args)))


def _interp_t(x, xs_f: list, xs, fs):
    """interp_table on tensors: the segment is chosen on floats exactly as the
    reference chooses it, the arithmetic is torch."""
    i = bisect.bisect_left(xs_f, _f(x))
    if i <= 0:
        i = 1
    elif i >= len(xs_f):
        i = len(xs_f) - 1
    x0, x1 = xs[i - 1], xs[i]
    return fs[i - 1] + (fs[i] - fs[i - 1]) * (x - x0) / (x1 - x0)


def table_from_map(inv_fn, z_lo: float, z_hi: float, nodes: int = 400):
    """(ys, zs): ys tensors (differentiable in the map), zs floats; the knot
    selection is the reference's, on the float values."""
    z_hi = max(z_hi, z_lo + 1e-9)
    step = (z_hi - z_lo) / nodes
    ys, zs = [], []
    for j in range(nodes + 1):
        z = z_lo + step * j
        y = inv_fn(_t(z))
        if not ys or _f(y) > _f(ys[-1]):
            ys.append(y)
            zs.append(z)
    if len(ys) < 2:
        y0 = inv_fn(_t(z_lo))
        ys, zs = [y0, y0 + 1e-9], [z_lo, z_lo + 1e-9]
    return ys, zs


class TorchPushforwardDist:
    """A torch z-space predictive pushed through a monotone y <-> z map."""

    def __init__(self, inner, ys=None, zs=None, inv_fn=None, fwd_fn=None, *,
                 log_jacobian_fn=None, component_moments_fn=None, scaled_inv_fn=None):
        self.inner = inner
        self.ys = None if ys is None else [_t(y) for y in ys]
        self.zs = None if zs is None else [float(z) for z in zs]
        self.inv_fn = inv_fn
        self.fwd_fn = fwd_fn
        self.log_jacobian_fn = log_jacobian_fn
        self.component_moments_fn = component_moments_fn
        self.scaled_inv_fn = scaled_inv_fn
        self._ys_f = None if ys is None else [_f(y) for y in self.ys]
        self._zs_t = None if zs is None else [_t(z) for z in self.zs]
        self._ref = None

    # --- the reference twin (floats) ------------------------------------

    def to_reference(self) -> ref.PushforwardDist:
        if self._ref is None:
            cmf = self.component_moments_fn
            self._ref = ref.PushforwardDist(
                self.inner.to_reference(), self._ys_f, self.zs,
                inv_fn=_on_floats(self.inv_fn), fwd_fn=_on_floats(self.fwd_fn),
                log_jacobian_fn=_on_floats(self.log_jacobian_fn),
                component_moments_fn=None if cmf is None else (
                    lambda m, s: tuple(_f(v) for v in cmf(_t(m), _t(s)))),
                scaled_inv_fn=_on_floats(self.scaled_inv_fn))
        return self._ref

    # --- the map ----------------------------------------------------------

    def _z(self, y):
        if self.fwd_fn is not None:
            return self.fwd_fn(y)
        return _interp_t(y, self._ys_f, self.ys, self._zs_t)

    def _y(self, z):
        if self.inv_fn is not None:
            return self.inv_fn(z)
        return _interp_t(z, self.zs, self._zs_t, self.ys)

    def _slope(self, y):
        if self.fwd_fn is not None:
            h = 1e-5 * (1.0 + abs(_f(y)))
            za, zb = self.fwd_fn(y + h), self.fwd_fn(y - h)
            if math.isfinite(_f(za)) and math.isfinite(_f(zb)) and _f(za) > _f(zb):
                return (za - zb) / (2.0 * h)
        if self.inv_fn is not None:
            z = self._z(y)
            h = 1e-5 * (1.0 + abs(_f(z)))
            dy = self.inv_fn(z + h) - self.inv_fn(z - h)
            if _f(dy) > 0.0:
                return 2.0 * h / dy
        i = bisect.bisect_left(self._ys_f, _f(y))
        i = min(max(i, 1), len(self._ys_f) - 1)
        return (self._zs_t[i] - self._zs_t[i - 1]) / (self.ys[i] - self.ys[i - 1])

    # --- queries ----------------------------------------------------------

    def logpdf(self, x):
        x = _t(x)
        z = self._z(x)
        zf = _f(z)
        if math.isinf(zf):
            return torch.as_tensor(-math.inf, dtype=DTYPE)
        if math.isnan(zf):
            return torch.as_tensor(math.nan, dtype=DTYPE)
        if self.log_jacobian_fn is not None:
            return self.inner.logpdf(z) + self.log_jacobian_fn(z)
        return self.inner.logpdf(z) + torch.log(_t(self._slope(x)))

    def pdf(self, x):
        return torch.exp(self.logpdf(x))

    def cdf(self, x):
        x = _t(x)
        z = self._z(x)
        zf = _f(z)
        if math.isinf(zf):
            return torch.as_tensor(0.0 if zf < 0 else 1.0, dtype=DTYPE)
        if math.isnan(zf):
            return torch.as_tensor(math.nan, dtype=DTYPE)
        return self.inner.cdf(z)

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 2100):
        return _t(self._y(_t(self.inner.quantile(p, tol=tol, max_iter=max_iter))))

    def crps(self, x):
        return torch.as_tensor(self.to_reference().crps(_f(_t(x))), dtype=DTYPE)

    @property
    def components(self):
        return TorchDist.from_reference(Dist.trusted(self.to_reference().components)).components

    @property
    def mean(self):
        return torch.as_tensor(self.to_reference().mean, dtype=DTYPE)

    @property
    def var(self):
        return torch.as_tensor(self.to_reference().var, dtype=DTYPE)

    @property
    def std(self):
        return torch.as_tensor(self.to_reference().std, dtype=DTYPE)

    # --- affine maps ------------------------------------------------------

    def affine(self, a, b) -> "TorchPushforwardDist":
        a, b = _t(a), _t(b)
        af, bf = _f(a), _f(b)
        if af == 0.0 or not math.isfinite(af) or not math.isfinite(bf):
            raise ValueError("affine needs a finite nonzero a and a finite b")
        r = 1.0 if af > 0 else -1.0
        inner = self.inner if r > 0 else self.inner.scale(-1.0)
        inv, fwd, lj = self.inv_fn, self.fwd_fn, self.log_jacobian_fn
        cmf, sinv = self.component_moments_fn, self.scaled_inv_fn
        log_a = torch.log(torch.abs(a))
        ys = zs = None
        if self.ys is not None:
            ys = [a * y + b for y in self.ys]
            zs = [r * z for z in self.zs]
            if r < 0:
                ys.reverse()
                zs.reverse()
        return TorchPushforwardDist(
            inner, ys, zs,
            inv_fn=None if inv is None else (lambda z: a * inv(r * z) + b),
            fwd_fn=None if fwd is None else (lambda y: r * fwd((y - b) / a)),
            log_jacobian_fn=None if lj is None else (lambda z: lj(r * z) - log_a),
            component_moments_fn=None if cmf is None else (
                lambda m, s: (lambda ms: (a * ms[0] + b, torch.abs(a) * ms[1]))(cmf(r * m, s))),
            scaled_inv_fn=None if sinv is None else (
                lambda z, w: a * sinv(r * z, w) + w * b))

    def shift(self, delta) -> "TorchPushforwardDist":
        return self.affine(1.0, delta)

    def scale(self, factor) -> "TorchPushforwardDist":
        if _f(_t(factor)) == 0:
            raise ValueError("scale factor must be nonzero")
        return self.affine(factor, 0.0)

    def __repr__(self) -> str:
        return f"TorchPushforwardDist(knots={len(self.ys or ())}, inner={self.inner!r})"


def has_components(d) -> bool:
    """Python's ``getattr(d, "components", None) is not None``."""
    return getattr(d, "components", None) is not None


def pushforward(d, inv_fn) -> TorchPushforwardDist:
    """The exact pushforward of ``d`` through the monotone torch map ``inv_fn``
    (transform._pushforward): table window [m - 10s, m + 10s] over a mixture,
    else the extreme quantiles padded by their own span."""
    if not isinstance(d, TorchPushforwardDist) and has_components(d):
        comps = [(_f(w), _f(m), _f(s)) for w, m, s in d.components]
        lo = min(m - 10.0 * s for _, m, s in comps)
        hi = max(m + 10.0 * s for _, m, s in comps)
    else:
        q_lo, q_hi = _f(d.quantile(1e-6)), _f(d.quantile(1.0 - 1e-6))
        lo, hi = 2.0 * q_lo - q_hi, 2.0 * q_hi - q_lo
    ys, zs = table_from_map(inv_fn, lo, hi)
    return TorchPushforwardDist(d, ys, zs, inv_fn=inv_fn)


def widen(d, delta, add):
    """Shift by ``delta`` and add Gaussian variance ``add`` (transform._widen):
    a mixture widens each component, a spliced law widens its body."""
    from skaters.torch.tails import TorchSplicedDist
    if isinstance(d, TorchSplicedDist):
        return d._with_body(widen(d.body, delta, add), False)
    if isinstance(d, TorchPushforwardDist):
        comps = d.components
        return TorchDist([w for w, _, _ in comps], [m + delta for _, m, _ in comps],
                         [torch.sqrt(s * s + add) for _, _, s in comps])
    return d.map(lambda m, s: m + delta, lambda m, s: torch.sqrt(s * s + add))
