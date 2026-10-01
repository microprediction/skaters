"""Generating processes with known conditional laws, and independent oracles.

Every test that uses this module compares library output against a quantity
computed WITHOUT the code under test:

- closed forms written out by hand (textbook ETS / AR impulse responses), on
  inputs where the quantity does not collapse to a trivial case (unequal
  per-horizon innovation variances, nonzero trend, non-constant scale);
- a forward-simulation oracle: for a transform whose forward map is affine in
  y with linearly evolving state, the multi-step inverse is pinned down by the
  forward recursion alone. Push an innovation path through forward(), read off
  impulse responses, and the propagated mean and variance follow by linearity.
  This never calls inverse_k, so agreement is evidence, not self-consistency.

Indexing convention (matches conjugate.inverse_k): after consuming y_t,
``dists[i]`` is the transformed-space predictive for time t+i+1 and the
returned ``out[h]`` is the predictive for y_{t+h+1}. Innovations at distinct
future times are independent (the assumption every inverse_k already makes).
"""
from __future__ import annotations
import copy
import math
import random


# ----------------------------------------------------------------- series
def iid(n, seed, dist="gauss", sigma=1.0):
    """iid noise. dist in {gauss, t4, laplace}; all scaled to unit variance x sigma."""
    g = random.Random(seed)
    out = []
    for _ in range(n):
        if dist == "gauss":
            x = g.gauss(0.0, 1.0)
        elif dist == "t4":
            x = g.gauss(0.0, 1.0) / math.sqrt(g.gammavariate(2.0, 1.0) / 2.0)   # t_4, var 2
            x /= math.sqrt(2.0)
        elif dist == "laplace":
            x = (g.expovariate(1.0) - g.expovariate(1.0)) / math.sqrt(2.0)      # var 1
        else:
            raise ValueError(dist)
        out.append(sigma * x)
    return out


def gaussian_ar(phi, sigma, n, seed, burn=200):
    """Stationary Gaussian AR(p). Returns (y, eps) after burn-in."""
    g = random.Random(seed)
    p = len(phi)
    y = [0.0] * p
    eps = []
    for _ in range(n + burn):
        e = g.gauss(0.0, sigma)
        y.append(sum(phi[j] * y[-1 - j] for j in range(p)) + e)
        eps.append(e)
    return y[p + burn:], eps[burn:]


def ar_oracle(phi, sigma, history, h):
    """Exact (mean, var) of y_{t+h} given the full history, h >= 1."""
    p = len(phi)
    psi = [1.0]
    for i in range(1, h):
        psi.append(sum(phi[j] * psi[i - 1 - j] for j in range(p) if i - 1 - j >= 0))
    buf = list(history[-p:])
    for _ in range(h):
        buf.append(sum(phi[j] * buf[-1 - j] for j in range(p)))
    return buf[-1], sigma * sigma * sum(c * c for c in psi)


def random_walk(sigma, n, seed, y0=0.0):
    g = random.Random(seed)
    y = [y0]
    for _ in range(n):
        y.append(y[-1] + g.gauss(0.0, sigma))
    return y


def holt_series(alpha, beta, sigma, n, seed, level0=10.0, trend0=0.05):
    """ETS(A,A,N) in innovations form. Returns (y, levels, trends) where
    levels[t], trends[t] are the states AFTER consuming y[t]."""
    g = random.Random(seed)
    l, b = level0, trend0
    y, L, B = [], [], []
    for _ in range(n):
        e = g.gauss(0.0, sigma)
        yt = l + b + e
        l = l + b + alpha * e
        b = b + alpha * beta * e
        y.append(yt); L.append(l); B.append(b)
    return y, L, B


def garch11(omega, alpha, beta, n, seed, burn=500):
    """GARCH(1,1) returns. Returns (r, h_next) where h_next[t] is the TRUE
    conditional variance of r[t+1] given r[:t+1]."""
    g = random.Random(seed)
    h = omega / (1.0 - alpha - beta)
    r, hn = [], []
    last = 0.0
    for i in range(n + burn):
        h = omega + alpha * last * last + beta * h
        x = math.sqrt(h) * g.gauss(0.0, 1.0)
        if i >= burn:
            r.append(x)
        last = x
        if i >= burn:
            hn.append(omega + alpha * x * x + beta * h)
    return r, hn


def sigma_path(n, seed, levels=(1.0, 3.0, 0.5, 2.0)):
    """Zero-mean Gaussian noise with a KNOWN piecewise-constant sd. Returns (y, sd)."""
    g = random.Random(seed)
    seg = max(1, n // len(levels))
    sd = [levels[min(i // seg, len(levels) - 1)] for i in range(n)]
    return [s * g.gauss(0.0, 1.0) for s in sd], sd


# ----------------------------------------------------------------- oracles
def forward_state(transform, series):
    """Run forward over `series`, return the transform state afterwards."""
    forward, _ = transform
    st = None
    for y in series:
        _, st = forward(y, st)
    return st


def _probe(forward, st, y):
    e, _ = forward(y, copy.deepcopy(st))
    return e


def inverse_path(forward, state, eps):
    """The y path that makes forward() emit exactly `eps`, using forward() only.
    Valid when forward is affine in y for a fixed state."""
    st = copy.deepcopy(state)
    ys = []
    for e in eps:
        a = _probe(forward, st, 0.0)
        b = _probe(forward, st, 1.0)
        y = (e - a) / (b - a)
        _, st = forward(y, st)
        ys.append(y)
    return ys


def propagated_moments(transform, state, means, vars_, tol=1e-9):
    """(mean_h, var_h) for h in 0..H-1 implied by the FORWARD recursion under
    independent innovations with the given per-horizon means and variances.

    Raises AssertionError if the forward map is not linear in the innovation
    path (so the caller knows this oracle does not apply)."""
    forward, _ = transform
    H = len(means)
    base = inverse_path(forward, state, [0.0] * H)
    c = [[0.0] * H for _ in range(H)]
    for i in range(H):
        e = [0.0] * H
        e[i] = 1.0
        path = inverse_path(forward, state, e)
        for h in range(H):
            c[h][i] = path[h] - base[h]
    # linearity: scaling and superposition
    e2 = [0.0] * H; e2[0] = 2.0
    p2 = inverse_path(forward, state, e2)
    pall = inverse_path(forward, state, [1.0] * H)
    scale_ref = 1.0 + max(abs(x) for x in base)
    for h in range(H):
        assert abs(p2[h] - (base[h] + 2.0 * c[h][0])) <= tol * scale_ref, "forward not linear (scaling)"
        assert abs(pall[h] - (base[h] + sum(c[h]))) <= tol * scale_ref, "forward not linear (superposition)"
    out_mean = [base[h] + sum(c[h][i] * means[i] for i in range(H)) for h in range(H)]
    out_var = [sum(c[h][i] ** 2 * vars_[i] for i in range(H)) for h in range(H)]
    return out_mean, out_var, c


def ets_ann_var(alpha, vars_):
    """ETS(A,N,N) (simple exponential smoothing): Var(y_{t+h+1}) = v_h + alpha^2 sum_{i<h} v_i.
    Hyndman & Athanasopoulos, FPP3 ch. 8 (with h-step index shifted to our 0-based h)."""
    return [vars_[h] + alpha * alpha * sum(vars_[:h]) for h in range(len(vars_))]


def ets_aan_var(alpha, beta_star, vars_):
    """ETS(A,A,N) (Holt): c_0 = 1, c_j = alpha + beta_star * j for j >= 1;
    Var(y_{t+h+1}) = sum_{j=0}^{h} c_j^2 v_{h-j}. Our holt_linear(alpha, beta) has
    beta_star = alpha * beta (trend update b += alpha*beta*eps)."""
    out = []
    for h in range(len(vars_)):
        tot = 0.0
        for j in range(h + 1):
            cj = 1.0 if j == 0 else alpha + beta_star * j
            tot += cj * cj * vars_[h - j]
        out.append(tot)
    return out


def ar_var(phi, vars_):
    """Var(y_{t+h+1}) = sum_{i<=h} psi_{h-i}^2 v_i with psi the AR impulse responses."""
    H = len(vars_)
    p = len(phi)
    psi = [1.0]
    for i in range(1, H):
        psi.append(sum(phi[j] * psi[i - 1 - j] for j in range(p) if i - 1 - j >= 0))
    return [sum(psi[h - i] ** 2 * vars_[i] for i in range(h + 1)) for h in range(H)]


def ks_uniform(u):
    """Kolmogorov-Smirnov distance of a sample from Uniform(0,1)."""
    s = sorted(u)
    n = len(s)
    return max(max(abs((i + 1) / n - x), abs(x - i / n)) for i, x in enumerate(s))
