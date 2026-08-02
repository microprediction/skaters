"""Zero-shot arm adapters for the week-long study, one registry.

Each adapter takes a one-step *change* series `ch` and returns a list of TEST
per-step predictive `Dist`s over the rolling one-step test window (the last
`fs.TEST` observations, each forecast from a `fs.CTX`-long context ending just
before it), or None if the model is unavailable. Every model's predictive is
turned into the SAME `Dist` (samples -> Gaussian KDE, quantiles -> smoothed
mixture) by reusing foundation_study's helpers, so scores are comparable and
nothing is reimplemented. The canonical runner (run_arm.py) walks these into the
per-step predictions.py schema.

Protocol matches foundation_study.py exactly (fixed context window, batched
inference, zero-shot), so laplace re-scored on the identical window is an
apples-to-apples baseline. Each arm runs in its OWN venv (deps conflict); the
registry entry is imported lazily so a venv missing a package still loads.

Attribution (research use): TabPFN "Built with PriorLabs-TabPFN"; TiRex includes
materials developed at NXAI under the NXAI Community License; flowstate uses the
ibm-research research checkpoint (arXiv:2508.05287), research-use only.
"""
from __future__ import annotations
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import foundation_study as fs           # sample_dist, quantile_dist, CTX, TEST, laplace
from skaters.api import laplace
from skaters.dist import Dist
from predictions import _norm_ppf as _nppf


def _ncdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

CTX, TEST = fs.CTX, fs.TEST
LEVELS9 = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
DEVICE = os.environ.get("FM_DEVICE", "cpu")


# ------------------------------------------------------------------ laplace baseline
def laplace_dists(ch, h=1):
    """Per-step laplace predictive over the test window (the h-step forecast made
    h observations earlier). Mirrors foundation_study.laplace_scores but returns
    the Dist objects so the canonical store records laplace per step too."""
    f = laplace(h); st = None; queue = []; out = []
    start = len(ch) - TEST
    for i, yv in enumerate(ch):
        if len(queue) >= h and i >= start:
            out.append(queue[-h][h - 1])
        d, st = f(yv, st)
        queue.append(d)
        if len(queue) > h:
            queue.pop(0)
    return out


# ------------------------------------------------------------------ foundation arms
_sundial = None
def sundial_dists(ch, h=1):
    """Sundial (thuml, flow-matching generative head): sample paths -> KDE Dist."""
    global _sundial
    try:
        import torch
        from transformers import AutoModelForCausalLM
        if _sundial is None:
            _sundial = AutoModelForCausalLM.from_pretrained(
                "thuml/sundial-base-128m", trust_remote_code=True).to(DEVICE).eval()
        ctx = fs._ctx_batch(ch if h == 1 else ch[:len(ch) - (h - 1)]).to(DEVICE)
        n_samples = int(os.environ.get("FM_SAMPLES", 30))
        with torch.no_grad():
            out = _sundial.generate(ctx, num_samples=n_samples, max_new_tokens=h)
        s = out[:, :, h - 1].float().cpu().numpy()         # [TEST, n_samples] at horizon h
        return [fs.sample_dist(s[i]) for i in range(len(s))]
    except Exception as e:                                 # noqa: BLE001
        print(f"  sundial failed: {e}", flush=True); return None


_tirex = None
def tirex_dists(ch, h=1):
    """TiRex (NX-AI, 35M xLSTM): 9-quantile head -> smoothed-mixture Dist. CPU
    backend='torch' (no CUDA kernel on this box)."""
    global _tirex
    try:
        import torch
        from tirex import load_model
        if _tirex is None:
            _tirex = load_model("NX-AI/TiRex", device=DEVICE, backend="torch")
        ctx = fs._ctx_batch(ch if h == 1 else ch[:len(ch) - (h - 1)])   # [TEST, CTX]
        q, _mean = _tirex.forecast(context=ctx, prediction_length=h,
                                   output_type="numpy")     # q: [TEST, h, 9]
        q = np.asarray(q)[:, h - 1, :]                       # horizon h
        return [fs.quantile_dist(LEVELS9, q[i]) for i in range(len(q))]
    except Exception as e:                                 # noqa: BLE001
        print(f"  tirex failed: {e}", flush=True); return None


_flowstate = None
def flowstate_dists(ch, h=1):
    """flowstate (IBM research checkpoint, SSM + functional-basis decoder):
    9-quantile output -> smoothed-mixture Dist."""
    global _flowstate
    try:
        import torch
        from tsfm_public.models.flowstate import FlowStateForPrediction
        if _flowstate is None:
            _flowstate = FlowStateForPrediction.from_pretrained(
                "ibm-research/flowstate", revision="r1.1").to(DEVICE).eval()
        src = ch if h == 1 else ch[:len(ch) - (h - 1)]
        ctx = fs._ctx_batch(src).to(DEVICE).unsqueeze(-1)  # [TEST, CTX, 1]
        with torch.no_grad():
            out = _flowstate(past_values=ctx, prediction_length=h)
        q = out.quantile_outputs.float().cpu().numpy()     # [TEST, 9, h, 1]
        q = q[:, :, h - 1, 0]                              # [TEST, 9] at horizon h
        return [fs.quantile_dist(LEVELS9, q[i]) for i in range(len(q))]
    except Exception as e:                                 # noqa: BLE001
        print(f"  flowstate failed: {e}", flush=True); return None


_tabpfn = None
def tabpfn_dists(ch, h=1):
    """TabPFN-TS (Prior Labs, in-context Bayesian): 9-quantile head -> Dist.
    Needs TABPFN_TOKEN (one-time license acceptance) for LOCAL weights; runs
    offline thereafter. Built with PriorLabs-TabPFN. One-step only for now."""
    if h != 1:
        print("  tabpfn: multi-horizon not implemented; skipping", flush=True)
        return None
    global _tabpfn
    try:
        import pandas as pd
        from tabpfn_time_series import (TabPFNTSPipeline, TabPFNMode,
                                        TimeSeriesDataFrame)
        from tabpfn_time_series.features import RunningIndexFeature
        if _tabpfn is None:
            _tabpfn = TabPFNTSPipeline(tabpfn_mode=TabPFNMode.LOCAL,
                                       temporal_features=[RunningIndexFeature()])
        n = len(ch); start = n - TEST
        base = pd.Timestamp("2000-01-01")
        crows, frows = [], []
        for k, t in enumerate(range(start, n)):
            win = ch[t - CTX:t]
            ts = pd.date_range(base, periods=CTX, freq="D")
            crows.extend((f"w{k}", ts[j], float(win[j])) for j in range(CTX))
            frows.append((f"w{k}", ts[-1] + pd.Timedelta(days=1), float("nan")))
        cdf = TimeSeriesDataFrame(pd.DataFrame(
            crows, columns=["item_id", "timestamp", "target"]
        ).set_index(["item_id", "timestamp"]))
        fdf = TimeSeriesDataFrame(pd.DataFrame(
            frows, columns=["item_id", "timestamp", "target"]
        ).set_index(["item_id", "timestamp"]))
        pred = _tabpfn.predict(cdf, fdf, quantiles=LEVELS9)
        qcols = [c for c in pred.columns if str(c).replace(".", "").isdigit()
                 or c in LEVELS9]
        out = [None] * TEST
        for k in range(TEST):
            row = pred.loc[f"w{k}"]
            vals = [float(row[c].iloc[0]) for c in LEVELS9]
            out[k] = fs.quantile_dist(LEVELS9, vals)
        return out
    except Exception as e:                                 # noqa: BLE001
        print(f"  tabpfn failed: {e}", flush=True); return None


# ------------------------------------------------------------------ calibration sandwich
# The coverage table showed the foundation models are sharp but OVER-CONFIDENT
# (90% intervals cover ~0.66-0.86), while laplace is well-calibrated (~0.90). So
# recalibrate the model with laplace by averaging their predictive QUANTILE
# functions per step (Vincentization): this widens the over-tight model intervals
# toward laplace's calibrated spread while keeping the model's center/shape where
# it is sharper (seasonal). Both sub-predictives are computed on the identical
# window in the model's own venv (laplace is pure-skaters). The combined Dist is
# rebuilt from the averaged quantiles via the same quantile_dist helper.
_VLEVELS = [0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98]


def vincentize(dists_a, dists_b):
    """Per-step quantile-averaged combination of two per-step Dist lists."""
    if dists_a is None or dists_b is None:
        return None
    out = []
    for da, db in zip(dists_a, dists_b):
        qa = np.array([da.quantile(p) for p in _VLEVELS])
        qb = np.array([db.quantile(p) for p in _VLEVELS])
        out.append(fs.quantile_dist(_VLEVELS, 0.5 * (qa + qb)))
    return out


def _sandwich(fm_fn, h=1):
    """Arm = quantile-average of a foundation model with laplace, same window."""
    def run(ch):
        return vincentize(fm_fn(ch, h), laplace_dists(ch, h))
    return run


# ------------------------------------------------------------------ adaptive residual sandwich
# The static blend borrows laplace's AVERAGE width; it can't track calibration
# that waxes and wanes. This instead uses the FM only for LOCATION and lets
# laplace model the residual (y - FM_median) online: laplace's scale adapts to
# volatility clustering and its GPD tails are calibrated, so the interval width
# breathes with the conditional uncertainty. The FM is run over an extended
# window (target + warmup) so laplace has residual history and the scored steps
# still align exactly with every other arm's last TEST steps.
_RESID_WARM = int(os.environ.get("FM_RESID_WARM", "128"))


def _resid_sandwich(fm_fn, h=1):
    """Arm = FM location + laplace on the FM residual stream (adaptive scale)."""
    def run(ch):
        target = TEST                       # stable scored-window length
        old = fs.TEST
        try:
            fs.TEST = target + _RESID_WARM  # FM forecasts the extended window
            fmx = fm_fn(ch, h)
        finally:
            fs.TEST = old
        if fmx is None or len(fmx) < target + _RESID_WARM:
            return None
        locs = [d.quantile(0.5) for d in fmx]
        ext = len(ch) - (target + _RESID_WARM)
        resid = [ch[ext + i] - locs[i] for i in range(len(locs))]
        f = laplace(1); st = None; pend = None; out = []
        for i, rt in enumerate(resid):
            if pend is not None and i >= _RESID_WARM:
                base = pend[0]; loc = locs[i]
                out.append(fs.quantile_dist(_VLEVELS,
                                            [loc + base.quantile(p) for p in _VLEVELS]))
            d, st = f(rt, st); pend = d
        return out
    return run


# ------------------------------------------------------------------ PIT recalibration sandwich
# Keep the FM's FULL predictive (scale and shape), fix only its calibration.
# Transform the observation through the FM's own CDF into normal-score space,
#   z_t = Phi^{-1}(F_t(y_t)),
# which is iid N(0,1) exactly when the FM is calibrated. Let laplace predict that
# z-series (its home turf) -> predictive G_t for z_t. Invert back through the FM
# CDF: the recalibrated p-quantile of y is F_t^{-1}(Phi(G_t^{-1}(p))). If the FM
# is calibrated, laplace learns z~N(0,1) and this passes the FM through unchanged;
# where the FM is over-confident, laplace's wider z-predictive widens it; when the
# miscalibration waxes and wanes, laplace's online scale tracks it. This is the
# "take their CDF, predict in the middle, go back" sandwich.
_PITLEVELS = [0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5,
              0.6, 0.7, 0.8, 0.9, 0.95, 0.975, 0.99]


def pit_sandwich(fm_fn, h=1):
    """Arm = laplace recalibration of the FM in its own PIT/normal-score space."""
    def run(ch):
        target = TEST
        old = fs.TEST
        try:
            fs.TEST = target + _RESID_WARM
            fmx = fm_fn(ch, h)
        finally:
            fs.TEST = old
        if fmx is None or len(fmx) < target + _RESID_WARM:
            return None
        ext = len(ch) - (target + _RESID_WARM)
        f = laplace(1); st = None; pend = None; out = []
        for i, fd in enumerate(fmx):
            yt = ch[ext + i]
            if pend is not None and i >= _RESID_WARM:
                G = pend
                yq = [fd.quantile(min(max(_ncdf(G.quantile(p)), 1e-6), 1 - 1e-6))
                      for p in _PITLEVELS]
                yq = list(np.maximum.accumulate(yq))     # numerical monotonicity
                out.append(fs.quantile_dist(_PITLEVELS, yq))
            u = min(max(fd.cdf(yt), 1e-6), 1 - 1e-6)
            d, st = f(_nppf(u), st); pend = d[0]
        return out
    return run


# ------------------------------------------------------------------ never-worse portfolio
# laplace's trunk combines candidates by their MEANS only (the leaf re-supplies
# scale), so an FM added there would lose its shape again. To keep the FM's full
# distribution AND make laplace strictly-not-worse, combine at the DISTRIBUTION
# level: a long-only online portfolio of {plain laplace, PIT-recalibrated FM},
# weights updated by each component's realized log-score (geometric forgetting).
# Because plain laplace is always a component, the portfolio converges to it
# wherever the FM adds nothing, and tilts toward the FM where it helps.
def mix_dists(dists, w):
    """Weighted-CDF mixture of arbitrary Dists (works for SplicedDist too, which
    exposes cdf/quantile but not .components), rebuilt as a quantile_dist on the
    standard grid. F_mix(y) = sum_i w_i F_i(y); invert per level by bisection."""
    lo = min(d.quantile(0.001) for d in dists)
    hi = max(d.quantile(0.999) for d in dists)
    if not (hi > lo):
        hi = lo + 1e-9
    qs = []
    for p in _PITLEVELS:
        a, b = lo, hi
        for _ in range(40):
            mid = 0.5 * (a + b)
            if sum(wi * d.cdf(mid) for wi, d in zip(w, dists)) < p:
                a = mid
            else:
                b = mid
        qs.append(0.5 * (a + b))
    return fs.quantile_dist(_PITLEVELS, list(np.maximum.accumulate(qs)))


_LAP_PRIOR = float(os.environ.get("PORT_LAP_PRIOR", "2.0"))


def portfolio_sandwich(fm_fn, forget=0.98, eta=0.8, lap_prior=None, h=1):
    """Arm = distribution-level long-only log-score portfolio of laplace and the
    PIT-recalibrated FM. laplace is the trusted incumbent: the weights start
    tilted to it (``lap_prior`` log-units) so the FM must EARN weight through
    realized log-score before it shifts the blend. This removes the finite-window
    drag on strata where laplace dominates (e.g. daily:econ) while still letting
    a genuinely-better FM take over fast (seasonal). Never worse than plain
    laplace in the limit; near-never-worse in the window with the prior."""
    pit = pit_sandwich(fm_fn, h)
    prior = _LAP_PRIOR if lap_prior is None else lap_prior

    def run(ch):
        lap = laplace_dists(ch, h)
        rec = pit(ch)
        if rec is None or len(lap) != len(rec):
            return None
        y = ch[len(ch) - TEST:]
        lw = [prior, 0.0]; out = []
        for i in range(len(lap)):
            m = max(lw); w = [math.exp(x - m) for x in lw]; tot = sum(w)
            w = [x / tot for x in w]
            out.append(mix_dists([lap[i], rec[i]], w))       # predict y[i] from y[<i]
            for j, d in enumerate((lap[i], rec[i])):          # then learn from y[i]
                lp = d.logpdf(float(y[i]))
                lp = 20.0 if lp > 20.0 else (-20.0 if not (lp >= -20.0) else lp)
                lw[j] = forget * lw[j] + eta * lp
        return out
    return run


# Foundation registry (Chronos / TimesFM reused from foundation_study). The
# "+lap" arms are the laplace-calibrated sandwiches of the sharp quantile models.
# make_registry(h) builds the same roster at forecast horizon h (h=1 = the
# canonical one-step study). Every adapter and sandwich takes an h that defaults
# to 1, so REGISTRY (h=1) is byte-for-byte the original behaviour.
def make_registry(h=1):
    return {
        "laplace":     lambda ch: laplace_dists(ch, h),
        "Sundial":     lambda ch: sundial_dists(ch, h),
        "TiRex":       lambda ch: tirex_dists(ch, h),
        "flowstate":   lambda ch: flowstate_dists(ch, h),
        "TabPFN":      lambda ch: tabpfn_dists(ch, h),
        "Chronos":     lambda ch: fs.chronos_dists(ch, h),
        "TimesFM":     lambda ch: fs.timesfm_dists(ch, h),
        "TimesFM+lap": _sandwich(fs.timesfm_dists, h),
        "TiRex+lap":   _sandwich(tirex_dists, h),
        "Chronos+lap": _sandwich(fs.chronos_dists, h),
        # adaptive: FM location + laplace conditional scale/tails on the residual
        "TimesFM~lap": _resid_sandwich(fs.timesfm_dists, h),
        "TiRex~lap":   _resid_sandwich(tirex_dists, h),
        "Chronos~lap": _resid_sandwich(fs.chronos_dists, h),
        # PIT recalibration: laplace predicts in the FM's own CDF space, then inverts
        "TimesFM@lap": pit_sandwich(fs.timesfm_dists, h),
        "TiRex@lap":   pit_sandwich(tirex_dists, h),
        "Chronos@lap": pit_sandwich(fs.chronos_dists, h),
        # never-worse portfolio: laplace + PIT-recalibrated FM, online log-score blend
        "TimesFM&lap": portfolio_sandwich(fs.timesfm_dists, h=h),
        "TiRex&lap":   portfolio_sandwich(tirex_dists, h=h),
        "Chronos&lap": portfolio_sandwich(fs.chronos_dists, h=h),
    }


REGISTRY = make_registry(1)
