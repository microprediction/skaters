"""A seasonal transform for non-integer periods (benchmark-side prototype).

laplace's seasonal candidates difference or anchor at an integer lag. A year is
52.18 weeks, so a lag of 52 slips a day and a quarter per year and drifts out of
phase over a few years. This transform instead removes a few Fourier harmonics
of the period, fitted online by exponentially weighted recursive least squares:

    s_t = b0 + sum_j  a_j sin(2 pi j t / P) + c_j cos(2 pi j t / P)
    forward:  y'_t = y_t - s_t     (s_t uses coefficients fitted to y_<t only)
    inverse:  the h-step predictive of y' is shifted by s_{t+h}

so the period can be any real number. The fit is causal: the coefficients that
form s_t are those before y_t is seen; y_t then updates them. The inverse is a
deterministic shift (coefficient uncertainty is not propagated). State is plain
lists, so it round-trips through json and deepcopy like every skaters state.

    from fourier_seasonal import fourier_seasonal
    conjugate(leaf(k=1), fourier_seasonal(365.25 / 7, harmonics=3), k=1)
"""
from __future__ import annotations

import math


def fourier_seasonal(period: float = 365.25 / 7, harmonics: int = 3, forget: float = 0.995,
                     delta: float = 100.0, warmup: int | None = None):
    assert period > 1 and harmonics >= 1 and 0 < forget <= 1
    p = 1 + 2 * harmonics
    warm = int(math.ceil(period)) if warmup is None else warmup

    def feats(t):
        x = [1.0]
        for j in range(1, harmonics + 1):
            a = 2.0 * math.pi * j * t / period
            x.append(math.sin(a)); x.append(math.cos(a))
        return x

    def fitted(beta, t):
        return sum(b * v for b, v in zip(beta, feats(t)))

    def forward(y: float, state: dict | None):
        if state is None:
            state = {"t": 0, "n": 0, "beta": [0.0] * p,
                     "P": [[(delta if i == j else 0.0) for j in range(p)] for i in range(p)]}
        t = state["t"]
        beta, P = state["beta"], state["P"]
        s = fitted(beta, t) if state["n"] >= warm else 0.0
        y_prime = y - s
        if math.isfinite(y):
            # exponentially weighted RLS update with (x_t, y_t)
            x = feats(t)
            Px = [sum(P[i][j] * x[j] for j in range(p)) for i in range(p)]
            denom = forget + sum(x[i] * Px[i] for i in range(p))
            k = [v / denom for v in Px]
            err = y - sum(b * v for b, v in zip(beta, x))
            state["beta"] = [beta[i] + k[i] * err for i in range(p)]
            state["P"] = [[(P[i][j] - k[i] * Px[j]) / forget for j in range(p)] for i in range(p)]
            state["n"] += 1
        state["t"] = t + 1
        return y_prime, state

    def inverse_k(dists, state):
        if state["n"] < warm:
            return list(dists)
        t0 = state["t"]            # the next time index is t0 (forward has advanced it)
        return [d.shift(fitted(state["beta"], t0 + h)) for h, d in enumerate(dists)]

    return forward, inverse_k
