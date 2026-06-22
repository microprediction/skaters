"""The real SOTA study: laplace vs AutoARIMA / AutoETS / GARCH-t / conformal.

Fair rolling one-step-ahead comparison on FRED one-step *changes*, scored on
BOTH held-out log-likelihood and CRPS (every method is turned into a `Dist` and
scored identically):

  * laplace            — ours (online, O(1)).
  * AutoARIMA, AutoETS — statsforecast, rolling 1-step via cross_validation with
                         periodic refit; the 90% interval gives a Gaussian Dist
                         (these emit densities, so this is the *real* likelihood
                         test, unlike a bare conformal CDF).
  * GARCH-t            — `arch` constant-mean GARCH(1,1) with Student-t
                         innovations: the classical SOTA for volatility
                         clustering + heavy tails, and the most honest opponent
                         on financial change-series. Refit every REFIT, variance
                         recursion filtered forward between refits; the
                         location-scale t is scored as a Gaussian scale-mixture.
  * SARIMAX            — statsmodels SARIMAX(1,0,1)+c, the canonical *exact*
                         Gaussian closed-form one-step predictive (not a band).
  * ETS-sm             — statsmodels simple exponential smoothing, Gaussian.
  * NF-StudentT        — NeuralForecast MLP with a Student-t distribution head
                         (exact df/loc/scale via return_params), a neural density
                         opponent in the matched online univariate protocol.
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
try:                                    # silence arch's SLSQP convergence chatter
    from arch.utility.exceptions import ConvergenceWarning as _ArchCW
    warnings.simplefilter("ignore", _ArchCW)
except Exception:                       # noqa: BLE001
    pass
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

try:                                    # GARCH-t opponent (the heavy-tail SOTA)
    from arch import arch_model
    from scipy.stats import chi2
    _HAVE_ARCH = True
except Exception:                       # noqa: BLE001
    _HAVE_ARCH = False

try:                                    # statsmodels exact-Gaussian references
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    from statsmodels.tsa.holtwinters import SimpleExpSmoothing
    _HAVE_SM = True
except Exception:                       # noqa: BLE001
    _HAVE_SM = False

try:                                    # NeuralForecast StudentT (neural density)
    import logging as _logging
    for _nm in ("pytorch_lightning", "lightning.pytorch", "lightning"):
        _logging.getLogger(_nm).setLevel(_logging.ERROR)
    from neuralforecast import NeuralForecast
    from neuralforecast.models import MLP
    from neuralforecast.losses.pytorch import DistributionLoss
    _HAVE_NF = True
except Exception:                       # noqa: BLE001
    _HAVE_NF = False

try:                                    # Prophet (the popular, heavy foil)
    import logging as _logging2
    for _nm in ("prophet", "cmdstanpy"):
        _logging2.getLogger(_nm).setLevel(_logging2.ERROR)
    from prophet import Prophet
    _HAVE_PROPHET = True
except Exception:                       # noqa: BLE001
    _HAVE_PROPHET = False

_HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.environ.get("SOTA_OUT", os.path.join(_HERE, "results_sota.csv"))

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


def student_t_dist(mu, var, nu, K=24):
    """Location-scale Student-t as a Gaussian *scale mixture* `Dist`, so it goes
    through the exact same logpdf/CRPS scoring as everything else. A standardised
    (unit-variance) t equals N(mu, var*(nu-2)/v) mixed over v ~ chi2_nu; we
    quantise v at K equal-probability nodes. Matches the analytic t logpdf to
    ~1e-3 at K=24."""
    nu = max(float(nu), 2.1)
    v = chi2.ppf((np.arange(K) + 0.5) / K, df=nu)
    s2 = var * (nu - 2.0)
    return Dist([(1.0 / K, mu, math.sqrt(max(s2 / vi, 1e-18))) for vi in v])


GARCH_WIN = 750         # capped expanding window for each GARCH refit


def garch_t_scores(ch):
    """Constant-mean GARCH(1,1) with Student-t innovations (the `arch` package) —
    the classical SOTA for volatility clustering + heavy tails. Rolling one-step:
    refit every REFIT steps, filter the conditional-variance recursion forward
    between refits, and score the resulting location-scale t over the same TEST
    window. Fit in a unit-variance-scaled space for optimiser stability, then map
    the predictive `Dist` back. Returns (logpdf, crps) or None if it cannot fit."""
    y = np.asarray(ch, float); n = len(y); start = n - TEST
    s = 1.0 / (np.std(y[:start]) or 1.0)
    ys = y * s
    mu = om = al = be = nu = None
    h_prev = res_prev = None; have = False
    lp = cr = 0.0; m = 0
    for t in range(start, n):
        if (not have) or (t - start) % REFIT == 0:
            hist = ys[max(0, t - GARCH_WIN):t]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    r = arch_model(hist, mean="Constant", vol="GARCH", p=1, q=1,
                                   dist="t", rescale=False).fit(
                                       disp="off", options={"maxiter": 200})
                mu = r.params["mu"]; om = r.params["omega"]
                al = r.params["alpha[1]"]; be = r.params["beta[1]"]; nu = r.params["nu"]
                h_prev = float(r.conditional_volatility[-1]) ** 2
                res_prev = float(hist[-1] - mu); have = True
            except Exception:           # noqa: BLE001
                if not have:
                    return None         # never managed to fit this series
        h_t = om + al * res_prev ** 2 + be * h_prev          # one-step cond. var
        d = student_t_dist(mu, h_t, nu).scale(1.0 / s)       # back to data space
        a, b = score_dist(d, y[t]); lp += a; cr += b; m += 1
        res_prev = float(ys[t] - mu); h_prev = h_t           # GARCH filter update
    return lp / m, cr / m


def sarimax_scores(ch, order=(1, 0, 1)):
    """statsmodels SARIMAX(1,0,1) with constant — the canonical *exact* Gaussian
    closed-form predictive (mean + se_mean), not a band reconstruction. Rolling
    one-step: refit every REFIT, cheap `append(refit=False)` filtering between."""
    y = np.asarray(ch, float); n = len(y); start = n - TEST
    lp = cr = 0.0; m = 0; res = None
    for t in range(start, n):
        if res is None or (t - start) % REFIT == 0:
            hist = y[max(0, t - GARCH_WIN):t]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    res = SARIMAX(hist, order=order, trend="c",
                                  enforce_stationarity=False,
                                  enforce_invertibility=False).fit(disp=False, maxiter=50)
            except Exception:           # noqa: BLE001
                if res is None:
                    return None
        fc = res.get_forecast(1)
        d = Dist.gaussian(float(fc.predicted_mean[0]), max(float(fc.se_mean[0]), 1e-9))
        a, b = score_dist(d, y[t]); lp += a; cr += b; m += 1
        res = res.append([y[t]], refit=False)
    return lp / m, cr / m


def ets_scores(ch):
    """statsmodels simple exponential smoothing (ETS A,N,N) on the change series;
    one-step Gaussian with se = residual std (exact for SES at h=1). Online
    smoothing recursion between periodic refits."""
    y = np.asarray(ch, float); n = len(y); start = n - TEST
    lp = cr = 0.0; m = 0; level = None; se = 1e-9; alpha = 0.3
    for t in range(start, n):
        if level is None or (t - start) % REFIT == 0:
            hist = y[max(0, t - GARCH_WIN):t]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fit = SimpleExpSmoothing(hist, initialization_method="estimated").fit()
                alpha = float(fit.params.get("smoothing_level", 0.3))
                level = float(fit.forecast(1)[0]); se = float(np.std(fit.resid)) or 1e-9
            except Exception:           # noqa: BLE001
                if level is None:
                    return None
        d = Dist.gaussian(level, max(se, 1e-9))
        a, b = score_dist(d, y[t]); lp += a; cr += b; m += 1
        level = level + alpha * (y[t] - level)               # SES recursion
    return lp / m, cr / m


PROPHET_Z90 = 1.6448536269514722


def prophet_scores(ch):
    """Facebook Prophet on the change series — the popular, heavy foil. A fresh
    Stan fit has NO cheap online update, so a true one-step-ahead forecast at step
    t requires fitting on history[:t] and predicting t — there is no honest
    shortcut (reusing a fit scores multi-step-ahead as one-step, which is garbage).
    So we refit at EVERY step over the TEST window. Ruinously slow (~TEST Stan fits
    per series); it is meant to run on a SMALL universe (SOTA_N small) — a method
    that is too slow for a series should skip that series, never cut corners within
    it. Returns mean (logpdf, crps, n=TEST) or None if it could not fit at all."""
    import contextlib, io
    y = np.asarray(ch, float); n = len(y); start = n - TEST
    ds_all = pd.date_range("2000-01-01", periods=n, freq="D")
    lp = cr = 0.0; m = 0
    for t in range(start, n):                       # every single step — no reuse
        hist = pd.DataFrame({"ds": ds_all[:t], "y": y[:t]})
        try:
            mdl = Prophet(interval_width=0.90, daily_seasonality=False,
                          weekly_seasonality=True, yearly_seasonality=True)
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                mdl.fit(hist)
                fc = mdl.predict(mdl.make_future_dataframe(
                    periods=1, freq="D")).set_index("ds")
        except Exception:               # noqa: BLE001
            continue
        row = fc.iloc[t]                # ds_all[t]: the one-step-ahead forecast
        sd = max((row["yhat_upper"] - row["yhat_lower"]) / (2 * PROPHET_Z90), 1e-9)
        a, b = score_dist(Dist.gaussian(float(row["yhat"]), sd), y[t])
        lp += a; cr += b; m += 1
    return (lp / m, cr / m, m) if m else None


NF_INPUT = int(os.environ.get("SOTA_NF_INPUT", 24))
NF_STEPS = int(os.environ.get("SOTA_NF_STEPS", 100))
NF_REFIT = int(os.environ.get("SOTA_NF_REFIT", 50))


def nf_scores(ch):
    """NeuralForecast MLP with a Student-t distribution head — a neural
    *density* opponent in the matched online univariate one-step protocol
    (per-series model, periodic refit). `return_params=True` gives exact
    (df, loc, scale), scored as the same Gaussian scale-mixture `Dist`. NB this
    is NF's weak regime: it is built for global cross-series training, which we
    deliberately exclude as a different protocol."""
    y = np.asarray(ch, float); n = len(y)
    df = pd.DataFrame({"unique_id": "s",
                       "ds": pd.date_range("2000-01-01", periods=n, freq="D"),
                       "y": y})
    m = MLP(h=1, input_size=NF_INPUT,
            loss=DistributionLoss("StudentT", return_params=True, num_samples=1),
            max_steps=NF_STEPS, num_layers=2, hidden_size=64, scaler_type="standard",
            enable_progress_bar=False, logger=False, enable_model_summary=False,
            accelerator="cpu")
    nf = NeuralForecast(models=[m], freq="D")
    try:
        import contextlib, io
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            warnings.simplefilter("ignore")
            cv = nf.cross_validation(df=df, n_windows=TEST, step_size=1, refit=NF_REFIT)
    except Exception:                   # noqa: BLE001
        return None
    cv = cv.sort_values("ds")
    lp = cr = 0.0; m = 0
    for _, row in cv.iterrows():
        nu = max(float(row["MLP-df"]), 2.1)
        sc = float(row["MLP-scale"]); var = sc * sc * nu / (nu - 2.0)
        d = student_t_dist(float(row["MLP-loc"]), var, nu)
        a, b = score_dist(d, float(row["y"])); lp += a; cr += b; m += 1
    return (lp / m, cr / m) if m else None


BATCH = int(os.environ.get("SOTA_BATCH", 60))   # series per statsforecast call
WORKERS = int(os.environ.get("SOTA_WORKERS", max(1, (os.cpu_count() or 2) - 1)))
# Per-series methods to skip (e.g. SOTA_SKIP="Prophet,NF-StudentT" for a big run).
SKIP = {s.strip() for s in os.environ.get("SOTA_SKIP", "").split(",") if s.strip()}


def _extract_cv(g):
    """Per-series statsforecast cross_validation slice -> picklable arrays for a
    worker (or None if the window is too short)."""
    if len(g) < TEST // 2:
        return None
    g = g.sort_values("ds")
    return {k: g[col].to_numpy() for k, col in (
        ("y", "y"), ("aa", "AutoARIMA"),
        ("aalo", "AutoARIMA-lo-90"), ("aahi", "AutoARIMA-hi-90"),
        ("ae", "AutoETS"), ("aelo", "AutoETS-lo-90"), ("aehi", "AutoETS-hi-90"))}


def score_one(payload):
    """Score every opponent for ONE series (runs in a worker process). Returns
    (sid, [rows]). The statsforecast-derived methods reuse the precomputed cv
    arrays; the rest fit per series here."""
    sid, ch, cvd = payload
    rows = []
    if cvd is not None:                          # AutoARIMA/AutoETS + conformal/ACI
        y = cvd["y"]
        acc = {m: [0.0, 0.0, 0] for m in
               ("AutoARIMA", "AutoETS", "AutoARIMA+conformal", "AutoARIMA+ACI")}
        resid = []; aci_scale = 1.0
        for t in range(len(y)):
            yt = y[t]
            for m, mean, lo, hi in (("AutoARIMA", cvd["aa"][t], cvd["aalo"][t], cvd["aahi"][t]),
                                    ("AutoETS", cvd["ae"][t], cvd["aelo"][t], cvd["aehi"][t])):
                a, b = score_dist(gauss_dist(mean, lo, hi), yt)
                acc[m][0] += a; acc[m][1] += b; acc[m][2] += 1
            pt = cvd["aa"][t]
            if len(resid) >= 40:
                win = resid[-250:]
                a, b = score_dist(conformal_dist(pt, win), yt)
                acc["AutoARIMA+conformal"][0] += a; acc["AutoARIMA+conformal"][1] += b
                acc["AutoARIMA+conformal"][2] += 1
                d2 = conformal_dist(pt, win, scale=aci_scale)
                a2, b2 = score_dist(d2, yt)
                acc["AutoARIMA+ACI"][0] += a2; acc["AutoARIMA+ACI"][1] += b2
                acc["AutoARIMA+ACI"][2] += 1
                lo2, hi2 = d2.quantile(0.05), d2.quantile(0.95)
                aci_scale *= 1.0 + 0.02 * ((0.0 if lo2 <= yt <= hi2 else 1.0) - 0.10)
                aci_scale = min(max(aci_scale, 0.2), 5.0)
            resid.append(yt - pt)
        for m, (lp, cr, n) in acc.items():
            if n:
                rows.append([sid, m, f"{lp/n:.6f}", f"{cr/n:.6f}", n])
    for name, fn, gate in (("GARCH-t", garch_t_scores, _HAVE_ARCH),
                           ("SARIMAX", sarimax_scores, _HAVE_SM),
                           ("ETS-sm", ets_scores, _HAVE_SM),
                           ("NF-StudentT", nf_scores, _HAVE_NF),
                           ("Prophet", prophet_scores, _HAVE_PROPHET)):
        if not gate or name in SKIP:
            continue
        try:
            r = fn(ch)
        except Exception:               # noqa: BLE001 — never let one opponent kill a series
            r = None
        if r is not None:
            nn = r[2] if len(r) > 2 else TEST     # methods may report their own n
            rows.append([sid, name, f"{r[0]:.6f}", f"{r[1]:.6f}", nn])
    lp, cr = laplace_scores(ch)
    rows.append([sid, "laplace", f"{lp:.6f}", f"{cr:.6f}", TEST])
    return sid, rows


def run():
    from concurrent.futures import ProcessPoolExecutor
    series = load_series()
    sids = list(series)
    # Resume: skip series already in the CSV and append (SOTA_RESUME=1).
    done_sids = set(); mode = "w"
    if os.environ.get("SOTA_RESUME") and os.path.exists(RESULTS):
        done_sids = {r["series"] for r in csv.DictReader(open(RESULTS))}
        mode = "a"
    print(f"loaded {len(sids)} series (HIST={HIST}, TEST={TEST}); {WORKERS} workers"
          + (f"; resuming ({len(done_sids)} already done)" if done_sids else "")
          + (f"; skipping {sorted(SKIP)}" if SKIP else ""), flush=True)
    done = len(done_sids)
    with open(RESULTS, mode) as fh, ProcessPoolExecutor(max_workers=WORKERS) as pool:
        w = csv.writer(fh)
        if mode == "w":
            w.writerow(["series", "method", "logpdf", "crps", "n"])
        # process in batches: statsforecast cross_validation (parallel, main proc)
        # then fan the per-series scoring out across the pool.
        for b0 in range(0, len(sids), BATCH):
            batch = [sid for sid in sids[b0:b0 + BATCH] if sid not in done_sids]
            if not batch:
                continue
            rows = []
            for sid in batch:
                ds = pd.date_range("1900-01-01", periods=len(series[sid]), freq="D")
                rows.extend((sid, d, float(v)) for d, v in zip(ds, series[sid]))
            df = pd.DataFrame(rows, columns=["unique_id", "ds", "y"])
            try:
                sf = StatsForecast(models=[AutoARIMA(), AutoETS()], freq="D", n_jobs=-1)
                cv = sf.cross_validation(df=df, h=1, step_size=1, n_windows=TEST,
                                         level=[90], refit=REFIT)
                cv = cv.reset_index() if "unique_id" not in cv.columns else cv
            except Exception as e:      # noqa: BLE001
                print(f"  batch CV {b0} FAILED: {e}", flush=True); cv = None
            payloads = [(sid, series[sid],
                         _extract_cv(cv[cv["unique_id"] == sid]) if cv is not None else None)
                        for sid in batch]
            for sid, srows in pool.map(score_one, payloads):
                for r in srows:
                    w.writerow(r)
                done += 1
            fh.flush()
            print(f"  done {done}/{len(sids)} series", flush=True)
    summarize()


def summarize():
    import collections
    by = collections.defaultdict(dict)
    for r in csv.DictReader(open(RESULTS)):
        by[r["series"]][r["method"]] = (float(r["logpdf"]), float(r["crps"]))

    # repeat fraction of each series' tail changes -> isolate continuous series,
    # since the lattice projection gives a large but metric-specific edge on
    # repeating/grid series that would otherwise dominate the aggregate.
    def rfrac(sid):
        ch = fred._to_changes(fred._load_levels(sid) or [])[-TEST:]
        return sum(1 for i in range(1, len(ch)) if ch[i] == ch[i - 1]) / max(len(ch) - 1, 1)
    cont = {s for s in by if rfrac(s) < 0.05}

    methods = ["AutoARIMA", "AutoETS", "SARIMAX", "ETS-sm", "GARCH-t",
               "NF-StudentT", "Prophet", "AutoARIMA+conformal", "AutoARIMA+ACI"]
    print(f"\n=== SOTA study: {len(by)} series ({len(cont)} continuous), rolling 1-step ===")
    print("per-series win-rate, laplace vs each (LL = higher logpdf; CRPS = lower):")
    print(f"  {'baseline':22s}{'LL all/cont':>14s}{'CRPS all/cont':>16s}")

    def wr(method, subset, idx, lower=False):
        sub = [by[s] for s in subset if method in by[s] and "laplace" in by[s]]
        if not sub:
            return float("nan")
        if lower:
            w = sum(1 for d in sub if d["laplace"][idx] < d[method][idx])
        else:
            w = sum(1 for d in sub if d["laplace"][idx] > d[method][idx])
        return 100.0 * w / len(sub)

    alls = set(by)
    for m in methods:
        ll = f"{wr(m, alls, 0):.0f}/{wr(m, cont, 0):.0f}%"
        cp = f"{wr(m, alls, 1, lower=True):.0f}/{wr(m, cont, 1, lower=True):.0f}%"
        print(f"  {m:22s}{ll:>14s}{cp:>16s}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        summarize()
    else:
        run()
