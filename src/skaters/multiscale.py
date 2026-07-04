"""Multi-scale ensemble: combine forecasters running on decimated clocks.

Native multi-step forecasting fans a one-step model out to horizon k, and on
long horizons the fan-out can inflate variance badly. A model on a *decimated*
clock (every s-th observation) reaches fine horizon h in only round(h/s) of its
own steps, so its predictive stays tight — but it is blind to the points it
skips. Neither scale dominates: benchmarked on FRED change series the fine
scale wins short horizons and the coarse scale long ones. So, as everywhere
else in this package, we do not choose — we run every scale and mix their
predictive distributions with likelihood softmax weights, letting each horizon
select its effective granularity through the weights.

Granularity is the one candidate axis that cannot live inside the usual
transform pool: decimation is many-ticks-to-one (it breaks the
scalar-in/scalar-out ``forward`` contract of :func:`skaters.conjugate.conjugate`)
and a coarse-clock model emits no fine one-step predictive for
:func:`skaters.terminal.terminal_leaf_ensemble` to weight. Hence this wrapper
sits *above* a base forecaster instead of inside it.

Phase: a fixed-phase scale-s model is up to s-1 ticks stale at forecast time.
We avoid that by keeping s phase-shifted copies per scale; each tick advances
exactly one copy (the one whose clock ends now), so the freshest coarse
forecast is always anchored at the current tick and the per-tick cost is one
base step per scale regardless of s.
"""

from __future__ import annotations
import math
from skaters.dist import Dist

_LOGPDF_FLOOR = -20.0


def multiscale(base, k: int, scales: list[int] | None = None,
               forget: float = 0.99, max_components: int = 20):
    """Wrap a base forecaster factory in a multi-scale ensemble.

    Args:
        base: factory ``base(k) -> skater`` for the per-scale forecasters.
        k: fine-clock forecast horizon.
        scales: decimation strides; defaults to ``{1, ceil(sqrt(k)), k}``.
            Scale s serves fine horizons h >= s at its coarse step round(h/s).
        forget: EWMA factor for each scale's mean one-step logpdf (its
            softmax score); ~1/(1-forget) steps of memory.
        max_components: prune each mixed horizon Dist to this many components.

    Returns a skater ``f(y, state) -> (list[Dist] of length k, state)``. With
    ``scales == [1]`` (e.g. k == 1) the base forecaster is returned unwrapped —
    multi-scale at a single scale is exactly the base model.
    """
    if scales is None:
        scales = sorted({1, math.ceil(math.sqrt(k)), k})
    scales = sorted({int(s) for s in scales if 1 <= s <= k})
    assert scales and scales[0] == 1, "scales must include 1"
    if scales == [1]:
        return base(k)
    subs = {s: base(max(1, math.ceil(k / s))) for s in scales}

    def _skater(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {
                "t": 0,
                "phase": {s: [None] * s for s in scales},   # per-phase sub states
                "pending": {s: [None] * s for s in scales}, # per-phase 1-step Dist to score
                "latest": {},                                # per-scale freshest dists
                "score": {s: None for s in scales},          # EWMA mean one-step logpdf
            }
        t = state["t"]
        for s in scales:
            ph = t % s
            prev = state["pending"][s][ph]
            if prev is not None:
                lp = max(prev.logpdf(y), _LOGPDF_FLOOR)
                m = state["score"][s]
                state["score"][s] = lp if m is None else forget * m + (1.0 - forget) * lp
            dists, state["phase"][s][ph] = subs[s](y, state["phase"][s][ph])
            state["pending"][s][ph] = dists[0]
            state["latest"][s] = dists
        state["t"] = t + 1

        scores = state["score"]
        top = max(m for m in scores.values() if m is not None) if any(
            m is not None for m in scores.values()) else 0.0
        out = []
        for h in range(1, k + 1):
            fcs, wts = [], []
            for s in scales:
                if s > h or s not in state["latest"]:
                    continue
                j = max(1, int(h / s + 0.5))   # half-up, portable to the JS twin
                dists = state["latest"][s]
                if j - 1 >= len(dists):
                    continue
                fcs.append(dists[j - 1])
                m = scores[s]
                wts.append(math.exp((m if m is not None else top) - top))
            # One eligible scale (e.g. h < every coarse stride): pass its Dist
            # through untouched — no renormalise, no prune.
            out.append(fcs[0] if len(fcs) == 1 else Dist.combine(fcs, wts).prune(max_components))
        return out, state

    return _skater
