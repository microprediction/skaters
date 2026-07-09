"""GPD tail splice: the conditional tail fit, in the predictive itself.

The parade z of a well-tuned body is honest in the bulk and too thin in the
tails (the calibration panel measured ~8x the promised alarm rate at 1e-3 on
non-price FRED; repairing it was worth +0.022 nats/tick of held-out
log-likelihood on 96% of series — benchmarks/anomaly/RESULTS.md sections 5-6).
This module repairs the predictive at the source.

Construction (the two-skater picture, packaged): the body defines a
predictable tail region — the parade z of horizon m beyond thresholds frozen
at warm-up quantiles. A trailing tail model fits a generalized Pareto to the
exceedances per side by censored maximum likelihood (Grimshaw profile; the
censored likelihood factorizes into the empirical exceedance rate plus the
conditional GPD density). Each issued predictive is then *spliced*: body
density in the interior (rescaled so mass is exact), GPD beyond.

Information flows body -> region -> tail -> output, never backwards: the
body's updates never see the tail's opinion, so z keeps its meaning and the
conditional fit keeps its "given the body's forecast" reading. Any
region-weighted *evaluation* (CSL league tables) must still use a reference
region exogenous to all contestants — that rule lives in the harness, not
here; the spliced predictive itself is scored by plain log-likelihood, which
is proper for any density however assembled.

All state is pure data. Pure stdlib. Mirrored in the JS twin (tails.mjs).
"""

from __future__ import annotations
import math

_EPS = 1e-12                     # PIT clamp, as in parade.py
_LOG_SQRT2PI = 0.5 * math.log(2.0 * math.pi)
_REFIT_EVERY = 25


# ---------------------------------------------------------------------------
# standard normal helpers (Acklam inverse: deterministic, JS-portable)
# ---------------------------------------------------------------------------

def _phi(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def _phi_logpdf(z: float) -> float:
    return -0.5 * z * z - _LOG_SQRT2PI


_ACK_A = (-3.969683028665376e+01, 2.209460984245205e+02,
          -2.759285104469687e+02, 1.383577518672690e+02,
          -3.066479806614716e+01, 2.506628277459239e+00)
_ACK_B = (-5.447609879822406e+01, 1.615858368580409e+02,
          -1.556989798598866e+02, 6.680131188771972e+01,
          -1.328068155288572e+01)
_ACK_C = (-7.784894002430293e-03, -3.223964580411365e-01,
          -2.400758277161838e+00, -2.549732539343734e+00,
          4.374664141464968e+00, 2.938163982698783e+00)
_ACK_D = (7.784695709041462e-03, 3.224671290700398e-01,
          2.445134137142996e+00, 3.754408661907416e+00)


def _phi_inv(p: float) -> float:
    """Acklam's rational approximation to the standard normal quantile,
    polished with one Halley step (relative error < 1e-13)."""
    p = min(max(p, _EPS), 1.0 - _EPS)
    if p < 0.02425:
        q = math.sqrt(-2.0 * math.log(p))
        x = ((((((_ACK_C[0] * q + _ACK_C[1]) * q + _ACK_C[2]) * q
                + _ACK_C[3]) * q + _ACK_C[4]) * q + _ACK_C[5])
             / ((((_ACK_D[0] * q + _ACK_D[1]) * q + _ACK_D[2]) * q
                 + _ACK_D[3]) * q + 1.0))
    elif p <= 0.97575:
        q = p - 0.5
        r = q * q
        x = ((((((_ACK_A[0] * r + _ACK_A[1]) * r + _ACK_A[2]) * r
                + _ACK_A[3]) * r + _ACK_A[4]) * r + _ACK_A[5]) * q
             / (((((_ACK_B[0] * r + _ACK_B[1]) * r + _ACK_B[2]) * r
                  + _ACK_B[3]) * r + _ACK_B[4]) * r + 1.0))
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        x = -((((((_ACK_C[0] * q + _ACK_C[1]) * q + _ACK_C[2]) * q
                 + _ACK_C[3]) * q + _ACK_C[4]) * q + _ACK_C[5])
              / ((((_ACK_D[0] * q + _ACK_D[1]) * q + _ACK_D[2]) * q
                  + _ACK_D[3]) * q + 1.0))
    e = _phi(x) - p
    u = e * math.sqrt(2.0 * math.pi) * math.exp(0.5 * x * x)
    return x - u / (1.0 + 0.5 * x * u)


# ---------------------------------------------------------------------------
# GPD helpers
# ---------------------------------------------------------------------------

def _gpd_logpdf(e: float, gamma: float, sigma: float) -> float:
    if abs(gamma) < 1e-9:
        return -math.log(sigma) - e / sigma
    arg = 1.0 + gamma * e / sigma
    if arg <= 0.0:
        return -745.0
    return -math.log(sigma) - (1.0 / gamma + 1.0) * math.log(arg)


def _gpd_sf(e: float, gamma: float, sigma: float) -> float:
    if e <= 0.0:
        return 1.0
    if abs(gamma) < 1e-9:
        return math.exp(-e / sigma)
    arg = 1.0 + gamma * e / sigma
    if arg <= 0.0:
        return 0.0
    return arg ** (-1.0 / gamma)


def _gpd_isf(p: float, gamma: float, sigma: float) -> float:
    """Excess e with survival probability p (inverse of _gpd_sf)."""
    p = min(max(p, 1e-300), 1.0)
    if abs(gamma) < 1e-9:
        return -sigma * math.log(p)
    return sigma / gamma * (p ** (-gamma) - 1.0)


_TAU_GRID = (0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0, 3.0,
             5.0, 8.0)


def _fit_ml(exc: list, s1: float) -> tuple:
    """Censored-ML GPD fit (Grimshaw profile over a fixed tau grid).

    Given tau = gamma/sigma the profile MLE is gamma_hat(tau) = mean
    log(1 + tau*e); the grid is deterministic so Python and JS agree
    bit-for-bit given the same window.
    """
    n = len(exc)
    emean = s1 / n
    if n < 20 or emean <= 0.0:
        return 0.0, max(emean, 1e-12)
    emax = max(exc)
    best_g, best_s, best_ll = 0.0, max(emean, 1e-12), -1e300
    taus = [t / emean for t in _TAU_GRID]
    taus.extend((-0.5 / emax, -0.25 / emax, -0.1 / emax))
    for tau in taus:
        if tau <= -1.0 / emax or abs(tau) < 1e-12:
            continue
        g = 0.0
        for e in exc:
            g += math.log1p(tau * e)
        g /= n
        if g <= 1e-9:
            continue
        sigma = g / tau
        if sigma <= 0.0:
            continue
        ll = -n * math.log(sigma) - (1.0 + 1.0 / g) * n * g
        if ll > best_ll:
            best_ll, best_g, best_s = ll, g, sigma
    return best_g, best_s


# ---------------------------------------------------------------------------
# the spliced predictive
# ---------------------------------------------------------------------------

class SplicedDist:
    """A body Dist with GPD tails spliced in beyond frozen z-thresholds.

    The splice lives in the body's own PIT space pushed through the standard
    normal: with u = body.cdf(y) and z = Phi^-1(u),

        F(y) = zeta_lo * SF_gpd(t_lo - z)                       z <  t_lo
        F(y) = zeta_lo + c * (Phi(z) - Phi(t_lo))               interior
        F(y) = 1 - zeta_up * SF_gpd(z - t_up)                   z >  t_up

    with c chosen so total mass is exactly 1. Interior density is just
    c * body.pdf(y); tail densities carry the GPD/phi ratio. ``quantile`` is
    exact (inverts the splice, then defers to the body); ``crps``, ``mean``
    and ``var`` are numeric (trapezoid over a quantile grid) — unlike the
    Gaussian-mixture closed forms, tails this heavy have no such luxury.
    """

    __slots__ = ("body", "t_lo", "t_up", "zeta_lo", "zeta_up",
                 "g_lo", "s_lo", "g_up", "s_up", "_c", "_plo", "_pup")

    def __init__(self, body, t_lo, t_up, zeta_lo, zeta_up,
                 g_lo, s_lo, g_up, s_up):
        self.body = body
        self.t_lo, self.t_up = t_lo, t_up
        self.zeta_lo, self.zeta_up = zeta_lo, zeta_up
        self.g_lo, self.s_lo = g_lo, s_lo
        self.g_up, self.s_up = g_up, s_up
        self._plo, self._pup = _phi(t_lo), _phi(t_up)
        interior = max(self._pup - self._plo, 1e-12)
        self._c = max(1.0 - zeta_lo - zeta_up, 1e-12) / interior

    def _z(self, x: float) -> float:
        u = min(max(self.body.cdf(x), _EPS), 1.0 - _EPS)
        return _phi_inv(u)

    def cdf(self, x: float) -> float:
        z = self._z(x)
        if z < self.t_lo:
            return self.zeta_lo * _gpd_sf(self.t_lo - z, self.g_lo, self.s_lo)
        if z > self.t_up:
            return 1.0 - self.zeta_up * _gpd_sf(z - self.t_up,
                                                self.g_up, self.s_up)
        return self.zeta_lo + self._c * (_phi(z) - self._plo)

    def logpdf(self, x: float) -> float:
        base = self.body.logpdf(x)
        if not math.isfinite(base):
            return base
        z = self._z(x)
        if z < self.t_lo:
            corr = (math.log(max(self.zeta_lo, 1e-300))
                    + _gpd_logpdf(self.t_lo - z, self.g_lo, self.s_lo)
                    - _phi_logpdf(z))
        elif z > self.t_up:
            corr = (math.log(max(self.zeta_up, 1e-300))
                    + _gpd_logpdf(z - self.t_up, self.g_up, self.s_up)
                    - _phi_logpdf(z))
        else:
            corr = math.log(self._c)
        return base + corr

    def pdf(self, x: float) -> float:
        lp = self.logpdf(x)
        return math.exp(lp) if lp < 700.0 else math.inf

    def quantile(self, p: float, tol: float = 1e-9,
                 max_iter: int = 100) -> float:
        assert 0 < p < 1
        if p < self.zeta_lo:
            z = self.t_lo - _gpd_isf(p / self.zeta_lo, self.g_lo, self.s_lo)
        elif p > 1.0 - self.zeta_up:
            z = self.t_up + _gpd_isf((1.0 - p) / self.zeta_up,
                                     self.g_up, self.s_up)
        else:
            u = self._plo + (p - self.zeta_lo) / self._c
            z = _phi_inv(min(max(u, _EPS), 1.0 - _EPS))
        ub = min(max(_phi(z), _EPS), 1.0 - _EPS)
        return self.body.quantile(ub, tol=tol, max_iter=max_iter)

    # numeric moments and CRPS over a fixed quantile grid (65 nodes)
    _GRID_N = 65

    def _qgrid(self) -> list:
        n = self._GRID_N
        return [self.quantile((i + 0.5) / n) for i in range(n)]

    @property
    def mean(self) -> float:
        q = self._qgrid()
        return sum(q) / len(q)

    @property
    def var(self) -> float:
        q = self._qgrid()
        m = sum(q) / len(q)
        return sum((x - m) * (x - m) for x in q) / len(q)

    @property
    def std(self) -> float:
        return math.sqrt(self.var)

    def crps(self, x: float) -> float:
        """CRPS = E|X - x| - 0.5 E|X - X'| via the quantile representation
        (E|X - X'| = 2 * integral of q(p)(2p - 1) dp), midpoint rule."""
        q = self._qgrid()
        n = len(q)
        t1 = sum(abs(v - x) for v in q) / n
        t2 = 2.0 * sum(v * (2.0 * (i + 0.5) / n - 1.0)
                       for i, v in enumerate(q)) / n
        return t1 - t2 * 0.5

    def to_dict(self) -> dict:
        return {"spliced": True, "body": self.body.to_dict(),
                "t_lo": self.t_lo, "t_up": self.t_up,
                "zeta_lo": self.zeta_lo, "zeta_up": self.zeta_up,
                "g_lo": self.g_lo, "s_lo": self.s_lo,
                "g_up": self.g_up, "s_up": self.s_up}

    def __repr__(self) -> str:
        return (f"SplicedDist(zeta=({self.zeta_lo:.4f},{self.zeta_up:.4f}), "
                f"gamma=({self.g_lo:.3f},{self.g_up:.3f}), body={self.body!r})")


# ---------------------------------------------------------------------------
# the wrapper
# ---------------------------------------------------------------------------

def _tail_new() -> dict:
    return {"t": None, "exc": [], "s1": 0.0, "nx": 0,
            "g": 0.0, "s": 1.0, "since": 0}


def _tail_add(tail: dict, e: float, nexc: int) -> None:
    tail["exc"].append(e)
    tail["s1"] += e
    tail["nx"] += 1
    if len(tail["exc"]) > nexc:
        tail["s1"] -= tail["exc"].pop(0)
    tail["since"] += 1
    # refit every add while the window is small (cheap), then every 25th
    if tail["since"] >= _REFIT_EVERY or len(tail["exc"]) <= 25:
        tail["g"], tail["s"] = _fit_ml(tail["exc"], tail["s1"])
        tail["since"] = 0


def gpdtails(base, k: int, level: float = 0.98, nexc: int = 500,
             warmup: int = 500):
    """Wrap a k-horizon skater so every issued predictive carries GPD tails.

    Per horizon: the body's own matured PIT (pushed through the standard
    normal) feeds a two-sided POT model — thresholds frozen at the ``level``
    warm-up quantiles, exceedances fitted by censored ML over the last
    ``nexc`` per side, exceedance rate empirical. Until a horizon's warm-up
    completes its dists pass through unchanged. Everything is strictly
    causal: this tick's dist is spliced with estimates from prior ticks only.
    """
    assert k >= 1
    assert 0.5 < level < 1.0
    assert nexc >= 50 and warmup >= 100

    def _skater(y: float, state: dict | None):
        if state is None:
            state = {"base": None, "pending": [],
                     "tails": [{"up": _tail_new(), "lo": _tail_new(),
                                "warm": [], "n": 0} for _ in range(k)]}
        # resolve arrivals against the BODY predictions made for them
        pend = state["pending"]
        n = len(pend)
        for m in range(1, k + 1):
            if m > n:
                continue
            d = pend[n - m][m - 1]
            u = d.cdf(y)
            if not math.isfinite(u):
                continue
            z = _phi_inv(min(max(u, _EPS), 1.0 - _EPS))
            th = state["tails"][m - 1]
            up, lo = th["up"], th["lo"]
            if up["t"] is None:
                th["warm"].append(z)
                if len(th["warm"]) >= warmup:
                    w = sorted(th["warm"])
                    iu = min(int(level * len(w)), len(w) - 1)
                    up["t"] = w[iu]
                    lo["t"] = w[len(w) - 1 - iu]
                    for x in w:
                        if x > up["t"]:
                            _tail_add(up, x - up["t"], nexc)
                        elif x < lo["t"]:
                            _tail_add(lo, lo["t"] - x, nexc)
                    th["n"] = len(w)
                    th["warm"] = []
            else:
                th["n"] += 1
                if z > up["t"]:
                    _tail_add(up, z - up["t"], nexc)
                elif z < lo["t"]:
                    _tail_add(lo, lo["t"] - z, nexc)

        dists, state["base"] = base(y, state["base"])
        pend.append(list(dists))
        if len(pend) > k:
            pend.pop(0)

        out = []
        for m, d in enumerate(dists, start=1):
            th = state["tails"][m - 1]
            up, lo = th["up"], th["lo"]
            if (up["t"] is None or len(up["exc"]) < 8
                    or len(lo["exc"]) < 8 or th["n"] <= 0):
                out.append(d)
                continue
            out.append(SplicedDist(
                d, lo["t"], up["t"],
                lo["nx"] / th["n"], up["nx"] / th["n"],
                lo["g"], lo["s"], up["g"], up["s"]))
        return out, state

    _skater.__name__ = f"gpdtails({getattr(base, '__name__', '?')}, k={k})"
    return _skater
