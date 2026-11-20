"""Exact pushforward of a predictive through a monotone coordinate map.

The component-wise delta method used by the nonlinear transform inverses
(``yeo_johnson``, ``power_transform``) maps each mixture component to
``N(inv(m), s * dinv(m))``. That is cheap and stays a plain :class:`Dist`,
and it has a structural blind spot: the inner components of a conjugated
forecaster all sit near the same location, so the mapped mixture comes out
location-symmetric about the mapped median. The skew that the coordinate
change is supposed to express lives in the curvature of the map *within* a
component's width, which the delta method linearizes away. The error grows
with the predictive spread, hence with horizon: measured on 120 strictly
positive FRED level series under the README's standalone composition
(leaf under OU under Yeo-Johnson, k=10), exact mapping beats the delta
method by a median +0.018 nats at h=10 (72% of series) for lambda=0 and
+0.015 (78%) for lambda=0.5, while h=1 is a wash.

:class:`PushforwardDist` is the exact treatment, the same idiom as
``SplicedDist``: keep the inner predictive in the transformed z-coordinate
and answer queries through the change of variables

    F_Y(y)      = F_Z(z(y))
    log p_Y(y)  = log p_Z(z(y)) + log dz/dy
    Q_Y(p)      = y(Q_Z(p))

The map can be supplied analytically or represented by a strictly increasing
table. CRPS uses numerical quadrature in either case.

Compatibility: consumers that need mixture components (``Dist.combine`` in
ensemble warm-up, the sticky projection) get a ``components`` property that
maps each inner Gaussian by moment matching. When the inner has no Gaussian
components, the compatibility view is a single Gaussian with moments estimated
on a quantile grid. The forecast's own queries still use the original inner.

Everything is stdlib-only and the state is pure data, as everywhere else.
"""

from __future__ import annotations
import bisect
import math

_SQRT2 = math.sqrt(2.0)
_SQRTPI = math.sqrt(math.pi)

# 7-point Gauss-Hermite nodes/weights (physicists'), for E[g(Z)], Z ~ N(0,1):
# E[g(Z)] ~= sum w_i/sqrt(pi) * g(sqrt(2) x_i). Exact for polynomials to
# degree 13, which pins pushforward means to ~1e-12 at practical spreads.
_GH7 = (
    (-2.6519613568352334, 9.717812450995192e-04),
    (-1.6735516287674714, 5.451558281912703e-02),
    (-0.8162878828589647, 4.256072526101278e-01),
    (0.0, 8.102646175568073e-01),
    (0.8162878828589647, 4.256072526101278e-01),
    (1.6735516287674714, 5.451558281912703e-02),
    (2.6519613568352334, 9.717812450995192e-04),
)


def _quantile_rule(n: int) -> tuple:
    # Fourth-power odds give the tails finer resolution under nonlinear maps.
    edges = [i**4 / (i**4 + (n - i)**4) for i in range(n + 1)]
    return tuple(((lo + hi) * 0.5, hi - lo) for lo, hi in zip(edges, edges[1:]))


_QUANTILE_RULE = _quantile_rule(257)


def _exp_or_inf(x: float) -> float:
    try:
        return math.exp(x)
    except OverflowError:
        return math.inf


def interp_table(x: float, xs: list, fs: list) -> float:
    """Piecewise-linear with linear extrapolation from the end segments."""
    i = bisect.bisect_left(xs, x)
    if i <= 0:
        i = 1
    elif i >= len(xs):
        i = len(xs) - 1
    x0, x1 = xs[i - 1], xs[i]
    return fs[i - 1] + (fs[i] - fs[i - 1]) * (x - x0) / (x1 - x0)


def table_from_map(inv_fn, z_lo: float, z_hi: float, nodes: int = 400):
    """(ys, zs) knots of a monotone map y = inv_fn(z) on [z_lo, z_hi].

    Knots where inv_fn fails to strictly increase (float ties on flat
    stretches) are dropped so every segment has a positive, finite slope.
    """
    z_hi = max(z_hi, z_lo + 1e-9)
    step = (z_hi - z_lo) / nodes
    ys, zs = [], []
    for j in range(nodes + 1):
        z = z_lo + step * j
        y = inv_fn(z)
        if not ys or y > ys[-1]:
            ys.append(y)
            zs.append(z)
    if len(ys) < 2:
        y0 = inv_fn(z_lo)
        ys, zs = [y0, y0 + 1e-9], [z_lo, z_lo + 1e-9]
    return ys, zs


class PushforwardDist:
    """A z-space predictive pushed through a monotone y <-> z map.

    Supply a table (``ys``, ``zs``) or an analytic map with ``inv_fn``,
    ``fwd_fn`` and ``log_jacobian_fn`` (log(dz/dy), evaluated at z). With a table
    and an optional inverse, the Jacobian is estimated by finite differences.
    ``component_moments_fn`` optionally gives the mapped mean and standard
    deviation of a Gaussian component. ``scaled_inv_fn(z, weight)`` evaluates
    the inverse times a positive weight, useful when the inverse overflows.
    """

    __slots__ = ("inner", "ys", "zs", "inv_fn", "fwd_fn", "log_jacobian_fn",
                 "component_moments_fn", "scaled_inv_fn", "_comps", "_grid")

    def __init__(self, inner, ys: list | None = None, zs: list | None = None,
                 inv_fn=None, fwd_fn=None, *, log_jacobian_fn=None,
                 component_moments_fn=None, scaled_inv_fn=None):
        self.inner = inner
        self.ys = ys
        self.zs = zs
        self.inv_fn = inv_fn
        self.fwd_fn = fwd_fn
        self.log_jacobian_fn = log_jacobian_fn
        self.component_moments_fn = component_moments_fn
        self.scaled_inv_fn = scaled_inv_fn
        self._comps = None
        self._grid = None

    # --- the map -----------------------------------------------------------

    def _z(self, y: float) -> float:
        # No clamp (skaters#221): interp_table already extrapolates linearly
        # past the table ends, which is the map's actual, exact behavior out
        # there. Clamping the OBSERVATION's coordinate made every query at a
        # large y (even under the identity map) return the same constant
        # density -- a non-integrable tail and a saturated CRPS breakpoint,
        # not a bounded score. A study that wants bounded scores floors the
        # reported logpdf/CRPS itself (bench_core.score_dist already does),
        # which does not require the distribution's own coordinate map to lie.
        if self.fwd_fn is not None:
            return self.fwd_fn(y)
        return interp_table(y, self.ys, self.zs)

    def _y(self, z: float) -> float:
        if self.inv_fn is not None:
            return self.inv_fn(z)
        return interp_table(z, self.zs, self.ys)

    def _slope(self, y: float) -> float:
        """dz/dy at y (central difference of the exact map when available,
        segment secant otherwise; end segments extend beyond the table)."""
        if self.fwd_fn is not None:
            h = 1e-5 * (1.0 + abs(y))
            za, zb = self.fwd_fn(y + h), self.fwd_fn(y - h)
            if math.isfinite(za) and math.isfinite(zb) and za > zb:
                return (za - zb) / (2.0 * h)
        if self.inv_fn is not None:
            z = self._z(y)
            h = 1e-5 * (1.0 + abs(z))
            dy = self.inv_fn(z + h) - self.inv_fn(z - h)
            if dy > 0.0:
                return 2.0 * h / dy
        ys, zs = self.ys, self.zs
        i = bisect.bisect_left(ys, y)
        i = min(max(i, 1), len(ys) - 1)
        return (zs[i] - zs[i - 1]) / (ys[i] - ys[i - 1])

    # --- queries (exact) ----------------------------------------------------

    def logpdf(self, x: float) -> float:
        z = self._z(x)
        if math.isinf(z):                       # x on or past a bound of the map
            return -math.inf
        if math.isnan(z):
            return math.nan
        if self.log_jacobian_fn is not None:
            return self.inner.logpdf(z) + self.log_jacobian_fn(z)
        return self.inner.logpdf(z) + math.log(self._slope(x))

    def pdf(self, x: float) -> float:
        return _exp_or_inf(self.logpdf(x))

    def cdf(self, x: float) -> float:
        z = self._z(x)
        if math.isinf(z):
            return 0.0 if z < 0 else 1.0
        if math.isnan(z):
            return math.nan
        return self.inner.cdf(z)

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 2100) -> float:
        return self._y(self.inner.quantile(p, tol=tol, max_iter=max_iter))

    def crps(self, x: float) -> float:
        """CRPS by quadrature over quantiles or over the table in z-space."""
        if not math.isfinite(x):
            return abs(x)
        if self.fwd_fn is not None or self.zs is None:
            return self._crps_from_quantiles(x)

        zstar = self._z(x)
        zs = self.zs
        s_lo = 1.0 / self._slope(self.ys[0])
        s_hi = 1.0 / self._slope(self.ys[-1])
        base = [zs[0] - 8.0, zs[0] - 6.0, zs[0] - 4.0, zs[0] - 2.0, zs[0] - 1.0]
        base += zs
        base += [zs[-1] + 1.0, zs[-1] + 2.0, zs[-1] + 4.0, zs[-1] + 6.0, zs[-1] + 8.0]
        base += [zstar - 1.0, zstar, zstar + 1.0]
        base = sorted(set(base))
        nodes = [base[0]]
        for z in base[1:]:
            lo = nodes[-1]
            gap = z - lo
            if gap > 0.1:
                pieces = min(int(gap / 0.1) + 1, 40)
                step = gap / pieces
                nodes.extend(lo + step * (j + 1) for j in range(pieces - 1))
            nodes.append(z)
        cdf = self.inner.cdf
        total = 0.0
        prev_z = nodes[0]
        c_prev = cdf(prev_z)
        for z in nodes[1:]:
            c = cdf(z)
            ind = 1.0 if prev_z >= zstar else 0.0
            g0 = (c_prev - ind) ** 2
            g1 = (c - ind) ** 2
            if z <= zs[0]:
                yp = s_lo
            elif prev_z >= zs[-1]:
                yp = s_hi
            else:
                yp = (self._y(z) - self._y(prev_z)) / (z - prev_z)
            total += 0.5 * (g0 + g1) * (z - prev_z) * yp
            prev_z, c_prev = z, c
        return total

    def _crps_from_quantiles(self, x: float) -> float:
        # Integrate twice the pinball loss, including observations outside the
        # support. Apply the weights first if the unweighted difference overflows.
        total = 0.0
        for q, (p, w) in zip(self._qgrid(), _QUANTILE_RULE):
            weight = 2.0 * w * ((1.0 - p) if q >= x else p)
            gap = abs(q - x)
            if math.isfinite(gap):
                total += weight * gap
            else:
                weighted_q = weight * q
                if math.isinf(q) and self.scaled_inv_fn is not None:
                    weighted_q = self.scaled_inv_fn(self.inner.quantile(p), weight)
                total += abs(weighted_q - weight * x)
        return total

    # --- affine maps ----------------------------------------------------------

    def affine(self, a: float, b: float) -> "PushforwardDist":
        """The law of a*Y + b, still a pushforward of (a reflection of) the
        same inner. a > 0 composes the map; a < 0 reflects the inner with
        ``inner.scale(-1)`` so the composed map stays increasing."""
        a, b = float(a), float(b)
        if a == 0.0 or not math.isfinite(a) or not math.isfinite(b):
            raise ValueError("affine needs a finite nonzero a and a finite b")
        r = 1.0 if a > 0 else -1.0          # z' = r * z
        inner = self.inner if r > 0 else self.inner.scale(-1.0)
        inv, fwd, lj = self.inv_fn, self.fwd_fn, self.log_jacobian_fn
        cmf, sinv = self.component_moments_fn, self.scaled_inv_fn
        log_a = math.log(abs(a))
        ys = zs = None
        if self.ys is not None:
            ys = [a * y + b for y in self.ys]
            zs = [r * z for z in self.zs]
            if r < 0:
                ys.reverse()
                zs.reverse()
        return PushforwardDist(
            inner, ys, zs,
            inv_fn=None if inv is None else (lambda z: a * inv(r * z) + b),
            fwd_fn=None if fwd is None else (lambda y: r * fwd((y - b) / a)),
            log_jacobian_fn=None if lj is None else (lambda z: lj(r * z) - log_a),
            component_moments_fn=None if cmf is None else (
                lambda m, s: (lambda ms: (a * ms[0] + b, abs(a) * ms[1]))(cmf(r * m, s))),
            scaled_inv_fn=None if sinv is None else (
                lambda z, w: a * sinv(r * z, w) + w * b))

    def shift(self, delta: float) -> "PushforwardDist":
        return self.affine(1.0, delta)

    def scale(self, factor: float) -> "PushforwardDist":
        if factor == 0:
            raise ValueError("scale factor must be nonzero")
        return self.affine(factor, 0.0)

    # --- Dist-compatibility shim ---------------------------------------------

    @property
    def components(self) -> list:
        """Moment-matched mixture components in y-space (lazy, cached).

        For a spliced or already transformed inner, return one Gaussian fitted
        to its mapped quantiles. This compatibility approximation can lose a
        support bound when a caller uses it to build a plain ``Dist``.
        """
        if self._comps is None:
            inner_comps = (None if isinstance(self.inner, PushforwardDist)
                           else getattr(self.inner, "components", None))
            if inner_comps is None:
                q = self._qgrid()
                mu = sum(w * y for y, (_, w) in zip(q, _QUANTILE_RULE))
                sd = math.inf if not math.isfinite(mu) else math.hypot(*(
                    math.sqrt(w) * (y - mu) for y, (_, w) in zip(q, _QUANTILE_RULE)
                ))
                self._comps = [(1.0, mu, sd)]
            else:
                moments = self.component_moments_fn or self._gaussian_moments
                self._comps = [(w, *moments(m, s)) for w, m, s in inner_comps if w > 0.0]
        return self._comps

    def _gaussian_moments(self, m: float, s: float) -> tuple[float, float]:
        # Centered quadrature (skaters#225). hypot also keeps std representable
        # when the corresponding variance is too large or small for a float.
        node_ys = [self._y(m + s * _SQRT2 * x) for x, _ in _GH7]
        mu = sum((w / _SQRTPI) * y for y, (_, w) in zip(node_ys, _GH7))
        if not math.isfinite(mu):
            return mu, math.inf
        sd = math.hypot(*(math.sqrt(w / _SQRTPI) * (y - mu)
                          for y, (_, w) in zip(node_ys, _GH7)))
        return mu, max(sd, 1e-12)

    def _qgrid(self) -> list:
        """Cache mapped quantiles used by numerical moments and CRPS."""
        if self._grid is None:
            self._grid = [self.quantile(p) for p, _ in _QUANTILE_RULE]
        return self._grid

    @property
    def mean(self) -> float:
        return sum(w * m for w, m, _ in self.components)

    @property
    def var(self) -> float:
        sd = self.std
        return sd * sd

    @property
    def std(self) -> float:
        comps = self.components
        if len(comps) == 1:
            return comps[0][2]
        mu = self.mean
        if not math.isfinite(mu):
            return math.inf
        return math.hypot(*(math.sqrt(w) * math.hypot(s, m - mu) for w, m, s in comps))

    def __repr__(self) -> str:
        return (f"PushforwardDist(knots={len(self.ys or ())}, "
                f"inner={self.inner!r})")

    def __len__(self) -> int:
        return len(self.components)
