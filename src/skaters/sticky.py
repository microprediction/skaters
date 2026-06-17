"""Sticky (zero-inflated) wrapper — bet on repetition.

Many real series — administrative rates, posted prices, anything quoted on a
grid — *repeat exactly*: the one-step change is a point mass at zero with rare
moves. A continuous predictive can't represent that; a Gaussian scale mixture
pays for it on both CRPS and likelihood.

`sticky` wraps any skater and blends in a near-Dirac spike at the last value
with weight ``p`` = the online estimate of how often the value repeats. On
repetitive series ``p`` is large and the spike captures the point mass (huge
likelihood, sharp CRPS); on continuous series ``p`` -> 0 and the wrapper
vanishes. Still a plain :class:`Dist` — just one extra narrow component.
"""

from __future__ import annotations
from skaters.dist import Dist


def sticky(base, k: int = 1, propensity_alpha: float = 0.05, spike_frac: float = 0.005):
    """Wrap a skater with a repetition spike.

    Args:
        base: any skater callable (y, state) -> (list[Dist], state).
        k: forecast horizon (must match base).
        propensity_alpha: EMA rate for the repeat probability p.
        spike_frac: spike width as a fraction of the base std (smaller = more
            committed to the point mass — how hard it "goes for it").
    """

    def _skater(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {"base": None, "last": None, "p": 0.0, "n": 0}

        dists, state["base"] = base(y, state["base"])
        state["n"] += 1
        if state["last"] is not None:
            a = propensity_alpha if propensity_alpha > 1.0 / state["n"] else 1.0 / state["n"]
            repeat = 1.0 if y == state["last"] else 0.0
            state["p"] = (1 - a) * state["p"] + a * repeat
        p = state["p"]
        spike_at = y  # if it repeats, the next value equals the last seen one

        out = []
        for d in dists:
            if p > 1e-6:
                spike_std = max(spike_frac * d.std, 1e-9)
                comps = [(p, spike_at, spike_std)]
                comps.extend(((1 - p) * w, m, s) for w, m, s in d.components)
                out.append(Dist(comps))
            else:
                out.append(d)
        state["last"] = y
        return out, state

    _skater.__name__ = f"sticky({getattr(base, '__name__', '?')})"
    return _skater
