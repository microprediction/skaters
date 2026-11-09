"""granger: laplace with trained parameters, mixed with laplace so it cannot do
much worse.

After Clive Granger, whose work with Bates (1969) founded forecast
combination: weight forecasters by how well they have done.

Two forecasters run side by side on every observation:

* the reference :func:`skaters.laplace`, unchanged;
* laplace's own machinery with trained values for its continuous
  hyperparameters (the candidate transforms' rates, the ensemble's learning
  rate, forgetting and complexity penalty, a prior log weight per candidate,
  the terminal leaf's eta and scale rate), plus a small gate: a two-layer
  network that reads the previous step's state and shifts the ensemble's
  combining weights for this step (the weight recursion itself is unchanged).

The issued predictive is their mixture, weighted by the Aggregating Algorithm
under log loss: a prior ``pi_lap`` on laplace times each forecaster's
likelihood on the series so far (undiscounted, unfloored). For every series
and every prefix,

    sum_t -log q_t(y_t)  <=  sum_t -log p_lap,t(y_t)  +  log(1 / pi_lap)

so granger's total log score is never more than ``log(1/pi_lap)`` (log 4 at
the shipped ``pi_lap = 0.25``) behind laplace's.

The trained values ship as one JSON file per frequency in
``skaters/granger_params``; they were fitted with :mod:`skaters.torch.learned`
(the training twin) and this module reproduces that model's forecasts without
torch. Pure standard library, like the rest of the package. Horizon 1 only.
"""
from __future__ import annotations

import json
import math
import os
from collections import deque

from skaters.api import laplace
from skaters.conjugate import conjugate
from skaters.leaf import leaf as _leaf, crps_leaf
from skaters.parade import parade as _parade
from skaters.sticky import sticky as _project
from skaters.tails import gpdtails as _gpdtails
from skaters.terminal import terminal_leaf_ensemble
import skaters.transform as _T

_HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_DIR = os.path.join(_HERE, "granger_params")
FREQUENCIES = ("monthly", "weekly", "hourly")
_NONFINITE_LP = -1e6


def load_params(frequency: str = "monthly") -> dict:
    """The shipped trained values for one frequency."""
    path = os.path.join(PARAMS_DIR, f"{frequency}.json")
    if not os.path.exists(path):
        raise ValueError(f"no granger parameters for {frequency!r}; have {available()}")
    with open(path) as fh:
        return json.load(fh)


def available() -> list:
    if not os.path.isdir(PARAMS_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(PARAMS_DIR) if f.endswith(".json"))


# ---------------------------------------------------------------------------
# the trained expert: laplace's pipeline built from the parameter file
# ---------------------------------------------------------------------------

def _candidate(chain, k):
    """A conjugation chain over the reference leaf; ``chain`` is outer first."""
    f = _leaf(k=k)
    for name, kw in reversed(chain):
        f = conjugate(f, getattr(_T, name)(**kw), k=k)
    return f


def _expert(P, k=1, gate_hook=None):
    n = len(P["candidates"])
    if len(P["trunk"]["prior_log_weights"]) != n or len(P["gate"]["l2_weight"]) != n or len(P["gate"]["l2_bias"]) != n:
        raise ValueError("granger: prior_log_weights and the gate output need one entry per candidate")
    cands = [_candidate(c["chain"], k) for c in P["candidates"]]
    depths = [int(c["depth"]) for c in P["candidates"]]
    t = P["trunk"]
    tl = P["tleaf"]

    def leaf_fn(k=1):
        return crps_leaf(k=k, eta=tl["eta"], scale_alpha=tl["scale_alpha"])

    f = terminal_leaf_ensemble(
        cands, k=k, leaf_fn=leaf_fn,
        learning_rate=t["learning_rate"], complexity_penalty=t["complexity_penalty"],
        depths=depths, prior_log_weights=list(t["prior_log_weights"]),
        max_components=20, forget=t["forget"], gate_hook=gate_hook)
    f = _project(f, k=k)        # sticky lattice projection
    f = _gpdtails(f, k=k)       # GPD tail splice
    f = _parade(f, k=k)         # PIT / z diagnostics
    return f


def _trunk_state(expert_state):
    """parade -> gpdtails -> sticky -> trunk: each wrapper keeps its inner state under "base"."""
    s = expert_state
    for _ in range(3):
        if s is None:
            return None
        s = s.get("base")
    return s


# ---------------------------------------------------------------------------
# the gate: features from the previous step -> offsets on the combining weights
# ---------------------------------------------------------------------------

def _gate(G, feats):
    hidden = [math.tanh(b + sum(w * x for w, x in zip(row, feats)))
              for row, b in zip(G["l1_weight"], G["l1_bias"])]
    return [b + sum(w * h for w, h in zip(row, hidden))
            for row, b in zip(G["l2_weight"], G["l2_bias"])]


def _features(state, n, k):
    z = state.get("z") or [None] * k
    zs = [0.0 if v is None else max(-8.0, min(8.0, float(v))) for v in z][:k]
    zs += [0.0] * (k - len(zs))
    desc = [state["repeat_frac"], state["abs_z_mean"]]
    ts = _trunk_state(state["learned"])
    if ts is not None and len(ts.get("log_w", [])) == n:
        lw = ts["log_w"]
        m = max(lw)
        lw = [max(v - m, -20.0) / 20.0 for v in lw]
    else:
        lw = [0.0] * n
    return zs + desc + lw


# ---------------------------------------------------------------------------
# the mixture
# ---------------------------------------------------------------------------

class MixtureDist:
    """A two-component mixture of predictive distributions with log weights.
    ``logpdf``, ``cdf`` and the moments are exact; ``quantile`` bisects the
    mixture CDF; ``crps`` uses a 65-point quantile grid (as the training twin)."""

    def __init__(self, dists, log_w):
        self.dists = list(dists)
        m = max(log_w)
        s = math.log(sum(math.exp(v - m) for v in log_w)) + m
        self.log_w = [v - s for v in log_w]
        self.w = [math.exp(v) for v in self.log_w]

    def logpdf(self, x):
        terms = [lw + d.logpdf(x) for lw, d in zip(self.log_w, self.dists)]
        m = max(terms)
        if m == -math.inf:
            return -math.inf
        return m + math.log(sum(math.exp(t - m) for t in terms))

    def pdf(self, x):
        return math.exp(self.logpdf(x))

    def cdf(self, x):
        return sum(w * d.cdf(x) for w, d in zip(self.w, self.dists))

    @property
    def mean(self):
        return sum(w * d.mean for w, d in zip(self.w, self.dists))

    @property
    def var(self):
        mu = self.mean
        return sum(w * (d.var + (d.mean - mu) ** 2) for w, d in zip(self.w, self.dists))

    @property
    def std(self):
        return math.sqrt(max(self.var, 0.0))

    def quantile(self, p, tol=1e-9, max_iter=200):
        if not 0 < p < 1:
            raise ValueError(f"quantile needs 0 < p < 1, got {p}")
        lo = min(d.quantile(p) for d in self.dists)
        hi = max(d.quantile(p) for d in self.dists)
        # absolute tol at scale >= 1, relative below it so small-scale series keep their digits
        tol = tol * min(1.0, max(abs(lo), abs(hi)))
        if hi - lo <= tol:
            return 0.5 * (lo + hi)
        for _ in range(max_iter):
            mid = 0.5 * (lo + hi)
            if self.cdf(mid) < p:
                lo = mid
            else:
                hi = mid
            if hi - lo <= tol:
                break
        return 0.5 * (lo + hi)

    def crps(self, x, n=65):
        q = [self.quantile((i + 0.5) / n) for i in range(n)]
        t1 = sum(abs(v - x) for v in q) / n
        t2 = 2.0 * sum(v * (2.0 * (i + 0.5) / n - 1.0) for i, v in enumerate(q)) / n
        return t1 - 0.5 * t2

    def __repr__(self):
        return f"MixtureDist(w={[round(w, 4) for w in self.w]})"


# ---------------------------------------------------------------------------
# granger
# ---------------------------------------------------------------------------

def granger(k: int = 1, frequency: str = "monthly", params: dict | None = None):
    """laplace's trained twin mixed with laplace (horizon 1).

    Args:
        k: forecast horizon; only 1 is trained.
        frequency: which shipped parameter set (``available()`` lists them).
        params: a parameter dict to use instead of a shipped file.

    Returns a skater ``f(y, state) -> ([MixtureDist], state)``; ``state`` is
    pure data (picklable), ``state["z"]`` carries the trained expert's
    calibration z like laplace's.
    """
    if k != 1:
        raise ValueError("granger is trained at horizon 1 only")
    P = params if params is not None else load_params(frequency)
    pi = float(P["pi_lap"])
    log_prior = [math.log(pi), math.log(1.0 - pi)]
    ref = laplace(k)
    # the gate's offset for the current call only (not state: set before every call)
    _current = {"offset": None}
    expert = _expert(P, k, gate_hook=lambda: _current["offset"])
    n = len(P["candidates"])
    G = P["gate"]

    def _skater(y, state):
        if state is None:
            state = {"lap": None, "learned": None, "pend": deque(maxlen=k),
                     "cum": [[[0.0, 0.0] for _ in range(k)] for _ in range(k)],
                     "t": 0, "z": [None] * k, "repeat_frac": 0.0, "abs_z_mean": 0.0,
                     "n": 0, "last_y": None}
        yv = float("nan") if y is None else float(y)
        finite = math.isfinite(yv)
        t = state["t"]
        # 1. score the matured forecasts for y_t (undiscounted, unfloored)
        if finite:
            pend = state["pend"]
            m = len(pend)
            for h in range(1, k + 1):
                if h <= m:
                    lap_d, lrn_d = pend[m - h]
                    ph = t % h
                    for j, d in enumerate((lap_d[h - 1], lrn_d[h - 1])):
                        lp = float(d.logpdf(yv))
                        state["cum"][h - 1][ph][j] += lp if math.isfinite(lp) else _NONFINITE_LP
        # 2. the trained expert, its combining weights shifted by the gate (which
        #    reads step t-1's state), then laplace
        _current["offset"] = _gate(G, _features(state, n, k))
        try:
            lrn, state["learned"] = expert(yv, state["learned"])
        finally:
            _current["offset"] = None
        lap, state["lap"] = ref(yv, state["lap"])
        state["pend"].append((lap, lrn))
        # 3. descriptors for the next step's gate
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
        # 4. the guaranteed mixture
        out = []
        for h in range(1, k + 1):
            c = state["cum"][h - 1][t % h]
            out.append(MixtureDist([lap[h - 1], lrn[h - 1]], [log_prior[0] + c[0], log_prior[1] + c[1]]))
        state["t"] = t + 1
        return out, state

    _skater.__name__ = f"granger(k={k}, frequency={frequency!r})"
    return _skater
