"""Conformal methods for time series, as benchmark arms.

Two kinds of arm, both scored through run_arm.py like every other arm.

1. Wrappers on a base forecaster (laplace, AutoARIMA). The base issues a full
   predictive F_t for each step; its probability integral transform
   u_t = F_t(y_t) is the nonconformity score. At every step the wrapper picks,
   for each target level tau on a 21-point grid, an adjusted level a_t(tau) from
   the scores seen so far. The issued predictive is F_t pushed through the
   monotone map A_t (piecewise linear through the (tau, a_t(tau)) knots):
   G_t = A_t^{-1}(F_t). Its tau-quantile is F_t's a_t(tau)-quantile, it keeps
   F_t's shape between knots, and there is no reconstruction from quantiles
   (an earlier version rebuilt a density from 21 quantiles: the smoothing
   undid the calibration, and coinciding quantiles on sticky series made
   density spikes worth several nats). Methods:

     id     a = tau, so G = F exactly: the base itself, a check.
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
   taxonomy). Deviations, stated: a cell with fewer than MIN_CELL responses is
   widened by doubling until it has them, and the step CDF is smoothed by a
   Gaussian kernel (Silverman's bandwidth, floored at BW_FLOOR of the history's
   robust scale) so it has a density to score. On series that repeat values
   any such density spikes, so log-score comparisons should be read on the
   continuous series; CRPS and coverage hold on all of them.
   Universal consistency is an IID result; a time series is not IID.
"""
from __future__ import annotations

import math

import numpy as np

import foundation_study as fs
from skaters.dist import Dist

TEST = fs.TEST
CAL = 128
LEVELS = np.array([0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5,
                   0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99])
A_MIN, A_MAX = 1e-9, 1.0 - 1e-9     # the extreme levels a quantile is read at
GAMMA = 0.02          # ACI step
RHO = 0.99            # nexcp weight decay per step
KI, CSAT = 0.02, 4.0  # pid integral gain and saturation scale
MIN_CELL = 8          # histogram system: minimum responses per cell
BW_FLOOR = 0.05       # histogram system: kernel bandwidth floor, in units of the history's robust scale


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


_PGRID = (np.arange(400) + 0.5) / 400                    # midpoints for quantile integrals


class Recalibrated:
    """The base predictive F pushed through a monotone level map: G = A^{-1}(F).

    A is piecewise linear through (0,0), (tau_i, a_i), (1,1): the wrapper's
    choice of base level a_i for target level tau_i. G keeps F's shape between
    knots (so laplace's own treatment of repeated values carries over), its
    tau_i-quantile is F's a_i-quantile exactly, and with a = tau it IS F.
    Density g(y) = f(y) / A'(G(y)).
    """

    def __init__(self, base, a):
        a = np.clip(np.asarray(a, float), A_MIN, A_MAX)
        a = np.maximum.accumulate(a)
        a = a + np.arange(len(a)) * 1e-12                # strictly increasing
        self.base = base
        self.tk = np.concatenate([[0.0], LEVELS, [1.0]])
        self.ak = np.concatenate([[0.0], a, [1.0]])
        self.ak = np.maximum.accumulate(np.minimum(self.ak, 1.0))
        self._q = None

    def _A(self, p):
        return np.interp(p, self.tk, self.ak)

    def _Ainv(self, u):
        return np.interp(u, self.ak, self.tk)

    def cdf(self, x):
        return float(self._Ainv(float(self.base.cdf(x))))

    def logpdf(self, x):
        u = float(self.base.cdf(x))
        j = int(np.clip(np.searchsorted(self.ak, u, side="right") - 1, 0, len(self.ak) - 2))
        slope = (self.ak[j + 1] - self.ak[j]) / (self.tk[j + 1] - self.tk[j])
        return float(self.base.logpdf(x)) - math.log(max(slope, 1e-300))

    def quantile(self, p):
        return float(self.base.quantile(float(np.clip(self._A(p), A_MIN, A_MAX))))

    def _qgrid(self):
        if self._q is None:
            self._q = np.maximum.accumulate(np.array([self.quantile(p) for p in _PGRID]))
        return self._q

    def crps(self, y):
        q = self._qgrid()
        return float(2.0 * np.mean(((y < q).astype(float) - _PGRID) * (q - y)))

    @property
    def mean(self):
        return float(np.mean(self._qgrid()))

    @property
    def std(self):
        return float(np.std(self._qgrid()))


def _issue(d, a):
    return Recalibrated(d, np.sort(a))


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
        # the cell's empirical distribution, kernel-smoothed: Silverman's bandwidth,
        # floored at BW_FLOOR of the history's robust scale so repeated values do
        # not become arbitrarily sharp spikes
        m = len(sel)
        sd = float(np.std(sel))
        iqr = float(np.subtract(*np.percentile(sel, [75, 25]))) / 1.349
        spread = min(sd, iqr) if min(sd, iqr) > 0 else max(sd, iqr)
        bw = max(0.9 * spread * m ** (-0.2), BW_FLOOR * s)
        out.append(Dist([(1.0 / m, float(v), bw) for v in sel]))
    return out


def registry(h=1):
    arms = {}
    for m in ("id", "roll", "nexcp", "aci", "pid"):
        arms[f"laplace+{m}"] = lambda ch, m=m: laplace_wrapped(ch, m, h)
        arms[f"AutoARIMA+{m}"] = lambda ch, m=m: arima_wrapped(ch, m, h)
    arms["vovk-hist"] = lambda ch: histogram_dists(ch, h)
    return arms
