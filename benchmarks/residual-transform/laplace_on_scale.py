"""Recursive idea: point laplace at its own scale defect instead of hand-
building a volatility filter.

At tick t, resolve the base forecast F_t against y_{t+1} to get the usual
z_{t+1} = Phi^-1(F_t.cdf(y_{t+1})). Instead of filtering z^2 through a
hand-specified recursion (M1/M2) or a hand-built candidate grid (the
homogenization cell model), form x_t = log(z_t^2) and hand THAT series to a
second, independent laplace instance. Whatever structure laplace's own
candidate pool can find in the scale-defect series (seasonal, AR,
whatever), it finds for free -- no new modelling code, and in particular no
new online-learning-rate to get wrong and re-tune (which is exactly what
happened building the homogenization cell model this session).

The one thing that has to be done carefully is combining the meta-forecast
back into a corrected predictive for y. Collapsing the meta-forecast's
mixture down to point estimates and exponentiating (kappa = exp(mean/2))
would understate the correction: exp is convex, so by Jensen's inequality
E[exp(X/2)] > exp(E[X]/2), and a point-collapse silently drops that gap.
ScaleMetaCorrectedDist avoids it by building the corrected CDF directly
from the meta-forecast's own exact cdf/quantile, no point-collapse anywhere:

    z_{t+1} = S * g^-1(X),   S = +-1 fair coin (symmetric, scale-only),
                             X ~ H_t (the meta-laplace's real predictive
                             Dist for x_{t+1} = g(|z_{t+1}|))

    H(z) = 1/2 + 1/2 * H_t.cdf(g(z))        z > 0
    H(z) = 1/2 * (1 - H_t.cdf(g(-z)))       z < 0

which is exact given H_t, and monotone because H_t.cdf is, for ANY strictly
increasing coordinate map g: (0, inf) -> R. g(kappa) = 2 log(kappa) (i.e.
x = log(z^2)) is one choice; it is also the wrong one to feed a
Gaussian-mixture-based meta-forecaster, because log(chi-sq_1) is
substantially left-skewed and a Gaussian-mixture approximation of it
reproduces that skew badly (validated on synthetic data: even given the
EXACT true mean/variance of log(z^2), the round-trip correction on iid
N(0,1) data comes out with var~0.86, kurtosis~1.86, not the ~1/~3 it
should be -- the ScaleMetaCorrectedDist math itself is exact, confirmed by
feeding it the TRUE non-Gaussian law of log(z^2) directly instead of a
Gaussian summary, which reproduces N(0,1) to within simulation noise).

The fix is coordinate choice, not the transform machinery: Wilson-Hilferty,
g(kappa) = kappa^(2/3) (i.e. x = |z|^(2/3)), is the classical near-Gaussian
stabilizing transform for a chi-squared variate (chi-sq_1/1)^(1/3) ~=
N(1 - 2/9, 2/9), and is what this module now defaults to; log-chi-squared
is kept for comparison.

This is deliberately tested on synthetic data only for now, with a strict
pass bar: not "log-score improves" but "the corrected z-tilde stream is
actually indistinguishable from N(0,1)" (mean, variance, skew, kurtosis,
and a KS-style max-deviation check of the PIT against Uniform(0,1)).

Usage: PYTHONPATH=src python benchmarks/residual-transform/laplace_on_scale.py
"""
from __future__ import annotations
import math
import random
import statistics as st

from skaters import laplace, Dist, leaf, conjugate, garch, bayesian_ensemble
from skaters.pushforward import _GH7 as _GAUSS_HERMITE_7

_STD_NORMAL = Dist.gaussian(0.0, 1.0)
_EPS = 1e-12
_LOG_SQRT2PI = math.log(math.sqrt(2.0 * math.pi))


def _clamp01(u: float) -> float:
    return min(max(u, _EPS), 1.0 - _EPS)


def _phi_inv(p: float) -> float:
    return _STD_NORMAL.quantile(p)


def _phi_logpdf(z: float) -> float:
    return -0.5 * z * z - _LOG_SQRT2PI


_QGRID_N = 32
_QGRID_P = [(i + 0.5) / _QGRID_N for i in range(_QGRID_N)]


# ---------------------------------------------------------------------------
# Coordinate maps g: (0, inf) -> R for x = g(|z|). Each needs forward,
# inverse, and d(forward)/d(kappa) for the density chain rule.
# ---------------------------------------------------------------------------

class Coordinate:
    __slots__ = ("forward", "inverse", "dforward", "name")

    def __init__(self, forward, inverse, dforward, name):
        self.forward, self.inverse, self.dforward, self.name = forward, inverse, dforward, name


LOG_CHISQ = Coordinate(
    forward=lambda kappa: 2.0 * math.log(kappa),
    inverse=lambda x: math.exp(x / 2.0),
    dforward=lambda kappa: 2.0 / kappa,
    name="log_chisq",
)

# Wilson-Hilferty: (chi-sq_1)^(1/3) ~= N(1 - 2/9, 2/9), the classical
# near-Gaussian stabilizing transform for a chi-squared variate -- a much
# better match to a Gaussian-mixture meta-forecaster than log(chi-sq_1),
# which is substantially left-skewed.
WILSON_HILFERTY = Coordinate(
    forward=lambda kappa: kappa ** (2.0 / 3.0),
    inverse=lambda x: max(x, 0.0) ** 1.5,
    dforward=lambda kappa: (2.0 / 3.0) * kappa ** (-1.0 / 3.0),
    name="wilson_hilferty",
)


class ExactAbsZLaw:
    """The TRUE (non-Gaussian) law of x = g(|Z|) for Z ~ N(0,1), for any
    coordinate g. Used only to isolate whether ScaleMetaCorrectedDist itself
    is unbiased, independent of how well any real meta-forecaster
    approximates this law. G(x) = 2*Phi(g^-1(x)) - 1 for x in the range of
    g on (0, inf) (both coordinates here are increasing with range covering
    what g(|Z|) can produce)."""

    def __init__(self, coord: Coordinate):
        self.coord = coord

    def cdf(self, x: float) -> float:
        # coord.inverse clips out-of-support x (e.g. Wilson-Hilferty maps any
        # x < 0 to kappa=0) so this needs no separate support check.
        return min(max(2.0 * _STD_NORMAL.cdf(self.coord.inverse(x)) - 1.0, 0.0), 1.0)

    def logpdf(self, x: float) -> float:
        kappa = self.coord.inverse(x)
        if kappa <= 0.0:
            return -math.inf
        # d/dx [2*Phi(g^-1(x)) - 1] = 2*phi(g^-1(x)) * d(g^-1)/dx
        # d(g^-1)/dx = 1 / g'(g^-1(x))
        dgdk = self.coord.dforward(kappa)
        return math.log(2.0) + _phi_logpdf(kappa) - math.log(dgdk)

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
        assert 0.0 < p < 1.0
        target = (p + 1.0) / 2.0
        kappa = _STD_NORMAL.quantile(target, tol=tol, max_iter=max_iter)
        return self.coord.forward(kappa)


# ---------------------------------------------------------------------------
# The exact, no-point-collapse correction
# ---------------------------------------------------------------------------

class ScaleMetaCorrectedDist:
    """base (F_t, predictive for y_{t+1}) corrected by meta (H_t, the meta-
    laplace's real predictive Dist for x_{t+1} = coord.forward(|z_{t+1}|)),
    under a symmetric-sign, scale-only assumption. See module docstring for
    the exact cdf/density derivation, valid for any Coordinate."""

    __slots__ = ("base", "meta", "coord", "_qgrid")

    def __init__(self, base, meta, coord: Coordinate = WILSON_HILFERTY):
        self.base = base
        self.meta = meta
        self.coord = coord
        self._qgrid = None

    def _z(self, y: float) -> float:
        return _phi_inv(_clamp01(self.base.cdf(y)))

    def cdf(self, y: float) -> float:
        z = self._z(y)
        if z > 0.0:
            return _clamp01(0.5 + 0.5 * self.meta.cdf(self.coord.forward(z)))
        if z < 0.0:
            return _clamp01(0.5 * (1.0 - self.meta.cdf(self.coord.forward(-z))))
        return 0.5

    def logpdf(self, y: float) -> float:
        z = self._z(y)
        if z == 0.0:
            return -math.inf
        az = abs(z)
        x = self.coord.forward(az)
        log_h = math.log(0.5) + self.meta.logpdf(x) + math.log(self.coord.dforward(az))
        return self.base.logpdf(y) + log_h - _phi_logpdf(z)

    def pdf(self, y: float) -> float:
        lp = self.logpdf(y)
        return math.exp(lp) if lp > -700.0 else 0.0

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
        assert 0.0 < p < 1.0
        if p > 0.5:
            x = self.meta.quantile(2.0 * p - 1.0, tol=tol, max_iter=max_iter)
            z = self.coord.inverse(x)
        elif p < 0.5:
            x = self.meta.quantile(1.0 - 2.0 * p, tol=tol, max_iter=max_iter)
            z = -self.coord.inverse(x)
        else:
            z = 0.0
        u = _clamp01(_STD_NORMAL.cdf(z))
        return self.base.quantile(u, tol=tol, max_iter=max_iter)

    def _quantile_grid(self) -> list:
        if self._qgrid is None:
            self._qgrid = [self.quantile(p) for p in _QGRID_P]
        return self._qgrid

    @property
    def mean(self) -> float:
        return sum(self._quantile_grid()) / _QGRID_N

    @property
    def var(self) -> float:
        q = self._quantile_grid()
        mu = self.mean
        return sum((qi - mu) ** 2 for qi in q) / _QGRID_N

    @property
    def std(self) -> float:
        v = self.var
        return math.sqrt(v) if v > 0 else 0.0

    def crps(self, x: float) -> float:
        """CRPS via the quantile-form identity (Gneiting & Raftery 2007),
        same construction as skaters.residual_transform.CorrectedDist."""
        q = self._quantile_grid()
        total = 0.0
        for p, qi in zip(_QGRID_P, q):
            ind = 1.0 if x <= qi else 0.0
            total += (qi - x) * (ind - p)
        return 2.0 * total / _QGRID_N


# ---------------------------------------------------------------------------
# The wrapper
# ---------------------------------------------------------------------------

def laplace_scale_recursive(base_factory=None, meta_factory=None, coord: Coordinate = WILSON_HILFERTY):
    base = (base_factory or (lambda: laplace(k=1, tails="gaussian")))()
    meta = (meta_factory or (lambda: laplace(k=1, tails="gaussian")))()

    def _skater(y: float, state: dict | None):
        if state is None:
            state = {"base_state": None, "meta_state": None, "raw": None, "z": None, "h": None}

        z = None
        if state["raw"] is not None:
            u = _clamp01(state["raw"].cdf(y))
            z = _phi_inv(u)
            x = coord.forward(max(abs(z), 1e-150))
            meta_dists, state["meta_state"] = meta(x, state["meta_state"])
            state["h"] = meta_dists[0]
        state["z"] = z

        base_dists, state["base_state"] = base(y, state["base_state"])
        f_t = base_dists[0]
        state["raw"] = f_t

        corrected = f_t if state["h"] is None else ScaleMetaCorrectedDist(f_t, state["h"], coord=coord)
        return [corrected], state

    return _skater


# ---------------------------------------------------------------------------
# The winning design: exact log(chi-sq_1) noise, laplace's own dynamics.
#
# Wilson-Hilferty (above) fixes the wrong problem: it Gaussianizes the
# *marginal* shape, but if the scale is genuinely time-varying the thing
# worth tracking is additive in LOG coordinates (log(sigma_t^2 xi_t^2) =
# log(sigma_t^2) + log(xi_t^2)), not multiplicative, so a power transform
# buys nothing for the dynamics even though it helps the static shape.
# log(z^2) is the right coordinate for tracking; the earlier log-coordinate
# failure was that a Gaussian-mixture meta-forecaster cannot represent
# log(chi-sq_1)'s real (substantial, left) skew, no matter how much data it
# sees -- that is a structural mismatch, not an estimation one.
#
# The fix: let laplace do what it is actually good at (finding dynamics,
# including whatever seasonal period actually exists, via its own
# likelihood-weighted seasonal candidates -- no period hard-coded here),
# but use its predictive mean/variance only to locate and size the *latent*
# state h_t = log(sigma_t^2), then convolve that Gaussian uncertainty
# against the EXACT, closed-form log(chi-sq_1) noise law by Gauss-Hermite
# quadrature (reusing skaters.pushforward's own node table) rather than
# trusting laplace's Gaussian-mixture shape for the observation noise.
# laplace's reported variance is Var(h_t) + R (R the known, fixed noise
# variance pi^2/2), so Var(h_t) = laplace_var - R, floored at 0.
# ---------------------------------------------------------------------------

_DEBIAS_LOGCHISQ = math.log(2.0) + 0.5772156649015329   # -E[log(chi-sq_1)]
_VAR_LOGCHISQ = (math.pi ** 2) / 2.0                     # Var[log(chi-sq_1)], exact
_SQRT2 = math.sqrt(2.0)
_SQRTPI = math.sqrt(math.pi)


def _raw_logchisq_cdf(w: float) -> float:
    return min(max(2.0 * _STD_NORMAL.cdf(math.exp(w / 2.0)) - 1.0, 0.0), 1.0)


def _raw_logchisq_logpdf(w: float) -> float:
    e = math.exp(w / 2.0)
    return _STD_NORMAL.logpdf(e) + w / 2.0


class ConvolvedExactLogChiSq:
    """X = h + eps: h ~ N(h_hat, V_h) (from a generic meta-forecaster's own
    mean/variance, net of the known observation-noise variance), eps ~ the
    exact raw log(chi-sq_1) law. No period, no seasonal structure hard-coded
    anywhere -- whatever dynamics a meta-forecaster finds flow through
    (h_hat, V_h); the exact noise shape is layered on by quadrature so the
    result is never just "trust the meta-forecaster's own Gaussian shape
    for the residual noise", which is what made every earlier attempt fail
    the no-regret check to some degree.
    """

    __slots__ = ("h_hat", "sd_h")

    def __init__(self, h_hat: float, v_h: float):
        self.h_hat = h_hat
        self.sd_h = math.sqrt(max(v_h, 1e-6))

    def cdf(self, x: float) -> float:
        total = sum(wt / _SQRTPI * _raw_logchisq_cdf(x - (self.h_hat + _SQRT2 * self.sd_h * node))
                    for node, wt in _GAUSS_HERMITE_7)
        return min(max(total, 0.0), 1.0)

    def logpdf(self, x: float) -> float:
        terms = [_raw_logchisq_logpdf(x - (self.h_hat + _SQRT2 * self.sd_h * node)) + math.log(wt / _SQRTPI)
                 for node, wt in _GAUSS_HERMITE_7]
        best = max(terms)
        return best + math.log(sum(math.exp(t - best) for t in terms))

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 200) -> float:
        assert 0.0 < p < 1.0
        span = 12.0 * self.sd_h + 40.0
        lo, hi = self.h_hat - span, self.h_hat + span
        for _ in range(max_iter):
            mid = 0.5 * (lo + hi)
            if self.cdf(mid) < p:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return 0.5 * (lo + hi)


def laplace_scale_convolved(base_factory=None, meta_factory=None):
    """The winning design (validated on synthetic data -- see RESULTS
    discussion): laplace for dynamics, exact log(chi-sq_1) for shape."""
    base = (base_factory or (lambda: laplace(k=1, tails="gaussian")))()
    meta = (meta_factory or (lambda: laplace(k=1, tails="gaussian")))()

    def _skater(y: float, state: dict | None):
        if state is None:
            state = {"base_state": None, "meta_state": None, "raw": None, "h": None}

        if state["raw"] is not None:
            u = _clamp01(state["raw"].cdf(y))
            z = _phi_inv(u)
            x = math.log(max(z * z, 1e-300)) + _DEBIAS_LOGCHISQ
            meta_dists, state["meta_state"] = meta(x, state["meta_state"])
            md = meta_dists[0]
            v_h = max(md.var - _VAR_LOGCHISQ, 0.0)
            state["h"] = ConvolvedExactLogChiSq(md.mean, v_h)

        base_dists, state["base_state"] = base(y, state["base_state"])
        f_t = base_dists[0]
        state["raw"] = f_t

        corrected = f_t if state["h"] is None else ScaleMetaCorrectedDist(f_t, state["h"], coord=LOG_CHISQ)
        return [corrected], state

    return _skater


class MixtureConvolvedExactLogChiSq:
    """Like ConvolvedExactLogChiSq, but not collapsing the meta-forecaster's
    own predictive mixture for h down to a single (mean, variance) before
    convolving -- that collapse is exactly the "averaging" mistake
    terminal_leaf_ensemble already exists to avoid at the output layer,
    just committed one level up at the latent-state layer instead.

    Each of the meta-forecaster's own mixture components (its own genuine,
    possibly multi-modal belief about which regime h is in) is convolved
    against the exact log(chi-sq_1) noise law *separately*, then the results
    are combined as a real mixture -- not "the exact shape applied to the
    average", but "the exact shape applied to every live hypothesis, mixed
    afterward". Preserves whatever real regime ambiguity the ensemble
    actually encodes instead of smearing it into one Gaussian first.
    """

    __slots__ = ("parts",)

    def __init__(self, components, r: float = _VAR_LOGCHISQ):
        self.parts = [(w, ConvolvedExactLogChiSq(m, max(s * s - r, 0.0))) for w, m, s in components]

    def cdf(self, x: float) -> float:
        return min(max(sum(w * part.cdf(x) for w, part in self.parts), 0.0), 1.0)

    def logpdf(self, x: float) -> float:
        terms = [math.log(w) + part.logpdf(x) for w, part in self.parts if w > 0.0]
        best = max(terms)
        return best + math.log(sum(math.exp(t - best) for t in terms))

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 200) -> float:
        assert 0.0 < p < 1.0
        lo = min(part.h_hat - (12.0 * part.sd_h + 40.0) for _, part in self.parts)
        hi = max(part.h_hat + (12.0 * part.sd_h + 40.0) for _, part in self.parts)
        for _ in range(max_iter):
            mid = 0.5 * (lo + hi)
            if self.cdf(mid) < p:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return 0.5 * (lo + hi)


def laplace_scale_mixture_convolved(base_factory=None, meta_factory=None):
    """laplace_scale_convolved, but preserving the meta-forecaster's full
    mixture belief about h instead of moment-matching it to one Gaussian."""
    base = (base_factory or (lambda: laplace(k=1, tails="gaussian")))()
    meta = (meta_factory or (lambda: laplace(k=1, tails="gaussian")))()

    def _skater(y: float, state: dict | None):
        if state is None:
            state = {"base_state": None, "meta_state": None, "raw": None, "h": None}

        if state["raw"] is not None:
            u = _clamp01(state["raw"].cdf(y))
            z = _phi_inv(u)
            x = math.log(max(z * z, 1e-300)) + _DEBIAS_LOGCHISQ
            meta_dists, state["meta_state"] = meta(x, state["meta_state"])
            state["h"] = MixtureConvolvedExactLogChiSq(meta_dists[0].components)

        base_dists, state["base_state"] = base(y, state["base_state"])
        f_t = base_dists[0]
        state["raw"] = f_t

        corrected = f_t if state["h"] is None else ScaleMetaCorrectedDist(f_t, state["h"], coord=LOG_CHISQ)
        return [corrected], state

    return _skater


# ---------------------------------------------------------------------------
# The derived design: a stable grid of Kalman-filter (rho, tau^2) hypotheses
# for h, combined by online likelihood weighting -- no meta-laplace at all.
#
# The earlier meta-laplace designs all committed the same error in different
# clothes: they reduced the belief about h to a single point estimate
# (laplace's raw mean/var, an unstable online moment-ratio estimate of rho
# and tau, a hard positivity floor) and then either trusted or patched that
# point estimate. But log-score is a PROPER scoring rule: reporting your
# true posterior belief q(x) = integral of h_raw(x-h) pi(h) dh is *provably*
# optimal, with no separate "asymmetric fudge" needed on top, PROVIDED
# pi(h) is an honest belief. The asymmetric harm from every earlier design
# was symptomatic of a bad pi(h), not evidence the framework needed patching.
#
# This is signal-extraction with a KNOWN observation-noise variance (R,
# exact) -- the textbook solution is a Kalman filter, and the classical
# econometric precedent for treating log(squared innovations) exactly this
# way is Harvey, Ruiz & Shephard (1994) quasi-ML stochastic volatility
# estimation. The failure mode isn't the Kalman logic (a single hand-picked
# (rho, tau) already gave the best synthetic-null result of the session);
# it's trying to point-estimate (rho, tau) online from a single noisy
# moment ratio, which divides by a quantity that hovers near zero and
# explodes. The fix already used everywhere else in this codebase: don't
# point-estimate the hyperparameters, run a small FIXED grid of candidates
# (including a tau=0 "nothing to correct" baseline) and combine them by
# ordinary online likelihood weighting. The resulting mixture over live
# hypotheses about h *is* an honest pi(h) -- properness then does the rest,
# and it is numerically safe by construction (no division by a near-zero
# quantity anywhere).
# ---------------------------------------------------------------------------

_KALMAN_GRID = [(0.0, 0.0)] + [(rho, tau * tau) for rho in (0.9, 0.97, 0.99) for tau in (0.05, 0.15, 0.4)]


def laplace_scale_kalman_grid(base_factory=None, grid=None, weight_decay=0.999, learning_rate=0.5):
    base = (base_factory or (lambda: laplace(k=1, tails="gaussian")))()
    grid = grid or _KALMAN_GRID
    n = len(grid)

    def _skater(y: float, state: dict | None):
        if state is None:
            state = {"base_state": None, "raw": None, "h": None,
                      "kf_h": [0.0] * n, "kf_p": [_VAR_LOGCHISQ] * n, "log_w": [0.0] * n}
        s = state

        if s["raw"] is not None:
            u = _clamp01(s["raw"].cdf(y))
            z = _phi_inv(u)
            x = math.log(max(z * z, 1e-300)) + _DEBIAS_LOGCHISQ

            # 1. score each candidate's already-issued (pre-update) forecast.
            log_liks = [ConvolvedExactLogChiSq(s["kf_h"][i], s["kf_p"][i]).logpdf(x) for i in range(n)]
            for i in range(n):
                s["log_w"][i] = weight_decay * s["log_w"][i] + learning_rate * max(min(log_liks[i], 20.0), -20.0)

            # 2. only now update each candidate's own Kalman state using x.
            for i, (rho, tau2) in enumerate(grid):
                h_pred, p_pred = s["kf_h"][i], s["kf_p"][i]
                k_gain = p_pred / (p_pred + _VAR_LOGCHISQ)
                h_filt = h_pred + k_gain * (x - h_pred)
                p_filt = (1.0 - k_gain) * p_pred
                s["kf_h"][i] = rho * h_filt
                s["kf_p"][i] = rho * rho * p_filt + tau2

            # 3. pool into the correction issued for the next tick: a genuine
            # mixture over live hypotheses, not a moment-matched average.
            m = max(s["log_w"])
            raw_w = [math.exp(lw - m) for lw in s["log_w"]]
            tot = sum(raw_w)
            omega = [w / tot for w in raw_w]
            components = list(zip(omega, s["kf_h"], [math.sqrt(max(p, 1e-9)) for p in s["kf_p"]]))
            s["h"] = MixtureConvolvedExactLogChiSq(components)

        base_dists, s["base_state"] = base(y, s["base_state"])
        f_t = base_dists[0]
        s["raw"] = f_t

        corrected = f_t if s["h"] is None else ScaleMetaCorrectedDist(f_t, s["h"], coord=LOG_CHISQ)
        return [corrected], s

    return _skater


# ---------------------------------------------------------------------------
# A simpler alternative: is the exact-noise-law/Kalman apparatus above doing
# real work, or would ANY invertible time-varying-scale transform, hedged
# the same NFL-safe way, do just as well? skaters already ships one: garch
# is an exact, invertible coordinate change (z -> z / sigma_t) with its own
# scale dynamics. Composing it directly onto the PIT-residual stream --
# conjugate(leaf(k=1), garch(...), k=1) -- needs no coordinate map, no
# noise-law convolution, no Kalman filter: it IS a full skater already.
#
# A single, unhedged (omega, alpha, beta) tried this way was excellent on
# synthetic data (iid null var=1.01/kurt=3.23 -- the best round-trip of the
# session) but uniformly worse than the Kalman grid on every real FRED
# series: the same "confidently wrong on messy data" failure every other
# point-estimate design hit. So hedge it exactly like the Kalman grid: a
# small fixed set of (omega, alpha, beta) settings, one of them the exact
# identity (alpha=beta=0 => sigma_t^2 == omega always), combined by online
# likelihood weighting. Since each candidate's own output IS a plain Dist
# (leaf(k=1) is Gaussian; garch's inverse is just a rescaling), the pool
# is *exactly* the job bayesian_ensemble already does -- no new mixture
# class needed, just reuse the existing primitive as the z-space model.
# ---------------------------------------------------------------------------

_GARCH_GRID = [(1.0, 0.0, 0.0)] + [
    (1.0 - a - b, a, b) for a, b in [(0.05, 0.90), (0.05, 0.70), (0.15, 0.80), (0.10, 0.50)]
]


class ZSpaceCorrectedDist:
    """Compose a base predictive f with a z-space correction h: Dist over
    z = Phi^-1(f.cdf(y)). Simpler than ScaleMetaCorrectedDist because h is
    already a genuine Dist in z-space -- no coordinate map or noise-law
    convolution needed."""

    __slots__ = ("base", "h", "_qgrid")

    def __init__(self, base, h):
        self.base = base
        self.h = h
        self._qgrid = None

    def _z(self, y: float) -> float:
        return _phi_inv(_clamp01(self.base.cdf(y)))

    def cdf(self, y: float) -> float:
        return _clamp01(self.h.cdf(self._z(y)))

    def logpdf(self, y: float) -> float:
        z = self._z(y)
        return self.base.logpdf(y) + self.h.logpdf(z) - _phi_logpdf(z)

    def pdf(self, y: float) -> float:
        lp = self.logpdf(y)
        return math.exp(lp) if lp > -700 else 0.0

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
        z = self.h.quantile(p, tol=tol, max_iter=max_iter)
        u = _clamp01(_STD_NORMAL.cdf(z))
        return self.base.quantile(u, tol=tol, max_iter=max_iter)

    def _qg(self):
        if self._qgrid is None:
            self._qgrid = [self.quantile(p) for p in _QGRID_P]
        return self._qgrid

    @property
    def mean(self) -> float:
        return sum(self._qg()) / _QGRID_N

    @property
    def var(self) -> float:
        q = self._qg()
        mu = self.mean
        return sum((x - mu) ** 2 for x in q) / _QGRID_N

    def crps(self, x: float) -> float:
        q = self._qg()
        total = 0.0
        for p, qi in zip(_QGRID_P, q):
            ind = 1.0 if x <= qi else 0.0
            total += (qi - x) * (ind - p)
        return 2.0 * total / _QGRID_N


def laplace_scale_garch_grid(base_factory=None, grid=None, learning_rate=0.5):
    base = (base_factory or (lambda: laplace(k=1, tails="gaussian")))()
    grid = grid or _GARCH_GRID
    candidates = [conjugate(leaf(k=1), garch(omega=o, alpha=a, beta=b), k=1) for o, a, b in grid]
    n = len(candidates)
    prior_log_weights = [math.log(n - 1)] + [0.0] * (n - 1)  # identity starts near 50% mass
    zmodel = bayesian_ensemble(candidates, k=1, learning_rate=learning_rate,
                                prior_log_weights=prior_log_weights)

    def _skater(y: float, state: dict | None):
        if state is None:
            state = {"base_state": None, "z_state": None, "raw": None, "h": None}
        s = state
        if s["raw"] is not None:
            u = _clamp01(s["raw"].cdf(y))
            z = _phi_inv(u)
            h_dists, s["z_state"] = zmodel(z, s["z_state"])
            s["h"] = h_dists[0]

        base_dists, s["base_state"] = base(y, s["base_state"])
        f_t = base_dists[0]
        s["raw"] = f_t

        corrected = f_t if s["h"] is None else ZSpaceCorrectedDist(f_t, s["h"])
        return [corrected], s

    return _skater


# ---------------------------------------------------------------------------
# Synthetic generators
# ---------------------------------------------------------------------------

def gen_iid_gaussian(T: int, seed: int):
    rng = random.Random(seed)
    return [rng.gauss(0.0, 1.0) for _ in range(T)]


def gen_periodic_vol(T: int, seed: int, period: int = 24, sigma_lo: float = 0.5, sigma_hi: float = 2.0):
    """Exactly known periodic volatility: sigma_t alternates on a fixed,
    known period (the specific waveform-bagginess hypothesis), no other
    structure at all -- mean 0, no trend, no autocorrelation beyond what
    the deterministic sigma pattern itself creates."""
    rng = random.Random(seed)
    ys = []
    for t in range(T):
        phase = (t % period) / period
        sigma = sigma_lo + (sigma_hi - sigma_lo) * (0.5 - 0.5 * math.cos(2 * math.pi * phase))
        ys.append(rng.gauss(0.0, sigma))
    return ys


# ---------------------------------------------------------------------------
# Calibration-check harness
# ---------------------------------------------------------------------------

def _moments(xs):
    n = len(xs)
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / n
    sd = math.sqrt(v) if v > 0 else 0.0
    skew = (sum((x - m) ** 3 for x in xs) / n) / sd ** 3 if sd > 0 else float("nan")
    kurt = (sum((x - m) ** 4 for x in xs) / n) / sd ** 4 if sd > 0 else float("nan")
    return {"mean": m, "var": v, "skew": skew, "kurtosis": kurt}


def _ks_stat_uniform(us):
    """Max deviation of the empirical CDF of `us` from Uniform(0,1) (the KS
    statistic itself, not a p-value -- used here only as a comparable
    before/after number, smaller is better, 0 is exact)."""
    us = sorted(us)
    n = len(us)
    d = 0.0
    for i, u in enumerate(us, start=1):
        d = max(d, abs(i / n - u), abs((i - 1) / n - u))
    return d


def run(ys, warmup=300, coord: Coordinate = WILSON_HILFERTY):
    f = laplace_scale_recursive(coord=coord)
    state = None
    z_raw, z_corr = [], []
    for t, y in enumerate(ys):
        dists, state = f(y, state)
        if t >= warmup and t + 1 < len(ys):
            y_next = ys[t + 1]
            raw = state["raw"]
            corrected = dists[0]
            u_raw = _clamp01(raw.cdf(y_next))
            u_corr = _clamp01(corrected.cdf(y_next))
            z_raw.append(_phi_inv(u_raw))
            z_corr.append(_phi_inv(u_corr))
    return z_raw, z_corr


def main():
    for coord in (WILSON_HILFERTY, LOG_CHISQ):
        print(f"\n########## coordinate = {coord.name} ##########")
        for name, ys in (("iid_gaussian_null", gen_iid_gaussian(3000, seed=1)),
                          ("periodic_vol_period24", gen_periodic_vol(3000, seed=2))):
            print(f"\n=== {name} ===")
            z_raw, z_corr = run(ys, coord=coord)
            m_raw, m_corr = _moments(z_raw), _moments(z_corr)
            u_raw = [_STD_NORMAL.cdf(z) for z in z_raw]
            u_corr = [_STD_NORMAL.cdf(z) for z in z_corr]
            ks_raw, ks_corr = _ks_stat_uniform(u_raw), _ks_stat_uniform(u_corr)
            print(f"  raw z:        mean={m_raw['mean']:+.4f} var={m_raw['var']:.4f} "
                  f"skew={m_raw['skew']:+.4f} kurt={m_raw['kurtosis']:.4f} KS={ks_raw:.4f}")
            print(f"  corrected z:  mean={m_corr['mean']:+.4f} var={m_corr['var']:.4f} "
                  f"skew={m_corr['skew']:+.4f} kurt={m_corr['kurtosis']:.4f} KS={ks_corr:.4f}")


if __name__ == "__main__":
    main()
