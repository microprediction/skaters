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
from skaters.api import laplace
from skaters.leaf import scale_mixture_leaf
from crps_leaf import crps_leaf


def _ours(method, factory):
    def predict(ch, start, refit=None):
        lp, cr, n = bc.roll_dist_scores(factory, ch, start)
        return [(method, lp, cr, n)] if n else []
    return Opponent(method, predict)


def _markov_factories():
    from markov_forecaster import (markov_skater, markov_mix_skater,
                                   markov_nudge_skater)
    return markov_skater, markov_mix_skater, markov_nudge_skater


OURS = [
    _ours("laplace", lambda: laplace(1)),
    _ours("markov", lambda: _markov_factories()[0]()),
    _ours("markov-mix", lambda: _markov_factories()[1]()),
    _ours("markov-nudge", lambda: _markov_factories()[2]()),
    _ours("markov-nudge-pre", lambda: __import__("markov_forecaster").markov_nudge_pre_skater()),
    _ours("markov-nudge-pre-nostick", lambda: __import__("markov_forecaster").markov_nudge_pre_skater(sticky=False)),
    _ours("laplace+markov", lambda: laplace(
        1, extra_candidates=[(lambda k: _markov_factories()[0](), 2)])),
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


def _statsforecast_predict(ch, start, refit, suffix=""):
    """One rolling-1-step CV yields AutoARIMA & AutoETS (Gaussian from the 90%
    band) AND the AutoARIMA-mean conformal + ACI variants (split-conformal over
    AutoARIMA residuals). The fitted-mean counterpart to the naive crepes.
    `refit` is the CV refit cadence (the accuracy/speed knob); `suffix` tags the
    emitted method names when the same models are swept across cadences."""
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
    return [(m + suffix, lp / k, cr / k, k) for m, (lp, cr, k) in out.items() if k]


# Same accuracy/speed sweep as the R stack: AutoARIMA refits are the cost, so
# register the CV at a few cadences (`BENCH_SF_REFITS`, shares the `5,25,100`
# default) — AutoARIMA-py@5/@25/@100 then sit on the *same* refit-cadence axis as
# auto.arima-R, port vs. real thing at matched cost. (AutoETS is cheap, its curve
# is near-flat.)
_SF_METHODS = ("AutoARIMA", "AutoETS", "AutoARIMA+conformal", "AutoARIMA+ACI")
_SF_REFITS = [int(x) for x in os.environ.get("BENCH_SF_REFITS", "5,25,100").split(",")]


def _make_sf(refit_val):
    suffix = f"@{refit_val}"

    def predict(ch, start, refit=None):        # ignore the preset refit; bake our own
        return _statsforecast_predict(ch, start, refit_val, suffix=suffix)
    return Opponent(f"statsforecast{suffix}", predict,
                    max_series=int(os.environ.get("BENCH_SF_MAX", 800)),
                    methods=[m + suffix for m in _SF_METHODS])


STATSFORECAST = [_make_sf(r) for r in _SF_REFITS] if _HAVE_SF else []


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


# ---- R (compound): the *actual* R forecast stack, not a Python port -----------
# One Rscript per series runs the rolling one-step CV in R and prints one line per
# scored step: `method,t,G,mu;sd` (a Gaussian predictive) or `method,t,Q,q1;q2;…`
# (a quantile grid at the shared TAUS levels, for a genuinely non-Gaussian
# predictive). Python rebuilds the matching Dist — Dist.gaussian or bc.grid_dist —
# and scores it through the one scorer. Gated on `Rscript` on PATH; each method is
# gated inside R on its package, so a missing package just drops that method:
#   forecast -> auto.arima-R, Theta-R (Gaussian), nnetar-R (simulated => quantiles)
#   smooth   -> ADAM-R (assumed-distribution predictive => quantiles)
#   rugarch  -> GARCH-t-R (Student-t conditional predictive => quantiles)
#   bsts     -> bsts-R (posterior-predictive draws => quantiles)
# Install: R, then `install.packages(c("forecast","smooth","rugarch","bsts"))`
# (forecast+smooth are the core; rugarch/bsts are optional heavier opponents).
import shutil
import subprocess
import tempfile

_RSCRIPT = shutil.which("Rscript")

# Canonical predictive-quantile grid, shared with the R side (must match exactly).
_R_TAUS = [0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5,
           0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.975, 0.99]

_R_SRC = r'''
suppressWarnings(suppressMessages({
args <- commandArgs(trailingOnly = TRUE)
datafile <- args[1]
start  <- as.integer(args[2])   # 0-based python index of the first scored step
refit  <- as.integer(args[3])
fitwin <- as.integer(args[4])
y <- scan(datafile, quiet = TRUE)
n <- length(y)
z90 <- 1.6448536269514722

# Shared quantile grid; LEVELS = the two-sided central-interval %s it needs.
TAUS <- c(0.01,0.025,0.05,0.1,0.15,0.2,0.25,0.3,0.4,0.5,
          0.6,0.7,0.75,0.8,0.85,0.9,0.95,0.975,0.99)
LEVELS <- sort(unique(round(abs(1 - 2 * TAUS[TAUS != 0.5]) * 100, 6)))

emitG <- function(method, t, mu, sd)
  cat(sprintf("%s,%d,G,%.10g;%.10g\n", method, t, mu, sd))
emitQ <- function(method, t, qs)
  cat(sprintf("%s,%d,Q,%s\n", method, t, paste(sprintf("%.10g", qs), collapse = ";")))
sdband <- function(lo, hi) max((hi - lo) / (2 * z90), 1e-9)

# Assemble a TAUS-ordered quantile vector from a fan of central intervals + point.
qgrid <- function(point, lower, upper, levels) {
  out <- numeric(length(TAUS))
  for (i in seq_along(TAUS)) {
    tau <- TAUS[i]
    if (isTRUE(all.equal(tau, 0.5))) { out[i] <- point; next }
    L <- round(abs(1 - 2 * tau) * 100, 6); j <- which(levels == L)[1]
    out[i] <- if (tau < 0.5) lower[j] else upper[j]
  }
  out
}

# BENCH_R_SKIP=name1,name2 drops those methods (e.g. skip the slow bsts-R for a
# high-throughput sweep). Empty by default -> run everything available.
SKIP <- strsplit(Sys.getenv("BENCH_R_SKIP", ""), ",")[[1]]
skip <- function(nm) nm %in% SKIP

have_forecast <- requireNamespace("forecast", quietly = TRUE)
have_smooth   <- requireNamespace("smooth",   quietly = TRUE)
have_rugarch  <- requireNamespace("rugarch",  quietly = TRUE)
have_bsts     <- requireNamespace("bsts",     quietly = TRUE)
if (have_forecast) suppressMessages(library(forecast))
if (have_smooth)   suppressMessages(library(smooth))
if (have_rugarch)  suppressMessages(library(rugarch))
if (have_bsts)     suppressMessages(library(bsts))

# t iterates python 0-based indices start..n-1. The first t obs (R y[1:t]) are the
# history; the realized value python-y[t] is scored on the Python side. fc_fn(m)
# returns list(mu,sd) -> emitG, or list(q=<TAUS-ordered values>) -> emitQ.
run_reuse <- function(name, refit_fn, reuse_fn, fc_fn) {
  if (skip(name)) return(invisible())
  fit <- NULL
  for (t in start:(n - 1)) {
    win <- y[max(1L, t - fitwin + 1L):t]
    if (length(win) < 20) next
    if (is.null(fit) || ((t - start) %% refit == 0L)) {
      fit <- tryCatch(refit_fn(win), error = function(e) NULL); m <- fit
    } else {
      m <- tryCatch(reuse_fn(win, fit), error = function(e)
             tryCatch(refit_fn(win), error = function(e2) NULL))
    }
    if (is.null(m)) next
    r <- tryCatch(fc_fn(m), error = function(e) NULL)
    if (is.null(r)) next
    if (!is.null(r$q)) emitQ(name, t, r$q) else emitG(name, t, r$mu, r$sd)
  }
}

if (have_forecast) {
  # auto.arima: exactly-Gaussian predictive -> emit mean+sd (the band is exact).
  # Reuse fitted orders between refits via Arima(model=) (refilter, no re-estimate).
  run_reuse("auto.arima-R",
    function(win) auto.arima(win),
    function(win, fit) Arima(win, model = fit),
    function(m) { f <- forecast(m, h = 1, level = 90)
                  list(mu = as.numeric(f$mean)[1],
                       sd = sdband(as.numeric(f$lower)[1], as.numeric(f$upper)[1])) })

  # Theta (M3 winner): Gaussian predictive; cheap, refit every step.
  if (!skip("Theta-R")) for (t in start:(n - 1)) {
    win <- y[max(1L, t - fitwin + 1L):t]
    if (length(win) < 20) next
    f <- tryCatch(thetaf(win, h = 1, level = 90), error = function(e) NULL)
    if (!is.null(f)) emitG("Theta-R", t, as.numeric(f$mean)[1],
                           sdband(as.numeric(f$lower)[1], as.numeric(f$upper)[1]))
  }

  # NNETAR (nonlinear autoregression): simulated predictive => real non-Gaussian
  # quantiles. Reuse the trained net between refits via nnetar(model=).
  run_reuse("nnetar-R",
    function(win) nnetar(win),
    function(win, fit) nnetar(win, model = fit),
    function(m) { f <- forecast(m, h = 1, PI = TRUE, level = LEVELS, npaths = 400)
                  list(q = qgrid(as.numeric(f$mean)[1],
                                 as.numeric(f$lower[1, ]), as.numeric(f$upper[1, ]), LEVELS)) })
}

if (have_smooth) {
  # ADAM (Svetunkov): state-space auto ETS/ARIMA with an assumed (possibly
  # non-Gaussian) distribution — score its real quantiles, not a Gaussian band.
  run_reuse("ADAM-R",
    function(win) adam(win, model = "ZZZ"),
    function(win, fit) adam(win, model = fit),
    function(m) { f <- forecast(m, h = 1, interval = "prediction", level = LEVELS / 100)
                  list(q = qgrid(as.numeric(f$mean)[1],
                                 as.numeric(f$lower[1, ]), as.numeric(f$upper[1, ]), LEVELS)) })
}

if (have_rugarch && !skip("GARCH-t-R")) {
  # GARCH(1,1)-t: heavy-tail conditional predictive; quantiles straight from the
  # fitted Student-t (mu + sigma * t_nu quantile). The R counterpart to arch's GARCH-t.
  spec <- ugarchspec(variance.model = list(model = "sGARCH", garchOrder = c(1, 1)),
                     mean.model = list(armaOrder = c(0, 0), include.mean = TRUE),
                     distribution.model = "std")
  gfit <- NULL
  for (t in start:(n - 1)) {
    win <- y[max(1L, t - fitwin + 1L):t]
    if (length(win) < 60) next
    if (is.null(gfit) || ((t - start) %% refit == 0L))
      gfit <- tryCatch(ugarchfit(spec, win, solver = "hybrid"), error = function(e) NULL)
    if (is.null(gfit)) next
    r <- tryCatch({
      fc <- ugarchforecast(gfit, n.ahead = 1)
      mu <- as.numeric(fitted(fc))[1]; sg <- as.numeric(sigma(fc))[1]
      nu <- coef(gfit)[["shape"]]
      mu + sg * qdist("std", p = TAUS, mu = 0, sigma = 1, shape = nu)
    }, error = function(e) NULL)
    if (!is.null(r)) emitQ("GARCH-t-R", t, r)
  }
}

if (have_bsts && !skip("bsts-R")) {
  # BSTS (Bayesian local level): posterior-predictive draws => sample quantiles.
  # No online update — a fresh short MCMC each step, so keep its max_series tiny.
  niter <- as.integer(Sys.getenv("BENCH_BSTS_NITER", "300"))
  for (t in start:(n - 1)) {
    win <- y[max(1L, t - fitwin + 1L):t]
    if (length(win) < 40) next
    r <- tryCatch({
      md <- bsts(win, state.specification = AddLocalLevel(list(), win),
                 niter = niter, ping = 0, seed = 1)
      pr <- predict(md, horizon = 1, burn = as.integer(niter / 3))
      as.numeric(quantile(as.numeric(pr$distribution), probs = TAUS))
    }, error = function(e) NULL)
    if (!is.null(r)) emitQ("bsts-R", t, r)
  }
}
}))
'''

_R_PATH = None
if _RSCRIPT:
    try:
        _fd, _R_PATH = tempfile.mkstemp(suffix=".R", prefix="skaters_rbench_")
        with os.fdopen(_fd, "w") as _f:
            _f.write(_R_SRC)
    except Exception:                          # noqa: BLE001
        _R_PATH = None


_R_METHODS = ("auto.arima-R", "Theta-R", "nnetar-R", "ADAM-R", "GARCH-t-R", "bsts-R")


def _r_line_dist(kind, payload):
    """Parse one R output line's predictive into a Dist: `G`->Gaussian(mu,sd),
    `Q`->grid_dist over the shared _R_TAUS. Returns None if unusable."""
    if kind == "G":
        mu_s, sd_s = payload.split(";")
        mu = float(mu_s); sd = max(float(sd_s), 1e-9)
        return Dist.gaussian(mu, sd) if np.isfinite(mu) and np.isfinite(sd) else None
    if kind == "Q":
        qs = [float(x) for x in payload.split(";")]
        if len(qs) != len(_R_TAUS):
            return None
        return bc.grid_dist(_R_TAUS, qs)
    return None


def _r_predict(ch, start, refit, suffix=""):
    if not (_RSCRIPT and _R_PATH):
        return []
    y = np.asarray(ch, float); n = len(y)
    if n - start < 30:
        return []
    tf = tempfile.NamedTemporaryFile("w", suffix=".dat", delete=False)
    try:
        tf.write("\n".join("%.12g" % float(v) for v in y)); tf.close()
        proc = subprocess.run(
            [_RSCRIPT, "--vanilla", _R_PATH, tf.name, str(start), str(refit), str(FIT_WIN)],
            capture_output=True, text=True,
            timeout=int(os.environ.get("BENCH_R_TIMEOUT", 1800)))
    except Exception:                          # noqa: BLE001
        return []
    finally:
        try:
            os.unlink(tf.name)
        except OSError:
            pass
    out = {}
    for line in proc.stdout.splitlines():
        parts = line.split(",")
        if len(parts) != 4:
            continue
        method, t_s, kind, payload = parts
        try:
            t = int(t_s)
        except ValueError:
            continue
        if not (0 <= t < n):
            continue
        try:
            d = _r_line_dist(kind, payload)
        except ValueError:
            continue
        if d is None:
            continue
        a, b = bc.score_dist(d, y[t])
        acc = out.setdefault(method + suffix, [0.0, 0.0, 0])
        acc[0] += a; acc[1] += b; acc[2] += 1
    return [(m, lp / k, cr / k, k) for m, (lp, cr, k) in out.items() if k]


# Refit cadence is the key accuracy/speed meta-variable: auto.arima and ADAM
# reuse the fitted model between refits, so a coarse cadence is far cheaper and
# (usually) a little less accurate. Register the R stack at a few cadences so the
# frontier plot shows each model's own accuracy-vs-speed curve, not one point.
# (Theta refits every step regardless, so its cadence knob is a near-flat line.)
_R_REFITS = [int(x) for x in os.environ.get("BENCH_R_REFITS", "5,25,100").split(",")]


def _make_r(refit_val):
    suffix = f"@{refit_val}"

    def predict(ch, start, refit=None):        # ignore the preset refit; bake our own
        return _r_predict(ch, start, refit_val, suffix=suffix)
    return Opponent(f"R{suffix}", predict,
                    max_series=int(os.environ.get("BENCH_R_MAX", 120)),
                    methods=[m + suffix for m in _R_METHODS])


R = [_make_r(r) for r in _R_REFITS] if _RSCRIPT else []


# ---- CSP: Conformal Seasonal Pools (Manokhin, arXiv:2605.03789) ----------------
# Training-free: the predictive pool mixes same-season empirical draws with signed
# residual draws around a seasonal-naive forecast. It's a predictive-distribution
# *sampler*, not just an interval builder, so — like the fitted conformal_dist — we
# KDE-smooth the pool into a Dist (Silverman bandwidth) and score BOTH logpdf and
# CRPS. The tails are empirical/thin (the same caveat as any conformal foil). Pure
# numpy, zero deps, so it always loads. `CSP-adaptive` widens/narrows the pool by
# recent 90% hit-rate (ACI-style), the paper's adaptive variant.
CSP_M   = int(os.environ.get("BENCH_CSP_M", 7))       # season period (weekly on daily FRED)
CSP_WIN = int(os.environ.get("BENCH_CSP_WIN", 750))   # capped look-back per step


def _csp_dist(s, m, nq=41, scale=1.0):
    """Predictive Dist for the step right after the contiguous window `s`."""
    s = np.asarray(s, float); L = len(s)
    if L <= m + 5:
        return None
    i = np.arange(L)
    same = s[i[i % m == L % m]]                        # same-season past draws
    snaive = s[L - m]                                  # seasonal-naive point
    resid = s[m:] - s[:-m]                             # seasonal-naive residuals
    pool = np.concatenate([same, snaive + scale * resid, snaive - scale * resid])
    if pool.size < 5:
        return None
    qs = np.quantile(pool, np.linspace(0.02, 0.98, nq))
    iqr = np.quantile(pool, 0.75) - np.quantile(pool, 0.25)
    spread = (iqr / 1.349) if iqr > 0 else (pool.max() - pool.min()) or 1.0
    h = max(0.9 * spread * pool.size ** (-0.2), 1e-9)  # Silverman
    return Dist([(1.0 / nq, float(q), h) for q in qs])


def _csp_predict(ch, start, refit=None):
    y = np.asarray(ch, float); n = len(y)
    lp = cr = 0.0; m = 0
    lpa = cra = 0.0; ma = 0; scale = 1.0
    for t in range(start, n):
        win = y[max(0, t - CSP_WIN):t]
        d = _csp_dist(win, CSP_M)
        if d is not None:
            a, b = bc.score_dist(d, y[t]); lp += a; cr += b; m += 1
        da = _csp_dist(win, CSP_M, scale=scale)
        if da is not None:
            aa, bb = bc.score_dist(da, y[t]); lpa += aa; cra += bb; ma += 1
            lo, hi = da.quantile(0.05), da.quantile(0.95)
            scale *= 1.0 + 0.02 * ((0.0 if lo <= y[t] <= hi else 1.0) - 0.10)
            scale = min(max(scale, 0.2), 5.0)
    out = []
    if m:
        out.append(("CSP", lp / m, cr / m, m))
    if ma:
        out.append(("CSP-adaptive", lpa / ma, cra / ma, ma))
    return out


CSP = [Opponent("CSP", _csp_predict, methods=["CSP", "CSP-adaptive"])]


# ---- registry & named opponent sets -------------------------------------------
ALL = OURS + CONFORMAL_NAIVE + STATSFORECAST + GARCH + STATSMODELS + NF + PROPHET + R + CSP
REGISTRY = {op.name: op for op in ALL}

SETS = {
    # cheap, scales to the whole daily universe
    "conformal-scale": [op.name for op in OURS] + [op.name for op in CONFORMAL_NAIVE + CSP],
    # the heavy SOTA opponents (small universe); ours + everything installed
    "sota": [op.name for op in OURS] + [op.name for op in
             (CONFORMAL_NAIVE + STATSFORECAST + GARCH + STATSMODELS + NF + PROPHET + R + CSP)],
}


def resolve(names):
    """names -> list[Opponent], skipping any whose deps are absent."""
    return [REGISTRY[n] for n in names if n in REGISTRY]
