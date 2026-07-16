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
from skaters.api import laplace, dantzig
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
    _ours("dantzig", lambda: dantzig(1)),
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


# ---- laplace-ss: laplace with a phase-aware terminal leaf ----------------------
# "Conform last, per phase": laplace's exact candidate population, but the
# terminal CRPS leaf is conjugated with seasonal_scale, so the ISSUED predictive
# width is conditioned on the phase of the cycle. The season period comes from
# BENCH_CSP_M (the same knowledge the CSP opponent is given). VERDICT: flattens
# per-phase PIT but scores WORSE than laplace on real seasonal series — the
# global leaf scale it displaces was also tracking regime drift, and CSP's edge
# lives in raw same-phase value pools, not residual width (see
# comparisons/laplace-vs-csp/README.md). Kept registered as the tape for that
# negative result; not a laplace candidate.
def _laplace_ss():
    from functools import partial
    from skaters.api import _build_candidates
    from skaters.terminal import terminal_leaf_ensemble
    from skaters.conjugate import conjugate
    from skaters.leaf import crps_leaf as _pkg_crps_leaf
    from skaters.transform import seasonal_scale
    from skaters.sticky import sticky
    from skaters.tails import gpdtails
    from skaters.parade import parade
    k = 1
    P = int(os.environ.get("BENCH_CSP_M", 24))
    cands, depths, _ = _build_candidates(k)

    def ss_leaf(k=1):
        return conjugate(_pkg_crps_leaf(k=k, scale_alpha=0.03),
                         seasonal_scale(P, 0.05), k=k)

    f = terminal_leaf_ensemble(cands, k=k, leaf_fn=ss_leaf,
                               learning_rate=0.8, complexity_penalty=0.005,
                               depths=depths, max_components=20, forget=0.99)
    return parade(gpdtails(sticky(f, k=k), k=k), k=k)


LAPLACE_SS = [_ours("laplace-ss", _laplace_ss)]


# ---- laplace-pe: laplace + hedged seasonal-anchor candidates -------------------
# The hedged seasonal location (seasonal_anchor): a 50/50 blend of a
# recency-weighted same-phase mean and the seasonal-naive — the naive adapts
# instantly but is one noisy draw, the phase-EMA averages the noise but lags
# shifts; the hedge beats either alone on every probed M4 series (the
# experiments that isolated it are in comparisons/laplace-vs-csp/). Location —
# unlike width — passes through the stock terminal intact (candidate means
# mix). Stock terminal, stock wrappers; the arm's period joins the stock
# {7,12,24} via BENCH_CSP_M. The stock anchors now ship in default laplace
# (api.py + JS mirror); laplace-pe differs only by adding the arm's own period.
def _laplace_pe():
    from skaters.api import _build_candidates, _objective_leaf
    from skaters.terminal import terminal_leaf_ensemble
    from skaters.conjugate import conjugate
    from skaters.leaf import leaf as _plain_leaf
    from skaters.transform import seasonal_anchor
    from skaters.sticky import sticky
    from skaters.tails import gpdtails
    from skaters.parade import parade
    k = 1
    cands, depths, _ = _build_candidates(k)
    periods = {7, 12, 24}
    m = os.environ.get("BENCH_CSP_M")
    if m and int(m) > 1:
        periods.add(int(m))
    for p in sorted(periods):
        cands.append(conjugate(_plain_leaf(k=k), seasonal_anchor(p, 0.2, 0.5), k=k))
        depths.append(1)
    f = terminal_leaf_ensemble(cands, k=k, leaf_fn=_objective_leaf("crps", 0.03),
                               learning_rate=0.8, complexity_penalty=0.005,
                               depths=depths, max_components=20, forget=0.99)
    return parade(gpdtails(sticky(f, k=k), k=k), k=k)


LAPLACE_PE = [_ours("laplace-pe", _laplace_pe)]


# ---- NNS-derived experiments (skaters#113) --------------------------------------
# laplace-pm: laplace with the partial-moment (two-piece normal) terminal leaf.
# laplace-pt: laplace + per-phase Holt anchor candidates (trend per phase).
def _laplace_pm():
    from skaters.api import laplace
    from nns_ideas import pm_leaf
    return laplace(1, leaf=pm_leaf)


def _laplace_pt():
    from skaters.api import _build_candidates, _objective_leaf
    from skaters.terminal import terminal_leaf_ensemble
    from skaters.conjugate import conjugate
    from skaters.leaf import leaf as _plain_leaf
    from skaters.sticky import sticky
    from skaters.tails import gpdtails
    from skaters.parade import parade
    from nns_ideas import phase_trend_anchor
    k = 1
    cands, depths, _ = _build_candidates(k)
    periods = {7, 12, 24}
    m = os.environ.get("BENCH_CSP_M")
    if m and int(m) > 1:
        periods.add(int(m))
    for p in sorted(periods):
        cands.append(conjugate(_plain_leaf(k=k), phase_trend_anchor(p), k=k))
        depths.append(1)
    f = terminal_leaf_ensemble(cands, k=k, leaf_fn=_objective_leaf("crps", 0.03),
                               learning_rate=0.8, complexity_penalty=0.005,
                               depths=depths, max_components=20, forget=0.99)
    return parade(gpdtails(sticky(f, k=k), k=k), k=k)


NNS_IDEAS = [_ours("laplace-pm", _laplace_pm), _ours("laplace-pt", _laplace_pt)]


# ---- terminal-stage variants: transfer distributional knowledge inside ---------
# The stock terminal collapses the candidate mixture to its mean; these conform
# a richer object (studentized residual / PIT of the full mixture) so candidate
# scale and shape knowledge reaches the issued predictive. See terminal_variants.
def _make_tv(name):
    def factory():
        import terminal_variants as tv
        return getattr(tv, name)()
    return factory


TERMINAL_VARIANTS = [_ours("laplace-stud", _make_tv("laplace_stud")),
                     _ours("laplace-pit", _make_tv("laplace_pit"))]


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
# BENCH_R_ONLY=name1,... restricts the run to those methods; the NNS methods are
# opt-in ONLY (they refit every step, so they run through their own opponent
# rather than taxing every R@* invocation).
SKIP <- strsplit(Sys.getenv("BENCH_R_SKIP", ""), ",")[[1]]
ONLY <- strsplit(Sys.getenv("BENCH_R_ONLY", ""), ",")[[1]]
OPTIN_METHODS <- c("NNS-R", "NNS-R-auto", "TBATS-R", "TBATS-R-ms")
skip <- function(nm) nm %in% SKIP ||
  (length(ONLY) > 0 && !(nm %in% ONLY)) ||
  (length(ONLY) == 0 && nm %in% OPTIN_METHODS)

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

if (have_forecast && (!skip("TBATS-R") || !skip("TBATS-R-ms"))) {
  # TBATS (De Livera-Hyndman-Snyder): Box-Cox + trend + trig seasonality +
  # ARMA errors. The arm's period via ts(frequency=); model reused between
  # refits. tbats(model=) intermittently emits corrupt filtered states on
  # shifting windows (forecast means hundreds of sigma out), so every reused
  # forecast is sanity-checked against the window scale and an insane one
  # forces a fresh fit; a step is skipped only if the fresh fit is insane too.
  # Quantile fan so a non-unit Box-Cox lambda's asymmetric intervals are
  # scored as shaped.
  tb_fc <- function(m) tryCatch(forecast(m, h = 1, level = LEVELS),
                                error = function(e) NULL)
  tb_sane <- function(f, sw) {
    if (is.null(f)) return(FALSE)
    mu <- as.numeric(f$mean)[1]
    wid <- as.numeric(f$upper[1, ncol(f$upper)]) - as.numeric(f$lower[1, 1])
    is.finite(mu) && is.finite(wid) && abs(mu) <= 10 * sw && wid <= 30 * sw
  }
  tb_run <- function(nm, mk) {
    gfit <- NULL
    for (t in start:(n - 1)) {
      win <- y[max(1L, t - fitwin + 1L):t]
      if (length(win) < 60) next
      sw <- max(sd(win), 1e-12)
      f <- NULL; m <- NULL
      if (!is.null(gfit) && ((t - start) %% refit != 0L)) {
        m <- tryCatch(tbats(mk(win), model = gfit, use.parallel = FALSE),
                      error = function(e) NULL)
        if (!is.null(m)) { f <- tb_fc(m); if (!tb_sane(f, sw)) { m <- NULL; f <- NULL } }
      }
      if (is.null(m)) {
        m <- tryCatch(tbats(mk(win), use.parallel = FALSE), error = function(e) NULL)
        if (!is.null(m)) { f <- tb_fc(m); if (!tb_sane(f, sw)) { m <- NULL; f <- NULL } }
      }
      if (is.null(m)) { gfit <- NULL; next }
      gfit <- m
      emitQ(nm, t, qgrid(as.numeric(f$mean)[1],
                         as.numeric(f$lower[1, ]), as.numeric(f$upper[1, ]),
                         LEVELS))
    }
  }
  m_env <- suppressWarnings(as.integer(Sys.getenv("BENCH_CSP_M", "")))
  sfreq <- if (!is.na(m_env) && m_env > 1) m_env else 1L
  if (!skip("TBATS-R"))
    tb_run("TBATS-R", function(win) if (sfreq > 1) ts(win, frequency = sfreq) else win)
  # Multi-seasonal variant: TBATS's trigonometric representation is BUILT for
  # several periods at once (the msts path); BENCH_TBATS_MS="24,168" supplies
  # them (hour-of-day AND hour-of-week on hourly data).
  ms <- suppressWarnings(as.numeric(strsplit(Sys.getenv("BENCH_TBATS_MS", ""), ",")[[1]]))
  if (!skip("TBATS-R-ms") && length(ms) >= 2 && all(is.finite(ms)))
    tb_run("TBATS-R-ms", function(win) msts(win, seasonal.periods = ms))
}

have_nns <- requireNamespace("NNS", quietly = TRUE)
if (have_nns && (!skip("NNS-R") || !skip("NNS-R-auto"))) {
  # NNS.ARMA (Viole): forecasts from same-phase component series at seasonal
  # periods. Point forecast only, so the predictive is a split-conformal band:
  # the TAUS quantiles of a rolling pool of its own one-step errors, warmed for
  # ~120 steps before the scored window (emit BEFORE appending the realized
  # error -- no leakage). NNS-R is given the arm's period (BENCH_CSP_M, the
  # same knowledge the CSP opponent gets); NNS-R-auto uses its own detection.
  m_env <- suppressWarnings(as.integer(Sys.getenv("BENCH_CSP_M", "")))
  variants <- list()
  if (!skip("NNS-R") && !is.na(m_env) && m_env > 1) variants[["NNS-R"]] <- m_env
  if (!skip("NNS-R-auto")) variants[["NNS-R-auto"]] <- NA
  for (nm in names(variants)) {
    sf <- variants[[nm]]
    errs <- numeric(0)
    for (t in max(30L, start - 120L):(n - 1)) {
      win <- y[max(1L, t - fitwin + 1L):t]
      if (length(win) < 40) next
      pt <- tryCatch(as.numeric(suppressMessages(suppressWarnings(
              if (is.na(sf))
                NNS::NNS.ARMA(win, h = 1, method = "lin",
                              negative.values = TRUE, plot = FALSE)
              else
                NNS::NNS.ARMA(win, h = 1, method = "lin", seasonal.factor = sf,
                              negative.values = TRUE, plot = FALSE))))[1],
            error = function(e) NULL)
      if (is.null(pt) || !is.finite(pt)) next
      if (t >= start && length(errs) >= 40)
        emitQ(nm, t, pt + as.numeric(quantile(errs, probs = TAUS)))
      errs <- c(errs, y[t + 1] - pt)
      if (length(errs) > 400) errs <- errs[-1]
    }
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


# ---- NNS (Viole): same-phase component forecasting -----------------------------
# Runs through the shared R script but opt-in (refits every step; see the R
# block). Cheap (~ms/call), so the budget is generous.
def _nns_predict(ch, start, refit=None):
    prev = os.environ.get("BENCH_R_ONLY")
    os.environ["BENCH_R_ONLY"] = "NNS-R,NNS-R-auto"
    try:
        return _r_predict(ch, start, refit=1)
    finally:
        if prev is None:
            os.environ.pop("BENCH_R_ONLY", None)
        else:
            os.environ["BENCH_R_ONLY"] = prev


NNSR = ([Opponent("NNS-R", _nns_predict,
                  max_series=int(os.environ.get("BENCH_NNS_MAX", 500)),
                  methods=["NNS-R", "NNS-R-auto"])]
        if _RSCRIPT else [])


def _tbats_predict(ch, start, refit=None):
    prev = os.environ.get("BENCH_R_ONLY")
    os.environ["BENCH_R_ONLY"] = "TBATS-R"
    try:
        return _r_predict(ch, start, refit=25)
    finally:
        if prev is None:
            os.environ.pop("BENCH_R_ONLY", None)
        else:
            os.environ["BENCH_R_ONLY"] = prev


def _tbats_ms_predict(ch, start, refit=None):
    prev = os.environ.get("BENCH_R_ONLY")
    os.environ["BENCH_R_ONLY"] = "TBATS-R-ms"
    try:
        return _r_predict(ch, start, refit=25)
    finally:
        if prev is None:
            os.environ.pop("BENCH_R_ONLY", None)
        else:
            os.environ["BENCH_R_ONLY"] = prev


TBATS = ([Opponent("TBATS-R", _tbats_predict,
                   max_series=int(os.environ.get("BENCH_TBATS_MAX", 250))),
          Opponent("TBATS-R-ms", _tbats_ms_predict,
                   max_series=int(os.environ.get("BENCH_TBATS_MAX", 250)))]
         if _RSCRIPT else [])


# ---- CSP: Conformal Seasonal Pools (Manokhin, arXiv:2605.03789) ----------------
# The AUTHOR'S reference package (pip install git+https://github.com/valeman/
# csp-forecaster.git): ConformalSeasonalPool fit on a rolling window, one-step
# predictive samples scored through the one scorer. The sample pool's quantile
# grid becomes a Dist via grid_dist (Silverman KDE, same convention as the other
# sample-based baselines) so it is scored on BOTH logpdf and CRPS.
#
# Variants are a star around the package's recommended defaults (adaptive,
# residual_mode="h_step", decay_unit="step"): season period m (daily FRED series
# are business-day, so the week is m=5, the month m=21; m=7 is the calendar-week
# alias for comparison), the paper-exact pool construction
# (residual_mode="paper", decay_unit="cycle"; mode stays "fast" — statistically
# equivalent per their README/tests), fixed (non-adaptive) mixing, recency decay
# off/strong, pool weight, calibration fraction, and the m=1 non-seasonal floor.
# BENCH_CSP_M recenters every variant on one period (12=monthly, 52=weekly,
# 24=hourly) for the frequency arms.
try:
    from csp_forecaster import ConformalSeasonalPool as _CSPool
except Exception:                                      # package not installed
    _CSPool = None

CSP_WIN   = int(os.environ.get("BENCH_CSP_WIN", 750))     # capped look-back per step
CSP_NSAMP = int(os.environ.get("BENCH_CSP_NSAMPLES", 256))
_CSP_M    = os.environ.get("BENCH_CSP_M")                  # recenter (freq arms)


def _csp_variants():
    base = int(_CSP_M) if _CSP_M else 5
    v = [(f"CSPr-m{m}", m, {}) for m in
         ([base] if _CSP_M else [5, 7, 21])]
    v += [
        (f"CSPr-m{base}-paper", base, dict(residual_mode="paper", decay_unit="cycle")),
        (f"CSPr-m{base}-fixed", base, dict(adaptive=False)),
        (f"CSPr-m{base}-lam0", base, dict(exp_lambda=0.0)),
        (f"CSPr-m{base}-lam05", base, dict(exp_lambda=0.05)),
        (f"CSPr-m{base}-pw30", base, dict(pool_weight=0.3)),
        (f"CSPr-m{base}-pw70", base, dict(pool_weight=0.7)),
        (f"CSPr-m{base}-cal25", base, dict(cal_fraction=0.25)),
        (f"CSPr-m{base}-cal100", base, dict(cal_fraction=1.0)),
        ("CSPr-m1", 1, {}),
    ]
    return v


_CSP_VARIANTS = _csp_variants()


def _csp_ref_predict(ch, start, refit=None):
    y = np.asarray(ch, float); n = len(y)
    acc = {name: [0.0, 0.0, 0] for name, _, _ in _CSP_VARIANTS}
    for t in range(start, n):
        win = y[max(0, t - CSP_WIN):t]
        for name, m, kw in _CSP_VARIANTS:
            if len(win) <= max(2 * m, 10):
                continue
            args = dict(mode="fast", random_state=100_000 + t)
            args.update(kw)
            f = _CSPool(**args).fit(win, seasonal_period=m)
            s = f.predict(H=1, n_samples=CSP_NSAMP).samples[0]
            taus = np.linspace(0.02, 0.98, 41)
            d = bc.grid_dist(taus, np.quantile(s, taus))
            if d is None:
                continue
            a, b = bc.score_dist(d, y[t])
            acc[name][0] += a; acc[name][1] += b; acc[name][2] += 1
    return [(name, lp / k, cr / k, k) for name, (lp, cr, k) in acc.items() if k]


CSP = ([Opponent("CSP", _csp_ref_predict, methods=[v[0] for v in _CSP_VARIANTS])]
       if _CSPool else [])


# ---- registry & named opponent sets -------------------------------------------
ALL = (OURS + LAPLACE_SS + LAPLACE_PE + NNS_IDEAS + TERMINAL_VARIANTS
       + CONFORMAL_NAIVE + STATSFORECAST + GARCH + STATSMODELS + NF + PROPHET
       + R + NNSR + TBATS + CSP)
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
