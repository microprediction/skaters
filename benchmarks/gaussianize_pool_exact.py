"""Exact-Bayes pool check for the grammar paper's Proposition (nesting bound).

Reruns pools G (with gaussianize chains) and H (without) as literal Bayes
mixtures: learning_rate = 1, no per-step complexity penalty, and the depth
prior applied ONCE through prior_log_weights, pi_c proportional to
exp(-0.005 * depth(c)). Proposition 6's telescoping identity then applies
verbatim to the reported pools.

Writes gaussianize_pool_exact.csv with per-series ll/crps for both pools.

Run:  python gaussianize_pool_exact.py [limit]
"""
from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import csv
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ladder_ablation as LA
import gaussianize_chain as GC
from skaters.bayesian import bayesian_ensemble

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "gaussianize_pool_exact.csv")
CONFIGS = ["Gx_pool_exact", "Hx_pool_exact"]


def _make(name):
    cands = GC._candidates(with_gauss=(name == "Gx_pool_exact"), sm=False)
    prior = [-0.005 * d for _, d in cands]
    return bayesian_ensemble([c for c, _ in cands], k=1, learning_rate=1.0,
                             complexity_penalty=0.0,
                             prior_log_weights=prior, max_components=20)


def score(job):
    sid, series = job
    try:
        row = [sid, len(series)]
        for name in CONFIGS:
            ll, cr = GC._score(lambda nm=name: _make(nm), series)
            row += [ll, cr]
        return row
    except Exception:
        return [sid, len(series)] + [float("nan")] * (2 * len(CONFIGS))


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    data = LA._corpus()
    ids = sorted(data)
    if limit:
        step = max(1, len(ids) // limit)
        ids = ids[::step][:limit]
    jobs = [(sid, data[sid]) for sid in ids]
    print(f"{len(jobs)} series x {len(CONFIGS)} exact-Bayes pools", flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=GC.MAX_WORKERS) as ex:
        futs = {ex.submit(score, j): j[0] for j in jobs}
        for k, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if k % 50 == 0:
                print(f"{k}/{len(jobs)}", flush=True)
    rows.sort(key=lambda r: r[0])
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "n"] + [f"{s}_{c}" for c in CONFIGS
                                      for s in ("ll", "crps")])
        w.writerows(rows)
    import statistics as st
    g_ll = [r[2] for r in rows if r[2] == r[2]]
    h_ll = [r[4] for r in rows if r[4] == r[4]]
    print(f"exact-Bayes pools: mean ll G {st.mean(g_ll):.4f}  H {st.mean(h_ll):.4f}"
          f"  delta {st.mean(g_ll) - st.mean(h_ll):+.4f}")


if __name__ == "__main__":
    main()
