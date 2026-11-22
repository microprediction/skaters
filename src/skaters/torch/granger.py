"""granger in torch: the twin of :func:`skaters.granger.granger`.

The same two forecasters and the same Aggregating-Algorithm mixture: the
torch :func:`skaters.torch.laplace`, and laplace's machinery with the
trained values of a shipped parameter file (candidate transforms, the
trunk's learning rate, forgetting, complexity penalty and prior log weights,
the terminal leaf's eta and scale rate), with the trained gate shifting the
trunk's combining weights for each step. Every trained value is an
``nn.Parameter``, so the shipped parameters are a starting point for further
training.

The gate's offset takes its value from the reference arithmetic on floats
(plain left-to-right sums, as every port computes it, because one ulp of
offset can tip a lattice decision) and its gradient from the same network as
a torch expression. The mixture weights are float bookkeeping on matured
scores, as in the reference. The state has the reference's layout
(docs/STATE.md): ``lap``, ``learned``, ``pend`` (a list of
``[laplace predictives, learned predictives]`` pairs, bound k), ``cum``,
``t``, ``z``, ``repeat_frac``, ``abs_z_mean``, ``n``, ``last_y``.
"""

from __future__ import annotations

import importlib
import math
from functools import partial

import torch
from torch import nn

from skaters.torch.dist import TorchDist, DTYPE, _t

_ref = importlib.import_module("skaters.granger")

__all__ = ["granger", "Granger", "MixtureDist"]


def _f(x) -> float:
    return float(x.detach()) if isinstance(x, torch.Tensor) else float(x)


class MixtureDist:
    """The reference two-expert mixture on torch predictives. ``logpdf``,
    ``cdf`` and the moments are torch expressions (differentiable in both
    experts and the weights); ``quantile`` and ``crps`` run on the reference
    :class:`skaters.granger.MixtureDist` built from the same components, so
    they carry no gradient and cannot drift from it."""

    def __init__(self, dists, log_w):
        self.dists = list(dists)
        lw = [_t(v) for v in log_w]
        m = lw[0] if _f(lw[0]) >= _f(lw[1]) else lw[1]
        for v in lw[2:]:
            m = v if _f(v) > _f(m) else m
        s = torch.log(sum(torch.exp(v - m) for v in lw)) + m
        self.log_w = [v - s for v in lw]
        self.w = [torch.exp(v) for v in self.log_w]
        self._ref = None

    def to_reference(self):
        if self._ref is None:
            self._ref = _ref.MixtureDist([d.to_reference() for d in self.dists],
                                         [_f(v) for v in self.log_w])
        return self._ref

    def logpdf(self, x):
        terms = []
        for lw, d in zip(self.log_w, self.dists):
            v = _t(d.logpdf(x))
            terms.append(torch.as_tensor(-math.inf, dtype=DTYPE) if _f(v) != _f(v) else lw + v)
        m = max(terms, key=_f)
        if _f(m) == math.inf:
            return torch.as_tensor(math.inf, dtype=DTYPE)
        if _f(m) == -math.inf:
            return torch.as_tensor(-math.inf, dtype=DTYPE)
        return m + torch.log(sum(torch.exp(t - m) for t in terms))

    def pdf(self, x):
        return torch.exp(self.logpdf(x))

    def cdf(self, x):
        return sum(w * _t(d.cdf(x)) for w, d in zip(self.w, self.dists))

    @property
    def mean(self):
        return sum(w * _t(d.mean) for w, d in zip(self.w, self.dists))

    @property
    def var(self):
        mu = self.mean
        return sum(w * (_t(d.var) + (_t(d.mean) - mu) ** 2) for w, d in zip(self.w, self.dists))

    @property
    def std(self):
        return torch.sqrt(torch.clamp(self.var, min=0.0))

    def quantile(self, p, tol=1e-9, max_iter=200):
        return torch.as_tensor(self.to_reference().quantile(p, tol=tol, max_iter=max_iter), dtype=DTYPE)

    def crps(self, x, n=65):
        return torch.as_tensor(self.to_reference().crps(_f(_t(x)), n=n), dtype=DTYPE)

    def __repr__(self):
        return f"MixtureDist(w={[round(_f(w), 4) for w in self.w]})"


class _Gate(nn.Module):
    """The trained two-layer gate, its weights as parameters."""

    def __init__(self, G: dict):
        super().__init__()
        self.G = G
        self.l1_weight = nn.Parameter(torch.as_tensor(G["l1_weight"], dtype=DTYPE))
        self.l1_bias = nn.Parameter(torch.as_tensor(G["l1_bias"], dtype=DTYPE))
        self.l2_weight = nn.Parameter(torch.as_tensor(G["l2_weight"], dtype=DTYPE))
        self.l2_bias = nn.Parameter(torch.as_tensor(G["l2_bias"], dtype=DTYPE))

    def forward(self, feats: list) -> torch.Tensor:
        with torch.no_grad():
            G = {"l1_weight": self.l1_weight.tolist(), "l1_bias": self.l1_bias.tolist(),
                 "l2_weight": self.l2_weight.tolist(), "l2_bias": self.l2_bias.tolist()}
            value = torch.as_tensor(_ref._gate(G, feats), dtype=DTYPE)
        x = torch.as_tensor(feats, dtype=DTYPE)
        t = self.l2_bias + self.l2_weight @ torch.tanh(self.l1_bias + self.l1_weight @ x)
        return value + (t - t.detach())          # the reference's value, the network's gradient


def _plain(state: dict) -> None:
    """Float bookkeeping restored from JSON arrives as tensors; make it floats."""
    from skaters.torch.state import floats
    state["cum"] = floats(state["cum"])
    for key in ("repeat_frac", "abs_z_mean", "last_y"):
        if isinstance(state[key], torch.Tensor):
            state[key] = float(state[key])
    state["z"] = floats(state["z"])


class Granger(nn.Module):
    def __init__(self, k: int = 1, frequency: str = "monthly", params: dict | None = None):
        super().__init__()
        if k != 1:
            raise ValueError("granger is trained at horizon 1 only")
        P = params if params is not None else _ref.load_params(frequency)
        _ref.validate_params(P)
        self.P = P
        self.k = k
        self.frequency = P.get("frequency", frequency)
        pi = float(P["pi_lap"])
        self.log_prior = [math.log(pi), math.log(1.0 - pi)]
        from skaters.torch.api import laplace
        self.lap = laplace(k)
        self.expert, self.trunk = self._expert(P, k)
        self.gate = _Gate(P["gate"])
        self.n = len(P["candidates"])

    @staticmethod
    def _expert(P, k):
        from skaters.torch.conjugate import conjugate
        from skaters.torch.leaf import leaf, crps_leaf
        from skaters.torch.parade import parade
        from skaters.torch.sticky import sticky
        from skaters.torch.tails import gpdtails
        from skaters.torch.trunk import TerminalLeafEnsemble
        from skaters.torch.transform import from_reference
        cands, mods = [], []
        for c in P["candidates"]:
            f = leaf(k=k)
            for name, kw in reversed(c["chain"]):
                m = from_reference(name, **kw)
                mods.append(m)
                f = conjugate(f, m, k=k)
            cands.append(f)
        t, tl = P["trunk"], P["tleaf"]
        trunk = TerminalLeafEnsemble(
            cands, k=k, leaf_fn=partial(crps_leaf, eta=tl["eta"], scale_alpha=tl["scale_alpha"]),
            learning_rate=t["learning_rate"], complexity_penalty=t["complexity_penalty"],
            depths=[int(c["depth"]) for c in P["candidates"]],
            prior_log_weights=list(t["prior_log_weights"]), max_components=20, forget=t["forget"])
        trunk.candidate_modules = nn.ModuleList(mods)
        return parade(gpdtails(sticky(trunk, k=k), k=k), k=k), trunk

    def _features(self, state):
        k, n = self.k, self.n
        z = state.get("z") or [None] * k
        zs = [0.0 if v is None else max(-8.0, min(8.0, float(v))) for v in z][:k]
        zs += [0.0] * (k - len(zs))
        desc = [state["repeat_frac"], state["abs_z_mean"]]
        ts = _ref._trunk_state(state["learned"])
        if ts is not None and len(ts.get("log_w", [])) == n:
            lw = [_f(v) for v in ts["log_w"]]
            m = max(lw)
            lw = [max(v - m, -20.0) / 20.0 for v in lw]
        else:
            lw = [0.0] * n
        return zs + desc + lw

    def forward(self, y, state=None):
        k = self.k
        if state is None:
            state = {"lap": None, "learned": None, "pend": [],
                     "cum": [[[0.0, 0.0] for _ in range(k)] for _ in range(k)],
                     "t": 0, "z": [None] * k, "repeat_frac": 0.0, "abs_z_mean": 0.0,
                     "n": 0, "last_y": None}
        else:
            _plain(state)
        yv = float("nan") if y is None else _f(_t(y))
        finite = math.isfinite(yv)
        t = state["t"]
        if finite:
            pend = state["pend"]
            m = len(pend)
            for h in range(1, k + 1):
                if h <= m:
                    lap_d, lrn_d = pend[m - h]
                    c = state["cum"][h - 1][t % h]
                    for j, d in enumerate((lap_d[h - 1], lrn_d[h - 1])):
                        c[j] += _ref._score(_f(d.logpdf(yv)))
                    mx = max(c)
                    c[0] -= mx
                    c[1] -= mx
        self.trunk.gate_offset = self.gate(self._features(state))
        try:
            lrn, state["learned"] = self.expert(yv, state["learned"])
        finally:
            self.trunk.gate_offset = None
        lap, state["lap"] = self.lap(yv, state["lap"])
        state["pend"].append([lap, lrn])
        if len(state["pend"]) > k:
            del state["pend"][0]
        pz = state["learned"].get("z") if isinstance(state["learned"], dict) else None
        state["z"] = list(pz) if pz is not None else [None] * k
        if finite:
            nn_ = state["n"] + 1
            rep = 1.0 if (state["last_y"] is not None and yv == state["last_y"]) else 0.0
            state["repeat_frac"] += (rep - state["repeat_frac"]) / nn_
            z0 = state["z"][0] if state["z"] else None
            if z0 is not None and math.isfinite(z0):
                state["abs_z_mean"] += (min(abs(z0), 8.0) - state["abs_z_mean"]) / nn_
            state["n"], state["last_y"] = nn_, yv
        out = []
        for h in range(1, k + 1):
            c = state["cum"][h - 1][t % h]
            out.append(MixtureDist([lap[h - 1], lrn[h - 1]],
                                   [self.log_prior[0] + c[0], self.log_prior[1] + c[1]]))
        state["t"] = t + 1
        return out, state


def granger(k: int = 1, frequency: str = "monthly", params: dict | None = None) -> Granger:
    """Factory with the reference's name and signature."""
    return Granger(k=k, frequency=frequency, params=params)
