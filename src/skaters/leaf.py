"""Residual distribution estimator: the leaf of every prediction tree.

The leaf sits at the bottom of a chain of transforms. It receives
(approximately) stationary residuals and estimates their distribution
online. It returns a Dist for each horizon.

This is the only node that "creates" distributional predictions.
Everything above it (transforms, conjugation, ensemble) just
propagates and combines Dists.
"""

from __future__ import annotations
import math
from skaters.dist import Dist
from skaters.runstats import running_var_init, running_var_update, running_var_get


def leaf(k: int = 1):
    """Centered Gaussian residual model.

    Assumes the input is approximately mean-zero residuals (after
    transforms have removed structure). Estimates variance online
    via Welford's algorithm.

    Returns Dist.gaussian(0, sigma) for each horizon. The zero mean
    reflects the assumption that transforms have removed the signal;
    the sigma reflects how much noise is left.
    """

    def _leaf(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {"var": running_var_init()}

        state["var"] = running_var_update(state["var"], y)
        _, var = running_var_get(state["var"])

        if math.isfinite(var) and var > 0:
            std = math.sqrt(var)
        else:
            # Bootstrap: use |y| as a rough scale estimate until we have data
            std = max(abs(y), 1e-8)

        d = Dist.gaussian(0.0, std)
        return [d] * k, state

    _leaf.__name__ = f"leaf(k={k})"
    return _leaf


_SCALE_BASIS = (0.7, 1.0, 1.6, 3.0, 6.0)


def scale_mixture_leaf(k: int = 1, gamma: float = 0.02, scale_alpha: float = 0.01,
                       scales: tuple = _SCALE_BASIS):
    """Residual model as a fixed Gaussian scale mixture, weights fit online.

    The plain :func:`leaf` emits a single Gaussian ``N(0, sigma)``. This emits
    a mixture ``sum_i w_i N(0, c_i * sigma)`` over a *fixed* dictionary of
    scales ``c_i`` (relative to the running scale), with the weights learned
    online by likelihood via recency-weighted EM. A Student-t — and most
    heavy-tailed natural data (returns, stochastic volatility) — *is* a
    Gaussian scale mixture, so this approximates it by construction, while
    staying a plain :class:`Dist` (the means are all 0).

    The weights are the "discrepancy from N(0,1)": all mass on ``c=1`` is a
    Gaussian (no cost on light-tailed data); mass bleeding into larger ``c``
    is heavier tails. Because every component shares the same mean, mixing
    *fattens* rather than *flattens*, so — unlike adding heavy leaves to the
    candidate pool — the shape survives into the ensemble.

    Judged by held-out log-likelihood it matches the Gaussian leaf on normal
    data and beats it as tails fatten (e.g. ~+0.13 nats on Student-t3).

    Args:
        k: forecast horizon.
        gamma: recency rate for the online-EM weight update (handles drift).
        scale_alpha: EWMA rate for the residual variance. Recency-weighted (a
            1/n bootstrap makes it Welford-like early), so the *scale* tracks
            drift as the weights track the *shape*.
        scales: the fixed scale dictionary, relative to the running scale.
    """
    C = tuple(scales)
    K = len(C)
    one_idx = min(range(K), key=lambda i: abs(C[i] - 1.0))  # start ~Gaussian

    def _leaf(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            w = [1e-6] * K
            w[one_idx] = 1.0
            state = {"v": 0.0, "w": w, "n": 0}

        state["n"] += 1
        a = scale_alpha if scale_alpha > 1.0 / state["n"] else 1.0 / state["n"]
        state["v"] = (1 - a) * state["v"] + a * y * y  # EWMA of E[residual^2]
        var = state["v"]

        sigma = math.sqrt(var) if (math.isfinite(var) and var > 0) else max(abs(y), 1e-8)
        z = y / sigma
        w = state["w"]
        dens = [w[i] * math.exp(-0.5 * z * z / (C[i] * C[i])) / C[i] for i in range(K)]
        total = sum(dens)
        if total > 0:
            g = gamma if gamma > 1.0 / state["n"] else 1.0 / state["n"]
            state["w"] = [(1 - g) * w[i] + g * dens[i] / total for i in range(K)]

        d = Dist([(state["w"][i], 0.0, C[i] * sigma) for i in range(K)])
        return [d] * k, state

    _leaf.__name__ = f"scale_mixture_leaf(k={k})"
    return _leaf


# ---------------------------------------------------------------------------
# CRPS leaf: same scale-mixture form, weights fit by online CRPS-gradient
# ---------------------------------------------------------------------------

_S2 = math.sqrt(2.0)
_INV = 1.0 / math.sqrt(2.0 * math.pi)
_A0 = 2.0 * _INV  # A(0, s) = 2 phi(0) s


def _Phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / _S2))


def _phi(x: float) -> float:
    return math.exp(-0.5 * x * x) * _INV


def _abs_normal(m: float, s: float) -> float:
    """E|N(m, s^2)| = m(2Phi(m/s) - 1) + 2s phi(m/s)."""
    if s <= 0:
        return abs(m)
    z = m / s
    return m * (2.0 * _Phi(z) - 1.0) + 2.0 * s * _phi(z)


FINE = tuple(round(0.4 * 1.28 ** i, 4) for i in range(15))  # log-spaced scale basis


def crps_leaf(k: int = 1, eta: float = 1.0, scale_alpha: float = 0.01, scales: tuple = FINE):
    """Residual model as a scale mixture, weights fit by online **CRPS**-gradient.

    Identical in form to :func:`scale_mixture_leaf` — a fixed dictionary of
    zero-mean Gaussian scales with online weights — but the *objective* is
    swapped: exponentiated-gradient descent on the simplex minimizing the
    closed-form mixture CRPS, instead of likelihood-EM. The mixture CRPS has a
    closed form (sums of ``E|N(m, s^2)|``), so its gradient w.r.t. each weight
    is exact.

    This is the "conform last" leaf — put it at the bottom of a
    likelihood-weighted ensemble (``model first``) and the predictive matches a
    CRPS specialist on CRPS while keeping, even slightly improving, likelihood
    on heavy-tailed data. On idealised light-tailed (Gaussian) data it costs a
    few thousandths of a nat versus the likelihood leaf.

    Args:
        k: forecast horizon.
        eta: exponentiated-gradient learning rate.
        scale_alpha: EWMA rate for the residual variance (Welford-like early).
        scales: the fixed scale dictionary, relative to the running scale.
    """
    C = tuple(scales)
    K = len(C)
    # pairwise A(0, sqrt(c_a^2 + c_b^2)) for the CRPS gradient's second term
    B = [[math.sqrt(C[a] * C[a] + C[b] * C[b]) * _A0 for b in range(K)] for a in range(K)]
    one_idx = min(range(K), key=lambda i: abs(C[i] - 1.0))

    def _leaf(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            w = [1e-6] * K
            w[one_idx] = 1.0
            state = {"v": 0.0, "w": w, "n": 0}
        state["n"] += 1
        a = scale_alpha if scale_alpha > 1.0 / state["n"] else 1.0 / state["n"]
        state["v"] = (1 - a) * state["v"] + a * y * y
        sig = math.sqrt(state["v"]) if (math.isfinite(state["v"]) and state["v"] > 0) else max(abs(y), 1e-8)
        z = y / sig
        w = state["w"]
        g = [_abs_normal(-z, C[c]) - sum(w[j] * B[c][j] for j in range(K)) for c in range(K)]
        gm = sum(g) / K
        # Exponentiated-gradient step, stabilized by subtracting the max exponent
        # so exp() cannot overflow to inf (which would normalize to nan weights
        # and crash Dist). Subtracting a constant from every exponent leaves the
        # normalized weights unchanged.
        e = [-eta * (g[c] - gm) for c in range(K)]
        emax = max(e)
        nw = [w[c] * math.exp(e[c] - emax) for c in range(K)]
        Z = sum(nw)
        if not (Z > 0.0 and math.isfinite(Z)):
            nw = list(w)  # degenerate update: keep the current weights
            Z = sum(nw)
        state["w"] = [x / Z for x in nw]
        d = Dist([(state["w"][c], 0.0, C[c] * sig) for c in range(K)])
        return [d] * k, state

    _leaf.__name__ = f"crps_leaf(k={k}, eta={eta})"
    return _leaf


# ---------------------------------------------------------------------------
# GARCH(1,1)-t leaf: same scale-mixture tails, but a genuine GARCH conditional
# variance instead of the EWMA/IGARCH scale of scale_mixture_leaf.
# ---------------------------------------------------------------------------

_GARCH_AB_GRID = [(a, b) for a in (0.02, 0.04, 0.06, 0.09, 0.12, 0.16, 0.20)
                  for b in (0.72, 0.78, 0.84, 0.88, 0.92, 0.95, 0.97) if a + b < 0.999]
# omega multipliers on the variance-targeted base (free omega vs pure targeting).
_GARCH_OMEGA_MULT = (0.5, 0.7, 1.0, 1.4, 2.0)


def garch_leaf(k: int = 1, gamma: float = 0.02, refit_every: int = 40,
               min_obs: int = 80, window: int = 400, scales: tuple = _SCALE_BASIS):
    """Terminal leaf with a GARCH(1,1) conditional variance and Student-t tails.

    Generalizes :func:`scale_mixture_leaf`. That leaf tracks scale with an EWMA of
    squared residuals — RiskMetrics / IGARCH, the ``omega=0, alpha+beta=1`` corner
    with no variance mean-reversion. ``garch_leaf`` instead runs a genuine GARCH
    recursion ``h_t = omega + alpha r_{t-1}^2 + beta h_{t-1}`` with ``(alpha, beta)``
    refit periodically by **variance-targeted** Gaussian QMLE (``omega = (1 - alpha
    - beta) * S^2`` over a trailing window), keeping the same fixed Gaussian
    scale-mixture (a scale mixture *is* a Student-t) for the tails. EWMA is the
    ``alpha+beta=1`` corner, so this strictly generalizes the EWMA leaf.

    Drop-in for the terminal-leaf slot (``leaf_fn``) of :func:`laplace`; pass it as
    ``laplace(leaf=garch_leaf)``. On price/return series, where volatility clusters
    but *reverts*, it recovers about half of the log-likelihood gap to a fitted
    GARCH(1,1)-t and is neutral-to-positive elsewhere (see
    ``benchmarks/garch_leaf_threeway.py``).

    Args:
        k: forecast horizon.
        gamma: recency rate for the online-EM tail-weight update.
        refit_every: steps between ``(alpha, beta)`` refits.
        min_obs: observations before the first refit.
        window: trailing window (observations) used for the refit.
        scales: the fixed scale dictionary, relative to the conditional sd.
    """
    from collections import deque
    C = tuple(scales)
    K = len(C)
    one_idx = min(range(K), key=lambda i: abs(C[i] - 1.0))

    def _leaf(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            w = [1e-6] * K
            w[one_idx] = 1.0
            state = {"h": 0.0, "s2": 0.0, "n": 0, "omega": 0.0, "alpha": 0.05,
                     "beta": 0.90, "buf": deque(maxlen=window), "w": w, "last_r2": 0.0}
        s = state
        s["n"] += 1
        a0 = 0.02 if 0.02 > 1.0 / s["n"] else 1.0 / s["n"]
        s["s2"] = (1 - a0) * s["s2"] + a0 * y * y
        if s["s2"] <= 0:
            s["s2"] = max(y * y, 1e-12)

        if s["n"] == 1:
            h = s["s2"]
        else:
            h = s["omega"] + s["alpha"] * s["last_r2"] + s["beta"] * s["h"]
        if h <= 1e-300:
            h = s["s2"]
        s["h"] = h
        s["last_r2"] = y * y
        s["buf"].append(y)

        if s["n"] >= min_obs and s["n"] % refit_every == 0 and len(s["buf"]) >= min_obs:
            resid = list(s["buf"])
            s2 = sum(r * r for r in resid) / len(resid)
            if s2 > 0:
                # Grid over (alpha, beta) AND a free omega multiplier, minimizing
                # the Gaussian QMLE NLL. Finer than pure variance targeting, which
                # roughly halves the distance to a fitted GARCH(1,1) (issue #25).
                best_om = best_al = best_be = None
                best_v = float("inf")
                for (al, be) in _GARCH_AB_GRID:
                    base = (1.0 - al - be) * s2
                    for c in _GARCH_OMEGA_MULT:
                        om = base * c if base * c > 1e-12 else 1e-12
                        hh = om / (1.0 - al - be)            # unconditional-variance init
                        v = 0.0
                        for r in resid:
                            hh = om + al * (r * r) + be * hh
                            if hh <= 1e-300:
                                hh = 1e-300
                            v += math.log(hh) + (r * r) / hh
                        if v < best_v:                       # first-wins on ties
                            best_v, best_om, best_al, best_be = v, om, al, be
                s["omega"], s["alpha"], s["beta"] = best_om, best_al, best_be

        sigma = math.sqrt(h) if (math.isfinite(h) and h > 0) else max(abs(y), 1e-8)
        z = y / sigma
        w = s["w"]
        dens = [w[i] * math.exp(-0.5 * z * z / (C[i] * C[i])) / C[i] for i in range(K)]
        total = sum(dens)
        if total > 0:
            g = gamma if gamma > 1.0 / s["n"] else 1.0 / s["n"]
            s["w"] = [(1 - g) * w[i] + g * dens[i] / total for i in range(K)]

        d = Dist([(s["w"][i], 0.0, C[i] * sigma) for i in range(K)])
        return [d] * k, s

    _leaf.__name__ = f"garch_leaf(k={k})"
    return _leaf
