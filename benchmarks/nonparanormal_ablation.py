"""Does the nonparanormal marginal transform pay? (issue #80 ablation)

Liu, Lafferty & Wasserman (JMLR 2009) estimate a Gaussian copula by Gaussianizing
each margin through a (Winsorized) empirical CDF: z = Phi^{-1}(F_n(y)). The
multivariate payoff (graph estimation) does not apply to a univariate stream, but
the marginal transform itself is a candidate *coordinate*: model the series where
its stationary marginal is exactly N(0,1), then push the predictive back through
the monotone inverse so it inherits the empirical marginal's skew/kurtosis.

Placement matters. In "model first, conform last" the trunk combines candidate
MEANS and the terminal leaf supplies all variance/tails — a pool candidate's
inverse-mapped shape never reaches the output distribution. So the honest test is
the OUTER conjugation of the whole forecaster:

    npn  = conjugate(laplace(k=1), gaussianize(), k=1)     # on the change series

Two departures from the paper, both deliberate:

  * No hard Winsorization. delta_n-clipping is variance control for covariance
    estimation; for density forecasting it flattens F exactly where the log-score
    is decided (new records). Instead the empirical CDF is blended with a running
    Gaussian, F = (n0*Phi + n*F_emp)/(n0 + n), which keeps F strictly increasing
    with Gaussian tails — finite density beyond the observed range, smooth inverse.
  * Online/causal: F_n uses only past observations (plus the running-moment
    Gaussian anchor), so the transform is a legal skaters (forward, inverse_k) pair.

Control arm: the SAME wrapper with n0 -> inf is cumulative standardization — it
isolates "the nonparametric shape helped" from "an outer standardize helped".

    PYTHONPATH=src python benchmarks/nonparanormal_ablation.py
    MAX_SERIES=40 PYTHONPATH=src python benchmarks/nonparanormal_ablation.py
"""

from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import bisect
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fred
import fred_universe
from bench_core import roll_dist_scores
from skaters import laplace
from skaters.conjugate import conjugate
from skaters.dist import Dist

MIN_CHANGES = 700
MAX_WORKERS = min(8, (os.cpu_count() or 4))
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "comparisons", "_nonparanormal.csv")


# ---------------------------------------------------------------------------
# Standard-normal quantile (Acklam's rational approximation, |rel err| < 1.2e-9)
# ---------------------------------------------------------------------------

_A = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
      1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
_B = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
      6.680131188771972e+01, -1.328068155288572e+01)
_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
      -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
      3.754408661907416e+00)
_P_LO, _P_HI = 0.02425, 1.0 - 0.02425


def _phi_inv(p: float) -> float:
    p = min(max(p, 1e-15), 1.0 - 1e-15)
    if p < _P_LO:
        q = math.sqrt(-2.0 * math.log(p))
        return ((((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5])
                / ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0))
    if p > _P_HI:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -((((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5])
                 / ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0))
    q = p - 0.5
    r = q * q
    return ((((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q
            / (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1.0))


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# ---------------------------------------------------------------------------
# The transform
# ---------------------------------------------------------------------------

def gaussianize(n0: float = 8.0, max_buffer: int = 4000):
    """Nonparanormal marginal transform: z = Phi^{-1}(F(y)), F a blended CDF.

    F(y) = (n0 * Phi((y - mu)/sigma) + n * F_emp(y)) / (n0 + n)

    where F_emp uses midranks (ties safe) and (mu, sigma) are cumulative running
    moments. n0 is the prior weight of the Gaussian anchor: small n0 -> the
    empirical shape dominates once n >> n0; n0 = inf (pass float('inf')) is the
    cumulative-standardization control. The forward is causal (buffer excludes
    the current point at evaluation time). The inverse maps each mixture
    component through the monotone quantile function: exact on the mean, and a
    symmetric quantile half-width for the std (the delta method without needing
    a density estimate).
    """
    pure_gauss = math.isinf(n0)

    def _F(y, buf, n, mu, sigma, count):
        g = _phi((y - mu) / sigma) if sigma > 0 else 0.5
        if pure_gauss or not buf:
            return g
        lo = bisect.bisect_left(buf, y)
        hi = bisect.bisect_right(buf, y)
        femp = (lo + 0.5 * (hi - lo) + 0.5) / (n + 1.0)
        return (n0 * g + n * femp) / (n0 + n)

    def _Q(p, buf, n, mu, sigma, count):
        """Invert the blended CDF by monotone bisection."""
        p = min(max(p, 1e-12), 1.0 - 1e-12)
        span = max(sigma, 1e-12)
        lo = (buf[0] if buf else mu) - 10.0 * span
        hi = (buf[-1] if buf else mu) + 10.0 * span
        while _F(lo, buf, n, mu, sigma, count) > p:
            lo -= 10.0 * span
        while _F(hi, buf, n, mu, sigma, count) < p:
            hi += 10.0 * span
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if _F(mid, buf, n, mu, sigma, count) < p:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            state = {"buf": [], "count": 0, "mean": 0.0, "m2": 0.0}
        if not math.isfinite(y):
            return 0.0, state
        buf, count = state["buf"], state["count"]
        n = len(buf)
        if count >= 2 and state["m2"] > 0:
            sigma = math.sqrt(state["m2"] / count)
            z = _phi_inv(_F(y, buf, n, state["mean"], sigma, count))
        else:
            z = 0.0
        # update running moments (Welford) and the sorted buffer
        count += 1
        delta = y - state["mean"]
        mean = state["mean"] + delta / count
        m2 = state["m2"] + delta * (y - mean)
        if not pure_gauss:
            bisect.insort(buf, y)
            if len(buf) > max_buffer:
                # drop an interior point rather than an extreme (keep the tails)
                del buf[len(buf) // 2]
        state = {"buf": buf, "count": count, "mean": mean, "m2": m2}
        return z, state

    def inverse_k(dists: list[Dist], state: dict) -> list[Dist]:
        count = state["count"]
        if count < 2 or state["m2"] <= 0:
            return dists
        buf = state["buf"]
        n = len(buf)
        mu = state["mean"]
        sigma = math.sqrt(state["m2"] / count)
        out = []
        for d in dists:
            comps = []
            for w, m, s in d.components:
                y_m = _Q(_phi(m), buf, n, mu, sigma, count)
                y_hi = _Q(_phi(m + s), buf, n, mu, sigma, count)
                y_lo = _Q(_phi(m - s), buf, n, mu, sigma, count)
                comps.append((w, y_m, max(0.5 * (y_hi - y_lo), 1e-15)))
            out.append(Dist(comps))
        return out

    return forward, inverse_k


# ---------------------------------------------------------------------------
# Study harness
# ---------------------------------------------------------------------------

ARMS = {
    "base": lambda: laplace(k=1),
    "npn":  lambda: conjugate(laplace(k=1), gaussianize(n0=8.0), k=1),
    "ctrl": lambda: conjugate(laplace(k=1), gaussianize(n0=float("inf")), k=1),
}


def score(sid):
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    if len(ch) < MIN_CHANGES:
        return None
    row = {"sid": sid}
    for name, make in ARMS.items():
        lp, cr, n = roll_dist_scores(make, ch)
        if not (math.isfinite(lp) and math.isfinite(cr)):
            return None
        row[name + "_lp"], row[name + "_cr"] = lp, cr
    # marginal shape of the changes, for the split
    m = len(ch)
    mu = sum(ch) / m
    c2 = sum((x - mu) ** 2 for x in ch) / m
    c3 = sum((x - mu) ** 3 for x in ch) / m
    c4 = sum((x - mu) ** 4 for x in ch) / m
    row["skew"] = c3 / c2 ** 1.5 if c2 > 0 else 0.0
    row["kurt"] = c4 / c2 ** 2 - 3.0 if c2 > 0 else 0.0
    return row


def main():
    uj = os.path.join(fred._CACHE, "universe_daily.json")
    tmap = ({s["id"]: s.get("title", "") for s in json.load(open(uj))}
            if os.path.exists(uj) else {})
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    if os.environ.get("STUDY_EXCLUDE_PRICE") == "1":
        _PRICE = {"equity", "fx", "commodity"}
        ids = [s for s in ids if fred_universe.asset_class(tmap.get(s, "")) not in _PRICE]
    cap = int(os.environ.get("MAX_SERIES", "0"))
    if cap:
        ids = ids[::max(1, len(ids) // cap)][:cap]

    rows = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score, s): s for s in ids}
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r:
                rows.append(r)
            if done % 20 == 0:
                print(f"  {done}/{len(ids)} scored ({len(rows)} kept)", flush=True)

    if not rows:
        print("no qualifying series (need cached FRED data)")
        return

    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    cols = list(rows[0].keys())
    with open(RESULTS, "w") as fh:
        fh.write(",".join(cols) + "\n")
        for r in rows:
            fh.write(",".join(str(r[c]) for c in cols) + "\n")
    print(f"wrote {len(rows)} rows -> {RESULTS}\n")

    import numpy as np
    absk = np.array([abs(r["skew"]) for r in rows])
    med = float(np.median(absk))
    splits = [
        ("ALL", rows),
        (f"|skew| > median ({med:.2f}) — shape should matter", [r for r in rows if abs(r["skew"]) > med]),
        (f"|skew| <= median — shape should be ~neutral", [r for r in rows if abs(r["skew"]) <= med]),
    ]
    for label, sub in splits:
        if not sub:
            continue
        print(f"{label}: n={len(sub)}")
        for arm in ("npn", "ctrl"):
            dlp = np.array([r[arm + "_lp"] - r["base_lp"] for r in sub])
            dcr = np.array([r["base_cr"] - r[arm + "_cr"] for r in sub])  # + = arm better
            print(f"  {arm} vs base:  LL {float(np.mean(dlp)):+.4f} nats "
                  f"(win {float(np.mean(dlp > 0)) * 100:.0f}%)   "
                  f"CRPS win {float(np.mean(dcr > 0)) * 100:.0f}%")
        print()


if __name__ == "__main__":
    main()
