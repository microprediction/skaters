"""Projected-transition-operator recalibration of a base forecaster's PIT
stream, per Peter Cotton's homogenization write-up (2026-08-10 note): the
"first prototype" of Section 11 -- Legendre basis (psi1, psi2), one lag, the
positivity-preserving exponential family of Section 4, fit by penalized
conditional MLE.

Reduced form. The object being estimated is not the microscopic process Y;
it is a low-dimensional summary of the transition operator of the base
model's *calibrated* PIT stream. Concretely:

    U0_t = F0_t(Y_t)                          raw PIT
    U_t  = G(U0_t)                            statically calibrated PIT
    psi(u) = (sqrt(3)(2u-1), sqrt(5)(6u^2-6u+1))   Legendre location/tail modes

    q_theta(v | u) = exp(psi(v)^T Theta psi(u)) / Z_theta(u)
    Z_theta(u)     = integral_0^1 exp(psi(s)^T Theta psi(u)) ds

Theta = 0 is the fast-mixing/IID-uniform limit (ordinary conformal
calibration); shrinkage toward Theta=0 in the fit is not a regularization
convenience, it is the null hypothesis this whole exercise is testing
against. The four entries of Theta have direct interpretations (see the
note): theta11 location persistence, theta22 tail/volatility persistence,
theta12 volatility state -> next signed error, theta21 signed error ->
next volatility state (the leverage-type cross term).

This module is pure z-space / u-space: no Dist, no skater, matching the
staged-rollout discipline already used for cell_model.py and
two_state_recalibrate.py in this same folder -- prove there is exploitable
structure on saved PIT streams first (Section 10's decisive test), before
building the Dist-composition wrapper.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize

SQ3 = np.sqrt(3.0)
SQ5 = np.sqrt(5.0)
_EPS = 1e-9


def psi(u):
    """u: scalar or array in [0,1]. Returns shape (2,) or (2, N)."""
    u = np.asarray(u, dtype=float)
    psi1 = SQ3 * (2.0 * u - 1.0)
    psi2 = SQ5 * (6.0 * u * u - 6.0 * u + 1.0)
    return np.stack([psi1, psi2], axis=0)


def Psi(u):
    """Antiderivatives of psi (Section 3), for the linear-expansion
    diagnostic only -- not used by the exponential-family fit/CDF, which
    integrates numerically instead."""
    u = np.asarray(u, dtype=float)
    Psi1 = SQ3 * (u * u - u)
    Psi2 = SQ5 * (2.0 * u ** 3 - 3.0 * u * u + u)
    return np.stack([Psi1, Psi2], axis=0)


# ---------------------------------------------------------------------------
# Gauss-Legendre quadrature, rescaled to an arbitrary [a, b] (used both for
# the full normalizer Z_theta(u) on [0,1] and for the cumulative C_t(u) on
# [0, u]) -- exact for polynomial integrands up to degree 2n-1, and the
# integrand here (exp of a quadratic) is smooth enough that n=48 is ample.
# ---------------------------------------------------------------------------

_GL_N = 48
_gl_x, _gl_w = np.polynomial.legendre.leggauss(_GL_N)


def _gauss_legendre_on(a: float, b: float):
    half = 0.5 * (b - a)
    nodes = half * _gl_x + 0.5 * (a + b)
    weights = half * _gl_w
    return nodes, weights


_Z01_NODES, _Z01_WEIGHTS = _gauss_legendre_on(0.0, 1.0)
_PSI_Z01 = psi(_Z01_NODES)  # (2, _GL_N), fixed nodes for the full [0,1] integral


def log_Z(theta: np.ndarray, psi_u: np.ndarray) -> np.ndarray:
    """log integral_0^1 exp(psi(s)^T theta psi(u)) ds, vectorized over a
    batch of contexts psi_u (shape (2, N)) -> shape (N,)."""
    w = theta @ psi_u  # (2, N)
    exponent = w.T @ _PSI_Z01  # (N, _GL_N)
    m = exponent.max(axis=1, keepdims=True)
    z = np.sum(_Z01_WEIGHTS[None, :] * np.exp(exponent - m), axis=1)
    return m[:, 0] + np.log(z)


def logpdf(v, u, theta: np.ndarray) -> np.ndarray:
    """log q_theta(v | u), vectorized."""
    psi_v, psi_u = psi(v), psi(u)
    w = theta @ psi_u  # (2, N) if u is a batch, else (2,)
    lin = np.sum(w * psi_v, axis=0)
    return lin - log_Z(theta, psi_u if psi_u.ndim == 2 else psi_u[:, None])


def cdf(v: float, u: float, theta: np.ndarray) -> float:
    """C_t(v) = integral_0^v q_theta(s | u) ds, single (u, theta)."""
    psi_u = psi(u)[:, None]
    w = (theta @ psi_u)[:, 0]  # (2,)
    logZ = log_Z(theta, psi_u)[0]
    if v <= 0.0:
        return 0.0
    if v >= 1.0:
        return 1.0
    nodes, weights = _gauss_legendre_on(0.0, v)
    exponent = w @ psi(nodes)  # (n,)
    m = exponent.max()
    return float(np.exp(m - logZ) * np.sum(weights * np.exp(exponent - m)))


def quantile(p: float, u: float, theta: np.ndarray, tol: float = 1e-10, max_iter: int = 100) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if cdf(mid, u, theta) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Static PIT calibration G: a monotone piecewise-linear map fit once on a
# training block's raw PIT values, mirroring gaussianize's own "minimal
# smoothing that makes the fence-post transform invertible" idiom (order
# statistics at (i+0.5)/n, linearly interpolated, identity-extended past
# the observed range so G stays a bijection on all of [0,1]).
# ---------------------------------------------------------------------------

class StaticG:
    __slots__ = ("_xs", "_ps")

    def __init__(self, u0_values):
        xs = np.sort(np.asarray(u0_values, dtype=float))
        n = len(xs)
        ps = (np.arange(n) + 0.5) / n
        self._xs = xs
        self._ps = ps

    def __call__(self, u0):
        p = np.interp(u0, self._xs, self._ps, left=0.0, right=1.0)
        return float(np.clip(p, _EPS, 1.0 - _EPS))


# ---------------------------------------------------------------------------
# Penalized conditional MLE fit of Theta on a training block.
# ---------------------------------------------------------------------------

def fit_theta(u_values, ridge: float = 1.0) -> np.ndarray:
    """u_values: calibrated PITs U_1..U_n (already through G). Fits Theta on
    consecutive pairs (U_{t-1}, U_t), t=2..n, by penalized MLE, shrinking
    toward Theta=0 (the fast-mixing/IID null) via an L2 penalty."""
    u = np.clip(np.asarray(u_values, dtype=float), _EPS, 1.0 - _EPS)
    psi_v = psi(u[1:])   # (2, N)
    psi_u = psi(u[:-1])  # (2, N)

    def neg_pen_loglik(theta_flat):
        theta = theta_flat.reshape(2, 2)
        w = theta @ psi_u  # (2, N)
        lin = np.sum(w * psi_v, axis=0)
        logZ = log_Z(theta, psi_u)
        ll = np.sum(lin - logZ)
        penalty = ridge * np.sum(theta * theta)
        return -(ll) + penalty

    res = minimize(neg_pen_loglik, x0=np.zeros(4), method="BFGS")
    return res.x.reshape(2, 2)


# ---------------------------------------------------------------------------
# Section 10's decisive test: mean held-out conditional log-score gain of
# q_theta over the null (q=1, ordinary uniform-PIT calibration), plus the
# checklist diagnostics.
# ---------------------------------------------------------------------------

def held_out_D(u_values, theta: np.ndarray) -> float:
    u = np.clip(np.asarray(u_values, dtype=float), _EPS, 1.0 - _EPS)
    ll = logpdf(u[1:], u[:-1], theta)
    return float(np.mean(ll))


def mode_autocorr(u_values, lag: int = 1):
    """Lag-l autocorrelation of psi1(U_t), psi2(U_t) -- the "removes lagged
    dependence in the signed and volatility PIT modes" checklist item."""
    u = np.clip(np.asarray(u_values, dtype=float), _EPS, 1.0 - _EPS)
    p = psi(u)  # (2, N)
    out = []
    for k in range(2):
        x = p[k]
        x0, x1 = x[:-lag], x[lag:]
        c = np.corrcoef(x0, x1)[0, 1]
        out.append(float(c))
    return tuple(out)


# ---------------------------------------------------------------------------
# Synthetic validation: null case (no structure to find) and a planted
# tail/volatility-persistence effect (theta22 > 0), simulated by drawing
# directly from q_theta itself via inverse-CDF sampling.
# ---------------------------------------------------------------------------

def simulate_chain(n: int, theta_true: np.ndarray, seed: int, u0: float = 0.5):
    rng = np.random.default_rng(seed)
    us = np.empty(n)
    u_prev = u0
    for t in range(n):
        p = rng.uniform(0.0, 1.0)
        u_prev = quantile(p, u_prev, theta_true)
        us[t] = u_prev
    return us


def main():
    print("--- null case: iid uniform, train/test split ---")
    rng = np.random.default_rng(2)
    u_all = rng.uniform(0.0, 1.0, size=4000)
    u_train, u_test = u_all[:2000], u_all[2000:]
    theta_hat = fit_theta(u_train, ridge=1.0)
    print("fitted theta:\n", theta_hat)
    print("held-out D (should be ~0):", held_out_D(u_test, theta_hat))

    print("\n--- planted effect: persistent tail/volatility mode (theta22=1.2) ---")
    theta_true = np.array([[0.0, 0.0], [0.0, 1.2]])
    u_all2 = simulate_chain(4000, theta_true, seed=7)
    u_train2, u_test2 = u_all2[:2000], u_all2[2000:]
    theta_hat2 = fit_theta(u_train2, ridge=1.0)
    print("true theta:\n", theta_true)
    print("fitted theta (train):\n", theta_hat2)
    print("held-out D:", held_out_D(u_test2, theta_hat2))

    v_test = np.array([cdf(u_test2[t], u_test2[t - 1], theta_hat2) for t in range(1, len(u_test2))])
    print("mode autocorr BEFORE correction (psi1,psi2):", mode_autocorr(u_test2[1:]))
    print("mode autocorr AFTER correction  (psi1,psi2):", mode_autocorr(v_test))


if __name__ == "__main__":
    main()
