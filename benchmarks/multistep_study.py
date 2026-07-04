"""Multi-step (h-step-ahead) evaluation on the non-price universe.

The main study is one-step. Here every forecaster predicts the change stream
$h$ steps ahead for $h \\in$ HORIZONS, and each horizon's predictive `Dist` is
scored (log-likelihood, CRPS) against the realised change $h$ steps later. Same
`Dist` scorer for all; laplace emits its native k-step list, the classical
baselines forecast(h) from a periodically-refit window.

Opponents (multi-step is principled for all of these): laplace vs statsforecast
AutoARIMA/AutoETS, arch GARCH(1,1)-t, and Prophet (whose home turf this is:
fit-once, predict-h). Conformal/CSP are one-step-only and excluded here.

    PYTHONPATH=src python benchmarks/multistep_study.py [summarize]

Env: MS_N (series cap), MS_HMAX, MS_ORIGINS (scored origins/series), MS_WIN
(fit window), MS_RESULTS, MS_ONLY (comma methods), STUDY_WORKERS.
"""
import csv
import math
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import fred
import fred_universe as fu
from bench_core import score_dist, gauss_dist, student_t_dist
from skaters.api import laplace

warnings.simplefilter("ignore")

HORIZONS = [int(h) for h in os.environ.get("MS_HORIZONS", "1,5,20").split(",")]
HMAX = int(os.environ.get("MS_HMAX", max(HORIZONS)))
N_ORIGINS = int(os.environ.get("MS_ORIGINS", "24"))       # scored origins per series
WIN = int(os.environ.get("MS_WIN", "500"))                # rolling fit window
BURN = 300
MIN_LEN = BURN + HMAX + N_ORIGINS + 10
N_SERIES = int(os.environ.get("MS_N", "150"))
RESULTS = os.environ.get("MS_RESULTS", os.path.join(_HERE, "comparisons", "_multistep.csv"))
WORKERS = int(os.environ.get("STUDY_WORKERS", min(16, (os.cpu_count() or 4))))
Z90 = 1.6448536269514722
ONLY = set(os.environ.get("MS_ONLY", "laplace,AutoARIMA,AutoETS,GARCH-t,Prophet").split(","))


def _origins(n):
    """Evenly-spaced origins in [BURN, n-HMAX-1] where all horizons are observable."""
    hi = n - HMAX - 1
    if hi <= BURN:
        return []
    step = max(1, (hi - BURN) // N_ORIGINS)
    return list(range(BURN, hi + 1, step))[:N_ORIGINS]


def _score_horizons(dists_by_origin, ch):
    """dists_by_origin: {origin: [Dist for h=1..HMAX]}. Returns {h: (lp, cr, n)}."""
    out = {}
    for h in HORIZONS:
        lp = cr = 0.0
        n = 0
        for t, dists in dists_by_origin.items():
            if h - 1 >= len(dists) or dists[h - 1] is None:
                continue
            a, b = score_dist(dists[h - 1], ch[t + h])
            lp += a
            cr += b
            n += 1
        if n:
            out[h] = (lp / n, cr / n, n)
    return out


def _laplace_online(ch, origins, **kw):
    f = laplace(HMAX, **kw)
    state = None
    want = set(origins)
    grabbed = {}
    for t, y in enumerate(ch):
        dists, state = f(y, state)
        if t in want:                       # dists forecast ch[t+1..t+HMAX]
            grabbed[t] = list(dists)
    return _score_horizons(grabbed, ch)


def _laplace_multistep(ch, origins):
    # single-scale (native fan-out); the multi-scale default is "laplace-msw"
    return _laplace_online(ch, origins, scales=[1])


def _laplace_msw_multistep(ch, origins):
    # the shipped default: multi-scale mixture at k > 1
    return _laplace_online(ch, origins)


def _sf_multistep(ch, origins):
    import numpy as np
    import pandas as pd
    from statsforecast import StatsForecast
    from statsforecast.models import AutoARIMA, AutoETS
    res = {"AutoARIMA": {}, "AutoETS": {}}
    for t in origins:
        hist = ch[max(0, t - WIN + 1):t + 1]
        df = pd.DataFrame({"unique_id": 0, "ds": np.arange(len(hist)), "y": hist})
        sf = StatsForecast(models=[AutoARIMA(), AutoETS()], freq=1, n_jobs=1)
        try:
            fc = sf.forecast(df=df, h=HMAX, level=[90])
        except Exception:
            continue
        for name in ("AutoARIMA", "AutoETS"):
            dists = []
            for h in range(1, HMAX + 1):
                row = fc.iloc[h - 1]
                mu = float(row[name])
                lo, hi = float(row[f"{name}-lo-90"]), float(row[f"{name}-hi-90"])
                dists.append(gauss_dist(mu, lo, hi))
            res[name][t] = dists
    return {name: _score_horizons(d, ch) for name, d in res.items()}


def _garch_multistep(ch, origins):
    import numpy as np
    from arch import arch_model
    grabbed = {}
    for t in origins:
        hist = np.asarray(ch[max(0, t - WIN + 1):t + 1], float) * 100.0   # scale for arch
        try:
            r = arch_model(hist, mean="Constant", vol="GARCH", p=1, q=1, dist="t").fit(disp="off")
            fc = r.forecast(horizon=HMAX, reindex=False)
            var = fc.variance.values[-1]                # per-horizon variance (scaled)
            mu = float(r.params.get("mu", 0.0)) / 100.0
            nu = float(r.params.get("nu", 8.0))
        except Exception:
            continue
        dists = [student_t_dist(mu, max(var[h - 1], 1e-12) / 1e4, nu) for h in range(1, HMAX + 1)]
        grabbed[t] = dists
    return {"GARCH-t": _score_horizons(grabbed, ch)}


def _prophet_multistep(ch, origins):
    import numpy as np
    import pandas as pd
    from prophet import Prophet
    grabbed = {}
    base = pd.Timestamp("2000-01-01")
    for t in origins:
        hist = ch[max(0, t - WIN + 1):t + 1]
        ds = pd.date_range(base, periods=len(hist), freq="D")
        df = pd.DataFrame({"ds": ds, "y": hist})
        try:
            m = Prophet(interval_width=0.90, weekly_seasonality=False,
                        yearly_seasonality=False, daily_seasonality=False)
            m.fit(df)
            fut = m.make_future_dataframe(periods=HMAX, freq="D")
            fc = m.predict(fut).iloc[-HMAX:]
        except Exception:
            continue
        dists = []
        for h in range(1, HMAX + 1):
            row = fc.iloc[h - 1]
            dists.append(gauss_dist(float(row["yhat"]), float(row["yhat_lower"]), float(row["yhat_upper"])))
        grabbed[t] = dists
    return {"Prophet": _score_horizons(grabbed, ch)}


def score_series(sid):
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    ch = ch[-6000:]
    if len(ch) < MIN_LEN:
        return sid, {}
    origins = _origins(len(ch))
    if not origins:
        return sid, {}
    per_method = {}
    if "laplace" in ONLY:
        per_method["laplace"] = _laplace_multistep(ch, origins)
    if "laplace-msw" in ONLY:
        per_method["laplace-msw"] = _laplace_msw_multistep(ch, origins)
    if {"AutoARIMA", "AutoETS"} & ONLY:
        try:
            per_method.update(_sf_multistep(ch, origins))
        except Exception:
            pass
    if "GARCH-t" in ONLY:
        try:
            per_method.update(_garch_multistep(ch, origins))
        except Exception:
            pass
    if "Prophet" in ONLY:
        try:
            per_method.update(_prophet_multistep(ch, origins))
        except Exception:
            pass
    return sid, {m: v for m, v in per_method.items() if m in ONLY or m in ("AutoARIMA", "AutoETS")}


def _universe():
    uj = os.path.join(fred._CACHE, "universe_daily.json")
    import json
    tmap = {s["id"]: s.get("title", "") for s in json.load(open(uj))} if os.path.exists(uj) else {}
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    PRICE = {"equity", "fx", "commodity"}
    return [s for s in ids if fu.asset_class(tmap.get(s, "")) not in PRICE]


def run():
    done = set()
    if os.path.exists(RESULTS):
        for r in csv.DictReader(open(RESULTS)):
            done.add(r["series"])
    uni = [s for s in _universe() if s not in done]
    fresh = not os.path.exists(RESULTS)
    fh = open(RESULTS, "a", newline="")
    w = csv.writer(fh)
    if fresh:
        w.writerow(["series", "method", "h", "logpdf", "crps", "n"])
    print(f"[multistep] horizons={HORIZONS} win={WIN} origins={N_ORIGINS} "
          f"workers={WORKERS} target={N_SERIES} (already {len(done)})", flush=True)
    scored = 0
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        futs = {}
        it = iter(uni)
        for sid in it:
            if len(futs) >= WORKERS * 3:
                break
            futs[pool.submit(score_series, sid)] = sid
        while futs and scored < N_SERIES:
            for fut in as_completed(list(futs)):
                sid = futs.pop(fut)
                try:
                    _sid, res = fut.result()
                except Exception:
                    res = {}
                if res.get("laplace"):
                    for m, byh in res.items():
                        for h, (lp, cr, n) in byh.items():
                            w.writerow([_sid, m, h, f"{lp:.6f}", f"{cr:.6f}", n])
                    fh.flush()
                    scored += 1
                    if scored % 10 == 0:
                        print(f"[multistep] scored {scored}/{N_SERIES}", flush=True)
                if scored >= N_SERIES:
                    break
                nxt = next(it, None)
                if nxt is not None:
                    futs[pool.submit(score_series, nxt)] = nxt
    fh.close()
    print(f"[multistep] done: {scored} series -> {RESULTS}", flush=True)
    summarize()


def summarize():
    rows = list(csv.DictReader(open(RESULTS)))
    sc = {}
    for r in rows:
        sc.setdefault((r["series"], int(r["h"])), {})[r["method"]] = (float(r["logpdf"]), float(r["crps"]))
    methods = sorted({r["method"] for r in rows if r["method"] != "laplace"})
    print(f"\n=== multi-step: laplace per-series win-rate by horizon ===")
    print(f"  {'opponent':12s}" + "".join(f"  h={h:<2d} LL/CRPS" for h in HORIZONS))
    for m in methods:
        cells = []
        for h in HORIZONS:
            nL = wL = nC = wC = 0
            for (sid, hh), d in sc.items():
                if hh != h or "laplace" not in d or m not in d:
                    continue
                la, lc = d["laplace"]; oa, oc = d[m]
                nL += 1; wL += la > oa
                nC += 1; wC += lc < oc
            cells.append(f"  {100*wL/nL:3.0f}/{100*wC/nC:3.0f}% (n={nL})" if nL else "   --      ")
        print(f"  {m:12s}" + "".join(cells))
    # laplace mean LL by horizon
    print("\n  laplace mean logpdf by horizon:")
    for h in HORIZONS:
        vals = [d["laplace"][0] for (sid, hh), d in sc.items() if hh == h and "laplace" in d]
        if vals:
            print(f"    h={h:<2d}  {sum(vals)/len(vals):+.3f}  (n={len(vals)})")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        summarize()
    else:
        run()
