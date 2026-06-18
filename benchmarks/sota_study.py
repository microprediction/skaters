"""The real SOTA study: laplace vs AutoARIMA / AutoETS / AutoARIMA+conformal.

Fair rolling one-step-ahead comparison on FRED one-step *changes*, scored on
BOTH held-out log-likelihood and CRPS (every method is turned into a `Dist` and
scored identically):

  * laplace            — ours (online, O(1)).
  * AutoARIMA, AutoETS — statsforecast, rolling 1-step via cross_validation with
                         periodic refit; the 90% interval gives a Gaussian Dist
                         (these emit densities, so this is the *real* likelihood
                         test, unlike a bare conformal CDF).
  * AutoARIMA+conformal — AutoARIMA point + a rolling split-conformal predictive
                         over recent residuals (a strong-mean conformal system).
  * AutoARIMA+ACI       — the same, with an online adaptive-conformal scale.

Writes benchmarks/results_sota.csv (one row per series x method) and prints a
summary with family-clustered win-rates. Run in the conda env with statsforecast
and a FRED key:  PYTHONPATH=src python benchmarks/sota_study.py
"""
from __future__ import annotations
import os, sys, math, warnings
warnings.filterwarnings("ignore")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import csv
import numpy as np
import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import AutoARIMA, AutoETS

import fred
import fred_universe
from skaters.dist import Dist
from skaters.api import laplace

_HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(_HERE, "results_sota.csv")

N_SERIES = int(os.environ.get("SOTA_N", 300))   # how many cached series to use
HIST = 1000                                     # last-N changes kept per series
TEST = 300                                      # rolling one-step test window
REFIT = 25                                      # refit ARIMA/ETS every N windows
Z90 = 1.6448536269514722                        # 90% two-sided z


def load_series():
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    out = {}
    for sid in ids:
        lv = fred._load_levels(sid)
        if not lv:
            continue
        ch = fred._to_changes(lv)
        if len(ch) < HIST:
            continue
        out[sid] = ch[-HIST:]
        if len(out) >= N_SERIES:
            break
    return out


def gauss_dist(mu, lo, hi):
    sd = max((hi - lo) / (2.0 * Z90), 1e-9)
    return Dist.gaussian(mu, sd)


def conformal_dist(point, resid_window, scale=1.0, nq=41):
    """Split-conformal predictive: point + a quantile grid of recent residuals,
    KDE-smoothed so it can be scored on likelihood (Silverman bandwidth from the
    robust spread). Capped at nq quantiles to keep mixture CRPS (O(K^2)) cheap."""
    r = np.asarray(resid_window)
    qs = np.quantile(r, np.linspace(0.02, 0.98, nq))
    iqr = np.quantile(r, 0.75) - np.quantile(r, 0.25)
    spread = (iqr / 1.349) if iqr > 0 else (r.max() - r.min()) or 1.0
    h = max(0.9 * spread * scale * len(r) ** (-0.2), 1e-9)
    return Dist([(1.0 / nq, point + scale * q, h) for q in qs])


def score_dist(d, y):
    lp = d.logpdf(y)
    return (lp if math.isfinite(lp) else -20.0), d.crps(y)


def laplace_scores(ch):
    """Mean logpdf/CRPS of laplace over the last TEST steps."""
    f = laplace(1); st = None; pend = None
    n = len(ch); start = n - TEST
    lp = cr = 0.0; m = 0
    for i, y in enumerate(ch):
        if pend is not None and i >= start:
            a, b = score_dist(pend[0], y); lp += a; cr += b; m += 1
        d, st = f(y, st); pend = d
    return lp / m, cr / m


BATCH = int(os.environ.get("SOTA_BATCH", 60))   # series per statsforecast call


def run():
    series = load_series()
    print(f"loaded {len(series)} series (HIST={HIST}, TEST={TEST})", flush=True)
    sids = list(series)

    with open(RESULTS, "w") as fh:
        w = csv.writer(fh); w.writerow(["series", "method", "logpdf", "crps", "n"])

      # process in batches so an overnight crash keeps prior results
        for b0 in range(0, len(sids), BATCH):
            batch = sids[b0:b0 + BATCH]
            rows = []
            for sid in batch:
                ch = series[sid]
                ds = pd.date_range("1900-01-01", periods=len(ch), freq="D")
                for d, v in zip(ds, ch):
                    rows.append((sid, d, float(v)))
            df = pd.DataFrame(rows, columns=["unique_id", "ds", "y"])
            try:
                sf = StatsForecast(models=[AutoARIMA(), AutoETS()], freq="D", n_jobs=-1)
                cv = sf.cross_validation(df=df, h=1, step_size=1, n_windows=TEST,
                                         level=[90], refit=REFIT)
                cv = cv.reset_index() if "unique_id" not in cv.columns else cv
            except Exception as e:  # noqa: BLE001
                print(f"  batch {b0}-{b0+len(batch)} FAILED: {e}", flush=True)
                continue
            _score_batch(w, fh, batch, series, cv)
            print(f"  done {min(b0+BATCH, len(sids))}/{len(sids)} series", flush=True)
    summarize()


def _score_batch(w, fh, batch, series, cv):
        for sid in batch:
            ch = series[sid]
            g = cv[cv["unique_id"] == sid].sort_values("ds")
            if len(g) < TEST // 2:
                continue
            y = g["y"].to_numpy()
            acc = {m: [0.0, 0.0, 0] for m in
                   ("AutoARIMA", "AutoETS", "AutoARIMA+conformal", "AutoARIMA+ACI")}
            resid = []                       # rolling AutoARIMA residuals
            aci_scale = 1.0                  # adaptive-conformal scale
            for t in range(len(g)):
                yt = y[t]
                # parametric Gaussian from each model's 90% band
                for m in ("AutoARIMA", "AutoETS"):
                    d = gauss_dist(g[m].iloc[t], g[f"{m}-lo-90"].iloc[t], g[f"{m}-hi-90"].iloc[t])
                    a, b = score_dist(d, yt); acc[m][0] += a; acc[m][1] += b; acc[m][2] += 1
                # conformal on AutoARIMA residuals (need a warm window)
                pt = g["AutoARIMA"].iloc[t]
                if len(resid) >= 40:
                    win = resid[-250:]
                    d = conformal_dist(pt, win)
                    a, b = score_dist(d, yt)
                    acc["AutoARIMA+conformal"][0] += a; acc["AutoARIMA+conformal"][1] += b
                    acc["AutoARIMA+conformal"][2] += 1
                    d2 = conformal_dist(pt, win, scale=aci_scale)
                    a2, b2 = score_dist(d2, yt)
                    acc["AutoARIMA+ACI"][0] += a2; acc["AutoARIMA+ACI"][1] += b2
                    acc["AutoARIMA+ACI"][2] += 1
                    # ACI: widen if the actual fell outside the ~90% band, else shrink
                    lo, hi = d2.quantile(0.05), d2.quantile(0.95)
                    aci_scale *= 1.0 + 0.02 * ((0.0 if lo <= yt <= hi else 1.0) - 0.10)
                    aci_scale = min(max(aci_scale, 0.2), 5.0)
                resid.append(yt - pt)
            for m, (lp, cr, n) in acc.items():
                if n:
                    w.writerow([sid, m, f"{lp/n:.6f}", f"{cr/n:.6f}", n])
            # ours, same test window
            lp, cr = laplace_scores(ch)
            w.writerow([sid, "laplace", f"{lp:.6f}", f"{cr:.6f}", TEST])
            fh.flush()


def summarize():
    import collections
    by = collections.defaultdict(dict)
    for r in csv.DictReader(open(RESULTS)):
        by[r["series"]][r["method"]] = (float(r["logpdf"]), float(r["crps"]))
    methods = ["laplace", "AutoARIMA", "AutoETS", "AutoARIMA+conformal", "AutoARIMA+ACI"]
    print(f"\n=== SOTA study: {len(by)} series, rolling 1-step ===")
    print(f"{'method':22s}{'mean logpdf':>13s}{'mean CRPS':>11s}"
          f"{'laplace beats (family)':>24s}")
    for m in methods:
        lp = [d[m][0] for d in by.values() if m in d]
        cr = [d[m][1] for d in by.values() if m in d]
        if m == "laplace":
            print(f"  {m:20s}{np.mean(lp):13.3f}{np.mean(cr):11.4f}{'—':>24s}")
            continue
        # family-clustered win-rate: laplace logpdf > method, per family then averaged
        fam = collections.defaultdict(list)
        for s, d in by.items():
            if "laplace" in d and m in d:
                fam[fred_universe.family(s)].append(1.0 if d["laplace"][0] > d[m][0] else 0.0)
        fr = [np.mean(v) for v in fam.values()]
        crfam = collections.defaultdict(list)
        for s, d in by.items():
            if "laplace" in d and m in d:
                crfam[fred_universe.family(s)].append(1.0 if d["laplace"][1] < d[m][1] else 0.0)
        crr = [np.mean(v) for v in crfam.values()]
        print(f"  {m:20s}{np.mean(lp):13.3f}{np.mean(cr):11.4f}"
              f"   LL {100*np.mean(fr):4.0f}%  CRPS {100*np.mean(crr):4.0f}%")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        summarize()
    else:
        run()
