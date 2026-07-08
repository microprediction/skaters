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
        """Log density at x, accumulated in log-space (log-sum-exp).

        A Gaussian mixture is strictly positive everywhere, so for finite x the
        log density is always finite. Computing ``log(sum(w * pdf))`` directly
        underflows to ``-inf`` once x sits many standard deviations from every
        component (e.g. after the scale collapses on a near-constant stream),
        because each ``exp(-z**2 / 2)`` rounds to 0.0. Summing the per-component
        log densities instead keeps the result finite and correct.
        """
        best = -math.inf
        terms = []
        for w, m, s in self.components:
            if w <= 0.0:
                continue
            if s <= 0.0:
                if x == m:
                    return math.inf
                continue
            z = (x - m) / s
            t = math.log(w) - 0.5 * z * z - math.log(s) - _LOG_SQRT2PI
            terms.append(t)
            if t > best:
                best = t
        if best == -math.inf:
            return -math.inf
        return best + math.log(sum(math.exp(t - best) for t in terms))

    def cdf(self, x: float) -> float:
        """Cumulative distribution function at x."""
        total = 0.0
        for w, m, s in self.components:
            total += w * _gaussian_cdf(x, m, s)
        return total

    def crps(self, x: float) -> float:
        """Continuous Ranked Probability Score at observation x.

        CRPS is a proper scoring rule (lower is better) with the same units
        as the data — more robust than logpdf, which is dominated by tails.
        Closed form for a Gaussian mixture (Grimit et al. 2006):

            CRPS = Σ_i w_i A(μ_i - x, σ_i)
                   - ½ Σ_i Σ_j w_i w_j A(μ_i - μ_j, √(σ_i²+σ_j²))

        where A(m, s) = E|N(m, s²)| = m(2Φ(m/s) - 1) + 2s·φ(m/s).
        """
        comps = self.components
        t1 = 0.0
        for w, m, s in comps:
            t1 += w * _abs_expectation(m - x, s)
        t2 = 0.0
        for wi, mi, si in comps:
            for wj, mj, sj in comps:
                t2 += wi * wj * _abs_expectation(mi - mj, math.sqrt(si * si + sj * sj))
        return t1 - 0.5 * t2

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
        """Variance of the mixture (law of total variance).

        Centered form ``sum w (s^2 + (m - mu)^2)`` rather than
        ``sum w (s^2 + m^2) - mu^2``: the latter catastrophically cancels when
        the means are large relative to the spreads (e.g. a tight component at
        a large mean), silently yielding var=0 and std=0 — an invalid Dist.
        """
        mu = self.mean
        return sum(w * (s * s + (m - mu) * (m - mu)) for w, m, s in self.components)

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
        max_components = max(1, max_components)   # a Dist needs >=1 component
        if len(self.components) <= max_components:
            return self
        # Sort first so the merge path (and hence the result) is independent of
        # component order — mixtures are order-free but the closest-pair scan
        # is not, and ties at equal means are common (lattice atoms).
        comps = sorted(self.components, key=lambda c: (c[1], c[2], c[0]))
        # Pair selection tolerates last-ulp noise in the means: pick the FIRST
        # pair within a hair of the true minimum distance, so platforms that
        # disagree at the ulp level (e.g. libm erf vs a polynomial) still merge
        # the same pairs in the same order. Exact argmin would amplify ulp
        # noise into macroscopically different mixtures.
        scale = abs(comps[0][1]) + abs(comps[-1][1]) + 1e-12
        while len(comps) > max_components:
            best_dist = float("inf")
            for i in range(len(comps)):
                for j in range(i + 1, len(comps)):
                    d = abs(comps[i][1] - comps[j][1])
                    if d < best_dist:
                        best_dist = d
            thresh = best_dist + 1e-9 * scale
            best_i = best_j = None
            for i in range(len(comps)):
                for j in range(i + 1, len(comps)):
                    if abs(comps[i][1] - comps[j][1]) <= thresh:
                        best_i, best_j = i, j
                        break
                if best_i is not None:
                    break
            if best_i is None:
                # Only reachable when a mean is NaN: every comparison above
                # is False, for the argmin and the threshold scan alike.
                # Merge the first pair so pruning terminates instead of
                # indexing with None.
                best_i, best_j = 0, 1
            # Merge the pair (moment-matching)
            wi, mi, si = comps[best_i]
            wj, mj, sj = comps[best_j]
            w_new = wi + wj
            if w_new < 1e-300:
                # Both weights are effectively zero — just average
                m_new = 0.5 * (mi + mj)
                s_new = max(si, sj, 1e-12)
            else:
                m_new = (wi * mi + wj * mj) / w_new
                # centered form — avoids the same cancellation as Dist.var
                v_new = (wi * (si * si + (mi - m_new) ** 2)
                         + wj * (sj * sj + (mj - m_new) ** 2)) / w_new
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


def _abs_expectation(m: float, s: float) -> float:
    """E|N(m, s²)| = m(2Φ(m/s) - 1) + 2s·φ(m/s).  (Used by CRPS.)"""
    if s <= 0:
        return abs(m)
    z = m / s
    return m * (2.0 * _gaussian_cdf(z, 0.0, 1.0) - 1.0) + 2.0 * s * _gaussian_pdf(z, 0.0, 1.0)
