"""Decompose Delta_5: score laplace(sticky=False) with the identical
delta-mixture log score. Usage: r5_nosticky.py dev|holdout"""
import os, sys, csv, math
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor, as_completed
HERE = os.path.dirname(os.path.abspath(__file__))
ARM = sys.argv[1] if len(sys.argv) > 1 else "dev"
CACHE = os.path.join(HERE, "data" if ARM == "dev" else "data_holdout")

import fred
fred._CACHE = CACHE
import ladder_ablation as LA
from skaters.api import laplace


def score(job):
    sid, series = job
    try:
        ll, _ = LA._logpdf(lambda: laplace(k=1, objective="likelihood", sticky=False), series)
        return [sid, ll]
    except Exception as e:
        import traceback
        print(f"FAIL {sid}: {e!r}", flush=True)
        traceback.print_exc()
        return [sid, float("nan")]


def main():
    fred._CACHE = CACHE
    data = LA._corpus()
    jobs = sorted(data.items())
    out = os.path.join(HERE, f"r5_nosticky_{ARM}.csv")
    print(f"{len(jobs)} series -> {out}", flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(score, j): j[0] for j in jobs}
        for done, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if done % 25 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}", flush=True)
    rows.sort()
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["series", "R5_nosticky"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
