"""Sticky / lattice projection — bet on the discrete values a series revisits.

Many real series — administrative rates, posted prices, anything quoted on a
grid — live on a small *lattice* of exact values and revisit them. A continuous
predictive can't put mass on an exact value; a Gaussian scale mixture pays for
it on both CRPS and likelihood.

`sticky` wraps any skater and adds near-Dirac atoms at the lattice values the
series keeps returning to. It maintains a recency-weighted frequency table of
exact values; a value becomes a lattice **atom** once its weight clears a noise
floor (i.e. it has been *revisited*, not seen once), and the atom carries that
value's recency-weighted frequency as its probability. The continuous part takes
the remaining mass and is **recentered** so the atoms never move the ensemble's
mean (mean-preserving). Everything stays a plain :class:`Dist`.

Two properties make this safe and general:

* On a **continuous** series no value is revisited, the table holds only
  singletons below the floor, no atom fires, and the wrapper vanishes.
* It captures **non-consecutive** recurrence — a value visited often but never
  twice in a row — which a consecutive-repeat gate misses entirely. The single
  near-Dirac spike of the earlier version is just the ``max_atoms=1`` case.

This is the *projection* axis. The complementary *pull* (the mean tracking the
last value) is left to the trunk, where the random-walk candidate earns its
weight by likelihood.
"""

from __future__ import annotations
from skaters.dist import Dist


def sticky(base, k: int = 1, propensity_alpha: float = 0.05,
           spike_frac: float = 0.005, thresh_mult: float = 1.8,
           max_atoms: int = 6, prune_eps: float = 1e-6):
    """Wrap a skater with mean-preserving lattice atoms.

    Args:
        base: any skater callable (y, state) -> (list[Dist], state).
        k: forecast horizon (must match base).
        propensity_alpha: EMA rate of the recency-weighted value table.
        spike_frac: atom width as a fraction of the base std (smaller = harder).
        thresh_mult: a value is a lattice atom once its weight exceeds
            ``thresh_mult * propensity_alpha`` — i.e. it has been revisited
            rather than seen once. This is what makes the wrapper vanish on
            continuous data.
        max_atoms: cap on the number of simultaneous atoms (top by frequency).
        prune_eps: drop table entries whose recency weight falls below this.
    """

    def _skater(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {"base": None, "counts": {}}

        dists, state["base"] = base(y, state["base"])

        # recency-weighted frequency table of exact values (sums to ~1).
        c = state["counts"]
        for key in list(c):
            c[key] *= (1.0 - propensity_alpha)
            if c[key] < prune_eps:
                del c[key]
        c[y] = c.get(y, 0.0) + propensity_alpha

        # lattice atoms = revisited values (above the noise floor), top by weight.
        thr = thresh_mult * propensity_alpha
        atoms = sorted(((v, w) for v, w in c.items() if w > thr),
                       key=lambda t: -t[1])[:max_atoms]

        out = []
        for d in dists:
            if not atoms:
                out.append(d)
                continue
            sw = sum(w for _, w in atoms)
            P = min(sw, 0.999)                 # total atom mass (cap < 1)
            pc = 1.0 - P
            atom_mean = sum(w * v for v, w in atoms) / sw
            spike_std = max(spike_frac * d.std, 1e-9)
            if pc <= 1e-9:                      # essentially pure atoms
                comps = [(w / sw, v, spike_std) for v, w in atoms]
                out.append(Dist(comps))
                continue
            # Mean-preserving: atoms of total mass P at mean `atom_mean` would
            # drag the mean by P*(atom_mean - mu); recenter the continuous part
            # by delta to cancel it, so E[out] == d.mean exactly.
            mu = d.mean
            delta = P * (mu - atom_mean) / pc
            comps = [(P * (w / sw), v, spike_std) for v, w in atoms]
            comps.extend((pc * w, m + delta, s) for w, m, s in d.components)
            out.append(Dist(comps))
        return out, state

    _skater.__name__ = f"sticky({getattr(base, '__name__', '?')})"
    return _skater
