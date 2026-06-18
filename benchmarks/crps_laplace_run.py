"""Score 'laplace trained on CRPS' on the 2.5k-series universe.

Demonstrates metric-agnosticism cleanly: laplace's EXACT structure (full
candidate trunk) with the terminal leaf's objective swapped from likelihood to
CRPS (leaf_fn=crps_leaf). Appends 'crps-laplace' rows to results_refresh.csv so
it can be compared against the same crepes on the same series.
"""
from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v,"1")
import csv, math, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fred
from crps_leaf import crps_leaf
from exhaustive_crps import skater_scores
from skaters.api import _build_candidates
from skaters.terminal import terminal_leaf_ensemble

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results_refresh.csv")
NAME = "crps-laplace"
MIN_CHANGES = 500
WORKERS = min(8, os.cpu_count() or 4)

def make(k=1):
    cands, depths, _ = _build_candidates(k)   # laplace's pool
    return terminal_leaf_ensemble(cands, leaf_fn=lambda k=1: crps_leaf(k=k, eta=1.0), k=k,
                                  learning_rate=0.8, complexity_penalty=0.005, depths=depths, max_components=20)

def score(sid):
    ch = fred._to_changes(fred._load_levels(sid) or [])
    if len(ch) < MIN_CHANGES: return sid, None
    try:
        crps, lp, n = skater_scores(make, ch)
        return sid, [sid, NAME, f"{crps:.6f}", f"{lp:.6f}", n]
    except Exception as e:
        print(f"  ERR {sid}: {e}", flush=True); return sid, None

def main():
    series = sorted({r["series"] for r in csv.DictReader(open(RESULTS))})
    done = {r["series"] for r in csv.DictReader(open(RESULTS)) if r["forecaster"] == NAME}
    todo = [s for s in series if s not in done]
    print(f"scoring {NAME} on {len(todo)} series ({len(done)} done)", flush=True)
    fin = 0
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(score, s): s for s in todo}
        for fut in as_completed(futs):
            _, row = fut.result()
            if row:
                with open(RESULTS, "a") as f: csv.writer(f).writerows([row])
            fin += 1
            if fin % 100 == 0: print(f"  {fin}/{len(todo)}", flush=True)
    print("done", flush=True)

if __name__ == "__main__":
    main()
