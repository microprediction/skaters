"""Gaussian mixture distribution: the distributional prediction type.

A Dist represents a predictive distribution as a weighted mixture of
Gaussians. This is the type that flows through the tree:

    - Leaves emit a Dist (e.g., centered Gaussian with empirical variance)
    - Transforms propagate Dists through their inverses
    - Ensembles combine Dists as weighted mixtures (exact, no approximation)
    - Queries: pdf, cdf, logpdf, quantile, mean, var, std

All math uses only the standard library (math.erf, math.exp, math.log).
No numpy, no scipy. Runs in Pyodide.

A Dist is a list of components: [(weight, mean, std), ...].
Weights are positive and sum to 1. Std is always > 0.
"""

from __future__ import annotations
import math

_SQRT2 = math.sqrt(2.0)
_SQRT2PI = math.sqrt(2.0 * math.pi)
_LOG_SQRT2PI = 0.5 * math.log(2.0 * math.pi)


class Dist:
    """A weighted mixture of Gaussians."""

    __slots__ = ("components",)

    def __init__(self, components: list[tuple[float, float, float]]):
        """Create from a list of (weight, mean, std) tuples.

        Weights must be positive. They will be normalized to sum to 1.
        """
        assert len(components) > 0
        w_total = sum(w for w, _, _ in components)
        assert w_total > 0
        self.components = [(w / w_total, m, s) for w, m, s in components]

    # --- Constructors ---

    @staticmethod
    def gaussian(mean: float = 0.0, std: float = 1.0) -> Dist:
        """A single Gaussian."""
        return Dist([(1.0, mean, std)])

    @staticmethod
    def combine(dists: list[Dist], weights: list[float] | None = None) -> Dist:
        """Weighted mixture of distributions (exact).

        This is the correct way to ensemble distributional predictions.
        """
        n = len(dists)
        if weights is None:
            weights = [1.0 / n] * n
        w_total = sum(weights)
        components = []
        for d, w_outer in zip(dists, weights):
            for w_inner, m, s in d.components:
                components.append((w_outer / w_total * w_inner, m, s))
        return Dist(components)

    # --- Queries ---

    def pdf(self, x: float) -> float:
        """Probability density at x."""
        total = 0.0
        for w, m, s in self.components:
            total += w * _gaussian_pdf(x, m, s)
        return total

    def logpdf(self, x: float) -> float:
        """Log probability density at x."""
        p = self.pdf(x)
        return math.log(p) if p > 0 else -math.inf

    def cdf(self, x: float) -> float:
        """Cumulative distribution function at x."""
        total = 0.0
        for w, m, s in self.components:
            total += w * _gaussian_cdf(x, m, s)
        return total

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
        """Inverse CDF via bisection."""
        assert 0 < p < 1
        # Initial bracket
        mu = self.mean
        sigma = math.sqrt(self.var)
        lo = mu - 8 * sigma
        hi = mu + 8 * sigma
        for _ in range(max_iter):
            mid = 0.5 * (lo + hi)
            if self.cdf(mid) < p:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return 0.5 * (lo + hi)

    @property
    def mean(self) -> float:
        """Mean of the mixture."""
        return sum(w * m for w, m, _ in self.components)

    @property
    def var(self) -> float:
        """Variance of the mixture (law of total variance)."""
        mu = self.mean
        return sum(w * (s * s + m * m) for w, m, s in self.components) - mu * mu

    @property
    def std(self) -> float:
        """Standard deviation."""
        v = self.var
        return math.sqrt(v) if v > 0 else 0.0

    # --- Transform support ---

    def shift(self, delta: float) -> Dist:
        """Shift all components by delta (for diff inverse)."""
        return Dist([(w, m + delta, s) for w, m, s in self.components])

    def scale(self, factor: float) -> Dist:
        """Scale location and spread by factor (for standardize inverse)."""
        assert factor != 0
        f = abs(factor)
        return Dist([(w, m * factor, s * f) for w, m, s in self.components])

    def affine(self, a: float, b: float) -> Dist:
        """Apply affine transform: x -> a*x + b."""
        assert a != 0
        return Dist([(w, a * m + b, abs(a) * s) for w, m, s in self.components])

    # --- Pruning ---

    def prune(self, max_components: int = 20) -> Dist:
        """Reduce component count by merging closest pairs."""
        comps = list(self.components)
        while len(comps) > max_components:
            # Find closest pair (by mean distance, weighted by mass)
            best_dist = float("inf")
            best_i = 0
            best_j = 1
            for i in range(len(comps)):
                for j in range(i + 1, len(comps)):
                    d = abs(comps[i][1] - comps[j][1])
                    if d < best_dist:
                        best_dist = d
                        best_i, best_j = i, j
            # Merge the pair (moment-matching)
            wi, mi, si = comps[best_i]
            wj, mj, sj = comps[best_j]
            w_new = wi + wj
            m_new = (wi * mi + wj * mj) / w_new
            v_new = (wi * (si * si + mi * mi) + wj * (sj * sj + mj * mj)) / w_new - m_new * m_new
            s_new = math.sqrt(max(v_new, 0.0))
            comps[best_i] = (w_new, m_new, s_new)
            comps.pop(best_j)
        return Dist(comps)

    # --- Serialization ---

    def to_dict(self) -> dict:
        return {"components": self.components}

    @staticmethod
    def from_dict(d: dict) -> Dist:
        return Dist([tuple(c) for c in d["components"]])

    # --- Dunder ---

    def __repr__(self) -> str:
        if len(self.components) == 1:
            _, m, s = self.components[0]
            return f"Dist(μ={m:.4g}, σ={s:.4g})"
        return f"Dist({len(self.components)} components, μ={self.mean:.4g}, σ={self.std:.4g})"

    def __len__(self) -> int:
        return len(self.components)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Dist):
            return NotImplemented
        return self.components == other.components


# ---------------------------------------------------------------------------
# Pure-Python Gaussian math
# ---------------------------------------------------------------------------

def _gaussian_pdf(x: float, mean: float, std: float) -> float:
    if std <= 0:
        return float("inf") if x == mean else 0.0
    z = (x - mean) / std
    return math.exp(-0.5 * z * z) / (std * _SQRT2PI)


def _gaussian_cdf(x: float, mean: float, std: float) -> float:
    if std <= 0:
        return 1.0 if x >= mean else 0.0
    return 0.5 * (1.0 + math.erf((x - mean) / (std * _SQRT2)))
