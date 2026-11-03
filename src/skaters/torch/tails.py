"""GPD tail splice in torch: the twin of :mod:`skaters.tails`.

The tail model (frozen thresholds, exceedance windows, censored-ML fits,
exceedance rates) is pure float data driven by matured PITs, and is computed
with the reference's own functions on floats: it is a constant in the
graph, as the fit is frozen between refits in the reference too. What is
differentiable is the spliced density itself, :class:`TorchSplicedDist`:
its interior is ``c * body.pdf`` and its tails carry the GPD/phi ratio at
``z = Phi^{-1}(body.cdf(x))``, with the normal quantile written in torch
(the same Acklam rational approximation and Halley step as the reference),
so a log score at ``x`` differentiates through the body's cdf and density.
``quantile``, ``mean``, ``var`` and ``crps`` follow the reference's exact
inversion and 65-node quantile grid.
"""

from __future__ import annotations

import math

import torch
from torch import nn

from skaters import tails as ref
from skaters.torch.dist import TorchDist, DTYPE, _t

_EPS = ref._EPS
_LOG_SQRT2PI = ref._LOG_SQRT2PI
_SQRT2 = math.sqrt(2.0)
_SQRT2PI = math.sqrt(2.0 * math.pi)


# ---------------------------------------------------------------------------
# standard normal helpers in torch (same coefficients and operation order)
# ---------------------------------------------------------------------------

def _phi_t(z):
    return 0.5 * torch.erfc(-z / _SQRT2)


def _phi_logpdf_t(z):
    return -0.5 * z * z - _LOG_SQRT2PI


def _phi_inv_t(p):
    """Acklam's approximation polished with one Halley step, on a 0-d tensor;
    the branch is taken on the value exactly as the reference branches."""
    p = torch.clamp(p, _EPS, 1.0 - _EPS)
    A, B, C, D = ref._ACK_A, ref._ACK_B, ref._ACK_C, ref._ACK_D
    pv = float(p.detach())
    if pv < 0.02425:
        q = torch.sqrt(-2.0 * torch.log(p))
        x = ((((((C[0] * q + C[1]) * q + C[2]) * q + C[3]) * q + C[4]) * q + C[5])
             / ((((D[0] * q + D[1]) * q + D[2]) * q + D[3]) * q + 1.0))
    elif pv <= 0.97575:
        q = p - 0.5
        r = q * q
        x = ((((((A[0] * r + A[1]) * r + A[2]) * r + A[3]) * r + A[4]) * r + A[5]) * q
             / (((((B[0] * r + B[1]) * r + B[2]) * r + B[3]) * r + B[4]) * r + 1.0))
    else:
        q = torch.sqrt(-2.0 * torch.log(1.0 - p))
        x = -((((((C[0] * q + C[1]) * q + C[2]) * q + C[3]) * q + C[4]) * q + C[5])
              / ((((D[0] * q + D[1]) * q + D[2]) * q + D[3]) * q + 1.0))
    e = _phi_t(x) - p
    u = e * _SQRT2PI * torch.exp(0.5 * x * x)
    return x - u / (1.0 + 0.5 * x * u)


def _gpd_logpdf_t(e, gamma: float, sigma: float):
    if abs(gamma) < 1e-9:
        return -math.log(sigma) - e / sigma
    arg = 1.0 + gamma * e / sigma
    if bool(arg <= 0.0):
        return torch.as_tensor(-745.0, dtype=DTYPE)
    return -math.log(sigma) - (1.0 / gamma + 1.0) * torch.log(arg)


def _gpd_sf_t(e, gamma: float, sigma: float):
    if bool(e <= 0.0):
        return torch.ones((), dtype=DTYPE)
    if abs(gamma) < 1e-9:
        return torch.exp(-e / sigma)
    arg = 1.0 + gamma * e / sigma
    if bool(arg <= 0.0):
        return torch.zeros((), dtype=DTYPE)
    return arg ** (-1.0 / gamma)


# ---------------------------------------------------------------------------
# the spliced predictive
# ---------------------------------------------------------------------------

class TorchSplicedDist:
    """A TorchDist body with GPD tails spliced in beyond frozen z-thresholds."""

    __slots__ = ("body", "t_lo", "t_up", "zeta_lo", "zeta_up",
                 "g_lo", "s_lo", "g_up", "s_up", "_c", "_plo", "_pup", "_grid")

    _GRID_N = ref.SplicedDist._GRID_N

    def __init__(self, body: TorchDist, t_lo, t_up, zeta_lo, zeta_up,
                 g_lo, s_lo, g_up, s_up):
        self.body = body
        self.t_lo, self.t_up = float(t_lo), float(t_up)
        self.zeta_lo, self.zeta_up = float(zeta_lo), float(zeta_up)
        self.g_lo, self.s_lo = float(g_lo), float(s_lo)
        self.g_up, self.s_up = float(g_up), float(s_up)
        self._plo, self._pup = ref._phi(self.t_lo), ref._phi(self.t_up)
        self._grid = None
        interior = max(self._pup - self._plo, 1e-12)
        self._c = max(1.0 - self.zeta_lo - self.zeta_up, 1e-12) / interior

    # --- conversions --------------------------------------------------------

    def to_reference(self) -> ref.SplicedDist:
        return ref.SplicedDist(self.body.to_reference(), self.t_lo, self.t_up,
                               self.zeta_lo, self.zeta_up,
                               self.g_lo, self.s_lo, self.g_up, self.s_up)

    @staticmethod
    def from_reference(sd: ref.SplicedDist) -> "TorchSplicedDist":
        return TorchSplicedDist(TorchDist.from_reference(sd.body), sd.t_lo, sd.t_up,
                                sd.zeta_lo, sd.zeta_up, sd.g_lo, sd.s_lo, sd.g_up, sd.s_up)

    def to_dict(self) -> dict:
        return self.to_reference().to_dict()

    # --- queries ------------------------------------------------------------

    def _z(self, x):
        u = torch.clamp(self.body.cdf(x), _EPS, 1.0 - _EPS)
        return _phi_inv_t(u)

    def cdf(self, x):
        x = _t(x)
        z = self._z(x)
        if bool(z < self.t_lo):
            return self.zeta_lo * _gpd_sf_t(self.t_lo - z, self.g_lo, self.s_lo)
        if bool(z > self.t_up):
            return 1.0 - self.zeta_up * _gpd_sf_t(z - self.t_up, self.g_up, self.s_up)
        return self.zeta_lo + self._c * (_phi_t(z) - self._plo)

    def logpdf(self, x):
        x = _t(x)
        base = self.body.logpdf(x)
        if not bool(torch.isfinite(base)):
            return base
        z = self._z(x)
        if bool(z < self.t_lo):
            corr = (math.log(max(self.zeta_lo, 1e-300))
                    + _gpd_logpdf_t(self.t_lo - z, self.g_lo, self.s_lo)
                    - _phi_logpdf_t(z))
        elif bool(z > self.t_up):
            corr = (math.log(max(self.zeta_up, 1e-300))
                    + _gpd_logpdf_t(z - self.t_up, self.g_up, self.s_up)
                    - _phi_logpdf_t(z))
        else:
            corr = math.log(self._c)
        return base + corr

    def pdf(self, x):
        lp = self.logpdf(x)
        if bool(lp < 700.0):
            return torch.exp(lp)
        return torch.as_tensor(math.inf, dtype=DTYPE)

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100):
        assert 0 < p < 1
        if p < self.zeta_lo:
            z = self.t_lo - ref._gpd_isf(p / self.zeta_lo, self.g_lo, self.s_lo)
        elif p > 1.0 - self.zeta_up:
            z = self.t_up + ref._gpd_isf((1.0 - p) / self.zeta_up, self.g_up, self.s_up)
        else:
            u = self._plo + (p - self.zeta_lo) / self._c
            z = ref._phi_inv(min(max(u, _EPS), 1.0 - _EPS))
        ub = min(max(ref._phi(z), _EPS), 1.0 - _EPS)
        return self.body.quantile(ub, tol=tol, max_iter=max_iter)

    def _qgrid(self):
        if self._grid is None:
            n = self._GRID_N
            self._grid = torch.stack([self.quantile((i + 0.5) / n).reshape(()) for i in range(n)])
        return self._grid

    @property
    def mean(self):
        q = self._qgrid()
        return torch.sum(q) / q.numel()

    @property
    def var(self):
        q = self._qgrid()
        m = torch.sum(q) / q.numel()
        return torch.sum((q - m) * (q - m)) / q.numel()

    @property
    def std(self):
        return torch.sqrt(self.var)

    def crps(self, x):
        x = _t(x)
        q = self._qgrid()
        n = q.numel()
        t1 = torch.sum(torch.abs(q - x)) / n
        idx = torch.arange(n, dtype=DTYPE)
        t2 = 2.0 * torch.sum(q * (2.0 * (idx + 0.5) / n - 1.0)) / n
        return t1 - t2 * 0.5

    def __repr__(self) -> str:
        return (f"TorchSplicedDist(zeta=({self.zeta_lo:.4f},{self.zeta_up:.4f}), "
                f"gamma=({self.g_lo:.3f},{self.g_up:.3f}), body={self.body!r})")


# ---------------------------------------------------------------------------
# the wrapper
# ---------------------------------------------------------------------------

class GpdTails(nn.Module):
    """Wrap a k-horizon torch skater so every issued predictive carries GPD
    tails, with the reference's tail bookkeeping on float PITs."""

    def __init__(self, base, k: int, level: float = 0.98, nexc: int = 500,
                 warmup: int = 500, rate_alpha: float = 0.002):
        super().__init__()
        assert k >= 1
        assert 0.5 < level < 1.0
        assert nexc >= 50 and warmup >= 100
        assert 0.0 < rate_alpha < 0.1
        self.base = base
        self.k = k
        self.level = float(level)
        self.nexc = int(nexc)
        self.warmup = int(warmup)
        self.rate_alpha = float(rate_alpha)

    def forward(self, y, state=None):
        k, level, nexc, warmup, rate_alpha = self.k, self.level, self.nexc, self.warmup, self.rate_alpha
        yt = _t(y)
        yv = float(yt.detach())
        if state is None:
            state = {"base": None, "pending": [],
                     "tails": [{"up": ref._tail_new(), "lo": ref._tail_new(),
                                "warm": [], "n": 0, "skipped": 0} for _ in range(k)]}
        pend = state["pending"]
        n = len(pend)
        with torch.no_grad():
            for m in range(1, k + 1):
                if m > n:
                    continue
                d = pend[n - m][m - 1]
                u = float(d.cdf(yv))
                if not math.isfinite(u):
                    continue
                z = ref._phi_inv(min(max(u, _EPS), 1.0 - _EPS))
                th = state["tails"][m - 1]
                up, lo = th["up"], th["lo"]
                if up["t"] is None:
                    if m >= 2 and th.get("skipped", 0) < 2 * m:
                        th["skipped"] = th.get("skipped", 0) + 1
                        continue
                    th["warm"].append(z)
                    if len(th["warm"]) >= warmup:
                        w = sorted(th["warm"])
                        iu = min(int(level * len(w)), len(w) - 1)
                        up["t"] = w[iu]
                        lo["t"] = w[len(w) - 1 - iu]
                        for x in w:
                            if x > up["t"]:
                                ref._tail_add(up, x - up["t"], nexc)
                            elif x < lo["t"]:
                                ref._tail_add(lo, lo["t"] - x, nexc)
                        th["n"] = len(w)
                        up["r"] = up["nx"] / len(w)
                        lo["r"] = lo["nx"] / len(w)
                        th["warm"] = []
                else:
                    th["n"] += 1
                    up["r"] += rate_alpha * ((1.0 if z > up["t"] else 0.0) - up["r"])
                    lo["r"] += rate_alpha * ((1.0 if z < lo["t"] else 0.0) - lo["r"])
                    if z > up["t"]:
                        ref._tail_add(up, z - up["t"], nexc)
                    elif z < lo["t"]:
                        ref._tail_add(lo, lo["t"] - z, nexc)

        dists, state["base"] = self.base(yt, state["base"])
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
            out.append(TorchSplicedDist(d, lo["t"], up["t"], lo["r"], up["r"],
                                        lo["g"], lo["s"], up["g"], up["s"]))
        return out, state


def gpdtails(base, k: int, **kwargs) -> GpdTails:
    """Factory with the reference's name and signature."""
    return GpdTails(base, k, **kwargs)
