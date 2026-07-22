"""Derive the small, committable summaries from the canonical per-step store.

Reads every benchmarks/preds/*.csv (the large, gitignored, regenerable per-step
store) and writes two small CSVs that ARE committed and that the charts read:

  canonical_summary_scores.csv   study, method, mean_ll, mean_crps, n_series, n_steps
  canonical_summary_dm.csv       study, model, vs, win, draw, loss, n

`study` is the corpus/stratum tag (daily/weekly/monthly/m4-hourly). The DM table
is per-series Diebold-Mariano (HAC SE, draw band) of each model against laplace
on the series both cover, split by stratum: the honest win/draw/loss replacement
for argmax win-rates. Everything derives from the one store, so this is cheap to
re-run as rounds accrue and the star maps converge.
"""
from __future__ import annotations
import collections
import csv
import glob
import os

import numpy as np

import predictions as P

_HERE = os.path.dirname(os.path.abspath(__file__))
PREDS = os.path.join(_HERE, "preds")
BASELINE = "laplace"


def load_all():
    """{(study, series, method): {'logpdf':arr, 'crps':arr}} across all shard files,
    rows kept in file (step) order so per-series arrays align across methods."""
    store = collections.defaultdict(lambda: {"logpdf": [], "crps": []})
    for path in sorted(glob.glob(os.path.join(PREDS, "*.csv"))):
        with open(path) as fh:
            for r in csv.DictReader(fh):
                k = (r["study"], r["series"], r["method"])
                for c in ("logpdf", "crps"):
                    v = r.get(c, "")
                    store[k][c].append(float(v) if v not in ("", "nan") else np.nan)
    for d in store.values():
        for c in d:
            d[c] = np.asarray(d[c], float)
    return store


def main():
    store = load_all()
    if not store:
        print("[summarize] no per-step data yet under preds/", flush=True)
        return
    studies = sorted({s for (s, _, _) in store})
    methods = sorted({m for (_, _, m) in store})

    # ---- per (study, method) mean scores ----
    with open(os.path.join(_HERE, "canonical_summary_scores.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["study", "method", "mean_ll", "mean_crps", "n_series", "n_steps"])
        for study in studies:
            for m in methods:
                lls, crps, nser, nstep = [], [], 0, 0
                for (st, s, mm), d in store.items():
                    if st != study or mm != m:
                        continue
                    lp = np.maximum(d["logpdf"], -20.0)
                    if np.isfinite(lp).any():
                        lls.append(float(np.nanmean(lp)))
                        crps.append(float(np.nanmean(d["crps"])))
                        nser += 1
                        nstep += int(np.isfinite(d["logpdf"]).sum())
                if nser:
                    w.writerow([study, m, f"{np.mean(lls):.6f}", f"{np.mean(crps):.6f}",
                                nser, nstep])

    # ---- per (study, model) DM win/draw/loss vs laplace ----
    with open(os.path.join(_HERE, "canonical_summary_dm.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["study", "model", "vs", "win", "draw", "loss", "n"])
        for study in studies:
            series_by = collections.defaultdict(set)
            for (st, s, m) in store:
                if st == study:
                    series_by[m].add(s)
            base = series_by.get(BASELINE, set())
            for m in methods:
                if m == BASELINE:
                    continue
                common = base & series_by.get(m, set())
                rec = {"win": 0, "draw": 0, "loss": 0}
                for s in common:
                    v, *_ = P.dm_contest(store[(study, s, m)]["logpdf"],
                                         store[(study, s, BASELINE)]["logpdf"])
                    rec["win" if v == "A" else "loss" if v == "B" else "draw"] += 1
                if common:
                    w.writerow([study, m, BASELINE, rec["win"], rec["draw"],
                                rec["loss"], len(common)])

    print(f"[summarize] {len(store)} (study,series,method) cells; "
          f"studies={studies}; methods={methods}", flush=True)


if __name__ == "__main__":
    main()
