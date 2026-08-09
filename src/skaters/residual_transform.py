"""Online residual-transform wrapper: learn to reshape a skater's own errors.

Every skater already resolves each arriving point against the prediction made
*for it* (see ``parade.py``): the PIT value ``u_t = F_{t-1}(y_t)`` and its
Gaussian-coordinate form ``z_t = Phi^-1(u_t)``. If the base skater is well
specified, ``z_t`` behaves like iid N(0,1). This module asks whether that
residual stream carries information a small online model can exploit to
reshape the *next* predictive distribution -- not by touching the base
skater, but by learning a monotone correction in ``z``-space and composing it
with whatever ``Dist`` the base skater already produced.

Given the base forecast ``F_t`` for ``y_{t+1}`` and a residual model ``H_t``
(a predictive distribution for ``z_{t+1}``, learned from ``z_1..z_t``), the
corrected forecast is

    F~_t(y) = H_t(Phi^-1(F_t(y)))
    Q~_t(p) = F_t.quantile(Phi(H_t.quantile(p)))

both closed-form once ``H_t`` has a closed-form cdf/quantile, so no
interpolation table is needed (contrast ``pushforward.py``, which needs one
because its map has no closed inverse in general). :class:`CorrectedDist`
implements this composition exactly for ``cdf``/``pdf``/``logpdf``/
``quantile``, and via a fixed quantile-grid quadrature for ``mean``/``std``/
``crps`` (no closed form for those in general).

Nested models (a deliberately narrow first cut -- see the residual-transform
research note):

    M0  identity            H_t = N(0, 1)                         (no learning)
    M1  dynamic scale       H_t = N(0, exp(ell_t)),  ell_{t+1} = a*ell_t + c*(z_t^2-1)
    M2  + leverage          ell_{t+1} = a*ell_t + b*z_t + c*(z_t^2-1)

M2 vs M1 is the cleanest test of a leverage-type effect: does the *sign* of
today's error predict tomorrow's error *magnitude*? ``a``, ``b``, ``c`` are
learned online by one step of gradient descent on ``-log h_t(z_{t+1})`` per
tick, via a real-time-recurrent-learning-lite sensitivity filter (the
recursion depends on only the previous step, so the exact parameter gradient
is a single extra O(1) state per parameter -- no batch refitting, matching
the rest of this library's "online only" discipline). The alternative
EWMA/moment approach is kept as a diagnostic (:class:`ResidualDiagnostics`,
the ``L_k`` leverage statistic) rather than a second learner.
"""

from __future__ import annotations
import math
from collections import deque, namedtuple
from skaters.dist import Dist

_STD_NORMAL = Dist.gaussian(0.0, 1.0)
_EPS = 1e-12
_LOG_SQRT2PI = math.log(math.sqrt(2.0 * math.pi))

# Learner stability bounds
_A_MIN, _A_MAX = 0.0, 0.995
_BC_MAX = 3.0
_ELL_MIN, _ELL_MAX = -20.0, 20.0
_SENS_MAX = 50.0
# Bounded loss gradient (the same "mixability" trick bayesian_ensemble.py uses
# on logpdf): an outlier z makes grad_ell = 0.5 - 0.5*z^2*exp(-ell) unbounded,
# and one huge SGD step can blow the (a, b, c) estimates onto their clip
# bounds and never recover. Clipping the gradient keeps every step bounded
# regardless of how surprising a single observation is.
_GRAD_MAX = 3.0

# Quantile-grid quadrature for mean/var/crps (midpoint rule on p in (0,1);
# avoids the p -> {0,1} endpoints where quantiles diverge, and needs no
# tabulated high-precision node/weight constants).
_QGRID_N = 32
_QGRID_P = [(i + 0.5) / _QGRID_N for i in range(_QGRID_N)]
_QGRID_W = 1.0 / _QGRID_N


def _phi(z: float) -> float:
    """Standard normal density."""
    return math.exp(-0.5 * z * z - _LOG_SQRT2PI)


def _phi_inv(p: float) -> float:
    """Standard normal quantile (bisection, same idiom as parade.py)."""
    return _STD_NORMAL.quantile(p)


def _clamp01(u: float) -> float:
    return min(max(u, _EPS), 1.0 - _EPS)


# ---------------------------------------------------------------------------
# Transformation families: H_t as three pure functions of (z or p, theta).
# theta is a plain dict; each family reads only the keys it needs, so a
# richer family (e.g. a future sinh-arcsinh skew/tail family) plugs in
# without touching CorrectedDist.
# ---------------------------------------------------------------------------

Family = namedtuple("Family", ["cdf", "quantile", "logpdf"])


def _identity_cdf(z: float, theta: dict) -> float:
    return _STD_NORMAL.cdf(z)


def _identity_quantile(p: float, theta: dict) -> float:
    return _phi_inv(p)


def _identity_logpdf(z: float, theta: dict) -> float:
    return -0.5 * z * z - _LOG_SQRT2PI


IDENTITY_FAMILY = Family(_identity_cdf, _identity_quantile, _identity_logpdf)


def _gss_cdf(z: float, theta: dict) -> float:
    sigma = math.exp(0.5 * theta["ell"])
    return _STD_NORMAL.cdf((z - theta["m"]) / sigma)


def _gss_quantile(p: float, theta: dict) -> float:
    sigma = math.exp(0.5 * theta["ell"])
    return theta["m"] + sigma * _phi_inv(p)


def _gss_logpdf(z: float, theta: dict) -> float:
    sigma = math.exp(0.5 * theta["ell"])
    zz = (z - theta["m"]) / sigma
    return -0.5 * zz * zz - math.log(sigma) - _LOG_SQRT2PI


GAUSSIAN_SHIFT_SCALE_FAMILY = Family(_gss_cdf, _gss_quantile, _gss_logpdf)


# ---------------------------------------------------------------------------
# CorrectedDist: F~_t = H_t[Phi^-1(F_t(.))], exact composition
# ---------------------------------------------------------------------------

class CorrectedDist:
    """The base predictive ``base`` reshaped by residual model ``family(theta)``.

    Duck-types the ``Dist`` query surface (cdf/pdf/logpdf/quantile/mean/std/
    crps) so it can be scored and inspected exactly like a plain ``Dist``.
    """

    __slots__ = ("base", "family", "theta", "_qgrid")

    def __init__(self, base, family: Family, theta: dict):
        self.base = base
        self.family = family
        self.theta = theta
        self._qgrid = None

    def _z(self, y: float) -> float:
        u = _clamp01(self.base.cdf(y))
        return _phi_inv(u)

    def cdf(self, y: float) -> float:
        return self.family.cdf(self._z(y), self.theta)

    def logpdf(self, y: float) -> float:
        z = self._z(y)
        # chain rule: log f~(y) = log f(y) + log h(z) - log phi(z)
        return self.base.logpdf(y) + self.family.logpdf(z, self.theta) + 0.5 * z * z + _LOG_SQRT2PI

    def pdf(self, y: float) -> float:
        lp = self.logpdf(y)
        return math.exp(lp) if lp > -700.0 else 0.0

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
        assert 0 < p < 1
        hp = self.family.quantile(p, self.theta)
        u = _clamp01(_STD_NORMAL.cdf(hp))
        return self.base.quantile(u, tol=tol, max_iter=max_iter)

    def _quantile_grid(self) -> list:
        if self._qgrid is None:
            self._qgrid = [self.quantile(p) for p in _QGRID_P]
        return self._qgrid

    @property
    def mean(self) -> float:
        q = self._quantile_grid()
        return sum(q) * _QGRID_W

    @property
    def var(self) -> float:
        q = self._quantile_grid()
        mu = self.mean
        return sum((qi - mu) ** 2 for qi in q) * _QGRID_W

    @property
    def std(self) -> float:
        v = self.var
        return math.sqrt(v) if v > 0 else 0.0

    def crps(self, x: float) -> float:
        """CRPS via the quantile-form identity (Gneiting & Raftery 2007):

            CRPS(F, x) = 2 * integral_0^1 (Q(p) - x) * (1{x <= Q(p)} - p) dp
        """
        q = self._quantile_grid()
        total = 0.0
        for p, qi in zip(_QGRID_P, q):
            ind = 1.0 if x <= qi else 0.0
            total += (qi - x) * (ind - p)
        return 2.0 * total * _QGRID_W

    def __repr__(self) -> str:
        return f"CorrectedDist(theta={self.theta!r}, base={self.base!r})"


# ---------------------------------------------------------------------------
# RTRL-lite online learners for M1 (scale) / M2 (scale + leverage)
# ---------------------------------------------------------------------------

_RMS_RHO = 0.01     # EWMA rate for the per-parameter squared-gradient scale
_RMS_EPS = 1e-6


def _init_scale_learner(learn_b: bool) -> dict:
    state = {"ell": 0.0, "a": 0.5, "c": 0.05, "ea": 0.0, "ec": 0.0, "g2a": 0.0, "g2c": 0.0}
    if learn_b:
        state["b"] = 0.0
        state["eb"] = 0.0
        state["g2b"] = 0.0
    return state


def _clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)


def _rms_step(lr: float, grad: float, g2_prev: float) -> tuple[float, float]:
    """One RMSProp-normalized step: the raw parameter gradient here is
    grad_ell * sensitivity, whose scale swings wildly with the current
    sensitivity (itself driven by how persistent `a` currently is), so a
    fixed-size SGD step is either too timid or unstable depending on regime.
    Normalizing by a running RMS of the gradient keeps every step ~lr in
    size regardless of that swing (the standard RMSProp fix for exactly
    this kind of ill-conditioned, time-varying gradient scale)."""
    g2_new = (1.0 - _RMS_RHO) * g2_prev + _RMS_RHO * grad * grad
    step = lr * grad / math.sqrt(g2_new + _RMS_EPS)
    return step, g2_new


def _update_scale_learner(state: dict, z: float, lr: float, learn_b: bool) -> dict:
    ell_prev = state["ell"]
    a, c = state["a"], state["c"]
    b = state.get("b", 0.0)

    # d(-log h)/d(ell), h = N(0, exp(ell_prev)):  0.5 - 0.5*z^2*exp(-ell_prev)
    grad_ell = _clip(0.5 - 0.5 * z * z * math.exp(-ell_prev), -_GRAD_MAX, _GRAD_MAX)

    step_a, g2a_new = _rms_step(lr, grad_ell * state["ea"], state["g2a"])
    step_c, g2c_new = _rms_step(lr, grad_ell * state["ec"], state["g2c"])
    a_new = _clip(a - step_a, _A_MIN, _A_MAX)
    c_new = _clip(c - step_c, -_BC_MAX, _BC_MAX)
    if learn_b:
        step_b, g2b_new = _rms_step(lr, grad_ell * state["eb"], state["g2b"])
        b_new = _clip(b - step_b, -_BC_MAX, _BC_MAX)
    else:
        b_new = 0.0

    ea_new = _clip(ell_prev + a_new * state["ea"], -_SENS_MAX, _SENS_MAX)
    ec_new = _clip((z * z - 1.0) + a_new * state["ec"], -_SENS_MAX, _SENS_MAX)

    ell_new = _clip(a_new * ell_prev + b_new * z + c_new * (z * z - 1.0), _ELL_MIN, _ELL_MAX)

    new_state = {"ell": ell_new, "a": a_new, "c": c_new, "ea": ea_new, "ec": ec_new,
                 "g2a": g2a_new, "g2c": g2c_new}
    if learn_b:
        eb_new = _clip(z + a_new * state["eb"], -_SENS_MAX, _SENS_MAX)
        new_state["b"] = b_new
        new_state["eb"] = eb_new
        new_state["g2b"] = g2b_new
    return new_state


def _theta_of(model: str, learner: dict) -> dict:
    if model == "m0":
        return {"m": 0.0, "ell": 0.0}
    theta = {"m": 0.0, "ell": learner["ell"], "a": learner["a"], "c": learner["c"]}
    if model == "m2":
        theta["b"] = learner["b"]
    return theta


_MODELS = ("m0", "m1", "m2")


# ---------------------------------------------------------------------------
# The wrapper
# ---------------------------------------------------------------------------

def residual_transform(base, model: str = "m2", lr: float = 0.01, k: int = 1):
    """Wrap a k=1 skater with an online residual-transform correction.

    Args:
        base: a k=1 skater callable, ``(y, state) -> (list[Dist], state)``.
        model: "m0" (identity, pass-through), "m1" (dynamic scale), or
            "m2" (dynamic scale + leverage). See the module docstring.
        lr: SGD learning rate for the online (a, b, c) update. Ignored for m0.
        k: forecast horizon of ``base``; only k=1 is supported.

    Returns:
        A skater callable ``(y, state) -> ([CorrectedDist], state)``. The
        returned state additionally carries, mirroring ``parade.py``'s
        naming:

        state["z"]     resolved z_t = Phi^-1(F_{t-1}(y_t)), None until the
                       first base forecast has matured (first tick only).
        state["raw"]   F_t, the base skater's own (uncorrected) forecast for
                       y_{t+1} -- lets M0/M1/M2 be compared against the
                       identical base-skater trajectory.
        state["theta"] the H_t parameters used to build the returned
                       CorrectedDist (includes the learned a/b/c for m1/m2).
    """
    assert k == 1, "residual_transform currently supports k=1 only"
    assert model in _MODELS, f"model must be one of {_MODELS}, got {model!r}"
    learn_b = model == "m2"
    family = IDENTITY_FAMILY if model == "m0" else GAUSSIAN_SHIFT_SCALE_FAMILY

    def _skater(y: float, state: dict | None) -> tuple[list, dict]:
        if state is None:
            learner0 = None if model == "m0" else _init_scale_learner(learn_b)
            state = {
                "base": None,
                "raw": None,
                "z": None,
                "learner": learner0,
                "theta": _theta_of(model, learner0 or {}),
            }

        z = None
        if state["raw"] is not None:
            u = _clamp01(state["raw"].cdf(y))
            z = _phi_inv(u)
            if model != "m0":
                state["learner"] = _update_scale_learner(state["learner"], z, lr, learn_b)
        state["z"] = z

        dists, state["base"] = base(y, state["base"])
        f_t = dists[0]
        state["raw"] = f_t

        theta = _theta_of(model, state["learner"] if model != "m0" else {})
        state["theta"] = theta
        corrected = CorrectedDist(f_t, family, theta)
        return [corrected], state

    _skater.__name__ = f"residual_transform({getattr(base, '__name__', '?')}, model={model})"
    return _skater


# ---------------------------------------------------------------------------
# Diagnostics: online EWMA moments and the leverage statistic L_k (section 6)
# ---------------------------------------------------------------------------

class ResidualDiagnostics:
    """Online EWMA diagnostics on a z-stream: moments and the leverage
    statistic ``L_k = E[z_t (z_{t+k}^2 - 1)]`` for k = 1..K.

    A diagnostic only (spec section 6/8A) -- it does not drive any learner
    in this module; feed it ``state["z"]`` from :func:`residual_transform`
    (or from ``parade``) to check Hypotheses 1-2 independent of any model.
    """

    def __init__(self, K: int = 5, halflife: float = 50.0):
        self.K = K
        self._alpha = 1.0 - 0.5 ** (1.0 / halflife)
        self.n = 0
        self.m1 = self.m2 = self.m3 = self.m4 = 0.0
        self._buf = deque(maxlen=K)
        self._L = [0.0] * K
        self._cross_sq = [0.0] * K

    def update(self, z: float) -> None:
        self.n += 1
        a = self._alpha if self._alpha > 1.0 / self.n else 1.0 / self.n
        z2 = z * z
        self.m1 = (1 - a) * self.m1 + a * z
        self.m2 = (1 - a) * self.m2 + a * z2
        self.m3 = (1 - a) * self.m3 + a * z * z2
        self.m4 = (1 - a) * self.m4 + a * z2 * z2
        for lag in range(1, self.K + 1):
            if len(self._buf) >= lag:
                z_lag = self._buf[-lag]
                self._L[lag - 1] = (1 - a) * self._L[lag - 1] + a * z_lag * (z2 - 1.0)
                self._cross_sq[lag - 1] = (1 - a) * self._cross_sq[lag - 1] + a * z_lag * z_lag * z2
        self._buf.append(z)

    def summary(self) -> dict:
        return {
            "n": self.n,
            "E[z]": self.m1, "E[z2]": self.m2, "E[z3]": self.m3, "E[z4]": self.m4,
            "L": list(self._L),
            "cross_sq": list(self._cross_sq),
        }
