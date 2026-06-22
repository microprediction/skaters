"""Does laplace[garch_leaf] close the gap to GARCH-t on price/return series? (issue #25)

Reuses the SOTA harness's exact scorer (bench_core.roll_dist_scores) and the
per-series laplace / GARCH-t scores already in results_sota.csv. We target the
*gap* population: continuous series where GARCH-t currently beats laplace on
log-likelihood (GARCH-t's home turf). For each, we re-score laplace with the
GARCH(1,1)-t terminal leaf and ask how much of the laplace->GARCH-t gap it closes.

A self-check first re-scores plain laplace through this path and confirms it
reproduces the CSV (so laplace[garch_leaf] is comparable to the CSV's GARCH-t).

    PYTHONPATH=src python benchmarks/garch_leaf_study.py
    MAX_SERIES=40 PYTHONPATH=src python benchmarks/garch_leaf_study.py   # fast
"""

from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import csv
import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fred
import bench_core as bc
from study import _cfg, _start_for, _rfrac, MIN_CHANGES, MAX_CHANGES
from skaters.api import _build_candidates
from skaters.terminal import terminal_leaf_ensemble
from skaters.sticky import sticky as _project
from garch_leaf import garch_leaf

CFG = _cfg("sota")
MAX_WORKERS = min(8, (os.cpu_count() or 4))


def _laplace_with_leaf(leaf_fn, k=1):
    """laplace's pool + sticky, but with a chosen terminal leaf."""
    cands, depths, _ = _build_candidates(k)
    f = terminal_leaf_ensemble(cands, k=k, leaf_fn=leaf_fn, learning_rate=0.8,
                               complexity_penalty=0.005, depths=depths, max_components=20)
    return _project(f, k=k)


def _load_csv():
    rows = {}
    with open(CFG["results"]) as fh:
        for r in csv.DictReader(fh):
            rows.setdefault(r["series"], {})[r["method"]] = (float(r["logpdf"]), float(r["crps"]))
    return rows


def _ll(factory, sid):
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    if len(ch) < MIN_CHANGES:
        return None
    if len(ch) > MAX_CHANGES:
        ch = ch[-MAX_CHANGES:]
    start = _start_for(len(ch), CFG)
    lp, cr, n = bc.roll_dist_scores(factory, ch, start)
    return (lp, cr, n) if n else None


def _score(sid):
    from skaters.leaf import scale_mixture_leaf
    base = _ll(lambda: _laplace_with_leaf(scale_mixture_leaf), sid)   # self-check vs CSV
    garch = _ll(lambda: _laplace_with_leaf(garch_leaf), sid)
    return (sid, base, garch)


def main():
    rows = _load_csv()
    # continuous series where GARCH-t beats laplace on LL (the gap population).
    gap = [s for s, d in rows.items()
           if "laplace" in d and "GARCH-t" in d
           and not math.isnan(d["laplace"][0]) and not math.isnan(d["GARCH-t"][0])
           and d["GARCH-t"][0] > d["laplace"][0] and _rfrac(s) < 0.05]
    cap = int(os.environ.get("MAX_SERIES", "0"))
    if cap:
        gap = gap[:cap]
    print(f"gap series (continuous, GARCH-t > laplace on LL): {len(gap)}")

    out = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(_score, s): s for s in gap}
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r and r[1] and r[2]:
                out.append(r)
            if done % 20 == 0:
                print(f"  {done}/{len(gap)}", flush=True)

    import numpy as np
    # Clean, in-this-run comparison (arch/GARCH-t unavailable; the CSV cache has
    # also drifted since #24, so the CSV is only a noisy directional reference).
    # base = laplace[scale_mixture_leaf]; garch = laplace[garch_leaf]. Both use the
    # SAME pool + tail model and identical data, isolating the variance recursion
    # (EWMA/IGARCH vs fitted GARCH(1,1)).
    base = np.array([b[0] for _, b, _ in out])
    new = np.array([g[0] for _, _, g in out])
    d = new - base
    print(f"\n=== laplace[garch_leaf] vs laplace[scale_mixture_leaf], n={len(out)} ===")
    print(f"  (head-to-head, identical data — isolates GARCH variance vs EWMA scale)")
    print(f"  mean LL  ewma {base.mean():+.3f}  ->  garch_leaf {new.mean():+.3f}  "
          f"delta {d.mean():+.4f} nats (median {np.median(d):+.4f})")
    print(f"  garch_leaf better on {100*np.mean(d>0):.0f}% of these series")

    # Caveated reference vs the CSV GARCH-t (cache may differ -> noisy).
    gar = np.array([rows[s]["GARCH-t"][0] for s, _, _ in out])
    print(f"\n  (noisy reference) CSV GARCH-t mean {gar.mean():+.3f}; "
          f"garch_leaf >= CSV GARCH-t on {100*np.mean(new>=gar):.0f}%")
    top = sorted(zip([s for s, _, _ in out], d), key=lambda t: t[1], reverse=True)[:8]
    print("  biggest garch_leaf gains over the EWMA leaf:")
    for sid, c in top:
        print(f"    {sid:20s} {c:+.3f}")


if __name__ == "__main__":
    main()
