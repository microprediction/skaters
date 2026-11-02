"""Diagnostic: log variance ratio against a frozen reference.

The caller passes residuals. The first ``burn_in`` finite residuals estimate
a reference variance, which then freezes. Each later update returns

    log((var(last ``window`` residuals) + eps) / ref_var)

using the ordinary (non-robust) population variance. ``+r`` and ``-r`` give
the same value: this is a surprise feature, not a coordinate of the residual,
and it has no inverse. It is not a conjugate transform.

One instance is one scale. A multi-scale reading is several instances with
different windows. The reference model that produced the residual stays with
the caller; this lens does not fit one.

A non-finite residual, or one large enough that its square overflows, is
ignored. The frozen reference and the last finite feature stay as they were.
"""

from __future__ import annotations

import math

# float(1e150) ** 2 still fits in IEEE-754; 1e200 does not.
_MAX_ABS = 1e150


def _population_var(values: list[float]) -> float:
    n = len(values)
    mean = sum(values) / n
    acc = 0.0
    for value in values:
        diff = value - mean
        acc += diff * diff
    return acc / n


class ResidualVarianceLens:
    """Log variance ratio of a trailing residual window to a frozen reference."""

    def __init__(self, burn_in: int = 60, window: int = 60, eps: float = 1e-12):
        if burn_in < 2:
            raise ValueError("burn_in must be at least 2")
        if window < 2:
            raise ValueError("window must be at least 2")
        if eps <= 0.0:
            raise ValueError("eps must be positive")
        self.burn_in = burn_in
        self.window = window
        self.eps = eps
        self.ref_var: float | None = None
        self._ref: list[float] = []
        self._recent: list[float] = []
        self._last = 0.0

    def update(self, epsilon: float) -> float:
        if not math.isfinite(epsilon) or abs(epsilon) > _MAX_ABS:
            return self._last
        if self.ref_var is None:
            self._ref.append(epsilon)
            if len(self._ref) >= self.burn_in:
                self.ref_var = _population_var(self._ref) + self.eps
                self._ref = []
            return 0.0
        self._recent.append(epsilon)
        if len(self._recent) > self.window:
            del self._recent[0]
        if len(self._recent) < 2:
            self._last = 0.0
            return 0.0
        var = _population_var(self._recent)
        self._last = math.log((var + self.eps) / self.ref_var)
        return self._last
