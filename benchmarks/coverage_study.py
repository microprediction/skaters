"""Coverage/calibration study: is anyone's 90% interval actually 90%?

Rolling one-step on continuous non-price series (same protocol as the main
study). Per method per series: empirical coverage of the nominal central 90%
interval over the last 300 points. laplace's coverage comes straight from the
parade PIT (u in [0.05, 0.95]); opponents' from their own 90% bands / quantiles.
Also aggregates laplace's PIT histogram (20 bins) for the calibration figure.
"""
import csv, math, os, sys, warnings
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, "benchmarks")
import fred
from bench_core import score_dist, gauss_dist, student_t_dist
from skaters import laplace

warnings.simplefilter("ignore")
N_SERIES = int(os.environ.get("CS_N", "1000"))
SCORE = 300; KEEP = 1000; REFIT = 25; WIN = 500
OUT = os.environ.get("CS_OUT", os.path.join("benchmarks", "comparisons", "_coverage.csv"))

def run_laplace(ch):
    f = laplace(1); st = None
    hits = 0; n = 0; bins = [0] * 20
    for t, y in enumerate(ch):
        _, st = f(y, st)
        u = st["pit"][0]
        if u is not None and t >= len(ch) - SCORE:
            hits += 0.05 <= u <= 0.95
            bins[min(19, int(u * 20))] += 1
            n += 1
    return (hits / n, bins, n) if n else None

def run_sf(ch):
    import numpy as np, pandas as pd
    from statsforecast import StatsForecast
    from statsforecast.models import AutoARIMA, AutoETS
    res = {"AutoARIMA": [0, 0], "AutoETS": [0, 0]}
    fc = None
    for t in range(len(ch) - SCORE, len(ch)):
        if fc is None or (t - (len(ch) - SCORE)) % REFIT == 0:
            hist = ch[max(0, t - WIN):t]
            df = pd.DataFrame({"unique_id": 0, "ds": np.arange(len(hist)), "y": hist})
            try:
                fc = StatsForecast(models=[AutoARIMA(), AutoETS()], freq=1, n_jobs=1).forecast(df=df, h=REFIT, level=[90])
            except Exception:
                fc = None
        if fc is None: continue
        row = fc.iloc[min((t - (len(ch) - SCORE)) % REFIT, len(fc) - 1)]
        for name in ("AutoARIMA", "AutoETS"):
            lo, hi = float(row[f"{name}-lo-90"]), float(row[f"{name}-hi-90"])
            res[name][0] += lo <= ch[t] <= hi
            res[name][1] += 1
    return {k: v[0] / v[1] for k, v in res.items() if v[1]}

def run_garch(ch):
    import numpy as np
    from arch import arch_model
    from scipy import stats as ss
    hits = n = 0; r = None
    for t in range(len(ch) - SCORE, len(ch)):
        if r is None or (t - (len(ch) - SCORE)) % REFIT == 0:
            hist = np.asarray(ch[max(0, t - WIN):t], float) * 100.0
            try:
                r = arch_model(hist, mean="Constant", vol="GARCH", p=1, q=1, dist="t").fit(disp="off")
            except Exception:
                r = None
        if r is None: continue
        try:
            v = r.forecast(horizon=1, reindex=False).variance.values[-1][0]
        except Exception:
            continue
        mu = float(r.params.get("mu", 0.0)) / 100.0
        nu = float(r.params.get("nu", 8.0))
        sd = math.sqrt(max(v, 1e-12) / 1e4 * nu / max(nu - 2, 0.1))
        q = ss.t.ppf(0.95, nu) * math.sqrt(max(v, 1e-12) / 1e4)
        hits += (mu - q) <= ch[t] <= (mu + q)
        n += 1
    return hits / n if n else None

def one(sid):
    lv = fred._load_levels(sid)
    ch = (fred._to_changes(lv) if lv else [])[-KEEP:]
    if len(ch) < KEEP: return sid, []
    rep = sum(1 for i in range(1, SCORE) if ch[-SCORE:][i] == ch[-SCORE:][i-1]) / (SCORE - 1)
    if rep >= 0.05: return sid, []
    rows = []
    r = run_laplace(ch)
    if not r: return sid, []
    cov, bins, n = r
    rows.append([sid, "laplace", f"{cov:.4f}", " ".join(map(str, bins))])
    try:
        for name, c in run_sf(ch).items():
            rows.append([sid, name, f"{c:.4f}", ""])
    except Exception: pass
    try:
        c = run_garch(ch)
        if c is not None: rows.append([sid, "GARCH-t", f"{c:.4f}", ""])
    except Exception: pass
    return sid, rows

def universe():
    import json
    import fred_universe as fu
    uj = os.path.join(fred._CACHE, "universe_daily.json")
    tmap = {s["id"]: s.get("title", "") for s in json.load(open(uj))} if os.path.exists(uj) else {}
    PRICE = {"equity", "fx", "commodity"}
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    return [s for s in ids if fu.asset_class(tmap.get(s, "")) not in PRICE]

def main():
    done = set()
    if os.path.exists(OUT):
        done = {r["series"] for r in csv.DictReader(open(OUT))}
    todo = [s for s in universe() if s not in done]
    fresh = not os.path.exists(OUT)
    fh = open(OUT, "a", newline=""); w = csv.writer(fh)
    if fresh: w.writerow(["series", "method", "coverage90", "pit_bins"])
    print(f"[cov] target {N_SERIES} (already {len(done)})", flush=True)
    scored = len(done)
    with ProcessPoolExecutor(max_workers=14) as pool:
        for sid, rows in pool.map(one, todo):
            if rows:
                for r in rows: w.writerow(r)
                fh.flush(); scored += 1
                if scored % 50 == 0: print(f"[cov] {scored}/{N_SERIES}", flush=True)
            if scored >= N_SERIES: break
    fh.close(); summarize()

def summarize():
    import statistics
    per = {}
    binsum = [0] * 20
    for r in csv.DictReader(open(OUT)):
        per.setdefault(r["method"], []).append(float(r["coverage90"]))
        if r["method"] == "laplace" and r["pit_bins"]:
            for i, b in enumerate(r["pit_bins"].split()): binsum[i] += int(b)
    print("\n=== empirical coverage of the nominal central 90% interval ===")
    print(f"{'method':12s} {'N':>5s} {'mean':>7s} {'median':>7s}  {'within +-2% of 90%':>18s}")
    for m, v in sorted(per.items()):
        ok = sum(1 for c in v if 0.88 <= c <= 0.92) / len(v)
        print(f"{m:12s} {len(v):5d} {statistics.mean(v):7.3f} {statistics.median(v):7.3f}  {100*ok:17.0f}%")
    tot = sum(binsum)
    print("\nlaplace aggregate PIT histogram (20 bins, share; flat = 0.050):")
    print("  " + " ".join(f"{b/tot:.3f}" for b in binsum))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        summarize()
    else:
        main()
