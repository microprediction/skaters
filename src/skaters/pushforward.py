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

where y <-> z is a strictly increasing piecewise-linear table, so dz/dy is a
segment slope and CRPS integrates in z-coordinates with a constant Jacobian
per segment.

Compatibility: consumers that need mixture components (``Dist.combine`` in
ensemble warm-up, the sticky projection) get a ``components`` property that
maps each inner component by 7-point Gauss-Hermite moment matching through
the table. Moment matching is the KL(true || q) optimum among Gaussians, so
the shim is the best answer the plain-``Dist`` representation admits; exact
queries stay exact.

Everything is stdlib-only and the state is pure data, as everywhere else.
"""

from __future__ import annotations
import bisect
import math
from skaters.dist import Dist

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

    The map is carried two ways: a piecewise-linear (ys, zs) table, always
    present, used for the y -> z direction and the CRPS segment weights; and
    an optional ``inv_fn`` (the exact z -> y map) which, when given, makes
    the z -> y direction and the Jacobian exact instead of table-limited.
    """

    __slots__ = ("inner", "ys", "zs", "inv_fn", "_comps")

    def __init__(self, inner, ys: list, zs: list, inv_fn=None):
        self.inner = inner
        self.ys = ys
        self.zs = zs
        self.inv_fn = inv_fn
        self._comps = None

    # --- the map -----------------------------------------------------------

    def _z(self, y: float) -> float:
        # clamp the linear extrapolation: past ~8 z-units beyond the table the
        # density is negligible, and an extreme end-segment slope must not
        # launch z to a magnitude whose finite logpdf poisons a study mean
        z = interp_table(y, self.ys, self.zs)
        return min(max(z, self.zs[0] - 8.0), self.zs[-1] + 8.0)

    def _y(self, z: float) -> float:
        if self.inv_fn is not None:
            return self.inv_fn(z)
        return interp_table(z, self.zs, self.ys)

    def _slope(self, y: float) -> float:
        """dz/dy at y (central difference of the exact map when available,
        segment secant otherwise; end segments extend beyond the table)."""
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
        return self.inner.logpdf(self._z(x)) + math.log(self._slope(x))

    def pdf(self, x: float) -> float:
        return self.inner.pdf(self._z(x)) * self._slope(x)

    def cdf(self, x: float) -> float:
        return self.inner.cdf(self._z(x))

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
        return self._y(self.inner.quantile(p, tol=tol, max_iter=max_iter))

    def crps(self, x: float) -> float:
        """CRPS by trapezoid in z-coordinates, where the Jacobian y'(z) is
        constant per table segment. The realization's z is always inserted as
        a node, and the indicator side is decided per segment, so the kink
        costs no accuracy. Validated to ~0.2% against ``Dist.crps`` through an
        identity table."""
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

    # --- Dist-compatibility shim ---------------------------------------------

    @property
    def components(self) -> list:
        """Moment-matched mixture components in y-space (lazy, cached).

        Each inner component is mapped by Gauss-Hermite through the table:
        the resulting (weight, mean, std) triple carries the pushforward's
        exact first two moments per component. This is the KL-optimal single
        Gaussian per component, so consumers that must have a plain mixture
        (``Dist.combine``, the sticky projection) get the best answer the
        representation admits. Exact queries do not use this path.
        """
        if self._comps is None:
            comps = []
            for w, m, s in self.inner.components:
                mu = 0.0
                m2 = 0.0
                for x, wt in _GH7:
                    y = self._y(m + s * _SQRT2 * x)
                    g = wt / _SQRTPI
                    mu += g * y
                    m2 += g * y * y
                sd = math.sqrt(max(m2 - mu * mu, 1e-24))
                comps.append((w, mu, max(sd, 1e-15)))
            self._comps = comps
        return self._comps

    @property
    def mean(self) -> float:
        return sum(w * m for w, m, _ in self.components)

    @property
    def var(self) -> float:
        mu = self.mean
        return sum(w * (s * s + (m - mu) ** 2) for w, m, s in self.components)

    @property
    def std(self) -> float:
        return math.sqrt(max(self.var, 0.0))

    def __repr__(self) -> str:
        return (f"PushforwardDist(knots={len(self.ys)}, "
                f"inner={self.inner!r})")

    def __len__(self) -> int:
        return len(self.inner)
