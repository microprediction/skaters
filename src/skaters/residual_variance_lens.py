"""Diagnostic: log variance ratio against a frozen reference.

A conditioning feature, not a conjugate transform. It is not wired into
laplace's pool.

The caller passes residuals. The first ``burn_in`` finite residuals estimate
a reference variance, which then freezes. Once the reference is frozen and
``window`` finite residuals have been seen, each update returns

    log(var(last ``window`` residuals) + eps) - log(ref_var)

using the ordinary (non-robust) population variance. The trailing window is
the last ``window`` finite residuals of the whole stream, burn-in included,
so it overlaps the reference when ``window`` reaches back that far. Before
both conditions hold the feature is 0.0 and ``state["ready"]`` is False, so
a gate can tell warm-up from a measured ratio of zero. The window is never
partial: with ``window > burn_in`` the feature stays silent past the freeze. ``+r`` and ``-r`` give
the same value, so the feature has no inverse to the residual.

The reference does not forget. A forgetting baseline drifts into a new
regime and stops seeing the break, which is what this feature measures.

One update function is one scale. A multi-scale reading is several functions
with different windows. The model that produced the residual stays with the
caller; this lens does not fit one. State is a plain dict owned by the stream.

A non-finite residual, or one large enough that its square overflows, is
ignored. The frozen reference and the last finite feature stay as they were.
"""

from __future__ import annotations

import math

# float(1e150) ** 2 still fits in IEEE-754; 1e200 does not.
_MAX_ABS = 1e150


def _population_var(values: list[float]) -> float:
    # Centre on a sample first: sum/n of a large constant can round one ulp
    # off the value itself, and squaring that rounding invents variance.
    n = len(values)
    shift = values[0]
    shifted = [value - shift for value in values]
    mean = sum(shifted) / n
    acc = 0.0
    for value in shifted:
        diff = value - mean
        acc += diff * diff
    return acc / n


def residual_variance_lens(burn_in: int = 60, window: int = 60, eps: float = 1e-12):
    """Log variance ratio of a trailing residual window to a frozen reference.

    Returns:
        ``update(epsilon, state) -> (feature, state)``. Pass ``state=None`` to
        start a stream.
    """
    if not isinstance(burn_in, int) or burn_in < 2:
        raise ValueError("burn_in must be an integer of at least 2")
    if not isinstance(window, int) or window < 2:
        raise ValueError("window must be an integer of at least 2")
    if not (math.isfinite(eps) and eps > 0.0):
        raise ValueError("eps must be positive and finite")

    def update(epsilon: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            state = {"ref": [], "ref_var": None, "recent": [], "last": 0.0,
                     "ready": False}
        else:
            state = {
                "ref": list(state["ref"]),
                "ref_var": state["ref_var"],
                "recent": list(state["recent"]),
                "last": state["last"],
                "ready": state.get("ready", False),
            }
        if not math.isfinite(epsilon) or abs(epsilon) > _MAX_ABS:
            return state["last"], state
        state["recent"].append(epsilon)
        if len(state["recent"]) > window:
            del state["recent"][0]
        if state["ref_var"] is None:
            state["ref"].append(epsilon)
            if len(state["ref"]) >= burn_in:
                state["ref_var"] = _population_var(state["ref"]) + eps
                state["ref"] = []
        if state["ref_var"] is None or len(state["recent"]) < window:
            return 0.0, state
        state["ready"] = True
        numerator = _population_var(state["recent"]) + eps
        # Subtract the logs. The quotient itself overflows when a flat
        # reference (eps) meets large finite residuals, even though both
        # variance terms are finite.
        if numerator > 0.0 and state["ref_var"] > 0.0 and math.isfinite(numerator):
            state["last"] = math.log(numerator) - math.log(state["ref_var"])
        return state["last"], state

    return update
