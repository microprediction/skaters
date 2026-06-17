"""Sticky (zero-inflated) wrapper — bet on repetition, lattice-aware.

Many real series — administrative rates, posted prices, anything quoted on a
grid — *repeat exactly*: the one-step change is a point mass at zero with rare
moves. A continuous predictive can't represent that; a Gaussian scale mixture
pays for it on both CRPS and likelihood.

`sticky` wraps any skater and blends in a near-Dirac atom with weight ``p`` (the
online estimate of how often the value repeats). It is the *projection*
mechanism only, and has two parts, learned separately:

* the **gate** ``p`` = EWMA of the exact-repeat indicator. It says *whether* to
  fire an atom at all; on continuous series it decays to zero and the wrapper
  vanishes cleanly.
* the **location** = the recency-weighted **modal value** — the value the series
  keeps returning to (its lattice attractor: 0 for a differenced series, the
  current level for a level series). This matters: anchoring the atom at the raw
  last value is wrong right after a move (the value that just changed is the
  *least* likely to recur), whereas the mode is where the mass belongs.

The atom is **mean-preserving** — the continuous part is recentered so the atom
adds mass without moving the ensemble's mean. The complementary *pull*
mechanism (the tendency of the mean to track the last value) is a separate
concern, left to the trunk where the random-walk candidate earns its weight by
likelihood. Everything stays a plain :class:`Dist` — one extra narrow component.

(The gate only counts *consecutive* repeats, so a value that recurs often but
non-consecutively is not yet captured — that is the job of the richer lattice
prior built on this same modal table.)
"""

from __future__ import annotations
from skaters.dist import Dist


def sticky(base, k: int = 1, propensity_alpha: float = 0.05,
           spike_frac: float = 0.005, prune_eps: float = 1e-6):
    """Wrap a skater with a lattice-aware, mean-preserving repetition atom.

    Args:
        base: any skater callable (y, state) -> (list[Dist], state).
        k: forecast horizon (must match base).
        propensity_alpha: EMA rate for both the repeat gate and the value table.
        spike_frac: atom width as a fraction of the base std (smaller = more
            committed to the point mass — how hard it "goes for it").
        prune_eps: drop modal-table entries whose recency weight falls below this.
    """

    def _skater(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {"base": None, "last": None, "p": 0.0, "n": 0, "counts": {}}

        dists, state["base"] = base(y, state["base"])
        state["n"] += 1

        # gate: recency-weighted probability that the value repeats exactly.
        if state["last"] is not None:
            a = propensity_alpha if propensity_alpha > 1.0 / state["n"] else 1.0 / state["n"]
            repeat = 1.0 if y == state["last"] else 0.0
            state["p"] = (1 - a) * state["p"] + a * repeat

        # location: recency-weighted modal value (the lattice attractor).
        c = state["counts"]
        for key in list(c):
            c[key] *= (1.0 - propensity_alpha)
            if c[key] < prune_eps:
                del c[key]
        c[y] = c.get(y, 0.0) + propensity_alpha
        mode = max(c, key=c.get)

        p = state["p"]
        pc = 1.0 - p
        out = []
        for d in dists:
            if p <= 1e-6:
                out.append(d)
                continue
            spike_std = max(spike_frac * d.std, 1e-9)
            if pc <= 1e-9:                     # p ~ 1: essentially a pure atom
                out.append(Dist([(1.0, mode, spike_std)]))
                continue
            # Mean-preserving: an atom of weight p at `mode` would drag the mean
            # by p*(mode - mu); recenter the continuous part by delta to cancel
            # it, so E[out] == d.mean exactly.
            mu = d.mean
            delta = p * (mu - mode) / pc
            comps = [(p, mode, spike_std)]
            comps.extend((pc * w, m + delta, s) for w, m, s in d.components)
            out.append(Dist(comps))
        state["last"] = y
        return out, state

    _skater.__name__ = f"sticky({getattr(base, '__name__', '?')})"
    return _skater
