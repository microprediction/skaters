"""Clean three-way: laplace / laplace[garch_leaf] / live GARCH-t (issue #25).

Runs all three on IDENTICAL current data (the CSV is used only to pick the
price/return population, not for scoring). Decides promotion of garch_leaf:
  * does it close the laplace->GARCH-t gap on the gap population, and
  * is it NFL-safe on a non-gap continuous control (doesn't hurt laplace)?

Requires `arch`.  PYTHONPATH=src python benchmarks/garch_leaf_threeway.py
  MAX_SERIES caps each of {gap, control}.
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
from opponents import _garch_predict
from garch_leaf import garch_leaf
from garch_leaf_study import _laplace_with_leaf
from skaters.leaf import scale_mixture_leaf

CFG = _cfg("sota")
REFIT = CFG["refit"]
MAX_WORKERS = min(8, (os.cpu_count() or 4))


def _prep(sid):
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    if len(ch) < MIN_CHANGES:
        return None, None
    if len(ch) > MAX_CHANGES:
        ch = ch[-MAX_CHANGES:]
    return ch, _start_for(len(ch), CFG)


def _score(args):
    sid, is_gap = args
    ch, start = _prep(sid)
    if ch is None:
        return None
    lp_lap, _, n = bc.roll_dist_scores(lambda: _laplace_with_leaf(scale_mixture_leaf), ch, start)
    lp_g, _, _ = bc.roll_dist_scores(lambda: _laplace_with_leaf(garch_leaf), ch, start)
    gt = _garch_predict(ch, start, REFIT)
    if not gt:
        return None
    return (sid, is_gap, lp_lap, lp_g, gt[0][1])


def _report(label, rows):
    import numpy as np
    if not rows:
        print(f"\n{label}: no series"); return
    lap = np.array([r[2] for r in rows]); gl = np.array([r[3] for r in rows]); gt = np.array([r[4] for r in rows])
    print(f"\n=== {label} (n={len(rows)}) — mean one-step LL ===")
    print(f"  laplace {lap.mean():+.3f}   laplace[garch_leaf] {gl.mean():+.3f}   GARCH-t {gt.mean():+.3f}")
    print(f"  garch_leaf vs laplace: delta {(gl-lap).mean():+.4f} nats, better on {100*np.mean(gl>lap):.0f}%")
    gap = gt - lap
    if gap.sum() > 0:
        print(f"  fraction of laplace->GARCH-t gap closed by garch_leaf: {100*float((gl-lap).sum()/gap.sum()):.0f}%")
    print(f"  garch_leaf >= GARCH-t on {100*np.mean(gl>=gt):.0f}%   (laplace >= GARCH-t on {100*np.mean(lap>=gt):.0f}%)")


def main():
    rows = {}
    with open(CFG["results"]) as fh:
        for r in csv.DictReader(fh):
            rows.setdefault(r["series"], {})[r["method"]] = (float(r["logpdf"]), float(r["crps"]))
    cont = [s for s, d in rows.items() if "laplace" in d and "GARCH-t" in d
            and not math.isnan(d["laplace"][0]) and not math.isnan(d["GARCH-t"][0]) and _rfrac(s) < 0.05]
    gap = [s for s in cont if rows[s]["GARCH-t"][0] > rows[s]["laplace"][0]]
    ctrl = [s for s in cont if s not in set(gap)]
    cap = int(os.environ.get("MAX_SERIES", "0"))
    if cap:
        gap, ctrl = gap[:cap], ctrl[:cap]
    work = [(s, True) for s in gap] + [(s, False) for s in ctrl]
    print(f"gap (price-like, GARCH-t>laplace): {len(gap)}   control (non-gap continuous): {len(ctrl)}")

    out = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(_score, w): w for w in work}
        done = 0
        for fut in as_completed(futs):
            r = fut.result(); done += 1
            if r:
                out.append(r)
            if done % 20 == 0:
                print(f"  {done}/{len(work)}", flush=True)

    _report("GAP population (GARCH-t's home turf)", [r for r in out if r[1]])
    _report("CONTROL (non-gap continuous — NFL safety)", [r for r in out if not r[1]])


if __name__ == "__main__":
    main()
