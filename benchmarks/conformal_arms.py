"""Conformal methods for time series, as benchmark arms.

Two kinds of arm, both scored through run_arm.py like every other arm.

1. Wrappers on a base forecaster (laplace, AutoARIMA). The base issues a full
   predictive F_t for each step; its probability integral transform
   u_t = F_t(y_t) is the nonconformity score. At every step the wrapper picks,
   for each target level tau on a 21-point grid, an adjusted level a_t(tau) from
   the scores seen so far, and issues the quantile F_t^{-1}(a_t(tau)). The 21
   quantiles become a density by the same generous reconstruction the
   foundation models get (nozzles.nozzle_wide). Methods:

     id     a = tau. No calibration: isolates what the reconstruction costs.
     roll   a = the tau-quantile of the last CAL scores (split conformal on a
            rolling calibration window).
     nexcp  the same with geometric weights rho^age (Barber, Candes, Ramdas and
            Tibshirani 2023, weighted conformal beyond exchangeability).
     aci    a_{t+1} = a_t + gamma (tau - 1{u_t <= a_t}) (Gibbs and Candes 2021,
            adaptive conformal inference, one tracker per level).
     pid    aci plus an integral term on the running coverage error with a
            tanh saturation (after Angelopoulos, Candes and Tibshirani 2023,
            conformal PID control; no scorecaster).

   The wrappers see CAL steps of base forecasts before the TEST window, online:
   every adjustment uses only scores already observed.

2. Vovk's histogram predictive system (Vovk, "Universally consistent
   predictive distributions", arXiv:1708.01902; Pattern Recognition 2022).
   The predictor is the previous change, standardized by the history's median
   and MAD; the line is cut into cells of width h_n, a power of two with
   h_n -> 0 and n h_n -> infinity (here h_n ~ 2 n^{-1/3}); the predictive
   distribution is the empirical distribution of the responses whose predictor
   fell in the same cell (the trivial conformity measure under the histogram
   taxonomy). Deviation, stated: a cell with fewer than MIN_CELL responses is
   widened by doubling until it has them, and the step CDF is read at the 21
   levels (Hill-type positions) and reconstructed like the wrappers.
   Universal consistency is an IID result; a time series is not IID.
"""
from __future__ import annotations

import math

import numpy as np

import foundation_study as fs
from nozzles import nozzle_wide

TEST = fs.TEST
CAL = 128
LEVELS = np.array([0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5,
                   0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99])
A_MIN, A_MAX = 1e-9, 1.0 - 1e-9     # the extreme levels a quantile is read at
GAMMA = 0.02          # ACI step
RHO = 0.99            # nexcp weight decay per step
KI, CSAT = 0.02, 4.0  # pid integral gain and saturation scale
MIN_CELL = 8          # histogram system: minimum responses per cell


def _weighted_quantile(x, w, p):
    o = np.argsort(x)
    x, w = x[o], w[o]
    c = np.cumsum(w) / w.sum()
    return np.interp(p, c, x)


class _Levels:
    """Adjusted levels a_t(tau) for one method, updated online by scores u_t."""

    def __init__(self, method):
        self.method = method
        self.u = []
        self.a = LEVELS.copy()
        self.integ = np.zeros_like(LEVELS)

    def levels(self):
        if self.method in ("aci", "pid"):
            return self.a.copy()
        if self.method == "id" or not self.u:
            return LEVELS.copy()
        u = np.asarray(self.u[-CAL:])
        if self.method == "roll":
            n = len(u)
            # finite-sample split-conformal positions: tau (n+1)/n, clipped
            return np.quantile(u, np.clip(LEVELS * (n + 1) / n, 0.0, 1.0))
        if self.method == "nexcp":
            age = np.arange(len(u))[::-1]
            return _weighted_quantile(u, RHO ** age, LEVELS)
        raise ValueError(f"unknown method {self.method!r}")

    def update(self, ut):
        self.u.append(ut)
        if self.method in ("aci", "pid"):
            err = (ut <= self.a).astype(float)          # 1 when y fell at or below the issued quantile
            self.a = self.a + GAMMA * (LEVELS - err)
            if self.method == "pid":
                self.integ += LEVELS - err
                t = len(self.u)
                self.a = self.a + KI * np.tanh(self.integ / (CSAT * math.sqrt(t)))
            # a is NOT clipped: the coverage guarantee needs it free to pass 0 or 1
            # (an infinite quantile); _issue clips only the level it reads


def _issue(d, a):
    a = np.clip(np.sort(a), A_MIN, A_MAX)
    q = np.array([d.quantile(float(x)) for x in a])
    q = np.maximum.accumulate(q)                         # quantiles never cross
    return nozzle_wide(LEVELS, q)


def wrap(base_dists, ys, method):
    """Conformal wrapper over a base's per-step predictives.

    base_dists[i] is the predictive for ys[i]; the last TEST of them are the
    scored steps, the earlier ones are calibration only. Returns TEST Dists.
    """
    n = len(base_dists)
    if n < TEST or len(ys) != n:
        return None
    lv = _Levels(method)
    out = []
    for i, (d, y) in enumerate(zip(base_dists, ys)):
        if i >= n - TEST:
            out.append(_issue(d, lv.levels()))
        lv.update(min(max(float(d.cdf(y)), 1e-9), 1.0 - 1e-9))
    return out


_memo = {}


def _base(kind, ch, k):
    """One base run per (kind, series): the five wrappers share it."""
    import hashlib
    import arm_adapters as aa
    sh = hashlib.sha1(np.asarray(ch, float).tobytes()).hexdigest()
    key = (kind, k, sh)
    if key not in _memo:
        if any(x[2] != sh for x in _memo):            # a new series: forget the last one
            _memo.clear()
        _memo[key] =(aa.laplace_dists(ch, 1, nsteps=k) if kind == "laplace"
                      else aa.statsforecast_dists(ch, 1, "AutoARIMA", nsteps=k))
    return _memo[key]


def _cal_steps(ch):
    return int(min(CAL + TEST, len(ch) - 60))


def laplace_wrapped(ch, method, h=1):
    if h != 1:
        return None
    k = _cal_steps(ch)
    base = _base("laplace", ch, k)
    return wrap(base, [float(v) for v in ch[-k:]], method)


def arima_wrapped(ch, method, h=1):
    if h != 1:
        return None
    k = _cal_steps(ch)
    base = _base("arima", ch, k)
    if base is None:
        return None
    return wrap(base, [float(v) for v in ch[-k:]], method)


def histogram_dists(ch, h=1, hist=1000):
    """Vovk's histogram predictive system on (previous change -> next change)."""
    if h != 1:
        return None
    y = np.asarray(ch, float)[-(hist + TEST + 1):]
    out = []
    for t in range(len(y) - TEST, len(y)):
        past = y[:t]
        x, r = past[:-1], past[1:]                       # predictor, response pairs
        med = np.median(past)
        mad = np.median(np.abs(past - med)) * 1.4826
        s = mad if mad > 0 else (np.std(past) if np.std(past) > 0 else 1.0)
        z, z0 = (x - med) / s, (y[t - 1] - med) / s
        n = len(r)
        hn = 2.0 ** round(math.log2(2.0 * n ** (-1.0 / 3.0)))
        while True:
            k = math.floor(z0 / hn)
            sel = r[(np.floor(z / hn) == k)]
            if len(sel) >= MIN_CELL or hn > 64:
                break
            hn *= 2.0
        if len(sel) < 2:
            sel = r
        srt = np.sort(sel)
        m = len(srt)
        pos = LEVELS * (m + 1) - 1                       # Hill-type positions on the order statistics
        q = np.interp(pos, np.arange(m), srt)
        q = np.maximum.accumulate(q)
        out.append(nozzle_wide(LEVELS, q))
    return out


def registry(h=1):
    arms = {}
    for m in ("id", "roll", "nexcp", "aci", "pid"):
        arms[f"laplace+{m}"] = lambda ch, m=m: laplace_wrapped(ch, m, h)
        arms[f"AutoARIMA+{m}"] = lambda ch, m=m: arima_wrapped(ch, m, h)
    arms["vovk-hist"] = lambda ch: histogram_dists(ch, h)
    return arms
