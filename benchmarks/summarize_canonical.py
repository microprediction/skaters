"""Derive the small, committable summaries from the canonical per-step store.

A mean of log-likelihood or CRPS ACROSS heterogeneous series is not an estimate
of anything: a few near-constant series (where laplace's lattice scores many
nats) dominate it, and raw-unit CRPS is swamped by a few huge-magnitude series.
So this reports only PAIRED or SCALE-FREE aggregates, all relative to laplace on
the series both cover:

  canonical_summary_vs_laplace.csv
      study, model, n_series, win, draw, loss,          # DM win/draw/loss (per series)
      med_dLL, q25_dLL, q75_dLL,                         # per-series ΔLL = model - laplace
      med_crps_ratio                                     # per-series CRPS_model / CRPS_laplace

  canonical_summary_coverage.csv
      study, method, n_steps, cov_central90, cal_median  # calibration from stored quantiles

`study` is the stratum tag (frequency:regime). Win/draw/loss is per-series
Diebold-Mariano (HAC SE, draw band). ΔLL is differenced per series so each
series' intrinsic difficulty cancels; the MEDIAN (not mean) is reported so no
single series dominates. CRPS is a per-series ratio (scale-free). Coverage is
pooled over steps (each step a Bernoulli), the one honest absolute number.
Everything derives from the one store, cheap to re-run as rounds accrue.
"""
from __future__ import annotations
import collections
import csv
import glob
import os

import numpy as np

import predictions as P

_HERE = os.path.dirname(os.path.abspath(__file__))
# CANON_PREDS lets the multi-horizon study summarize its own preds tree, and
# CANON_SUFFIX names the output (e.g. "_h4") so it does not clobber the k=1 files.
PREDS = os.environ.get("CANON_PREDS", os.path.join(_HERE, "preds"))
SUFFIX = os.environ.get("CANON_SUFFIX", "")
BASELINE = "laplace"
_COLS = ("y", "q05", "q50", "q95", "logpdf", "crps")


def load_all():
    """{(study, series, method): {col: arr}} across all shard files, rows kept in
    file (step) order so per-series arrays align across methods."""
    store = collections.defaultdict(lambda: {c: [] for c in _COLS})
    for path in sorted(glob.glob(os.path.join(PREDS, "*__*.csv"))):
        with open(path) as fh:
            for r in csv.DictReader(fh):
                k = (r["study"], r["series"], r["method"])
                for c in _COLS:
                    v = r.get(c, "")
                    store[k][c].append(float(v) if v not in ("", "nan") else np.nan)
    for d in store.values():
        for c in d:
            d[c] = np.asarray(d[c], float)
    return store


def _series_mean(a, floor=None):
    a = np.asarray(a, float)
    if floor is not None:
        a = np.maximum(a, floor)
    return float(np.nanmean(a)) if np.isfinite(a).any() else np.nan


def main():
    store = load_all()
    if not store:
        print("[summarize] no per-step data yet under preds/", flush=True)
        return
    studies = sorted({s for (s, _, _) in store})
    methods = sorted({m for (_, _, m) in store})

    # ---- paired, scale-free comparison of each model vs laplace ----
    with open(os.path.join(_HERE, f"canonical_summary_vs_laplace{SUFFIX}.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["study", "model", "n_series", "win", "draw", "loss",
                    "med_dLL", "q25_dLL", "q75_dLL", "med_crps_ratio"])
        for study in studies:
            by = collections.defaultdict(set)
            for (st, s, m) in store:
                if st == study:
                    by[m].add(s)
            base = by.get(BASELINE, set())
            for m in methods:
                if m == BASELINE:
                    continue
                common = sorted(base & by.get(m, set()))
                if not common:
                    continue
                rec = {"win": 0, "draw": 0, "loss": 0}
                dlls, ratios = [], []
                for s in common:
                    dm = store[(study, s, m)]
                    bl = store[(study, s, BASELINE)]
                    v, *_ = P.dm_contest(dm["logpdf"], bl["logpdf"])
                    rec["win" if v == "A" else "loss" if v == "B" else "draw"] += 1
                    dlls.append(_series_mean(dm["logpdf"], -20.0)
                                - _series_mean(bl["logpdf"], -20.0))
                    cb = _series_mean(bl["crps"])
                    cm = _series_mean(dm["crps"])
                    if cb and np.isfinite(cb) and cb > 0 and np.isfinite(cm):
                        ratios.append(cm / cb)
                dlls = np.asarray(dlls, float)
                w.writerow([study, m, len(common), rec["win"], rec["draw"], rec["loss"],
                            f"{np.nanmedian(dlls):.4f}",
                            f"{np.nanpercentile(dlls, 25):.4f}",
                            f"{np.nanpercentile(dlls, 75):.4f}",
                            f"{np.nanmedian(ratios):.4f}" if ratios else ""])

    # ---- calibration: interval coverage from the stored quantiles ----
    with open(os.path.join(_HERE, f"canonical_summary_coverage{SUFFIX}.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["study", "method", "n_steps", "cov_central90", "cal_median"])
        for study in studies:
            for m in methods:
                ys, q05s, q50s, q95s = [], [], [], []
                for (st, s, mm), d in store.items():
                    if st == study and mm == m:
                        ys.append(d["y"]); q05s.append(d["q05"])
                        q50s.append(d["q50"]); q95s.append(d["q95"])
                if not ys:
                    continue
                y = np.concatenate(ys); q05 = np.concatenate(q05s)
                q50 = np.concatenate(q50s); q95 = np.concatenate(q95s)
                ok = np.isfinite(y) & np.isfinite(q05) & np.isfinite(q95) & np.isfinite(q50)
                n = int(ok.sum())
                if not n:
                    continue
                cov = float(np.mean((y[ok] >= q05[ok]) & (y[ok] <= q95[ok])))
                cal = float(np.mean(y[ok] <= q50[ok]))
                w.writerow([study, m, n, f"{cov:.4f}", f"{cal:.4f}"])

    print(f"[summarize] {len(store)} (study,series,method) cells; "
          f"studies={studies}; methods={methods}", flush=True)


if __name__ == "__main__":
    main()
