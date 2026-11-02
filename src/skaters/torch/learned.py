"""A learned forecaster that is laplace at worst (#297, step 2).

Two sequential probabilistic experts and one guaranteed outer mixture:

* ``laplace``: the reference :func:`skaters.laplace`, frozen, no gradients.
  This is the floor.
* ``learned``: :func:`skaters.torch.laplace` with every continuous
  hyperparameter trainable, plus a state-conditioned gate whose output is
  added to the trunk's prequential log weights at the combine step (it
  multiplies the weights; the weight recursion is untouched). The gate's last
  layer starts at zero and the parameters start at laplace's values, so at
  initialisation the learned expert equals laplace to the parity gate.
* the outer mixture: the exact density mixture of the two experts' predictives
  with weights from the *undiscounted, unfloored* cumulative log-likelihood of
  each expert's matured forecasts, the Aggregating Algorithm with ``eta = 1``
  under log loss. Because a horizon-``h`` forecast matures ``h`` steps after
  it is issued, horizon ``h`` runs ``h`` interleaved instances, one per phase
  ``t mod h``, each weighting only its own matured forecasts (the same phase
  split the multiscale uses). Within a phase the mixture telescopes, so for
  every prefix ``T`` and every horizon ``h``

      sum_t -log q_t(y_t)  <=  sum_t -log p_lap,t(y_t)  -  h * log(pi_lap)

  where ``pi_lap`` is laplace's prior share (default one half: a rent of
  ``h log 2`` nats over the whole stream, not per step). Nothing the gate or
  the optimizer does to the learned expert can break this bound; the learned
  expert can only displace laplace where it scores better on the stream.
  Flooring the scores that drive the weights would break the telescoping, so
  the weights use the raw log-likelihoods (a non-finite one counts as -1e6);
  the harness applies its own floor when it records the mixture's score.

Causality: the forecast issued at ``t`` for ``y_{t+1}`` uses the gate's
features from step ``t`` (the parade's ``z`` after ``y_t`` and each trunk's
prequential log weights after scoring ``y_t``); the cumulative scores that
weight the mixture use only matured forecasts. Changing ``y_t`` cannot change
the forecast that was issued for ``y_t``.

Training is not in this module (step 3): the module exposes gradients at the
output and :meth:`LearnedLaplace.project_` to keep the transform parameters
inside their valid regions after an optimizer step.
"""
from __future__ import annotations

import math
from collections import deque

import torch
import torch.nn as nn

from skaters.torch.dist import DTYPE, TorchDist, _t
from skaters.torch.tails import TorchSplicedDist
from skaters.torch.trunk import TerminalLeafEnsemble

_NONFINITE_LP = -1e6       # a non-finite log-likelihood in the weight update (weight -> 0)
_EPS = 1e-12


def _to_torch_dist(d):
    """A reference Dist or SplicedDist as a constant torch distribution."""
    if isinstance(d, (TorchDist, TorchSplicedDist)):
        return d
    if hasattr(d, "body"):          # reference SplicedDist
        return TorchSplicedDist.from_reference(d)
    return TorchDist.from_reference(d)


class MixtureDist:
    """A finite mixture of arbitrary torch distributions (anything with
    ``logpdf``, ``cdf``, ``quantile``, ``mean`` and ``var``), weights given as
    log weights. ``logpdf`` is exact (log-sum-exp); ``cdf`` and the moments are
    exact; ``quantile`` is a bisection on the mixture CDF; ``crps`` integrates
    ``(F(x) - 1{x >= y})^2`` on a quantile grid of the mixture."""

    def __init__(self, dists, log_w):
        assert len(dists) == len(log_w) >= 1
        self.dists = list(dists)
        lw = torch.stack([_t(v).reshape(()) for v in log_w])
        self.log_w = lw - torch.logsumexp(lw, dim=0)

    @property
    def weights(self):
        return torch.exp(self.log_w)

    def logpdf(self, x):
        lps = torch.stack([_t(d.logpdf(x)).reshape(()) for d in self.dists])
        return torch.logsumexp(self.log_w + lps, dim=0)

    def pdf(self, x):
        return torch.exp(self.logpdf(x))

    def cdf(self, x):
        cs = torch.stack([_t(d.cdf(x)).reshape(()) for d in self.dists])
        return torch.sum(self.weights * cs)

    @property
    def mean(self):
        ms = torch.stack([_t(d.mean).reshape(()) for d in self.dists])
        return torch.sum(self.weights * ms)

    @property
    def var(self):
        w = self.weights
        ms = torch.stack([_t(d.mean).reshape(()) for d in self.dists])
        vs = torch.stack([_t(d.var).reshape(()) for d in self.dists])
        mu = torch.sum(w * ms)
        return torch.sum(w * (vs + (ms - mu) ** 2))

    @property
    def std(self):
        return torch.sqrt(torch.clamp(self.var, min=0.0))

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 200):
        if not 0 < p < 1:
            raise ValueError(f"quantile needs 0 < p < 1, got {p}")
        with torch.no_grad():
            lo = min(float(d.quantile(p)) for d in self.dists)
            hi = max(float(d.quantile(p)) for d in self.dists)
            if hi - lo < tol:
                return torch.as_tensor(0.5 * (lo + hi), dtype=DTYPE)
            for _ in range(max_iter):
                mid = 0.5 * (lo + hi)
                if float(self.cdf(mid)) < p:
                    lo = mid
                else:
                    hi = mid
                if hi - lo < tol:
                    break
            return torch.as_tensor(0.5 * (lo + hi), dtype=DTYPE)

    def _qgrid(self, n: int = 65):
        with torch.no_grad():
            ps = [(i + 0.5) / n for i in range(n)]
            return torch.stack([self.quantile(p) for p in ps])

    def crps(self, x):
        """CRPS = E|X - x| - E|X - X'|/2 on the mixture's quantile grid
        (the same estimator the spliced distributions use)."""
        x = _t(x)
        q = self._qgrid()
        n = q.numel()
        t1 = torch.sum(torch.abs(q - x)) / n
        idx = torch.arange(n, dtype=DTYPE)
        t2 = 2.0 * torch.sum(q * (2.0 * (idx + 0.5) / n - 1.0)) / n
        return t1 - t2 * 0.5

    def __repr__(self) -> str:
        return f"MixtureDist(w={[round(float(w), 4) for w in self.weights]})"


class Gate(nn.Module):
    """A small state-conditioned gate: features -> log-weight offsets over a
    trunk's candidates. The last layer starts at zero, so the offset is zero
    (the prequential weights are unchanged) until training moves it."""

    def __init__(self, n_in: int, n_out: int, hidden: int = 32):
        super().__init__()
        self.l1 = nn.Linear(n_in, hidden, dtype=DTYPE)
        self.l2 = nn.Linear(hidden, n_out, dtype=DTYPE)
        nn.init.zeros_(self.l2.weight)
        nn.init.zeros_(self.l2.bias)

    def forward(self, feats):
        return self.l2(torch.tanh(self.l1(feats)))


# parameter name -> (low, high) for LearnedLaplace.project_; names are the
# attribute names the torch transforms and the trunk give their parameters
BOUNDS = {
    "alpha": (1e-4, 1.0 - 1e-4), "beta": (1e-4, 1.0 - 1e-4), "mean_alpha": (1e-4, 1.0 - 1e-4),
    "kappa": (1e-4, 1.0 - 1e-4), "shrinkage": (0.0, 1.0), "weight": (0.0, 1.0),
    "omega": (1e-12, None), "decay": (1e-4, 1.0 - 1e-4), "lam": (1e-6, 1.0),
    "ridge": (1e-10, None), "d": (-1.0, 1.0), "p": (-2.0, 2.0), "lmbda": (-2.0, 2.0),
    "learning_rate": (1e-3, 1.0), "forget": (0.5, 1.0), "complexity_penalty": (0.0, None),
    "floor": (1e-12, None),
}


class LearnedLaplace(nn.Module):
    """laplace frozen as the floor, a trainable torch laplace with a learned
    gate as the challenger, and the Aggregating-Algorithm mixture on top."""

    def __init__(self, k: int = 1, pi_lap: float = 0.5, gate_hidden: int = 32,
                 tails: str = "gpd"):
        super().__init__()
        assert 0.0 < pi_lap < 1.0
        from skaters.api import laplace as ref_laplace
        from skaters.torch.api import laplace as torch_laplace
        self.k = k
        self.log_prior = torch.log(torch.as_tensor([pi_lap, 1.0 - pi_lap], dtype=DTYPE))
        self.ref_f = ref_laplace(k, tails=tails)          # frozen reference closure
        self.learned = torch_laplace(k, tails=tails)      # trainable twin
        self.trunks = [m for m in self.learned.modules() if isinstance(m, TerminalLeafEnsemble)]
        assert self.trunks, "the torch laplace exposes no trunk"
        self.n_feat = k + 2
        self.gates = nn.ModuleList(Gate(self.n_feat + t.n, t.n, gate_hidden) for t in self.trunks)

    # ---- the two experts --------------------------------------------------

    def _learned_dists(self, y, state):
        """The learned expert's k predictives (a hook for tests, which corrupt it)."""
        dists, state["learned"] = self.learned(y, state["learned"])
        return dists

    def _laplace_dists(self, yv, state):
        dists, state["lap"] = self.ref_f(yv, state["lap"])
        return [_to_torch_dist(d) for d in dists]

    # ---- gate features (all from the previous step, so strictly causal) --------

    def _features(self, state, trunk):
        z = state.get("z") or [None] * self.k
        zs = [0.0 if v is None else max(-8.0, min(8.0, float(v))) for v in z][:self.k]
        zs += [0.0] * (self.k - len(zs))
        desc = [state.get("repeat_frac", 0.0), state.get("abs_z_mean", 0.0)]
        if trunk.last_log_w is not None and trunk.last_log_w.numel() == trunk.n:
            lw = trunk.last_log_w
            lw = torch.clamp(lw - torch.max(lw), min=-20.0) / 20.0
        else:
            lw = torch.zeros(trunk.n, dtype=DTYPE)
        return torch.cat([torch.as_tensor(zs + desc, dtype=DTYPE), lw])

    def _set_gate_offsets(self, state):
        for gate, trunk in zip(self.gates, self.trunks):
            trunk.gate_offset = gate(self._features(state, trunk))

    def _clear_gate_offsets(self):
        for trunk in self.trunks:
            trunk.gate_offset = None

    # ---- the step -----------------------------------------------------------

    def forward(self, y, state=None):
        k = self.k
        if state is None:
            state = {
                "lap": None, "learned": None,
                "pend": deque(maxlen=k),              # (lap_dists, learned_dists) issued earlier
                # cumulative log-lik [horizon, phase, expert]: phase = issue time mod horizon
                "cum": torch.zeros(k, k, 2, dtype=DTYPE),
                "t": 0,
                "z": [None] * k, "repeat_frac": 0.0, "abs_z_mean": 0.0,
                "n": 0, "last_y": None,
            }
        yv = float("nan") if y is None else float(y)
        finite = math.isfinite(yv)
        t = state["t"]
        # 1. score the matured forecasts for y_t: the horizon-h forecast issued at
        #    t-h belongs to phase (t-h) mod h == t mod h (undiscounted, unfloored)
        if finite:
            pend = state["pend"]
            m = len(pend)
            cum = state["cum"].clone()
            for h in range(1, k + 1):
                if h <= m:
                    lap_d, lrn_d = pend[m - h]
                    ph = t % h
                    for j, d in enumerate((lap_d[h - 1], lrn_d[h - 1])):
                        lp = float(d.logpdf(yv))
                        cum[h - 1, ph, j] += lp if math.isfinite(lp) else _NONFINITE_LP
            state["cum"] = cum
        # 2. the experts' forecasts for y_{t+1..t+k}; the gate reads step t-1's features
        self._set_gate_offsets(state)
        try:
            lrn = self._learned_dists(yv, state)
        finally:
            self._clear_gate_offsets()
        lap = self._laplace_dists(yv, state)
        state["pend"].append((lap, lrn))
        # 3. descriptors for the next step's gate (from the learned expert's parade)
        pz = state["learned"].get("z") if isinstance(state["learned"], dict) else None
        state["z"] = list(pz) if pz is not None else [None] * k
        if finite:
            n = state["n"] + 1
            rep = 1.0 if (state["last_y"] is not None and yv == state["last_y"]) else 0.0
            state["repeat_frac"] += (rep - state["repeat_frac"]) / n
            z0 = state["z"][0] if state["z"] else None
            if z0 is not None and math.isfinite(z0):
                state["abs_z_mean"] += (min(abs(z0), 8.0) - state["abs_z_mean"]) / n
            state["n"], state["last_y"] = n, yv
        # 4. the guaranteed mixture, per horizon, from this issue time's phase
        out = []
        for h in range(1, k + 1):
            lw = self.log_prior + state["cum"][h - 1, t % h]
            out.append(MixtureDist([lap[h - 1], lrn[h - 1]], lw))
        state["t"] = t + 1
        return out, state

    # ---- training helpers -----------------------------------------------------

    @torch.no_grad()
    def project_(self):
        """Clamp every bounded parameter of the learned expert into its valid
        region (call after each optimizer step)."""
        for name, p in self.learned.named_parameters():
            leaf = name.rsplit(".", 1)[-1]
            if leaf in BOUNDS:
                lo, hi = BOUNDS[leaf]
                p.clamp_(min=lo if lo is not None else -math.inf, max=hi if hi is not None else math.inf)

    def trainable_parameters(self):
        """The learned expert's and the gates' parameters (laplace has none)."""
        return list(self.learned.parameters()) + list(self.gates.parameters())


def learned(k: int = 1, pi_lap: float = 0.5, gate_hidden: int = 32, tails: str = "gpd") -> LearnedLaplace:
    """Factory in the skater style: ``f(y, state) -> (dists, state)``."""
    return LearnedLaplace(k=k, pi_lap=pi_lap, gate_hidden=gate_hidden, tails=tails)
