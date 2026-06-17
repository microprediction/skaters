"""Large systematic study: skaters vs crepes on ~1-3k daily FRED series.

This scales the curated 42-series benchmark up to a bias-free universe (see
fred_universe.enumerate_daily) so the headline becomes "X% +/- CI over N
systematically-selected series", not "93% on a list I picked".

Pipeline:
  1. Resolve the universe (top-N daily series by popularity).
  2. Fetch + cache levels (throttled), convert to one-step changes
     (log-diff for positive levels, else first-diff), keep series with
     >= MIN_CHANGES usable changes.
  3. Score every (series, forecaster) in parallel; append to results_large.csv
     immediately, skipping series already fully scored (crash-safe resume).
  4. Summarize: best-of-ours vs best-of-crepes CRPS win-rate with a bootstrap
     CI, a family-clustered rate (correlated curves counted once), a per-class
     breakdown, and dirac's log-likelihood lift.

Run (in the conda env with crepes + a FRED key):
    PYTHONPATH=src python benchmarks/large_study.py
"""

from __future__ import annotations

# Keep numeric libs single-threaded so the process pool doesn't oversubscribe.
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import csv
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fred
import fred_universe
from exhaustive_crps import FORECASTERS, crepes_crps, skater_scores

_HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.environ.get("STUDY_RESULTS", os.path.join(_HERE, "results_large.csv"))

N_CANDIDATES = int(os.environ.get("STUDY_N_CANDIDATES", 3500))  # consider (by popularity)
MAX_QUALIFY = int(os.environ.get("STUDY_MAX_QUALIFY", 2500))    # stop once this many pass
MIN_CHANGES = 500       # need a real history to score
MAX_WORKERS = int(os.environ.get("STUDY_WORKERS", min(8, (os.cpu_count() or 4))))
CACHED_ONLY = os.environ.get("STUDY_CACHED_ONLY") == "1"        # smoke test: no network


# ---- phase 1: throttled fetch + qualify --------------------------------------

def _cache_path(sid):
    return os.path.join(fred._CACHE, f"{sid}.csv")


def qualify_universe():
    """Resolve the universe and return [(sid, title)] for series that load and
    have >= MIN_CHANGES changes. Fetches missing series with light throttling."""
    if CACHED_ONLY:
        # Score whatever is already cached (power-safe interim run). Pull titles
        # from the resolved universe so the class breakdown still works.
        tmap = {}
        ujson = os.path.join(fred._CACHE, "universe_daily.json")
        if os.path.exists(ujson):
            import json
            tmap = {s["id"]: s.get("title", "") for s in json.load(open(ujson))}
        ids = [f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv")]
        universe = [{"id": s, "title": tmap.get(s, "")} for s in ids][:MAX_QUALIFY]
    else:
        universe = fred_universe.enumerate_daily(N_CANDIDATES)
    qualified = []
    fetched = 0
    for i, meta in enumerate(universe):
        sid = meta["id"]
        miss = not os.path.exists(_cache_path(sid))
        levels = fred._load_levels(sid)          # fetches + caches on miss
        if miss:
            fetched += 1
            time.sleep(0.5)                       # ~120 req/min ceiling
        if not levels:
            continue
        ch = fred._to_changes(levels)
        if len(ch) >= MIN_CHANGES:
            qualified.append((sid, meta["title"]))
        if (i + 1) % 200 == 0:
            print(f"  scanned {i+1}/{len(universe)}  qualified={len(qualified)}  "
                  f"fetched={fetched}", flush=True)
        if len(qualified) >= MAX_QUALIFY:
            break
    print(f"qualified {len(qualified)} series (fetched {fetched} new)", flush=True)
    return qualified


# ---- phase 2: parallel scoring -----------------------------------------------

def score_series(sid):
    """Run every forecaster on one series. Returns (sid, [rows]); each row is
    [sid, name, crps, logpdf_or_blank, n]. Module-level for the process pool."""
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    rows = []
    if len(ch) < MIN_CHANGES:
        return sid, rows
    for name, spec in FORECASTERS.items():
        try:
            if spec[0] == "crepes":
                crps, n = crepes_crps(ch, window=spec[1])
                lp = ""
            else:
                crps, lp, n = skater_scores(spec[1], ch)
            rows.append([sid, name, f"{crps:.6f}",
                         (f"{lp:.6f}" if lp != "" else ""), n])
        except Exception as e:  # noqa: BLE001 — one bad pair shouldn't kill the run
            print(f"  ERR {sid}/{name}: {e}", flush=True)
    return sid, rows


def _completed_series():
    """Series already fully scored (all forecasters present) in the CSV."""
    counts = {}
    if os.path.exists(RESULTS):
        with open(RESULTS) as f:
            r = csv.reader(f)
            next(r, None)
            for row in r:
                if len(row) >= 2:
                    counts[row[0]] = counts.get(row[0], 0) + 1
    need = len(FORECASTERS)
    return {s for s, c in counts.items() if c >= need}


def run():
    if not os.path.exists(RESULTS):
        with open(RESULTS, "w") as f:
            csv.writer(f).writerow(["series", "forecaster", "crps", "logpdf", "n"])

    qualified = qualify_universe()
    titles = dict(qualified)
    done = _completed_series()
    todo = [sid for sid, _ in qualified if sid not in done]
    print(f"scoring {len(todo)} series ({len(done)} already done) "
          f"on {MAX_WORKERS} workers", flush=True)

    t0 = time.time()
    finished = 0
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score_series, sid): sid for sid in todo}
        for fut in as_completed(futs):
            sid = futs[fut]
            try:
                _, rows = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"  ERR {sid}: {e}", flush=True)
                continue
            if rows:
                with open(RESULTS, "a") as f:
                    csv.writer(f).writerows(rows)
            finished += 1
            if finished % 25 == 0 or finished == len(todo):
                rate = finished / max(time.time() - t0, 1e-9)
                eta = (len(todo) - finished) / max(rate, 1e-9)
                print(f"  {finished}/{len(todo)} series  "
                      f"({rate*60:.0f}/min, ETA {eta/60:.0f} min)", flush=True)

    summarize(titles)


# ---- summary -----------------------------------------------------------------

OURS = ["laplace", "kahneman", "scalemix-leaf",
        "crps-leaf-0.3", "crps-leaf-0.6", "crps-leaf-1.0", "dirac"]
CREPES = ["crepes-w250", "crepes-w400", "crepes-w750"]


def _load_results():
    by = {}
    with open(RESULTS) as f:
        r = csv.DictReader(f)
        for row in r:
            def fl(x):
                try:
                    return float(x)
                except (TypeError, ValueError):
                    return float("nan")
            by.setdefault(row["series"], {})[row["forecaster"]] = (
                fl(row["crps"]), fl(row["logpdf"]))
    return by


def _best(d, keys, idx):
    vals = [d[k][idx] for k in keys if k in d and not math.isnan(d[k][idx])]
    return min(vals) if vals else float("nan")


def summarize(titles=None):
    import numpy as np
    titles = titles or {}
    by = _load_results()

    wins, fams, classes, lifts = [], [], [], []
    for sid, d in by.items():
        o = _best(d, OURS, 0)
        c = _best(d, CREPES, 0)
        if math.isnan(o) or math.isnan(c):
            continue
        win = 1.0 if o < c else 0.0
        wins.append(win)
        fams.append(fred_universe.family(sid))
        classes.append(fred_universe.asset_class(titles.get(sid, "")))
        if "dirac" in d and not math.isnan(d["dirac"][1]):
            best_other = max((d[k][1] for k in OURS
                              if k != "dirac" and k in d and not math.isnan(d[k][1])),
                             default=float("nan"))
            if not math.isnan(best_other):
                lifts.append(d["dirac"][1] - best_other)

    n = len(wins)
    if not n:
        print("no scored series yet")
        return
    w = np.asarray(wins)
    rng = np.random.default_rng(0)

    def boot(values, weights=None):
        vals = np.asarray(values)
        idx = rng.integers(0, len(vals), size=(2000, len(vals)))
        means = vals[idx].mean(axis=1)
        return np.percentile(means, [2.5, 97.5])

    lo, hi = boot(w)
    print(f"\n=== {n} systematically-selected daily FRED series ===")
    print(f"CRPS  best-of-ours beats best-of-crepes: "
          f"{w.mean()*100:.1f}%  (95% CI {lo*100:.1f}-{hi*100:.1f}%)")

    # family-clustered: average within family, then over families
    fam_means = {}
    for f, x in zip(fams, wins):
        fam_means.setdefault(f, []).append(x)
    fam_rate = np.asarray([np.mean(v) for v in fam_means.values()])
    flo, fhi = boot(fam_rate)
    print(f"      family-clustered ({len(fam_means)} families): "
          f"{fam_rate.mean()*100:.1f}%  (95% CI {flo*100:.1f}-{fhi*100:.1f}%)")

    # per-class breakdown
    print("\n  by asset class (approx):")
    cls = {}
    for c, x in zip(classes, wins):
        cls.setdefault(c, []).append(x)
    for c in sorted(cls, key=lambda k: -len(cls[k])):
        v = cls[c]
        print(f"      {c:10s} n={len(v):4d}  ours win {np.mean(v)*100:5.1f}%")

    # likelihood: dirac lift + mean logpdf per forecaster (crepes has none)
    if lifts:
        la = np.asarray(lifts)
        print(f"\n  dirac log-likelihood lift over best other-ours: "
              f"mean {la.mean():+.3f} nats  (positive on {np.mean(la>0)*100:.0f}% of series)")
    print("  mean logpdf per forecaster (ours; crepes emits no density):")
    for k in OURS:
        v = [d[k][1] for d in by.values() if k in d and not math.isnan(d[k][1])]
        if v:
            print(f"      {k:16s} {sum(v)/len(v):7.3f}  (n={len(v)})")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        summarize()
    else:
        run()
