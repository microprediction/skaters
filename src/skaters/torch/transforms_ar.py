"""Torch ports of the autoregressive transforms ``ar`` and ``grouped_ar``.

The reference runs recursive least squares over Python lists; here the same
recursion runs over lists of 0-d float64 tensors in the same arithmetic
order, so the two ports agree to round-off. Two reference details are
mirrored on purpose:

* Wherever the reference uses the builtin ``sum()`` on floats (the AR
  prediction, ``_dot``, the impulse-response and power-iteration sums),
  CPython 3.12+ performs Neumaier-compensated summation. ``_psum`` below
  reproduces that algorithm on tensors; plain ``+=`` loops in the
  reference (``_mat_vec``, the h-step mean and variance) stay plain.
* The stationarity projection ``_ar_stationary`` uses the reference's own
  closed forms (p <= 2) and 60-step power iteration (p > 2); no eigen-solve.
"""

from __future__ import annotations

import math

import torch

from skaters.torch.dist import TorchDist, DTYPE, _t
from skaters.torch.transform import TorchTransform, register, _p, _zero


def _psum(terms):
    """CPython's float ``sum()`` (Neumaier compensation) on 0-d tensors."""
    total = _zero()
    c = _zero()
    for x in terms:
        t = total + x
        if bool(torch.abs(total) >= torch.abs(x)):
            c = c + ((total - t) + x)
        else:
            c = c + ((x - t) + total)
        total = t
    return total + c


def _mat_vec(M, v, n):
    out = []
    for i in range(n):
        s = _zero()
        for j in range(n):
            s = s + M[i * n + j] * v[j]
        out.append(s)
    return out


def _dot(a, b, n):
    return _psum(a[i] * b[i] for i in range(n))


def _spectral_radius(phi):
    p = len(phi)
    if p == 1:
        return torch.abs(phi[0])
    if p == 2:
        a, b = phi[0], phi[1]
        disc = a * a + 4.0 * b
        if bool(disc >= 0.0):
            r = torch.sqrt(disc)
            return torch.maximum(torch.abs((a + r) / 2.0), torch.abs((a - r) / 2.0))
        return torch.hypot(a / 2.0, torch.sqrt(-disc) / 2.0)
    v = [torch.ones((), dtype=DTYPE)] * p
    rho = _zero()
    for _ in range(60):
        nv = [_psum(phi[j] * v[j] for j in range(p))] + v[:-1]
        m = torch.abs(nv[0])
        for x in nv[1:]:
            m = torch.maximum(m, torch.abs(x))
        if not bool(m):
            m = torch.ones((), dtype=DTYPE)
        v = [x / m for x in nv]
        rho = m
    return rho


def _stationary(phi, margin=0.999):
    rho = _spectral_radius(phi)
    if bool(rho <= margin):
        return phi
    g = margin / rho
    return [phi[j] * g ** (j + 1) for j in range(len(phi))]


def _finite_and_bounded(P):
    for v in P:
        if not bool(torch.isfinite(v)):
            return False
    m = torch.abs(P[0])
    for v in P[1:]:
        m = torch.maximum(m, torch.abs(v))
    return not bool(m > 1e10)


def _ar_inverse(dists, buf, phi, p):
    """Shared h-step inverse: AR recursion for the mean, psi convolution for
    the variance (issue #245), in the reference's accumulation order."""
    H = len(dists)
    psi = [torch.ones((), dtype=DTYPE)]
    for i in range(1, H):
        psi.append(_psum(phi[j] * psi[i - 1 - j] for j in range(p) if i - 1 - j >= 0))
    recovered = []
    result = []
    for h in range(H):
        ar_mean = _zero()
        for j in range(p):
            lag_h = h - j - 1
            if lag_h < 0:
                idx = len(buf) + lag_h
                if 0 <= idx < len(buf):
                    ar_mean = ar_mean + phi[j] * buf[idx]
            elif lag_h < len(recovered):
                ar_mean = ar_mean + phi[j] * recovered[lag_h]
        total_mean = dists[h].mean + ar_mean
        total_var = _zero()
        for i in range(h + 1):
            total_var = total_var + psi[h - i] * psi[h - i] * dists[i].var
        if bool(total_var > 0):
            total_std = torch.sqrt(total_var)
        else:
            total_std = torch.clamp(dists[h].std, min=1e-12)
        recovered.append(total_mean)
        result.append(TorchDist.gaussian(total_mean, total_std))
    return result


class AR(TorchTransform):
    reference = "ar"

    def __init__(self, order: int = 2, lam: float = 0.99, ridge: float = 1.0,
                 decay: float = 0.0):
        super().__init__()
        assert order >= 1
        assert 0 < lam <= 1
        assert decay >= 0
        self.p = int(order)
        self.lam = _p(lam)
        self.ridge = _p(ridge)
        self.decay = _p(decay)

    def reference_args(self):
        return {"order": self.p, "lam": float(self.lam), "ridge": float(self.ridge),
                "decay": float(self.decay)}

    def _init_P(self):
        p = self.p
        P = [_zero()] * (p * p)
        for j in range(p):
            # the reference writes ``ridge`` when decay == 0; ``(j+1)**0.0`` is
            # exactly 1.0, so this is the same number and keeps decay in the graph
            P[j * p + j] = self.ridge / ((j + 1) ** self.decay)
        return P

    def _fresh(self):
        return {"buffer": [], "phi": [_zero()] * self.p, "P": self._init_P(), "n": 0}

    def _init_state(self, y):
        # the reference folds the first observation through the same step
        return self._step(y, self._fresh())[1]

    def forward(self, y, state=None):
        y = _t(y)
        if state is None:
            return self._step(y, self._fresh())
        return self._step(y, state)

    def _step(self, y, state):
        p = self.p
        lam = self.lam
        buf = list(state["buffer"])
        phi = list(state["phi"])
        P = list(state["P"])
        n = state["n"] + 1
        if len(buf) >= p:
            x = [buf[-(i + 1)] for i in range(p)]
            prediction = _psum(phi[i] * x[i] for i in range(p))
            residual = y - prediction
            Px = _mat_vec(P, x, p)
            denom = lam + _dot(x, Px, p)
            if bool(torch.abs(denom) > 1e-15):
                K = [px / denom for px in Px]
                for i in range(p):
                    phi[i] = phi[i] + K[i] * residual
                for i in range(p):
                    for j in range(p):
                        P[i * p + j] = (P[i * p + j] - K[i] * Px[j]) / lam
                if not _finite_and_bounded(P):
                    P = self._init_P()
        else:
            residual = y
        buf.append(y)
        if len(buf) > 2 * p + 10:
            buf.pop(0)
        return residual, {"buffer": buf, "phi": phi, "P": P, "n": n}

    def inverse_k(self, dists, state):
        return _ar_inverse(dists, list(state["buffer"]), _stationary(list(state["phi"])), self.p)


def _build_groups(max_lag: int) -> list[int]:
    groups, g, size, assigned = [], 0, 1, 0
    while assigned < max_lag:
        for _ in range(size):
            if assigned >= max_lag:
                break
            groups.append(g)
            assigned += 1
        g += 1
        size *= 2
    return groups


class GroupedAR(TorchTransform):
    reference = "grouped_ar"

    def __init__(self, max_lag: int = 16, lam: float = 0.99, ridge: float = 1.0):
        super().__init__()
        assert max_lag >= 1
        assert 0 < lam <= 1
        assert ridge > 0
        self.max_lag = int(max_lag)
        self.lam = _p(lam)
        self.ridge = _p(ridge)
        self.groups = _build_groups(self.max_lag)
        self.n_groups = max(self.groups) + 1

    def reference_args(self):
        return {"max_lag": self.max_lag, "lam": float(self.lam), "ridge": float(self.ridge)}

    def _eye(self):
        n = self.n_groups
        P = [_zero()] * (n * n)
        for i in range(n):
            P[i * n + i] = self.ridge * 1.0
        return P

    def _fresh(self):
        return {"buffer": [], "theta": [_zero()] * self.n_groups, "P": self._eye(), "n": 0}

    def _init_state(self, y):
        return self._step(y, self._fresh())[1]

    def forward(self, y, state=None):
        y = _t(y)
        if state is None:
            return self._step(y, self._fresh())
        return self._step(y, state)

    def _step(self, y, state):
        n_groups, max_lag, lam = self.n_groups, self.max_lag, self.lam
        buf = list(state["buffer"])
        theta = list(state["theta"])
        P = list(state["P"])
        n = state["n"] + 1
        if len(buf) >= max_lag:
            x = [_zero()] * n_groups
            for j in range(max_lag):
                x[self.groups[j]] = x[self.groups[j]] + buf[-(j + 1)]
            prediction = _psum(theta[g] * x[g] for g in range(n_groups))
            residual = y - prediction
            Px = _mat_vec(P, x, n_groups)
            denom = lam + _dot(x, Px, n_groups)
            if bool(torch.abs(denom) > 1e-15):
                K = [px / denom for px in Px]
                for g in range(n_groups):
                    theta[g] = theta[g] + K[g] * residual
                for i in range(n_groups):
                    for j in range(n_groups):
                        P[i * n_groups + j] = (P[i * n_groups + j] - K[i] * Px[j]) / lam
                if not _finite_and_bounded(P):
                    P = self._eye()
        else:
            residual = y
        buf.append(y)
        if len(buf) > max_lag + 10:
            buf.pop(0)
        return residual, {"buffer": buf, "theta": theta, "P": P, "n": n}

    def inverse_k(self, dists, state):
        theta = list(state["theta"])
        phi = _stationary([theta[self.groups[j]] for j in range(self.max_lag)])
        return _ar_inverse(dists, list(state["buffer"]), phi, self.max_lag)


register(AR)
register(GroupedAR)
