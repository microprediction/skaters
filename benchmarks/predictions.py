"""Canonical prediction store for the benchmark studies. One schema, one loader.

Every study should record the SAME thing, per (series, method) and per test
STEP: the realized value and the predictive it was scored against. Every metric
(log-likelihood, CRPS, coverage, and Diebold-Mariano draws) then derives from
this one source, instead of each study inventing its own summary CSV in its own
column order. That per-step granularity is also what makes DRAWS possible: the
DM test needs the step-by-step loss differential, which a series-mean summary
throws away.

Schema (CSV, append-friendly and crash-safe like the studies themselves):

    study, series, method, step, y, mean, std, q05, q50, q95, logpdf, crps

- study/series/method/step identify the row; y is the realized value.
- mean/std/q05/q50/q95 summarise the predictive (enough for coverage and for
  re-scoring simple metrics without re-running the model).
- logpdf/crps are the per-step scores (floor logpdf at study time or here).

Derive summaries with mean_scores(); classify contests with dm_contest().
Big per-step files are regenerable (gitignore them); commit the small derived
summaries and the draw labels. skaters core is never imported here beyond Dist.
"""
from __future__ import annotations

import csv
import math
import os

import numpy as np

SCHEMA = ["study", "series", "method", "step", "y",
          "mean", "std", "q05", "q50", "q95", "logpdf", "crps"]

_Z = 1.959963984540054  # z_{0.975}; draw band is +/- _Z * SE(dbar)


# --------------------------------------------------------------- writing
class PredictionWriter:
    """Append per-step rows in the canonical schema. Crash-safe: opens in
    append mode and writes the header only for a fresh file."""

    def __init__(self, path):
        self.path = path
        new = not os.path.exists(path)
        self._fh = open(path, "a", newline="")
        self._w = csv.writer(self._fh)
        if new:
            self._w.writerow(SCHEMA)

    def step(self, study, series, method, step, y, dist=None, *,
             mean=None, std=None, q05=None, q50=None, q95=None,
             logpdf=None, crps=None, floor=-20.0):
        """Record one test step. Pass a skaters Dist to fill mean/std/quantiles
        and the scores automatically, or pass the summary fields directly."""
        if dist is not None:
            mean = dist.mean if mean is None else mean
            std = dist.std if std is None else std
            q05 = dist.quantile(0.05) if q05 is None else q05
            q50 = dist.quantile(0.50) if q50 is None else q50
            q95 = dist.quantile(0.95) if q95 is None else q95
            if logpdf is None:
                lp = dist.logpdf(y)
                logpdf = max(lp, floor) if math.isfinite(lp) else floor
            if crps is None:
                crps = dist.crps(y)
        self._w.writerow([study, series, method, step, _f(y), _f(mean), _f(std),
                          _f(q05), _f(q50), _f(q95), _f(logpdf), _f(crps)])

    def flush(self):
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self):
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def _f(x):
    return "" if x is None else f"{float(x):.6f}"


# --------------------------------------------------------------- loading
def load(path):
    """Return {(series, method): {col: np.array}} with per-step arrays."""
    out = {}
    with open(path) as fh:
        for r in csv.DictReader(fh):
            key = (r["series"], r["method"])
            d = out.setdefault(key, {c: [] for c in SCHEMA[3:]})
            for c in SCHEMA[3:]:
                v = r.get(c, "")
                d[c].append(float(v) if v not in ("", "nan") else np.nan)
    for d in out.values():
        for c in d:
            d[c] = np.asarray(d[c], float)
    return out


def mean_scores(loaded, floor=-20.0):
    """Per (series, method) mean logpdf (floored) and mean crps — the small
    committable study summary that the charts read."""
    rows = {}
    for (s, m), d in loaded.items():
        lp = np.maximum(d["logpdf"], floor)
        rows[(s, m)] = {"logpdf": float(np.nanmean(lp)),
                        "crps": float(np.nanmean(d["crps"])),
                        "n": int(np.isfinite(d["logpdf"]).sum())}
    return rows


# --------------------------------------------------------------- draws (DM)
def dm_contest(ll_a, ll_b, alpha=0.05, floor=-20.0):
    """Diebold-Mariano on the per-step log-score differential d_t = ll_a - ll_b.
    HAC (Newey-West, Bartlett) long-run variance. Returns
    (verdict, dbar, se, stat): verdict is 'A' if A significantly better, 'B' if
    B, else 'draw'. The draw band is |dbar| <= eps with eps = z_{1-alpha/2}*SE."""
    a = np.maximum(np.asarray(ll_a, float), floor)
    b = np.maximum(np.asarray(ll_b, float), floor)
    d = a - b
    d = d[np.isfinite(d)]
    n = len(d)
    if n < 8:
        return ("draw", float("nan"), float("nan"), 0.0)
    dbar = d.mean()
    d0 = d - dbar
    L = max(1, int(round(n ** (1.0 / 3.0))))
    lrv = float(d0 @ d0) / n
    for k in range(1, L + 1):
        w = 1.0 - k / (L + 1.0)          # Bartlett kernel
        lrv += 2.0 * w * float(d0[k:] @ d0[:-k]) / n
    se = math.sqrt(max(lrv, 1e-300) / n)
    stat = dbar / se if se > 0 else 0.0
    z = _Z if abs(alpha - 0.05) < 1e-9 else _norm_ppf(1 - alpha / 2)
    if stat > z:
        return ("A", dbar, se, stat)
    if stat < -z:
        return ("B", dbar, se, stat)
    return ("draw", dbar, se, stat)


def pairwise_record(loaded, a, b, alpha=0.05):
    """Win/draw/loss record of method `a` vs `b` across the series both cover,
    by a per-series DM test. Returns {'win','draw','loss','n'} for `a`."""
    rec = {"win": 0, "draw": 0, "loss": 0, "n": 0}
    series = {s for (s, m) in loaded if m == a} & {s for (s, m) in loaded if m == b}
    for s in series:
        v, *_ = dm_contest(loaded[(s, a)]["logpdf"], loaded[(s, b)]["logpdf"], alpha)
        rec["n"] += 1
        rec["win" if v == "A" else "loss" if v == "B" else "draw"] += 1
    return rec


def _norm_ppf(p):
    # Acklam's inverse-normal approximation (no scipy dependency).
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl = 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p <= 1 - pl:
        q = p - 0.5
        r = q*q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


if __name__ == "__main__":
    # self-test: A clearly better, then A~B (draw), then B better
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, 300)
    print("A>>B :", dm_contest(base + 0.30, base)[0], "(expect A)")
    print("A~=B :", dm_contest(base + 0.002, base)[0], "(expect draw)")
    print("A<<B :", dm_contest(base, base + 0.30)[0], "(expect B)")
