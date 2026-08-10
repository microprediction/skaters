"""Skater convention: an online univariate model is a callable:

    dists, state = f(y, state)

where:
    y:      float             - new observation
    state:  dict | None       - prior state (None on first call)
    dists:  list[Dist]        - distributional forecasts for horizons 1..k
    state:  dict              - updated state (pass back next call)

Every skater returns full distributional predictions. Point forecasts
are just dist.mean. Uncertainty is dist.std or dist.quantile().
Log-likelihood is dist.logpdf(y_actual).

A skater is always a tree of transforms with a distributional leaf
at the bottom. The leaf estimates the residual distribution; the
transforms propagate it back to the original space.

Missing observations
--------------------
A non-finite ``y`` (NaN or infinity) means "no observation this tick", not a
value and not an error. Streams gap, and a forecaster deployed in a browser or
a streaming sidecar must not crash or corrupt itself when they do.

The tick advances time but carries no information, so:

  * the value never reaches the tree, and the fitted state is not advanced
    (an EWMA fed NaN is poisoned permanently: mu + alpha*(nan - mu) = nan,
    and no amount of clean data afterwards recovers it);
  * the forecast AGES by one horizon — the previous tick's h+1 predictive is
    returned as this tick's h — so what you get is the predictive that
    genuinely targets the point being forecast. After k consecutive gaps the
    longest available horizon (h=k) is held;
  * ``state["pit"]`` and ``state["z"]`` are all ``None``, since nothing was
    resolved. Anomaly detection reads these, so a gap must not look like a
    residual of zero;
  * ``state["skipped"]`` counts them, so gaps are auditable rather than
    invisible;
  * a gap before any observation has no forecast to age and no scale
    information, so it emits a wide zero-centred Gaussian and leaves the tree
    untouched. The first finite value then initializes it exactly as a true
    first observation would.

Callers who prefer to fail loudly on missing data should check finiteness
before calling. The reverse is not available: nothing can recover a state that
has already been silently corrupted.
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable
from skaters.dist import Dist


@runtime_checkable
class Skater(Protocol):
    def __call__(self, y: float, state: dict | None) -> tuple[list[Dist], dict]:
        ...
