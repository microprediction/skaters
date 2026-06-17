"""Race the *hybrid* against crepes: likelihood trunk + CRPS terminal leaf.

The earlier study raced `crps-leaf` standalone (mean hard-zero, no mean model).
This builds what the architecture was designed for and what we actually want to
test:

  * trunk  -> the full candidate ensemble (drift/Holt/AR/frac/fast-slow/...),
              weighted online by LOG-LIKELIHOOD (terminal_leaf_ensemble's
              built-in mean weighting), and
  * leaf   -> a single CRPS-fit scale-mixture at the very end.

So the mean is a real likelihood-selected forecast and only the residual *shape*
is optimized for CRPS. Scored against crepes (best of 3 windows) on the already
cached daily FRED series. Appends to results_large.csv and prints a comparison.

    PYTHONPATH=src python benchmarks/crps_ensemble_run.py
"""

from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import csv
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fred
import fred_universe
from exhaustive_crps import skater_scores
from crps_leaf import crps_leaf
from skaters.api import _build_candidates
from skaters.terminal import terminal_leaf_ensemble
from skaters.sticky import sticky

_HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(_HERE, "results_large.csv")
MIN_CHANGES = 500
MAX_WORKERS = int(os.environ.get("STUDY_WORKERS", min(8, (os.cpu_count() or 4))))


def _crps_terminal_leaf(k=1):
    return crps_leaf(k=k, eta=1.0)


def make_crps_ensemble(k=1):
    """Likelihood-weighted candidate trunk + a single CRPS-fit terminal leaf."""
    cands, depths, _ = _build_candidates(k)            # plain-leaf candidates -> likelihood trunk
    return terminal_leaf_ensemble(
        cands, leaf_fn=_crps_terminal_leaf, k=k,
        learning_rate=0.8, complexity_penalty=0.005, depths=depths,
        max_components=20,
    )


def make_sticky_crps_ensemble(k=1):
    """The hybrid + a zero-inflation repeat spike: CRPS-shaped residual that also
    bets on exact repeats. Aims to hold the CRPS win and take the likelihood crown."""
    return sticky(make_crps_ensemble(k), k=k, spike_frac=0.003)


# New forecasters to add to the race (single, fixed — no best-of cherry-picking).
NEW = {
    "crps-ensemble": lambda: make_crps_ensemble(1),
    "sticky-crps-ensemble": lambda: make_sticky_crps_ensemble(1),
}


def score_one(sid):
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    rows = []
    if len(ch) < MIN_CHANGES:
        return sid, rows
    for name, factory in NEW.items():
        try:
            crps, lp, n = skater_scores(factory, ch)
            rows.append([sid, name, f"{crps:.6f}", f"{lp:.6f}", n])
        except Exception as e:  # noqa: BLE001
            print(f"  ERR {sid}/{name}: {e}", flush=True)
    return sid, rows


def _already_done():
    """Series that already have EVERY new forecaster scored."""
    have = {}
    if os.path.exists(RESULTS):
        with open(RESULTS) as f:
            r = csv.reader(f)
            next(r, None)
            for row in r:
                if len(row) >= 2 and row[1] in NEW:
                    have.setdefault(row[0], set()).add(row[1])
    need = set(NEW)
    return {s for s, got in have.items() if need <= got}


def run():
    # series already scored in the big run = the qualified, cached universe
    cached = set()
    if os.path.exists(RESULTS):
        with open(RESULTS) as f:
            r = csv.reader(f)
            next(r, None)
            for row in r:
                if len(row) >= 2:
                    cached.add(row[0])
    done = _already_done()
    todo = sorted(cached - done)
    # existing (series, forecaster) pairs, so we never write a duplicate row
    have_pairs = set()
    if os.path.exists(RESULTS):
        with open(RESULTS) as f:
            r = csv.reader(f)
            next(r, None)
            for row in r:
                if len(row) >= 2:
                    have_pairs.add((row[0], row[1]))
    print(f"scoring {sorted(NEW)} on {len(todo)} series ({len(done)} done) "
          f"on {MAX_WORKERS} workers", flush=True)

    t0 = time.time()
    fin = 0
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score_one, sid): sid for sid in todo}
        for fut in as_completed(futs):
            sid = futs[fut]
            try:
                _, rows = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"  ERR {sid}: {e}", flush=True)
                continue
            rows = [r for r in rows if (r[0], r[1]) not in have_pairs]
            if rows:
                with open(RESULTS, "a") as f:
                    csv.writer(f).writerows(rows)
            fin += 1
            if fin % 25 == 0 or fin == len(todo):
                rate = fin / max(time.time() - t0, 1e-9)
                print(f"  {fin}/{len(todo)}  ({rate*60:.0f}/min, "
                      f"ETA {(len(todo)-fin)/max(rate,1e-9)/60:.0f} min)", flush=True)
    compare()


def compare():
    import csv as _csv
    from collections import defaultdict
    by = defaultdict(dict)
    for r in _csv.DictReader(open(RESULTS)):
        try:
            c, l = float(r["crps"]), (float(r["logpdf"]) if r["logpdf"] else float("nan"))
        except ValueError:
            c, l = float("nan"), float("nan")
        by[r["series"]][r["forecaster"]] = (c, l)

    CREPES = ["crepes-w250", "crepes-w400", "crepes-w750"]

    def rate(keys, label):
        raw, fam = [], defaultdict(list)
        for s, d in by.items():
            o = min((d[k][0] for k in keys if k in d and not math.isnan(d[k][0])), default=math.inf)
            c = min((d[k][0] for k in CREPES if k in d and not math.isnan(d[k][0])), default=math.inf)
            if math.isinf(o) or math.isinf(c):
                continue
            w = 1.0 if o < c else 0.0
            raw.append(w)
            fam[fred_universe.family(s)].append(w)
        fr = [sum(v) / len(v) for v in fam.values()]
        print(f"  {label:34s} raw {100*sum(raw)/len(raw):5.1f}%   "
              f"family {100*sum(fr)/len(fr):5.1f}%   (N={len(raw)})")

    print("\nCRPS win-rate vs best-of-crepes:")
    rate(["sticky-crps-ensemble"], "sticky-crps-ensemble (hybrid+spike)")
    rate(["crps-ensemble"], "crps-ensemble (hybrid, single)")
    rate(["crps-leaf-1.0"], "crps-leaf-1.0 (bare leaf, single)")
    rate(["laplace"], "laplace (likelihood trunk+leaf)")

    # logpdf comparison (the hybrid keeps a real density too)
    print("\n  mean logpdf:")
    for k in ["sticky-crps-ensemble", "crps-ensemble", "laplace", "crps-leaf-1.0", "dirac"]:
        v = [d[k][1] for d in by.values() if k in d and not math.isnan(d[k][1])]
        if v:
            print(f"      {k:16s} {sum(v)/len(v):7.3f}  (n={len(v)})")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        compare()
    else:
        run()
