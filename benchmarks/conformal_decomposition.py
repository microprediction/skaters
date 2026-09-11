"""Conforming versus stopping: matched-predictor decomposition of conformal loss.

Fix ONE point predictor for every method: the full-grammar laplace mean. Then
vary only the residual representation (a genuinely nested state ladder) and, at
each rung, fit BOTH estimators:

  Q_j  score-trained residual law measurable w.r.t. T_j   ("keep transforming")
  C_j  empirical law of the T_j-transformed residuals      ("conform here")

Rungs (residual states, all conditional on the same fixed mean m_t):
  T0  const                      Q0 = N(muR, vR) expanding     C0 = empirical r
  T1  sigma_t (EWMA scale)       Q1 = N(0, sigma_t^2)          C1 = sigma_t * empirical z
  T2  + AR(1) serial state       Q2 = Gaussian AR-whitened     C2 = state + empirical w
  T3  + mixture shape            Q3 = scale-mixture leaf on w  C3 = PIT-recalibrated Q3

Split conformal/CPS is C0; normalized conformal is C1; distributional (PIT)
conformal is C3. The exact telescoping of the paper (eq. conformsplit):

  L(C_j) - L(Q_3) = [L(C_j) - L(Q_j)]  +  sum_{k>j} [L(Q_{k-1}) - L(Q_k)]
                     conforming cost        early-stopping cost

Primary score: CRPS via the K=99 quantile grid (2/K * sum of pinball losses),
proper and identically approximated for every method, defined for empirical
laws. Summaries are per-series normalized by that series' Q0 CRPS.

    PYTHONPATH=src python benchmarks/conformal_decomposition.py [N_SERIES]
"""

from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import bisect
import csv
import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fred
from skaters.api import laplace
from skaters.leaf import scale_mixture_leaf

MIN_LEN = 600
BURN = 300
MAX_WORKERS = min(8, (os.cpu_count() or 4))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conformal_decomposition.csv")

K = 99
TAUS = [(i + 1) / 100.0 for i in range(K)]
try:
    from statistics import NormalDist
    _PHI_INV = [NormalDist().inv_cdf(t) for t in TAUS]
except Exception:
    raise SystemExit("needs python3.8+ statistics.NormalDist")

METHODS = ["Q0", "C0", "Q1", "C1", "Q2", "C2", "Q3", "C3", "LAP"]


def crps_from_quantiles(qs, y):
    """CRPS approximated as (2/K) * sum of pinball losses on the tau grid."""
    s = 0.0
    for t, q in zip(TAUS, qs):
        d = y - q
        s += (t * d) if d >= 0 else ((t - 1.0) * d)
    return 2.0 * s / K


def emp_quantiles(sorted_vals):
    """Type-7-ish empirical quantiles on the tau grid from a sorted list."""
    n = len(sorted_vals)
    out = []
    for t in TAUS:
        h = t * (n - 1)
        i = int(h)
        g = h - i
        out.append(sorted_vals[i] if i + 1 >= n
                   else sorted_vals[i] * (1 - g) + sorted_vals[i + 1] * g)
    return out


def score_series(job):
    sid, series = job
    try:
        return _score_series(sid, series)
    except Exception as e:
        return [sid, len(series)] + [float("nan")] * len(METHODS) + [repr(e)]


def _score_series(sid, series):
    # ---- pass 1: fixed point predictor = full-grammar laplace mean -------
    # Also record laplace's own predictive quantiles: the "transforms all the
    # way down, conform last" cell of the grid, under the same CRPS grid.
    f = laplace(k=1, objective="likelihood")
    state = None
    pend = None
    means = []          # m_t: mean forecast made BEFORE seeing y_t (index t)
    lap_q = []          # laplace's predictive quantiles at t (or None)
    for y in series:
        means.append(pend[0].mean if pend is not None else 0.0)
        lap_q.append([pend[0].quantile(t) for t in TAUS] if pend is not None else None)
        d, state = f(y, state)
        pend = d

    # ---- pass 2: residual ladder, prequential ---------------------------
    alpha = 0.03        # EWMA rate for the scale state
    lam = 0.995         # decay for the AR(1) recursion
    muR = 0.0; vR_m2 = 0.0; nR = 0          # expanding residual moments (T0)
    v = None            # EWMA residual variance (T1)
    g = None            # expanding residual variance for the scale floor
    sxx = 1e-8; sxy = 0.0                   # decayed AR(1) sums on z (T2)
    s2w = 1.0           # EWMA variance of AR-whitened w
    leaf = scale_mixture_leaf(k=1)          # mixture shape on w (T3)
    leaf_state = None
    leaf_pend = None
    z_prev = 0.0
    sorted_r = []; sorted_z = []; sorted_w = []; sorted_u = []
    crps = {m: 0.0 for m in METHODS}
    nsc = 0

    for t in range(1, len(series)):
        y = series[t]
        m = means[t]
        r = y - m

        # ---- states available BEFORE seeing r (from data up to t-1) -----
        varR = vR_m2 / (nR - 1) if nR > 2 else None
        lo = 0.0025 * (g if g else 0.0)
        vt = max(v if v is not None else (varR or 1.0), lo)
        sig = math.sqrt(vt) if vt > 0 else 1.0
        phi = max(-0.99, min(0.99, sxy / sxx)) if sxx > 1e-9 else 0.0
        arm = phi * z_prev                    # AR(1) mean of z_t
        sw = math.sqrt(max(s2w, 1e-12))

        ok = (t > BURN and varR is not None and len(sorted_r) > 50
              and len(sorted_w) > 50 and len(sorted_u) > 50
              and leaf_pend is not None and lap_q[t] is not None)
        if ok:
            qs = {}
            qs["Q0"] = [m + muR + math.sqrt(varR) * q for q in _PHI_INV]
            qs["C0"] = [m + q for q in emp_quantiles(sorted_r)]
            qs["Q1"] = [m + sig * q for q in _PHI_INV]
            qs["C1"] = [m + sig * q for q in emp_quantiles(sorted_z)]
            qs["Q2"] = [m + sig * (arm + sw * q) for q in _PHI_INV]
            qs["C2"] = [m + sig * (arm + q) for q in emp_quantiles(sorted_w)]
            D = leaf_pend[0]
            q3w = [D.quantile(tau) for tau in TAUS]
            qs["Q3"] = [m + sig * (arm + q) for q in q3w]
            if len(sorted_u) > 50:
                uq = emp_quantiles(sorted_u)
                q3c = [D.quantile(min(0.9999, max(0.0001, u))) for u in uq]
                qs["C3"] = [m + sig * (arm + q) for q in q3c]
            else:
                qs["C3"] = qs["Q3"]
            qs["LAP"] = lap_q[t]
            for meth in METHODS:
                crps[meth] += crps_from_quantiles(qs[meth], y)
            nsc += 1

        # ---- update states with the observed residual -------------------
        nR += 1
        d0 = r - muR
        muR += d0 / nR
        vR_m2 += d0 * (r - muR)
        g = r * r if g is None else g + (r * r - g) / nR
        v = r * r if v is None else (1 - alpha) * v + alpha * r * r
        z = r / sig
        w = z - arm
        sxx = lam * sxx + z_prev * z_prev
        sxy = lam * sxy + z_prev * z
        s2w = (1 - alpha) * s2w + alpha * w * w
        if leaf_pend is not None:
            u = leaf_pend[0].cdf(w)
            if math.isfinite(u):
                bisect.insort(sorted_u, min(1.0, max(0.0, u)))
        ld, leaf_state = leaf(w, leaf_state)
        leaf_pend = ld
        bisect.insort(sorted_r, r)
        bisect.insort(sorted_z, z)
        bisect.insort(sorted_w, w)
        z_prev = z

    if not nsc:
        return [sid, len(series)] + [float("nan")] * len(METHODS) + ["too short"]
    return [sid, len(series)] + [crps[m] / nsc for m in METHODS]


def _corpus():
    out = {}
    for fn in sorted(os.listdir(fred._CACHE)):
        if not fn.endswith(".csv") or fn == "m4_hourly.csv":
            continue
        sid = fn[:-4]
        ch = fred._to_changes(fred._load_levels(sid) or [])
        if len(ch) < MIN_LEN:
            continue
        rep = sum(1 for i in range(1, len(ch)) if ch[i] == ch[i - 1]) / (len(ch) - 1)
        if rep < 0.05:
            out[sid] = ch
    return out


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    data = _corpus()
    ids = sorted(data)
    if limit:
        step = max(1, len(ids) // limit)
        ids = ids[::step][:limit]
    jobs = [(sid, data[sid]) for sid in ids]
    print(f"{len(jobs)} continuous series, fixed laplace mean, "
          f"{MAX_WORKERS} workers -> {OUT}", flush=True)

    rows = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score_series, j): j[0] for j in jobs}
        for done, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if done % 10 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}", flush=True)

    rows.sort()
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["series", "n"] + METHODS)
        w.writerows(rows)

    good = [r for r in rows if len(r) == 2 + len(METHODS)
            and all(isinstance(x, float) and math.isfinite(x) and x > 0 for x in r[2:])]
    print(f"\n{len(good)}/{len(rows)} series scored")
    if not good:
        return
    import statistics
    # normalize each series by its Q0 CRPS so scales are comparable
    norm = [{m: r[2 + i] / r[2] for i, m in enumerate(METHODS)} for r in good]
    print("\nCRPS relative to Q0 (mean / median across series; lower is better):")
    for m in METHODS:
        vals = [d[m] for d in norm]
        print(f"  {m}: {statistics.mean(vals):.4f} / {statistics.median(vals):.4f}")
    print("\nconforming vs fitting at the same rung, C_j - Q_j (share of series where"
          " conforming HELPS):")
    for j in range(4):
        dif = [d[f"C{j}"] - d[f"Q{j}"] for d in norm]
        helps = sum(1 for x in dif if x < 0) / len(dif)
        print(f"  rung {j}: mean {statistics.mean(dif):+.4f} "
              f"median {statistics.median(dif):+.4f}  conforming helps on "
              f"{100*helps:.0f}% of series")
    print("\nearly stopping cost, Q_j - Q3:")
    for j in range(3):
        dif = [d[f"Q{j}"] - d["Q3"] for d in norm]
        print(f"  rung {j}: mean {statistics.mean(dif):+.4f} "
              f"median {statistics.median(dif):+.4f}")
    lapc1 = [d["LAP"] - d["C1"] for d in norm]
    print("\nlaplace full density vs normalized conformal, LAP - C1: "
          "mean %+.4f median %+.4f, laplace better on %.0f%% of series" % (
              statistics.mean(lapc1), statistics.median(lapc1),
              100 * sum(1 for x in lapc1 if x < 0) / len(lapc1)))
    print("\ndecomposition for split conformal C0 vs best fitted Q3 "
          "(normalized units):")
    conf = [d["C0"] - d["Q0"] for d in norm]
    stop = [d["Q0"] - d["Q3"] for d in norm]
    tot = [d["C0"] - d["Q3"] for d in norm]
    print(f"  total shortfall  mean {statistics.mean(tot):+.4f}")
    print(f"  conforming part  mean {statistics.mean(conf):+.4f}")
    print(f"  stopping part    mean {statistics.mean(stop):+.4f}")


if __name__ == "__main__":
    main()
