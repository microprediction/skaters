"""One benchmark, many presets.

    PYTHONPATH=src python benchmarks/study.py conformal-scale     # ours vs naive-mean crepes, whole daily universe
    PYTHONPATH=src python benchmarks/study.py sota                # ours vs the heavy baselines, small universe
    PYTHONPATH=src python benchmarks/study.py <preset> summarize  # just print the table

A preset fixes only three things: which opponents, how big a universe, and the
scoring window. Everything else — the FRED change-series loader, the one-step
`Dist` scorer (`bench_core`), the opponent registry (`opponents`), the pipelined
crash-safe runner, and the summary — is shared. Slow opponents carry a per-method
`max_series` budget: they cover fewer series (N reported) but always score a
covered series fully and honestly. Results append to one CSV; reruns resume.
"""
from __future__ import annotations
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
import bench_core as bc
import opponents as opp

_HERE = os.path.dirname(os.path.abspath(__file__))
MIN_CHANGES = int(os.environ.get("STUDY_MIN_CHANGES", 500))   # relax (e.g. 200) to admit weekly/monthly
MAX_CHANGES = int(os.environ.get("STUDY_MAX_CHANGES", 6000))   # never stall on a giant series
WORKERS = int(os.environ.get("STUDY_WORKERS", min(16, (os.cpu_count() or 4))))
CACHED_ONLY = os.environ.get("STUDY_CACHED_ONLY") == "1"
# Out-of-scope screen (see README, "Out-of-scope series"): a single move that
# dwarfs the series' own typical variation carries no scale information an
# autonomous forecaster could use. Excludes the mostly-constant (MAD==0) and
# calm-then-jump classes in one rule. Set STUDY_MAX_EXCURSION=0 to disable.
MAX_EXCURSION = float(os.environ.get("STUDY_MAX_EXCURSION", 1000))


def _median(v):
    s = sorted(v); m = len(s)
    return s[m // 2] if m % 2 else 0.5 * (s[m // 2 - 1] + s[m // 2])


def _scope_tag(changes):
    """Legitimacy tag for an autonomous distributional forecast: '' if in scope,
    else the reason it is out of scope (see README, "Out-of-scope series").
    Judging these is philosophically impossible, not a flaw of any forecaster:
    the series simply never offered a scale to be judged against."""
    if not changes:
        return "empty"
    v0 = changes[0]; lead = 0
    for c in changes:
        if c == v0:
            lead += 1
        else:
            break
    if lead >= max(100, 0.5 * len(changes)):
        return "leading-flat"          # starts with a long constant run (many zeros, etc.)
    if MAX_EXCURSION > 0:
        mad = _median([abs(c - _median(changes)) for c in changes])
        if mad <= 0.0:
            return "no-variation"      # (near-)constant throughout
        if (max(abs(c) for c in changes) / mad) > MAX_EXCURSION:
            return "excursion"         # a single move dwarfing the series' own scale
    return ""

# preset -> (opponent set, n_candidates, max_qualify, window_mode, test, refit, csv)
# conformal-scale reuses results_large.csv — the canonical 10,822-series sweep —
# so a rerun resumes it (no re-scoring) and summarize reproduces the headline.
PRESETS = {
    "conformal-scale": dict(opponents="conformal-scale", n_candidates=100000,
                            max_qualify=100000, window="burn", test=0, refit=25,
                            csv="results_large.csv"),
    "sota": dict(opponents="sota", n_candidates=700, max_qualify=500,
                 window="lastN", test=300, refit=25, csv="results_sota.csv"),
}


def _cfg(preset):
    c = dict(PRESETS[preset])
    c["n_candidates"] = int(os.environ.get("STUDY_N_CANDIDATES", c["n_candidates"]))
    c["max_qualify"] = int(os.environ.get("STUDY_MAX_QUALIFY", c["max_qualify"]))
    c["test"] = int(os.environ.get("STUDY_TEST", c["test"]))   # scored window; relax to 200 for low-freq
    c["window"] = os.environ.get("STUDY_WINDOW", c["window"])  # "burn" (all points) or "lastN" (cap to test)
    c["results"] = os.environ.get("STUDY_RESULTS", os.path.join(_HERE, c["csv"]))
    return c


def _start_for(n, cfg):
    """First scored index for a series of length n under this preset's window."""
    if cfg["window"] == "lastN":
        return max(bc.BURN, n - cfg["test"])
    return bc.BURN


# ---- universe iterator (generator: yields as each series qualifies) ----------

def iter_qualified(cfg):
    if CACHED_ONLY:
        import json
        uj = os.path.join(fred._CACHE, "universe_daily.json")
        tmap = ({s["id"]: s.get("title", "") for s in json.load(open(uj))}
                if os.path.exists(uj) else {})
        ids = [f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv")]
        universe = [{"id": s, "title": tmap.get(s, "")} for s in ids][:cfg["max_qualify"]]
    else:
        universe = fred_universe.enumerate_daily(cfg["n_candidates"])

    # Optional a-priori universe restriction by asset class. STUDY_EXCLUDE_PRICE=1
    # drops equity/fx/commodity (GARCH-t's home turf) so the study is the general
    # / non-price economic universe; STUDY_ONLY_PRICE=1 keeps only those.
    _excl = os.environ.get("STUDY_EXCLUDE_PRICE") == "1"
    _only = os.environ.get("STUDY_ONLY_PRICE") == "1"
    if _excl or _only:
        _PRICE = {"equity", "fx", "commodity"}
        universe = [m for m in universe
                    if (fred_universe.asset_class(m.get("title", "")) in _PRICE) == _only]

    n_qual = fetched = 0
    tagged = []                        # (sid, tag) for out-of-scope series
    for i, meta in enumerate(universe):
        sid = meta["id"]
        miss = not os.path.exists(os.path.join(fred._CACHE, f"{sid}.csv"))
        levels = fred._load_levels(sid)
        if miss:
            fetched += 1; time.sleep(0.5)
        if not levels:
            continue
        changes = fred._to_changes(levels)
        if len(changes) < MIN_CHANGES:
            continue
        tag = _scope_tag(changes)
        if tag:
            tagged.append((sid, tag))
            continue
        n_qual += 1
        yield sid, meta["title"]
        if (i + 1) % 200 == 0:
            print(f"  scanned {i+1}/{len(universe)}  qualified={n_qual}  fetched={fetched}",
                  flush=True)
        if n_qual >= cfg["max_qualify"]:
            break
    # Tag the illegitimate series explicitly rather than dropping them silently.
    if tagged:
        man = os.path.join(_HERE, "out_of_scope.csv")
        with open(man, "w") as fh:
            fh.write("series,tag\n")
            for sid, tag in tagged:
                fh.write(f"{sid},{tag}\n")
        from collections import Counter
        by = Counter(t for _, t in tagged)
        print(f"tagged out-of-scope: {len(tagged)} series {dict(by)} -> {man}", flush=True)
    print(f"scan complete: qualified {n_qual} (fetched {fetched} new)", flush=True)


# ---- per-series scoring (worker) ---------------------------------------------

def score_series(payload):
    """Run the given opponents on ONE series. payload = (sid, opp_names, refit,
    window, test). Returns (sid, [rows]) with rows [sid, method, crps, logpdf, n]."""
    sid, opp_names, refit, window, test = payload
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    if len(ch) < MIN_CHANGES:
        return sid, []
    if len(ch) > MAX_CHANGES:
        ch = ch[-MAX_CHANGES:]
    start = max(bc.BURN, len(ch) - test) if window == "lastN" else bc.BURN
    rows = []
    for op in opp.resolve(opp_names):
        try:
            for method, lp, cr, n in op.predict(ch, start, refit):
                rows.append([sid, method, f"{cr:.6f}",
                             ("" if lp is None else f"{lp:.6f}"), n])
        except Exception as e:  # noqa: BLE001 — one opponent must not kill a series
            print(f"  ERR {sid}/{op.name}: {e}", flush=True)
    return sid, rows


def _done_methods(results):
    """sid -> set(methods already scored), for crash-safe resume."""
    d = {}
    if os.path.exists(results):
        with open(results) as f:
            r = csv.reader(f); next(r, None)
            for row in r:
                if len(row) >= 2:
                    d.setdefault(row[0], set()).add(row[1])
    return d


# ---- runner ------------------------------------------------------------------

def run(preset):
    cfg = _cfg(preset)
    opps = opp.resolve(opp.SETS[cfg["opponents"]])
    only = os.environ.get("STUDY_ONLY")            # restrict to these opponent names
    if only:                                       # (comparison folders use this)
        keep = {s.strip() for s in only.split(",") if s.strip()}
        opps = [o for o in opps if o.name in keep]
    results = cfg["results"]
    print(f"[{preset}] opponents: {[o.name for o in opps]}", flush=True)
    print(f"[{preset}] {WORKERS} workers, window={cfg['window']}"
          f"{'/'+str(cfg['test']) if cfg['window']=='lastN' else ''}, cap={MAX_CHANGES}",
          flush=True)

    done = _done_methods(results)
    counts = {o.name: 0 for o in opps}                 # series covered per opponent
    for sid, ms in done.items():                       # seed budgets from a resumed CSV
        for o in opps:
            if all(m in ms for m in o.methods):
                counts[o.name] += 1

    new = not os.path.exists(results)
    titles = {}; submitted = finished = 0; t0 = time.time()
    with open(results, "a", newline="") as fh, \
            ProcessPoolExecutor(max_workers=WORKERS) as pool:
        w = csv.writer(fh)
        if new:
            w.writerow(["series", "method", "crps", "logpdf", "n"]); fh.flush()
        futs = {}

        def collect(fut):
            nonlocal finished
            sid = futs.pop(fut)
            try:
                _, rows = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"  ERR {sid}: {e}", flush=True); return
            seen = done.get(sid, set())
            for row in rows:
                if row[1] not in seen:                 # don't double-write on resume
                    w.writerow(row)
            fh.flush(); finished += 1
            if finished % 25 == 0:
                rate = finished / max(time.time() - t0, 1e-9)
                print(f"  scored {finished} (submitted {submitted}, in-flight "
                      f"{len(futs)}) — {rate*60:.0f}/min", flush=True)

        for sid, title in iter_qualified(cfg):
            titles[sid] = title
            ms = done.get(sid, set())
            todo = []
            for o in opps:
                if all(m in ms for m in o.methods):
                    continue                           # already fully scored (resume)
                if o.max_series is not None and counts[o.name] >= o.max_series:
                    continue                           # budget spent — skip this series
                todo.append(o.name); counts[o.name] += 1
            if not todo:
                continue
            futs[pool.submit(score_series,
                             (sid, todo, cfg["refit"], cfg["window"], cfg["test"]))] = sid
            submitted += 1
            for f in [f for f in list(futs) if f.done()]:
                collect(f)
            while len(futs) >= WORKERS * 4:
                collect(next(as_completed(list(futs))))
        for fut in as_completed(list(futs)):
            collect(fut)

    print(f"[{preset}] done: scored {finished} series this run", flush=True)
    for o in opps:
        print(f"    {o.name:16s} covered {counts[o.name]} series", flush=True)
    summarize(preset, titles)


# ---- summary -----------------------------------------------------------------

OURS = ["laplace", "laplace-ll", "laplace-nostick", "scalemix-leaf",
        "crps-leaf-0.3", "crps-leaf-0.6", "crps-leaf-1.0"]
CREPES = ["crepes-w250", "crepes-w400", "crepes-w750"]


def _load(results):
    by = {}
    with open(results) as f:
        for row in csv.DictReader(f):
            def fl(x):
                try:
                    return float(x)
                except (TypeError, ValueError):
                    return float("nan")
            method = row.get("method") or row.get("forecaster")   # tolerate either header
            by.setdefault(row["series"], {})[method] = (fl(row["logpdf"]), fl(row["crps"]))
    return by


def _rfrac(sid):
    ch = bc and fred._to_changes(fred._load_levels(sid) or [])
    ch = ch[-300:] if ch else []
    return sum(1 for i in range(1, len(ch)) if ch[i] == ch[i - 1]) / max(len(ch) - 1, 1)


def summarize(preset, titles=None):
    import numpy as np
    titles = titles or {}
    results = _cfg(preset)["results"]
    by = _load(results)
    if not by:
        print("no scored series yet"); return
    cont = {s for s in by if _rfrac(s) < 0.05}

    def winrate(method, idx, lower, subset=None):
        """laplace beats `method` on metric idx (lower=CRPS, else LL); raw% + N."""
        ss = subset if subset is not None else set(by)
        wins = [(1.0 if ((by[s]["laplace"][idx] < by[s][method][idx]) == lower) else 0.0)
                for s in ss if "laplace" in by[s] and method in by[s]
                and not math.isnan(by[s]["laplace"][idx]) and not math.isnan(by[s][method][idx])]
        return (100.0 * sum(wins) / len(wins), len(wins)) if wins else (float("nan"), 0)

    print(f"\n=== [{preset}] {len(by)} series ({len(cont)} continuous) — laplace vs each ===")
    others = [m for m in (sorted({k for d in by.values() for k in d}) ) if m != "laplace"]
    print(f"  {'method':22s}{'CRPS all/cont':>16s}{'LL all/cont':>16s}{'N':>7s}")
    for m in others:
        c_all, n = winrate(m, 1, True)
        c_co, _ = winrate(m, 1, True, cont)
        # LL only where the method emits a density (finite logpdf somewhere)
        has_ll = any(m in d and not math.isnan(d[m][0]) for d in by.values())
        l_all = winrate(m, 0, False)[0] if has_ll else float("nan")
        l_co = winrate(m, 0, False, cont)[0] if has_ll else float("nan")
        cc = f"{c_all:.0f}/{c_co:.0f}%"
        ll = (f"{l_all:.0f}/{l_co:.0f}%" if has_ll else "  — (CDF)")
        print(f"  {m:22s}{cc:>16s}{ll:>16s}{n:>7d}")

    # conformal headline: fixed laplace vs best-of-crepes (its best window per series)
    if any(c in {k for d in by.values() for k in d} for c in CREPES):
        def best_crepes(d):
            vs = [d[c][1] for c in CREPES if c in d and not math.isnan(d[c][1])]
            return min(vs) if vs else float("nan")
        wins = [1.0 if by[s]["laplace"][1] < best_crepes(by[s]) else 0.0
                for s in by if "laplace" in by[s] and not math.isnan(best_crepes(by[s]))]
        if wins:                               # crepes may be listed but uninstalled (N=0)
            print(f"\n  laplace beats best-of-crepes (its best window per series): "
                  f"{100*sum(wins)/len(wins):.1f}% of {len(wins)} series")

    print("\n  mean logpdf (ours; crepes emits no density):")
    for m in OURS:
        v = [d[m][0] for d in by.values() if m in d and not math.isnan(d[m][0])]
        if v:
            print(f"    {m:16s} {sum(v)/len(v):7.3f}  (n={len(v)})")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    preset = args[0] if args and args[0] in PRESETS else "conformal-scale"
    if "summarize" in args:
        summarize(preset)
    else:
        run(preset)
