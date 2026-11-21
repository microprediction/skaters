"""Shape transforms as torch modules: fractional differencing and the two
signed power families (power_transform, yeo_johnson), and gaussianize.

Same arithmetic order as :mod:`skaters.transform`; the continuous
hyperparameters (``d``, ``p``, ``lmbda``) are parameters, so the fractional
weights, the delta-method derivatives and the exact pushforward's map
(``exact=True``, :mod:`skaters.torch.pushforward`) carry gradients.
"""

from __future__ import annotations

import math

import torch

from skaters.torch.dist import TorchDist, DTYPE, _t
from skaters.torch.transform import TorchTransform, _p, _zero, register
from skaters.torch.pushforward import TorchPushforwardDist, has_components, pushforward


def _frac_diff_weights(d: torch.Tensor, window: int) -> list:
    """w[0] = 1, w[k] = -w[k-1] * (d - k + 1) / k, as tensors of ``d``."""
    w = [torch.ones((), dtype=DTYPE)]
    for i in range(1, window):
        w.append(-w[-1] * (d - i + 1) / i)
    return w


class FractionalDifference(TorchTransform):
    reference = "fractional_difference"

    def __init__(self, d: float = 0.4, window: int = 50):
        super().__init__()
        self.d = _p(d)
        self.window = int(window)

    def reference_args(self):
        return {"d": float(self.d), "window": self.window}

    def _weights(self) -> list:
        return _frac_diff_weights(self.d, self.window)

    def forward(self, y, state=None):
        # The reference emits w[0] * y = y on the first call, not 0.
        y = _t(y)
        buf = [] if state is None else list(state["buffer"])
        buf.append(y)
        if len(buf) > self.window:
            buf.pop(0)
        n = len(buf)
        w = self._weights()
        z = _zero()
        for j in range(n):
            z = z + w[j] * buf[n - 1 - j]
        return z, {"buffer": buf}

    def inverse_k(self, dists, state):
        H = len(dists)
        w = self._weights()
        window = self.window
        buf = list(state["buffer"])
        cbuf: list = [None] * len(buf)
        result = []
        for h, d_in in enumerate(dists):
            buf.append(_zero())
            cbuf.append(None)
            n = len(buf)
            shift = _zero()
            coef = [_zero() for _ in range(H)]
            coef[h] = torch.ones((), dtype=DTYPE)
            for j in range(1, min(n, window)):
                shift = shift - w[j] * buf[n - 1 - j]
                cj = cbuf[n - 1 - j]
                if cj is not None:
                    for i in range(h):
                        coef[i] = coef[i] - w[j] * cj[i]
            recovered_mean = d_in.mean + shift
            buf[-1] = recovered_mean
            cbuf[-1] = coef
            total_var = _zero()
            for i in range(h + 1):
                total_var = total_var + coef[i] * coef[i] * dists[i].var
            if bool(total_var > 0):
                std = torch.sqrt(total_var)
            else:
                std = torch.clamp(d_in.std, min=1e-12)
            result.append(TorchDist.gaussian(recovered_mean, std))
            if len(buf) > window:
                buf.pop(0)
                cbuf.pop(0)
        return result


class PowerTransform(TorchTransform):
    reference = "power_transform"

    def __init__(self, p: float = 0.5, exact: bool = False):
        super().__init__()
        assert 0 < p < 1
        self.exact = bool(exact)
        self.p = _p(p)

    def reference_args(self):
        return {"p": float(self.p), "exact": self.exact}

    # |y|**p at y == 0 is 0, but its derivative in p is 0**p * log(0) = 0 * -inf,
    # which autograd evaluates to NaN; one exact zero (common on repeat-heavy
    # series) then poisons the whole window's gradient. The base is swapped for
    # 1 where y == 0 (so the unused branch's gradient is finite) and the value
    # set to 0: values are unchanged, and the gradient at 0 is 0.
    @staticmethod
    def _signed_pow(y, e):
        a = torch.abs(y)
        nz = a > 0
        return torch.copysign(torch.where(nz, torch.where(nz, a, torch.ones_like(a)) ** e,
                                          torch.zeros_like(a)), y)

    def _fwd(self, y):
        return self._signed_pow(y, self.p)

    def _inv(self, yp):
        return self._signed_pow(yp, 1.0 / self.p)

    def forward(self, y, state=None):
        y = _t(y)
        return self._fwd(y), (state or {})

    def inverse_k(self, dists, state):
        if self.exact:
            return [pushforward(d, self._inv) for d in dists]
        inv_p = 1.0 / self.p
        result = []
        for d in dists:
            if not has_components(d):          # tail-spliced: exact pushforward
                result.append(pushforward(d, self._inv))
                continue
            ws, ms, ss = [], [], []
            for w, mu, sigma in d.components:
                orig_mean = self._inv(mu)
                abs_mu = torch.abs(mu)
                if bool(abs_mu > 1e-12):
                    deriv = inv_p * abs_mu ** (inv_p - 1)
                else:
                    deriv = inv_p
                orig_std = torch.clamp(sigma * deriv, min=1e-12)
                ws.append(w); ms.append(orig_mean); ss.append(orig_std)
            result.append(TorchDist(ws, ms, ss))
        return result


class YeoJohnson(TorchTransform):
    reference = "yeo_johnson"

    def __init__(self, lmbda: float = 0.0, exact: bool = False):
        super().__init__()
        self.exact = bool(exact)
        self.lmbda = _p(lmbda)

    def reference_args(self):
        return {"lmbda": float(self.lmbda), "exact": self.exact}

    # the L == 0 and L == 2 cases are the reference's closed-form limits,
    # taken on the parameter's float value exactly as the reference does
    def _fwd(self, y):
        L = self.lmbda
        Lf = float(L.detach())
        if bool(y >= 0.0):
            return torch.log1p(y) if Lf == 0.0 else ((y + 1.0) ** L - 1.0) / L
        if Lf == 2.0:
            return -torch.log1p(-y)
        return -(((-y + 1.0) ** (2.0 - L) - 1.0) / (2.0 - L))

    def _inv(self, yp):
        L = self.lmbda
        Lf = float(L.detach())
        if bool(yp >= 0.0):
            if Lf == 0.0:
                return torch.expm1(torch.clamp(yp, max=350.0))
            base = torch.clamp(L * yp + 1.0, min=1e-12)
            return base ** (1.0 / L) - 1.0
        if Lf == 2.0:
            return 1.0 - torch.exp(torch.clamp(-yp, max=350.0))
        base = torch.clamp(-(2.0 - L) * yp + 1.0, min=1e-12)
        return 1.0 - base ** (1.0 / (2.0 - L))

    def _dinv(self, yp):
        L = self.lmbda
        Lf = float(L.detach())
        if bool(yp >= 0.0):
            if Lf == 0.0:
                return torch.exp(torch.clamp(yp, max=350.0))
            base = torch.clamp(L * yp + 1.0, min=1e-12)
            return base ** (1.0 / L - 1.0)
        if Lf == 2.0:
            return torch.exp(torch.clamp(-yp, max=350.0))
        base = torch.clamp(-(2.0 - L) * yp + 1.0, min=1e-12)
        return base ** (1.0 / (2.0 - L) - 1.0)

    def forward(self, y, state=None):
        y = _t(y)
        return self._fwd(y), (state or {})

    def inverse_k(self, dists, state):
        if self.exact:
            return [pushforward(d, self._inv) for d in dists]
        result = []
        for d in dists:
            if not has_components(d):          # tail-spliced: exact pushforward
                result.append(pushforward(d, self._inv))
                continue
            ws, ms, ss = [], [], []
            for w, mu, sigma in d.components:
                ws.append(w)
                ms.append(self._inv(mu))
                ss.append(torch.clamp(sigma * self._dinv(mu), min=1e-12))
            result.append(TorchDist(ws, ms, ss))
        return result


# ---------------------------------------------------------------------------
# log coordinate with a one-sided bound
# ---------------------------------------------------------------------------

def _nextafter_t(b: float, toward: float):
    return torch.as_tensor(math.nextafter(b, toward), dtype=DTYPE)


class LogTransform(TorchTransform):
    """``log_transform(lower=..., upper=...)``: the inverse is the exact
    pushforward through the analytic map, in torch."""
    reference = "log_transform"

    def __init__(self, lower=None, upper=None):
        super().__init__()
        if lower is not None and upper is not None:
            raise ValueError("log_transform takes one bound: lower or upper")
        b = float(upper if upper is not None else (0.0 if lower is None else lower))
        if not math.isfinite(b):
            raise ValueError("log_transform needs a finite bound")
        self.lower, self.upper = lower, upper
        self.b = b
        self.direction = -1.0 if upper is not None else 1.0
        self.bound_label = "upper" if upper is not None else "lower"

    def reference_args(self):
        return {"lower": self.lower, "upper": self.upper}

    def _fwd_query(self, y):
        d, b = self.direction, self.b
        gap = d * (y - b)
        g = float(gap.detach())
        if g <= 0.0:
            return torch.as_tensor(-d * math.inf, dtype=DTYPE)
        if math.isinf(g):
            half_gap = d * (0.5 * y - 0.5 * b)
            return d * (torch.log(half_gap) + math.log(2.0))
        return d * torch.log(gap)

    def _inverse_at_scale(self, z, weight):
        d = self.direction
        weight = _t(weight)
        bound = weight * self.b
        log_gap = d * z + torch.log(weight)
        gap = torch.exp(log_gap)
        if math.isinf(float(gap.detach())):
            return 2.0 * (0.5 * bound + d * torch.exp(log_gap - math.log(2.0)))
        return bound + d * gap

    def _inv(self, z):
        y = self._inverse_at_scale(z, 1.0)
        if float(y.detach()) == self.b:
            return _nextafter_t(self.b, self.direction * math.inf)
        return y

    def _log_jacobian(self, z):
        return -self.direction * z

    def _moments(self, m, s):
        d = self.direction
        variance = s * s
        log_mean_gap = d * m + 0.5 * variance
        mean = self._inverse_at_scale(d * log_mean_gap, 1.0)
        vf = float(variance.detach())
        if float(s.detach()) == 0.0:
            return mean, torch.zeros((), dtype=DTYPE)
        if vf < 1e-16:
            log_relative_std = torch.log(s)
        elif vf > 40.0:
            log_relative_std = 0.5 * variance
        else:
            log_relative_std = 0.5 * torch.log(torch.expm1(variance))
        return mean, torch.exp(log_mean_gap + log_relative_std)

    def forward(self, y, state=None):
        y = _t(y)
        if not math.isfinite(float(y.detach())):
            return y, (state or {})
        z = self._fwd_query(y)
        if float(z.detach()) == -self.direction * math.inf:
            raise ValueError(f"log_transform: observation {float(y)!r} must lie inside "
                             f"{self.bound_label}={self.b}")
        return z, (state or {})

    def inverse_k(self, dists, state):
        return [TorchPushforwardDist(d, inv_fn=self._inv, fwd_fn=self._fwd_query,
                                     log_jacobian_fn=self._log_jacobian,
                                     component_moments_fn=self._moments,
                                     scaled_inv_fn=self._inverse_at_scale)
                for d in dists]


# ---------------------------------------------------------------------------
# empirical Gaussianization
# ---------------------------------------------------------------------------

def _herm(s, dx, v0, v1, t0, t1):
    s2 = s * s
    s3 = s2 * s
    return (v0 * (2 * s3 - 3 * s2 + 1) + dx * t0 * (s3 - 2 * s2 + s)
            + v1 * (-2 * s3 + 3 * s2) + dx * t1 * (s3 - s2))


def _herm_ds(s, dx, v0, v1, t0, t1):
    s2 = s * s
    return (v0 * (6 * s2 - 6 * s) + dx * t0 * (3 * s2 - 4 * s + 1)
            + v1 * (-6 * s2 + 6 * s) + dx * t1 * (3 * s2 - 2 * s))


def _gz_fwd(y, knots):
    """The reference ``_fwd`` on a tensor y over float knots."""
    import bisect
    cs, zs, ts = knots
    yf = float(y.detach())
    if yf <= cs[0]:
        s0 = ts[0] if ts else (zs[1] - zs[0]) / (cs[1] - cs[0])
        return zs[0] + s0 * (y - cs[0])
    if yf >= cs[-1]:
        s1 = ts[-1] if ts else (zs[-1] - zs[-2]) / (cs[-1] - cs[-2])
        return zs[-1] + s1 * (y - cs[-1])
    i = bisect.bisect_right(cs, yf) - 1
    if ts is None:
        return zs[i] + (zs[i + 1] - zs[i]) * (y - cs[i]) / (cs[i + 1] - cs[i])
    dx = cs[i + 1] - cs[i]
    return _herm((y - cs[i]) / dx, dx, zs[i], zs[i + 1], ts[i], ts[i + 1])


def _gz_inv(z, knots):
    """The reference ``_inv`` on a tensor z over float knots."""
    import bisect
    cs, zs, ts = knots
    z = _t(z)
    zf = float(z.detach())
    if zf <= zs[0]:
        s0 = ts[0] if ts else (zs[1] - zs[0]) / (cs[1] - cs[0])
        return cs[0] + (z - zs[0]) / max(s0, 1e-12)
    if zf >= zs[-1]:
        s1 = ts[-1] if ts else (zs[-1] - zs[-2]) / (cs[-1] - cs[-2])
        return cs[-1] + (z - zs[-1]) / max(s1, 1e-12)
    i = bisect.bisect_right(zs, zf) - 1
    if ts is None:
        return cs[i] + (cs[i + 1] - cs[i]) * (z - zs[i]) / (zs[i + 1] - zs[i])
    dx = cs[i + 1] - cs[i]
    s = (z - zs[i]) / (zs[i + 1] - zs[i])
    for _ in range(6):
        d = _herm_ds(s, dx, zs[i], zs[i + 1], ts[i], ts[i + 1])
        if float(_t(d).detach()) <= 1e-14:
            break
        s = s - (_herm(s, dx, zs[i], zs[i + 1], ts[i], ts[i + 1]) - z) / d
        s = torch.clamp(s, 0.0, 1.0)
    return cs[i] + s * dx


class Gaussianize(TorchTransform):
    """``gaussianize(...)``. The sketch, the knots and their guards are data
    driven with no continuous parameter, so the state is the reference's own
    and is advanced by the reference; the forward value and the inverse are
    torch maps over the same knots, so gradients flow through y and through
    the inner predictive."""
    reference = "gaussianize"

    def __init__(self, max_knots: int = 39, warmup: int = 30, n_particles: int = 9,
                 smooth: bool = False, slope_cap: float = 20.0, z_max: float = 8.0,
                 guard: str = "move"):
        super().__init__()
        from statistics import NormalDist
        from skaters import transform as reftr
        self.kw = dict(max_knots=max_knots, warmup=warmup, n_particles=n_particles,
                       smooth=smooth, slope_cap=slope_cap, z_max=z_max, guard=guard)
        self._ref_forward, _ = reftr.gaussianize(**self.kw)
        nd = NormalDist()
        J = n_particles
        self.J = J
        self.z_max = float(z_max)
        self._mids = [nd.inv_cdf((j + 0.5) / J) for j in range(J)]
        self._edges = [nd.inv_cdf(j / J) for j in range(1, J)]

    def reference_args(self):
        return dict(self.kw)

    @staticmethod
    def _moments(state):
        n, mu, m2 = state["n"], state["mu"], state["m2"]
        var = m2 / (n - 1) if n > 2 else 0.0
        sigma = math.sqrt(var) if var > 0 else 1e-8
        return mu, sigma

    def forward(self, y, state=None):
        y = _t(y)
        if state is None:
            state = {"buf": [], "n": 0, "mu": 0.0, "m2": 0.0, "knots": None}
        knots = state["knots"]
        if knots is not None:
            z = _t(_gz_fwd(y, knots))
        else:
            mu, sigma = self._moments(state)
            if sigma <= 1e-8:
                sigma = max(abs(float(y.detach()) - mu), 1e-8)
            z = (y - mu) / sigma if state["n"] else _zero()
        z = torch.clamp(z, -self.z_max, self.z_max)
        _, state = self._ref_forward(float(y.detach()), state)   # advance the sketch
        return z, state

    def inverse_k(self, dists, state):
        knots = state["knots"]
        if knots is None:
            mu, sigma = self._moments(state)
            return [d.affine(sigma, mu) for d in dists]
        inv = lambda z: _t(_gz_inv(z, knots))   # noqa: E731
        J = self.J
        result = []
        for d in dists:
            if not has_components(d):          # tail-spliced: exact pushforward
                result.append(pushforward(d, inv))
                continue
            ws, ms, ss = [], [], []
            for w, mu, sig in d.components:
                pts = [inv(mu + sig * q) for q in self._mids]
                eds = [inv(mu + sig * e) for e in self._edges]
                for j in range(J):
                    lo = eds[j - 1] if j > 0 else None
                    hi = eds[j] if j < J - 1 else None
                    if lo is not None and hi is not None:
                        std = (hi - lo) / 2.0
                    elif hi is not None:
                        std = hi - pts[j]
                    else:
                        std = pts[j] - lo
                    ws.append(w / J); ms.append(pts[j]); ss.append(torch.clamp(std, min=1e-9))
            result.append(TorchDist(ws, ms, ss).prune(12))
        return result


for _cls in (FractionalDifference, PowerTransform, YeoJohnson, LogTransform, Gaussianize):
    register(_cls)
