"""Genuinely exact Bayes pools for the grammar paper's nesting proposition.

The earlier runner (gaussianize_pool_exact.py) used the shared ensemble,
which clamps each expert's log density to [-20, 20] before the weight
update, prunes the emitted mixture to 20 components, and leaves the
scoring reference blend outside the updates. This runner removes all
three gaps so the telescoping identity applies verbatim to the scored
log likelihoods:

  - expert weights update by the exact blended likelihood
    p_bar_c(y) = (1 - DELTA_REF) p_c(y) + DELTA_REF g(y), with g the same
    expanding-window Gaussian reference the scorer uses, in the same
    update order;
  - the emitted mixture is never pruned, and the log score is computed
    from the full mixture, so the scored density is exactly the Bayes
    mixture over the blended experts;
  - the depth prior is applied once, through the initial log weights.

CRPS is reported from a 20-component pruned copy of the predictive, for
cost only. The log score and the weights are exact.

Writes grammar_exact_bayes.csv with per-series ll/crps for pools
G (with gaussianize chains) and H (without).

Run:  python grammar_exact_bayes.py [limit]
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

import ladder_ablation as LA
import gaussianize_chain as GC
from skaters.dist import Dist

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "grammar_exact_bayes.csv")
CONFIGS = ["G_exact", "H_exact"]


def exact_bayes_pool(cands, prior_log_weights):
    """Exact Bayes mixture over blended experts, unclamped and unpruned."""
    delta = LA.DELTA_REF
    log_keep, log_ref = math.log(1 - delta), math.log(delta)

    def _pool(y, state):
        if state is None:
            state = {"s": [None] * len(cands), "pend": [None] * len(cands),
                     "lw": list(prior_log_weights),
                     "n": 0, "mu": 0.0, "m2": 0.0}
        # 1. update weights with the blended likelihood of each pending
        #    predictive, using the reference built from strictly past data
        if state["pend"][0] is not None and state["n"] > 2 and state["m2"] > 0:
            var = state["m2"] / (state["n"] - 1)
            lg = -0.5 * math.log(2 * math.pi * var) \
                - (y - state["mu"]) ** 2 / (2 * var)
            for i, pend in enumerate(state["pend"]):
                lq = pend[0].logpdf(y)
                if not math.isfinite(lq):
                    lq = -1e12
                a, b = log_keep + lq, log_ref + lg
                hi = max(a, b)
                state["lw"][i] += hi + math.log(math.exp(a - hi)
                                                + math.exp(b - hi))
            mx = max(state["lw"])
            state["lw"] = [w - mx for w in state["lw"]]
        # 2. absorb y into the reference moments
        state["n"] += 1
        d0 = y - state["mu"]
        state["mu"] += d0 / state["n"]
        state["m2"] += d0 * (y - state["mu"])
        # 3. run the experts and emit the full posterior-weighted mixture
        dists = []
        for i, c in enumerate(cands):
            d, state["s"][i] = c(y, state["s"][i])
            state["pend"][i] = d
            dists.append(d)
        ws = [math.exp(w) for w in state["lw"]]
        tot = sum(ws)
        comps = []
        for w, d in zip(ws, dists):
            for (cw, mu, sd) in d[0].components:
                comps.append((w / tot * cw, mu, sd))
        return [Dist(comps)], state
    return _pool


def _make(name):
    cands = GC._candidates(with_gauss=(name == "G_exact"), sm=False)
    prior = [-0.005 * d for _, d in cands]
    return exact_bayes_pool([c for c, _ in cands], prior)


def _score_pool(make, series):
    """GC._score with CRPS taken from a pruned copy of the predictive.
    The log score uses the full mixture and is exact."""
    f = make()
    state = None
    pend = None
    lp = cr = 0.0
    n = 0
    mu = m2 = 0.0
    nobs = 0
    for i, y in enumerate(series):
        if pend is not None and i > GC.BURN and nobs > 2 and m2 > 0:
            var = m2 / (nobs - 1)
            lg = -0.5 * math.log(2 * math.pi * var) - (y - mu) ** 2 / (2 * var)
            lq = pend[0].logpdf(y)
            if not math.isfinite(lq):
                lq = -1e12
            a = math.log(1 - LA.DELTA_REF) + lq
            b = math.log(LA.DELTA_REF) + lg
            hi = max(a, b)
            lp += hi + math.log(math.exp(a - hi) + math.exp(b - hi))
            cr += pend[0].prune(20).crps(y)
            n += 1
        nobs += 1
        d0 = y - mu
        mu += d0 / nobs
        m2 += d0 * (y - mu)
        d, state = f(y, state)
        pend = d
    return (lp / n, cr / n) if n else (float("nan"), float("nan"))


def score(job):
    sid, series = job
    try:
        row = [sid, len(series)]
        for name in CONFIGS:
            ll, cr = _score_pool(lambda nm=name: _make(nm), series)
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
    print(f"exact pools: mean ll G {st.mean(g_ll):.4f}  H {st.mean(h_ll):.4f}"
          f"  delta {st.mean(g_ll) - st.mean(h_ll):+.4f}")


if __name__ == "__main__":
    main()
