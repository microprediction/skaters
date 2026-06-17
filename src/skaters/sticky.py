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

This is the *projection* mechanism only — it adds discrete mass at the realized
value and is **mean-preserving** (the continuous part is recentered so the
atom never moves the ensemble's mean). The complementary *pull* mechanism (the
tendency of the mean to track the last value) is a separate concern handled in
the trunk by the persistence/random-walk candidate and its prior — not here.
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
        pc = 1.0 - p
        spike_at = y  # if it repeats, the next value equals the last seen one

        out = []
        for d in dists:
            if p <= 1e-6:
                out.append(d)
                continue
            spike_std = max(spike_frac * d.std, 1e-9)
            if pc <= 1e-9:                     # p ~ 1: essentially a pure atom
                out.append(Dist([(1.0, spike_at, spike_std)]))
                continue
            # Pure *projection*: add atom mass at the repeat value WITHOUT moving
            # the mean. An atom of weight p at spike_at would drag the mean by
            # p*(spike_at - mu); recenter the continuous part by delta to cancel
            # it, so E[out] == d.mean exactly (the ensemble's mean is untouched).
            mu = d.mean
            delta = p * (mu - spike_at) / pc
            comps = [(p, spike_at, spike_std)]
            comps.extend((pc * w, m + delta, s) for w, m, s in d.components)
            out.append(Dist(comps))
        state["last"] = y
        return out, state

    _skater.__name__ = f"sticky({getattr(base, '__name__', '?')})"
    return _skater
