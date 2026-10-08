"""Nozzles: named ways to reconstruct a scoreable Dist from a quantile-only
model's output, and a scorer that runs all of them on the same quantiles.

A model like Chronos, TimesFM, or TiRex emits quantiles (deciles here), not a
density. Turning those quantiles into something with a logpdf is a modeling
choice independent of the underlying model, and that choice can move the
measured score by more than the model comparison it is supposedly enabling
(see papers/soft-benchmarks/paper.md, Section 5). This module makes that
choice explicit and comparable instead of silently fixed.

Two of the four nozzles here are the ones already living, uncompared, in this
repo: `grid` is bench_core.grid_dist (one global Silverman bandwidth from the
IQR), `local` is foundation_study.quantile_dist (a bandwidth fit per node from
its own neighbours). `narrow` and `wide` are the same local-bandwidth
construction at a fixed fraction/multiple of `local`'s bandwidth, bracketing
the sensitivity range rather than claiming either is correct. All four are
run through skaters.dist.Dist, which normalizes weights to sum to 1
regardless of what a nozzle hands it (see skaters/dist.py Dist.__init__) --
so this module cannot reproduce the pre-2026-08-17 mis-normalization bug; it
tests reconstruction SHAPE sensitivity, a separate and still-live question.

    PYTHONPATH=src:benchmarks .venv-sota/bin/python -c "
    import nozzles
    print(nozzles.score_all([0.1,...,0.9], [q1,...,q9], y_actual))
    "
"""
from __future__ import annotations
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from skaters.dist import Dist
import bench_core as bc


def _local_bandwidth_comps(levels, qs, scale):
    """foundation_study.quantile_dist's per-node construction, with the
    bandwidth multiplied by `scale` (1.0 reproduces it exactly)."""
    levels = np.asarray(levels, float); qs = np.asarray(qs, float)
    order = np.argsort(levels); levels, qs = levels[order], qs[order]
    comps = []
    for i in range(len(qs)):
        lo = levels[i - 1] if i > 0 else 0.0
        hi = levels[i + 1] if i < len(qs) - 1 else 1.0
        w = max((hi - lo) / 2.0, 1e-6)
        if i == 0:
            sp = abs(qs[1] - qs[0])
        elif i == len(qs) - 1:
            sp = abs(qs[-1] - qs[-2])
        else:
            sp = abs(qs[i + 1] - qs[i - 1]) / 2.0
        comps.append((w, float(qs[i]), max(scale * 0.5 * sp, 1e-9)))
    return comps


def nozzle_grid(levels, qs):
    """bench_core.grid_dist: one global Silverman bandwidth from the IQR."""
    return bc.grid_dist(levels, qs)


def nozzle_local(levels, qs):
    """foundation_study.quantile_dist: bandwidth fit per node."""
    return Dist(_local_bandwidth_comps(levels, qs, scale=1.0))


def nozzle_narrow(levels, qs):
    """`local`'s construction at 1/3 bandwidth: an aggressively tight
    reconstruction, the failure mode the original bump nozzle exhibited
    (though that bug was mis-normalization, not narrowness alone; see the
    module docstring)."""
    return Dist(_local_bandwidth_comps(levels, qs, scale=1.0 / 3.0))


def nozzle_wide(levels, qs):
    """`local`'s construction at 3x bandwidth: a generously smoothed
    reconstruction, spreading more mass toward the tails."""
    return Dist(_local_bandwidth_comps(levels, qs, scale=3.0))


NOZZLES = {
    "grid": nozzle_grid,
    "local": nozzle_local,
    "narrow": nozzle_narrow,
    "wide": nozzle_wide,
}


def score_all(levels, qs, y):
    """{nozzle_name: (logpdf, crps)} for one point, every registered nozzle,
    through the one shared scorer (bench_core.score_dist)."""
    out = {}
    for name, fn in NOZZLES.items():
        d = fn(levels, qs)
        if d is None:
            continue
        out[name] = bc.score_dist(d, y)
    return out


def spread(scores):
    """max - min logpdf across nozzles, for one scored point -- the
    nozzle-choice sensitivity, directly comparable in units to a model-vs-
    model gap."""
    lps = [lp for lp, _ in scores.values()]
    return max(lps) - min(lps) if lps else float("nan")
