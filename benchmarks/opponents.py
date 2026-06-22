"""Opponent registry for the unified study.

Every opponent is a callable ``predict(ch, start, refit) -> [(method, logpdf|None,
crps, n), ...]`` — it forecasts the one-step change and scores every step with
index >= ``start`` through ``bench_core`` (the one scorer). A *compound* opponent
(statsforecast) returns several methods from one shared fit. Heavy dependencies
are gated at import: a missing dep simply drops that opponent from ``REGISTRY``.

Each opponent carries a ``max_series`` budget. A method that is too slow for the
whole universe just covers fewer series (the runner stops feeding it past its
budget); on the series it does cover it evaluates fully and honestly — never a
cheaper within-series approximation. ``summarize`` reports each method's N.
"""
from __future__ import annotations
import os
import warnings
import numpy as np

import bench_core as bc
from skaters.dist import Dist

REFIT = int(os.environ.get("BENCH_REFIT", 25))     # refit fittable baselines every N steps
FIT_WIN = int(os.environ.get("BENCH_FIT_WIN", 750))  # capped look-back per refit
warnings.filterwarnings("ignore")


class Opponent:
    """name -> predict(ch, start, refit) -> [(method, logpdf|None, crps, n)]."""
    def __init__(self, name, predict, max_series=None, methods=None):
        self.name = name
        self.predict = predict
        self.max_series = max_series          # None = unlimited (cheap method)
        self.methods = methods or [name]      # method names this opponent emits


# ---- ours: online Dist-emitting policies --------------------------------------
from skaters.api import laplace, doob
from skaters.leaf import scale_mixture_leaf
from crps_leaf import crps_leaf


def _ours(method, factory):
    def predict(ch, start, refit=None):
        lp, cr, n = bc.roll_dist_scores(factory, ch, start)
        return [(method, lp, cr, n)] if n else []
    return Opponent(method, predict)


def doob_after_laplace(k=1):
    """Distributional residual stacking: laplace removes the predictable part, so
    its one-step residual e_t = y_t - mean_t is a driftless martingale-difference
    — doob's home. We use laplace's MEAN and doob's residual DISTRIBUTION. doob is
    fed the residual martingale M = cumsum(e); its predictive for the next level
    M' (mean M) is shifted to laplace's next mean: D_y = doob_dist.shift(m_next-M).

    EXPERIMENT — NEGATIVE RESULT (kept for reproducibility, not registered).
    laplace's standardized residuals do retain volatility clustering (lag-1
    ACF(z^2) ~0.13 vs ~0.25 raw; significant on ~79% of series), but stacking doob
    nonetheless LOSES to plain laplace (beats it on LL 17%, CRPS 5% over 60 series;
    mean LL 2.67 vs 2.70): it discards laplace's CRPS/likelihood-conformed tail for
    doob's noisier residual vol-estimate, costing more than the leftover clustering
    is worth. So it is not in any preset's opponent set."""
    lap = laplace(k); db = doob(k)

    def f(y, state):
        st = state or {"lap": None, "db": None, "M": 0.0, "mprev": None}
        if st["mprev"] is not None:
            st["M"] += (y - st["mprev"])              # accrue the residual martingale
        lap_d, st["lap"] = lap(y, st["lap"])          # laplace: the mean model
        m_next = lap_d[0].mean
        db_d, st["db"] = db(st["M"], st["db"])        # doob: the residual vol clock
        D = db_d[0].shift(m_next - st["M"]) if st["mprev"] is not None else lap_d[0]
        st["mprev"] = m_next
        return [D], st
    f.__name__ = f"doob_after_laplace(k={k})"
    return f


OURS = [
    _ours("laplace", lambda: laplace(1)),
    _ours("laplace-ll", lambda: laplace(1, objective="likelihood")),
    _ours("laplace-nostick", lambda: laplace(1, sticky=False)),
    _ours("scalemix-leaf", lambda: scale_mixture_leaf(1)),
    _ours("crps-leaf-0.3", lambda: crps_leaf(eta=0.3)),
    _ours("crps-leaf-0.6", lambda: crps_leaf(eta=0.6)),
    _ours("crps-leaf-1.0", lambda: crps_leaf(eta=1.0)),
]


# ---- conformal, parameterized by mean model -----------------------------------
def _conformal_naive(window):
    def predict(ch, start, refit=None):
        cr, n = bc.crepes_pinball(ch, window=window, start=start, mean=0.0)
        return [(f"crepes-w{window}", None, cr, n)] if n else []   # CDF -> no logpdf
    return Opponent(f"crepes-w{window}", predict)


CONFORMAL_NAIVE = [_conformal_naive(w) for w in (250, 400, 750)]


# ---- statsforecast (compound): AutoARIMA, AutoETS, + AutoARIMA-mean conformal --
try:
    import pandas as pd
    from statsforecast import StatsForecast
    from statsforecast.models import AutoARIMA, AutoETS
    _HAVE_SF = True
except Exception:                              # noqa: BLE001
    _HAVE_SF = False


def _statsforecast_predict(ch, start, refit):
    """One rolling-1-step CV yields AutoARIMA & AutoETS (Gaussian from the 90%
    band) AND the AutoARIMA-mean conformal + ACI variants (split-conformal over
    AutoARIMA residuals). The fitted-mean counterpart to the naive crepes."""
    y = np.asarray(ch, float); n = len(y)
    nw = n - start
    if nw < 30:
        return []
    df = pd.DataFrame({"unique_id": "s",
                       "ds": pd.date_range("2000-01-01", periods=n, freq="D"), "y": y})
    try:
        sf = StatsForecast(models=[AutoARIMA(), AutoETS()], freq="D", n_jobs=1)
        cv = sf.cross_validation(df=df, h=1, step_size=1, n_windows=nw,
                                 level=[90], refit=refit).sort_values("ds")
    except Exception:                          # noqa: BLE001
        return []
    yv = cv["y"].to_numpy()
    out = {m: [0.0, 0.0, 0] for m in
           ("AutoARIMA", "AutoETS", "AutoARIMA+conformal", "AutoARIMA+ACI")}
    resid = []; aci = 1.0
    for t in range(len(yv)):
        yt = yv[t]
        for m, col in (("AutoARIMA", "AutoARIMA"), ("AutoETS", "AutoETS")):
            d = bc.gauss_dist(cv[col].iloc[t], cv[f"{col}-lo-90"].iloc[t], cv[f"{col}-hi-90"].iloc[t])
            a, b = bc.score_dist(d, yt); out[m][0] += a; out[m][1] += b; out[m][2] += 1
        pt = cv["AutoARIMA"].iloc[t]
        if len(resid) >= 40:
            win = resid[-250:]
            a, b = bc.score_dist(bc.conformal_dist(pt, win), yt)
            out["AutoARIMA+conformal"][0] += a; out["AutoARIMA+conformal"][1] += b
            out["AutoARIMA+conformal"][2] += 1
            d2 = bc.conformal_dist(pt, win, scale=aci)
            a2, b2 = bc.score_dist(d2, yt)
            out["AutoARIMA+ACI"][0] += a2; out["AutoARIMA+ACI"][1] += b2
            out["AutoARIMA+ACI"][2] += 1
            lo2, hi2 = d2.quantile(0.05), d2.quantile(0.95)
            aci *= 1.0 + 0.02 * ((0.0 if lo2 <= yt <= hi2 else 1.0) - 0.10)
            aci = min(max(aci, 0.2), 5.0)
        resid.append(yt - pt)
    return [(m, lp / k, cr / k, k) for m, (lp, cr, k) in out.items() if k]


STATSFORECAST = ([Opponent("statsforecast", _statsforecast_predict,
                           max_series=int(os.environ.get("BENCH_SF_MAX", 800)),
                           methods=["AutoARIMA", "AutoETS",
                                    "AutoARIMA+conformal", "AutoARIMA+ACI"])]
                 if _HAVE_SF else [])


# ---- GARCH(1,1)-t (arch) ------------------------------------------------------
try:
    from arch import arch_model
    _HAVE_ARCH = True
except Exception:                              # noqa: BLE001
    _HAVE_ARCH = False


def _garch_predict(ch, start, refit):
    y = np.asarray(ch, float); n = len(y)
    s = 1.0 / (np.std(y[:start]) or 1.0); ys = y * s
    mu = om = al = be = nu = None; h_prev = res_prev = None; have = False
    lp = cr = 0.0; m = 0
    for t in range(start, n):
        if (not have) or (t - start) % refit == 0:
            hist = ys[max(0, t - FIT_WIN):t]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    r = arch_model(hist, mean="Constant", vol="GARCH", p=1, q=1, dist="t",
                                   rescale=False).fit(disp="off", options={"maxiter": 200})
                mu = r.params["mu"]; om = r.params["omega"]
                al = r.params["alpha[1]"]; be = r.params["beta[1]"]; nu = r.params["nu"]
                h_prev = float(r.conditional_volatility[-1]) ** 2
                res_prev = float(hist[-1] - mu); have = True
            except Exception:                  # noqa: BLE001
                if not have:
                    return []
        h_t = om + al * res_prev ** 2 + be * h_prev
        d = bc.student_t_dist(mu, h_t, nu).scale(1.0 / s)
        a, b = bc.score_dist(d, y[t]); lp += a; cr += b; m += 1
        res_prev = float(ys[t] - mu); h_prev = h_t
    return [("GARCH-t", lp / m, cr / m, m)] if m else []


GARCH = ([Opponent("GARCH-t", _garch_predict,
                   max_series=int(os.environ.get("BENCH_GARCH_MAX", 800)))]
         if _HAVE_ARCH else [])


# ---- statsmodels: SARIMAX(1,0,1)+c and SES ------------------------------------
try:
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    from statsmodels.tsa.holtwinters import SimpleExpSmoothing
    _HAVE_SM = True
except Exception:                              # noqa: BLE001
    _HAVE_SM = False


def _sarimax_predict(ch, start, refit):
    y = np.asarray(ch, float); n = len(y); res = None
    lp = cr = 0.0; m = 0
    for t in range(start, n):
        if res is None or (t - start) % refit == 0:
            hist = y[max(0, t - FIT_WIN):t]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    res = SARIMAX(hist, order=(1, 0, 1), trend="c", enforce_stationarity=False,
                                  enforce_invertibility=False).fit(disp=False, maxiter=50)
            except Exception:                  # noqa: BLE001
                if res is None:
                    return []
        fc = res.get_forecast(1)
        d = Dist.gaussian(float(fc.predicted_mean[0]), max(float(fc.se_mean[0]), 1e-9))
        a, b = bc.score_dist(d, y[t]); lp += a; cr += b; m += 1
        res = res.append([y[t]], refit=False)
    return [("SARIMAX", lp / m, cr / m, m)] if m else []


def _ets_predict(ch, start, refit):
    y = np.asarray(ch, float); n = len(y)
    lp = cr = 0.0; m = 0; level = None; se = 1e-9; alpha = 0.3
    for t in range(start, n):
        if level is None or (t - start) % refit == 0:
            hist = y[max(0, t - FIT_WIN):t]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fit = SimpleExpSmoothing(hist, initialization_method="estimated").fit()
                alpha = float(fit.params.get("smoothing_level", 0.3))
                level = float(fit.forecast(1)[0]); se = float(np.std(fit.resid)) or 1e-9
            except Exception:                  # noqa: BLE001
                if level is None:
                    return []
        d = Dist.gaussian(level, max(se, 1e-9))
        a, b = bc.score_dist(d, y[t]); lp += a; cr += b; m += 1
        level = level + alpha * (y[t] - level)
    return [("ETS-sm", lp / m, cr / m, m)] if m else []


STATSMODELS = ([Opponent("SARIMAX", _sarimax_predict, int(os.environ.get("BENCH_SM_MAX", 800))),
                Opponent("ETS-sm", _ets_predict, int(os.environ.get("BENCH_SM_MAX", 800)))]
               if _HAVE_SM else [])


# ---- NeuralForecast Student-t head --------------------------------------------
try:
    from neuralforecast import NeuralForecast
    from neuralforecast.models import MLP
    from neuralforecast.losses.pytorch import DistributionLoss
    _HAVE_NF = True
except Exception:                              # noqa: BLE001
    _HAVE_NF = False


def _nf_predict(ch, start, refit):
    import pandas as pd, contextlib, io
    y = np.asarray(ch, float); n = len(y)
    df = pd.DataFrame({"unique_id": "s",
                       "ds": pd.date_range("2000-01-01", periods=n, freq="D"), "y": y})
    m_ = MLP(h=1, input_size=int(os.environ.get("BENCH_NF_INPUT", 24)),
             loss=DistributionLoss("StudentT", return_params=True, num_samples=1),
             max_steps=int(os.environ.get("BENCH_NF_STEPS", 100)), num_layers=2,
             hidden_size=64, scaler_type="standard", enable_progress_bar=False,
             logger=False, enable_model_summary=False, accelerator="cpu")
    try:
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            cv = NeuralForecast(models=[m_], freq="D").cross_validation(
                df=df, n_windows=n - start, step_size=1,
                refit=int(os.environ.get("BENCH_NF_REFIT", 50)))
    except Exception:                          # noqa: BLE001
        return []
    cv = cv.sort_values("ds"); lp = cr = 0.0; m = 0
    for _, row in cv.iterrows():
        nu = max(float(row["MLP-df"]), 2.1); sc = float(row["MLP-scale"])
        d = bc.student_t_dist(float(row["MLP-loc"]), sc * sc * nu / (nu - 2.0), nu)
        a, b = bc.score_dist(d, float(row["y"])); lp += a; cr += b; m += 1
    return [("NF-StudentT", lp / m, cr / m, m)] if m else []


NF = ([Opponent("NF-StudentT", _nf_predict, int(os.environ.get("BENCH_NF_MAX", 300)))]
      if _HAVE_NF else [])


# ---- Prophet (refit EVERY step — no honest shortcut) --------------------------
try:
    import logging as _lg
    for _nm in ("prophet", "cmdstanpy"):
        _lg.getLogger(_nm).setLevel(_lg.ERROR)
    from prophet import Prophet
    _HAVE_PROPHET = True
except Exception:                              # noqa: BLE001
    _HAVE_PROPHET = False


def _prophet_predict(ch, start, refit):
    import pandas as pd, contextlib, io
    y = np.asarray(ch, float); n = len(y)
    ds_all = pd.date_range("2000-01-01", periods=n, freq="D")
    lp = cr = 0.0; m = 0
    for t in range(start, n):                  # every step; a fresh Stan fit each time
        try:
            mdl = Prophet(interval_width=0.90, daily_seasonality=False,
                          weekly_seasonality=True, yearly_seasonality=True)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                mdl.fit(pd.DataFrame({"ds": ds_all[:t], "y": y[:t]}))
                fc = mdl.predict(mdl.make_future_dataframe(periods=1, freq="D")).set_index("ds")
        except Exception:                      # noqa: BLE001
            continue
        row = fc.iloc[t]
        sd = max((row["yhat_upper"] - row["yhat_lower"]) / (2 * bc.Z90), 1e-9)
        a, b = bc.score_dist(Dist.gaussian(float(row["yhat"]), sd), y[t]); lp += a; cr += b; m += 1
    return [("Prophet", lp / m, cr / m, m)] if m else []


PROPHET = ([Opponent("Prophet", _prophet_predict, int(os.environ.get("BENCH_PROPHET_MAX", 30)))]
           if _HAVE_PROPHET else [])


# ---- registry & named opponent sets -------------------------------------------
ALL = OURS + CONFORMAL_NAIVE + STATSFORECAST + GARCH + STATSMODELS + NF + PROPHET
REGISTRY = {op.name: op for op in ALL}

SETS = {
    # cheap, scales to the whole daily universe
    "conformal-scale": [op.name for op in OURS] + [op.name for op in CONFORMAL_NAIVE],
    # the heavy SOTA opponents (small universe); ours + everything installed
    "sota": [op.name for op in OURS] + [op.name for op in
             (CONFORMAL_NAIVE + STATSFORECAST + GARCH + STATSMODELS + NF + PROPHET)],
}


def resolve(names):
    """names -> list[Opponent], skipping any whose deps are absent."""
    return [REGISTRY[n] for n in names if n in REGISTRY]
