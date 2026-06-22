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
  4. Summarize: the fixed default policy `laplace` vs best-of-crepes CRPS
     win-rate with a bootstrap CI (NOT best-of-ours — that is post-hoc per-series
     selection, not an honest rate), a family-clustered rate (correlated curves
     counted once), a per-class breakdown, and the sticky/lattice lift (laplace vs
     laplace-nostick).

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
# Cap pathologically long series (some daily FRED series span decades) so crepes'
# windowed CPS can't stall a worker for minutes on one series. Scores the most
# recent MAX_CHANGES changes.
MAX_CHANGES = int(os.environ.get("STUDY_MAX_CHANGES", 6000))
MAX_WORKERS = int(os.environ.get("STUDY_WORKERS", min(8, (os.cpu_count() or 4))))
CACHED_ONLY = os.environ.get("STUDY_CACHED_ONLY") == "1"        # smoke test: no network


# ---- phase 1: throttled fetch + qualify --------------------------------------

def _cache_path(sid):
    return os.path.join(fred._CACHE, f"{sid}.csv")


def iter_qualified():
    """Yield (sid, title) as each series qualifies (>= MIN_CHANGES changes),
    fetching misses with light throttling. A generator (not a batch return) so
    scoring can start on the first qualifier instead of waiting for the whole
    universe to download — see run()."""
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
    n_qual = fetched = 0
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
            n_qual += 1
            yield sid, meta["title"]
        if (i + 1) % 200 == 0:
            print(f"  scanned {i+1}/{len(universe)}  qualified={n_qual}  "
                  f"fetched={fetched}", flush=True)
        if n_qual >= MAX_QUALIFY:
            break
    print(f"scan complete: qualified {n_qual} series (fetched {fetched} new)", flush=True)


# ---- phase 2: parallel scoring -----------------------------------------------

def score_series(sid):
    """Run every forecaster on one series. Returns (sid, [rows]); each row is
    [sid, name, crps, logpdf_or_blank, n]. Module-level for the process pool."""
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    rows = []
    if len(ch) < MIN_CHANGES:
        return sid, rows
    if len(ch) > MAX_CHANGES:          # bound per-series cost; never stall on a giant
        ch = ch[-MAX_CHANGES:]
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
    """Pipeline: submit each series for scoring the moment it qualifies, draining
    completed workers as we go, so scoring overlaps the (throttled) download
    instead of waiting behind a full-universe barrier. Crash-safe — each series'
    rows are appended and flushed immediately; already-scored series are skipped."""
    new = not os.path.exists(RESULTS)
    done = _completed_series()
    titles = {}
    t0 = time.time()
    submitted = finished = 0
    with open(RESULTS, "a", newline="") as fh, \
            ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        w = csv.writer(fh)
        if new:
            w.writerow(["series", "forecaster", "crps", "logpdf", "n"]); fh.flush()
        futs = {}

        def collect(fut):
            nonlocal finished
            sid = futs.pop(fut)
            try:
                _, rows = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"  ERR {sid}: {e}", flush=True); return
            if rows:
                w.writerows(rows); fh.flush()
            finished += 1
            if finished % 25 == 0:
                rate = finished / max(time.time() - t0, 1e-9)
                print(f"  scored {finished} (submitted {submitted}, in-flight "
                      f"{len(futs)}) — {rate*60:.0f}/min", flush=True)

        for sid, title in iter_qualified():
            titles[sid] = title
            if sid in done:
                continue
            futs[pool.submit(score_series, sid)] = sid
            submitted += 1
            for f in [f for f in list(futs) if f.done()]:   # drain, don't block
                collect(f)
            while len(futs) >= MAX_WORKERS * 4:              # backpressure
                collect(next(as_completed(list(futs))))
        for fut in as_completed(list(futs)):                 # drain the tail
            collect(fut)

    print(f"done: scored {finished} new series this run ({submitted} submitted)",
          flush=True)
    summarize(titles)

    summarize(titles)


# ---- summary -----------------------------------------------------------------

OURS = ["laplace", "laplace-ll", "laplace-nostick", "scalemix-leaf",
        "crps-leaf-0.3", "crps-leaf-0.6", "crps-leaf-1.0"]
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

    # Headline policy is the single fixed default, `laplace` — NOT best-of-ours.
    # Best-of-ours is post-hoc per-series selection (cherry-picking the winning
    # policy after seeing the answer), so it is not an honest win-rate. We give the
    # opponent its best calibration window (best-of-crepes) — charitable to them.
    rng = np.random.default_rng(0)

    def boot(values):
        vals = np.asarray(values, float)
        if len(vals) == 0:
            return float("nan"), float("nan")
        idx = rng.integers(0, len(vals), size=(2000, len(vals)))
        return tuple(np.percentile(vals[idx].mean(axis=1), [2.5, 97.5]))

    def fam_rate(pairs):                       # pairs: [(family, win), ...]
        fm = {}
        for fam, x in pairs:
            fm.setdefault(fam, []).append(x)
        return np.asarray([np.mean(v) for v in fm.values()]), len(fm)

    def compare(get_c):                        # laplace (fixed) vs one fixed column
        wv, famp, clsp = [], [], []
        for sid, d in by.items():
            if "laplace" not in d or math.isnan(d["laplace"][0]):
                continue
            c = get_c(d)
            if math.isnan(c):
                continue
            x = 1.0 if d["laplace"][0] < c else 0.0
            wv.append(x)
            famp.append((fred_universe.family(sid), x))
            clsp.append((fred_universe.asset_class(titles.get(sid, "")), x))
        return wv, famp, clsp

    # sticky/lattice lift (independent of crepes): laplace vs laplace-nostick — the
    # repeat-mass story the dropped `dirac` policy used to carry.
    lifts = [d["laplace"][1] - d["laplace-nostick"][1] for d in by.values()
             if "laplace" in d and "laplace-nostick" in d
             and not math.isnan(d["laplace"][1]) and not math.isnan(d["laplace-nostick"][1])]

    n = sum(1 for d in by.values() if "laplace" in d
            and not math.isnan(d["laplace"][0]) and not math.isnan(_best(d, CREPES, 0)))
    if not n:
        print("no scored series yet")
        return

    print(f"\n=== {n} systematically-selected daily FRED series ===")
    # Headline (the strong story): laplace beats crepes even when crepes is handed
    # its BEST calibration window PER SERIES — maximally charitable to the opponent.
    # Beating that is harder than beating any single fixed window, so we feature it.
    wb, _fb, _cb = compare(lambda d: _best(d, CREPES, 0))
    frb, nfb = fam_rate(_fb)
    lo, hi = boot(wb); flo, fhi = boot(frb)
    print(f"CRPS  laplace (fixed default) beats best-of-crepes — crepes given its")
    print(f"      best window PER SERIES — on {np.mean(wb)*100:.1f}% of series "
          f"(CI {lo*100:.1f}-{hi*100:.1f}%); {frb.mean()*100:.1f}% family-clustered "
          f"({nfb} families, CI {flo*100:.1f}-{fhi*100:.1f}%)")
    print("      and laplace beats each FIXED window individually (raw / family):")
    hardest = None
    for k in CREPES:
        wv, famp, _ = compare(lambda d, k=k: d[k][0] if k in d else float("nan"))
        if not wv:
            continue
        raw = np.mean(wv) * 100
        fr, _nf = fam_rate(famp)
        print(f"        vs {k:12s} {raw:5.1f}% raw   {fr.mean()*100:5.1f}% family   (n={len(wv)})")
        if hardest is None or raw < hardest[0]:
            hardest = (raw, k)

    # per-class breakdown on the HARDEST fixed window (conservative single choice)
    hw = hardest[1] if hardest else CREPES[0]
    _wv, _fp, clsp = compare(lambda d: d[hw][0] if hw in d else float("nan"))
    print(f"\n  by asset class (laplace vs hardest fixed window {hw}):")
    cls = {}
    for c, x in clsp:
        cls.setdefault(c, []).append(x)
    for c in sorted(cls, key=lambda k: -len(cls[k])):
        v = cls[c]
        print(f"      {c:10s} n={len(v):4d}  laplace win {np.mean(v)*100:5.1f}%")

    # likelihood: dirac lift + mean logpdf per forecaster (crepes has none)
    if lifts:
        la = np.asarray(lifts)
        print(f"\n  sticky (lattice) log-likelihood lift, laplace vs laplace-nostick: "
              f"mean {la.mean():+.3f} nats  (positive on {np.mean(la>0)*100:.0f}% of series)")
    # per-policy CRPS win-rate vs best-of-crepes (raw + family-clustered) and mean logpdf
    fam_of = {sid: fred_universe.family(sid) for sid in by}
    print("\n  per-policy: CRPS win-rate vs best-of-crepes (raw / family) and mean logpdf:")
    print(f"      {'policy':16s}{'CRPS raw':>10s}{'CRPS fam':>10s}{'mean LL':>10s}{'n':>7s}")
    for k in OURS:
        per, fam_acc, lls = [], {}, []
        for sid, d in by.items():
            if k not in d:
                continue
            c = _best(d, CREPES, 0)
            if not math.isnan(d[k][0]) and not math.isnan(c):
                wv = 1.0 if d[k][0] < c else 0.0
                per.append(wv); fam_acc.setdefault(fam_of[sid], []).append(wv)
            if not math.isnan(d[k][1]):
                lls.append(d[k][1])
        if not per:
            continue
        raw = np.mean(per) * 100
        fam = np.mean([np.mean(v) for v in fam_acc.values()]) * 100
        mll = sum(lls) / len(lls) if lls else float("nan")
        print(f"      {k:16s}{raw:9.1f}%{fam:9.1f}%{mll:10.3f}{len(per):7d}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        summarize()
    else:
        run()
