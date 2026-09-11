"""In-situ terminal-leaf A/B inside shipped laplace.

Four configurations, identical everywhere except the terminal leaf:
  A  shipped, objective='crps'        (crps_leaf)
  B  shipped, objective='likelihood'  (scale_mixture_leaf)
  C  laplace(leaf=conforming_leaf)    (empirical KDE-as-Dist)
  D  laplace(leaf=ensemble_leaf)      (score-weighted conforming+mixture)

Each is scored prequentially on BOTH metrics: the delta-mixture log score
(as in ladder_ablation) and a 19-point quantile approximation to CRPS
(taus 0.05..0.95 via Dist.quantile). Sticky/gpdtails/parade stay at shipped
defaults in every configuration, so this isolates the leaf.

    PYTHONPATH=src python benchmarks/leaf_insitu.py [N_SERIES]
"""
from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")
import csv, math, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fred
from ladder_ablation import _corpus, BURN, DELTA_REF
from skaters.api import laplace
from skaters.leaf import conforming_leaf, ensemble_leaf

MAX_WORKERS = min(8, (os.cpu_count() or 4))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leaf_insitu.csv")
TAUS = [i / 20.0 for i in range(1, 20)]
CONFIGS = ["A_crps", "B_lik", "C_conf", "D_ens"]


def make(cfg):
    if cfg == "A_crps":
        return laplace(k=1)
    if cfg == "B_lik":
        return laplace(k=1, objective="likelihood")
    if cfg == "C_conf":
        return laplace(k=1, leaf=partial(conforming_leaf))
    return laplace(k=1, leaf=partial(ensemble_leaf))


def run_one(cfg, series):
    f = make(cfg)
    state = None; pend = None
    mu = 0.0; m2 = 0.0; nobs = 0
    ll = 0.0; cr = 0.0; n = 0
    for i, y in enumerate(series):
        if pend is not None and i > BURN and nobs > 2 and m2 > 0:
            var = m2 / (nobs - 1)
            lg = -0.5 * math.log(2 * math.pi * var) - (y - mu) ** 2 / (2 * var)
            lq = pend[0].logpdf(y)
            if not math.isfinite(lq):
                lq = -1e12
            a = math.log(1 - DELTA_REF) + lq
            b = math.log(DELTA_REF) + lg
            hi = max(a, b)
            ll += hi + math.log(math.exp(a - hi) + math.exp(b - hi))
            s = 0.0
            for t in TAUS:
                q = pend[0].quantile(t)
                d = y - q
                s += (t * d) if d >= 0 else ((t - 1.0) * d)
            cr += 2.0 * s / len(TAUS)
            n += 1
        nobs += 1
        d0 = y - mu
        mu += d0 / nobs
        m2 += d0 * (y - mu)
        d, state = f(y, state)
        pend = d
    return (ll / n if n else float("nan"), cr / n if n else float("nan"))


def score(job):
    sid, series = job
    try:
        row = [sid, len(series)]
        for cfg in CONFIGS:
            ll, cr = run_one(cfg, series)
            row += [ll, cr]
        return row
    except Exception:
        return [sid, len(series)] + [float("nan")] * (2 * len(CONFIGS))


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    data = _corpus()
    ids = sorted(data)
    if limit:
        step = max(1, len(ids) // limit)
        ids = ids[::step][:limit]
    jobs = [(sid, data[sid]) for sid in ids]
    print(f"{len(jobs)} series x {len(CONFIGS)} configs -> {OUT}", flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score, j): j[0] for j in jobs}
        for done, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if done % 25 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}", flush=True)
    rows.sort()
    cols = ["series", "n"] + [f"{m}_{c}" for c in CONFIGS for m in ("ll", "crps")]
    cols = ["series", "n"]
    for c in CONFIGS:
        cols += [f"ll_{c}", f"crps_{c}"]
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        w.writerows(rows)
    import statistics, random
    good = [r for r in rows if all(isinstance(x, float) and math.isfinite(x) for x in r[2:])]
    print(f"\n{len(good)}/{len(rows)} series scored")
    if not good:
        return
    idx = {name: i + 2 for i, name in enumerate(
        [f"{m}_{c}" for c in CONFIGS for m in ("ll", "crps")])}
    idx = {}
    j = 2
    for c in CONFIGS:
        idx[f"ll_{c}"] = j; idx[f"crps_{c}"] = j + 1; j += 2
    print("\nlog score (nats/obs, higher better):")
    for c in CONFIGS:
        v = [r[idx[f"ll_{c}"]] for r in good]
        print(f"  {c:7s} mean {statistics.mean(v):+.4f} median {statistics.median(v):+.4f}")
    print("\nCRPS relative to A_crps (lower better):")
    base = [r[idx["crps_A_crps"]] for r in good]
    for c in CONFIGS:
        v = [r[idx[f"crps_{c}"]] / b for r, b in zip(good, base) if b > 0]
        print(f"  {c:7s} mean {statistics.mean(v):.4f} median {statistics.median(v):.4f}")
    rng = random.Random(0)
    for m, better in (("crps", -1), ("ll", 1)):
        for c in ("C_conf", "D_ens"):
            ref = "A_crps" if m == "crps" else "B_lik"
            d = [(r[idx[f"{m}_{c}"]] - r[idx[f"{m}_{ref}"]]) * better for r in good]
            wins = sum(1 for x in d if x > 0) / len(d)
            boots = []
            for _ in range(1000):
                sm = [d[rng.randrange(len(d))] for _ in range(len(d))]
                boots.append(sum(sm) / len(sm))
            boots.sort()
            print(f"{m}: {c} vs {ref}: mean improvement {statistics.mean(d):+.5f} "
                  f"[90% {boots[50]:+.5f},{boots[949]:+.5f}] wins {100*wins:.0f}%")


if __name__ == "__main__":
    main()
