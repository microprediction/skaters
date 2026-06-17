"""Does the Yeo-Johnson coordinate prior pay? (NFL ablation, on levels.)

The coordinate group only helps in the space where it applies: forecasting a
*level* whose natural coordinate is multiplicative/log (prices, indices). So we
feed raw LEVELS (not changes) to two otherwise-identical ensembles:

  with-coord    = laplace's full pool (includes the Yeo-Johnson group)
  without-coord = the same pool minus the coordinate candidates

and compare held-out log-likelihood, split by whether the series is strictly
positive. NFL prediction: with-coord wins on positive/multiplicative series and
is ~neutral (a wrong coordinate is down-weighted) on signed ones.

    PYTHONPATH=src python benchmarks/coord_ablation.py
"""

from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fred
from skaters.api import _build_candidates
from skaters.terminal import terminal_leaf_ensemble

MIN_LEN = 800
MAX_WORKERS = min(8, (os.cpu_count() or 4))


def _ensemble(drop=None):
    cands, depths, groups = _build_candidates(1)
    drop = set(groups["coordinate"]) if drop == "coord" else set()
    keep = [i for i in range(len(cands)) if i not in drop]
    c = [cands[i] for i in keep]
    d = [depths[i] for i in keep]
    return terminal_leaf_ensemble(c, k=1, learning_rate=0.8,
                                  complexity_penalty=0.005, depths=d, max_components=20)


def _logpdf(make, series, burn=300):
    f = make()
    state = None
    pend = None
    lp = 0.0
    n = 0
    for i, y in enumerate(series):
        if pend is not None and i > burn:
            v = pend[0].logpdf(y)
            lp += v if math.isfinite(v) else -20.0
            n += 1
        d, state = f(y, state)
        pend = d
    return lp / n if n else float("nan")


def score(sid):
    levels = fred._load_levels(sid)
    vals = [v for _, v in levels] if levels else []
    if len(vals) < MIN_LEN:
        return None
    positive = all(v > 0 for v in vals)
    with_c = _logpdf(lambda: _ensemble(drop=None), vals)
    without_c = _logpdf(lambda: _ensemble(drop="coord"), vals)
    return (sid, positive, with_c, without_c)


def main():
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    rows = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score, s): s for s in ids}
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r:
                rows.append(r)
            if done % 50 == 0:
                print(f"  {done}/{len(ids)} scored", flush=True)

    import numpy as np
    for label, sub in [("positive (log-coordinate applies)", [r for r in rows if r[1]]),
                       ("signed (coordinate should be neutral)", [r for r in rows if not r[1]]),
                       ("ALL", rows)]:
        if not sub:
            continue
        diff = np.array([r[2] - r[3] for r in sub])     # with - without
        win = float(np.mean(diff > 0)) * 100
        print(f"\n{label}: n={len(sub)}")
        print(f"  mean logpdf  with-coord {np.mean([r[2] for r in sub]):+.3f}  "
              f"without {np.mean([r[3] for r in sub]):+.3f}  "
              f"delta {diff.mean():+.4f} nats")
        print(f"  with-coord better on {win:.0f}% of series")


if __name__ == "__main__":
    main()
