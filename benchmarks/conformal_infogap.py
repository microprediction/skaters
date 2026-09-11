"""Direct information-gap experiment: how much conditional predictability
remains in the transformed residual stream, rung by rung?

For each series, fix the laplace mean and produce four transformed streams
prequentially (same states as conformal_decomposition.py):

  j=0  raw residuals            r_t
  j=1  standardized             z_t = r_t / sigma_t          (EWMA scale)
  j=2  serially whitened        w_t = z_t - phi_t z_{t-1}    (decayed AR(1))
  j=3  PIT-normalized           v_t = Phi^{-1}(F_t(w_t))     (mixture-leaf CDF)

For each stream, compare a CHALLENGER that sees the stream's own past (a fresh
laplace instance run on the stream) against the POOLED marginal law (KDE over
the stream's past values). Both are evaluated as delta-mixtures with the
stream's expanding Gaussian (delta=0.01), so both are genuine densities and
the held-out mean log-score difference

  gap_j = L(pooled) - L(challenger)   (nats/obs)

is the challenger's conditional-versus-pooled predictive gain: the held-out
difference between two past-measurable procedures, exactly
E_H KL(P_{Z|H}||M_H) - E_H KL(P_{Z|H}||Q_H). Since the pooled estimator is
itself computed from the past, there is no isolated mutual-information term;
this is a comparative predictive diagnostic, not an estimate of or bound on
I(Z;past). A genuine bound would use a joint-versus-product variational
objective (DV/NWJ). The theory predicts the curve decreases in j as
transforms remove conditional structure.

    PYTHONPATH=src python benchmarks/conformal_infogap.py [N_SERIES]
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
from statistics import NormalDist

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conformal_decomposition import _corpus, BURN
from skaters.api import laplace
from skaters.leaf import scale_mixture_leaf

MAX_WORKERS = min(8, (os.cpu_count() or 4))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conformal_infogap.csv")
STREAMS = ["raw", "std", "white", "pit"]
DELTA = 0.01
_ND = NormalDist()


def _streams(series):
    """Prequential transformed residual streams under the fixed laplace mean."""
    f = laplace(k=1, objective="likelihood")
    state = None
    pend = None
    means = []
    for y in series:
        means.append(pend[0].mean if pend is not None else 0.0)
        d, state = f(y, state)
        pend = d
    alpha = 0.03
    lam = 0.995
    v = None; g = None; nR = 0
    sxx = 1e-8; sxy = 0.0
    leaf = scale_mixture_leaf(k=1)
    leaf_state = None; leaf_pend = None
    z_prev = 0.0
    out = {m: [] for m in STREAMS}
    for t in range(1, len(series)):
        r = series[t] - means[t]
        lo = 0.0025 * (g if g else 0.0)
        vt = max(v if v is not None else 1.0, lo)
        sig = math.sqrt(vt) if vt > 0 else 1.0
        phi = max(-0.99, min(0.99, sxy / sxx)) if sxx > 1e-9 else 0.0
        z = r / sig
        w = z - phi * z_prev
        out["raw"].append(r)
        out["std"].append(z)
        out["white"].append(w)
        if leaf_pend is not None:
            u = leaf_pend[0].cdf(w)
            u = min(1 - 1e-6, max(1e-6, u)) if math.isfinite(u) else 0.5
            out["pit"].append(_ND.inv_cdf(u))
        else:
            out["pit"].append(0.0)
        nR += 1
        g = r * r if g is None else g + (r * r - g) / nR
        v = r * r if v is None else (1 - alpha) * v + alpha * r * r
        sxx = lam * sxx + z_prev * z_prev
        sxy = lam * sxy + z_prev * z
        ld, leaf_state = leaf(w, leaf_state)
        leaf_pend = ld
        z_prev = z
    return out


def _mix_logpdf(lq, y, mu, var):
    """delta-mixture with the expanding Gaussian reference."""
    if var <= 0 or not math.isfinite(var):
        return lq if math.isfinite(lq) else -20.0
    lg = -0.5 * math.log(2 * math.pi * var) - (y - mu) ** 2 / (2 * var)
    if not math.isfinite(lq):
        lq = -1e12
    a = math.log(1 - DELTA) + lq
    b = math.log(DELTA) + lg
    hi = max(a, b)
    return hi + math.log(math.exp(a - hi) + math.exp(b - hi))


def _kde_logpdf_sorted(sorted_vals, sd, x):
    n = len(sorted_vals)
    h = 1.06 * (sd if sd > 0 else 1.0) * n ** (-0.2)
    centers = sorted_vals if n < 256 else \
        [sorted_vals[int(i * (n - 1) / 255)] for i in range(256)]
    ssum = 0.0
    for m in centers:
        ssum += math.exp(-0.5 * ((x - m) / h) ** 2)
    val = ssum / (len(centers) * h * math.sqrt(2 * math.pi))
    return math.log(val) if val > 0 else -50.0


def _gap(stream):
    """Held-out mean log-score gain of challenger-on-stream over pooled KDE."""
    import bisect
    f = laplace(k=1, objective="likelihood")
    state = None; pend = None
    sorted_v = []
    mu = 0.0; m2 = 0.0; nobs = 0
    tot = 0.0; n = 0
    for i, y in enumerate(stream):
        if pend is not None and i > BURN and nobs > 50 and m2 > 0:
            var = m2 / (nobs - 1)
            sd = math.sqrt(var)
            lch = _mix_logpdf(pend[0].logpdf(y), y, mu, var)
            lpo = _mix_logpdf(_kde_logpdf_sorted(sorted_v, sd, y), y, mu, var)
            tot += lch - lpo
            n += 1
        nobs += 1
        d0 = y - mu
        mu += d0 / nobs
        m2 += d0 * (y - mu)
        bisect.insort(sorted_v, y)
        d, state = f(y, state)
        pend = d
    return tot / n if n else float("nan")


def score(job):
    sid, series = job
    try:
        st = _streams(series)
        return [sid, len(series)] + [_gap(st[m]) for m in STREAMS]
    except Exception as e:
        return [sid, len(series)] + [float("nan")] * len(STREAMS) + [repr(e)]


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    data = _corpus()
    ids = sorted(data)
    if limit:
        step = max(1, len(ids) // limit)
        ids = ids[::step][:limit]
    jobs = [(sid, data[sid]) for sid in ids]
    print(f"{len(jobs)} series, streams {STREAMS}, {MAX_WORKERS} workers -> {OUT}",
          flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score, j): j[0] for j in jobs}
        for done, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if done % 10 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}", flush=True)
    rows.sort()
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["series", "n"] + [f"gap_{m}" for m in STREAMS])
        w.writerows(rows)
    good = [r for r in rows if len(r) == 2 + len(STREAMS)
            and all(isinstance(x, float) and math.isfinite(x) for x in r[2:])]
    print(f"\n{len(good)}/{len(rows)} series scored")
    if not good:
        return
    import random, statistics
    rng = random.Random(0)
    print("\nconditional-versus-pooled challenger gain (nats/obs):")
    for i, m in enumerate(STREAMS):
        vals = [r[2 + i] for r in good]
        boots = []
        for _ in range(1000):
            sm = [vals[rng.randrange(len(vals))] for _ in range(len(vals))]
            boots.append(sum(sm) / len(sm))
        boots.sort()
        pos = sum(1 for x in vals if x > 0) / len(vals)
        print(f"  {m:6s} mean {statistics.mean(vals):+.4f} "
              f"[90% CI {boots[50]:+.4f},{boots[949]:+.4f}] "
              f"median {statistics.median(vals):+.4f}  positive on {100*pos:.0f}%")


if __name__ == "__main__":
    main()
