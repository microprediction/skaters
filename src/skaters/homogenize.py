"""Online homogenized scale-mixture correction: a small Bayesian-hedged pool
of two-point Gaussian scale-mixture hypotheses for a skater's own PIT
residual stream.

If a base skater is well specified, its resolved residual ``z_t =
Phi^-1(F_{t-1}(y_t))`` (see ``parade.py``) behaves like iid N(0,1). In
practice two kinds of structure are often left over: a *predictable* shift
in conditional variance, and *unresolved heterogeneity* -- excess kurtosis
that a single time-varying variance can't explain, because the residual is
really drawn from a mix of several latent regimes at once. A Hermite/
Edgeworth expansion names these two effects precisely (``H_2(z) = z^2-1``
for the first, ``H_4(z) = z^4-6z^2+3`` for the second) but the naive
correction ``phi(z)[1 + c2*H_2(z) + c4*H_4(z)]`` is not usable directly: it
can go negative in the tails, so it isn't a valid density and its cdf isn't
guaranteed monotone.

This module uses a globally valid stand-in with the same two effects built
in: a two-point Gaussian scale mixture

    g(z) = 1/2 * N(0, v(1-delta))(z) + 1/2 * N(0, v(1+delta))(z)

(a single N(0, v) when ``delta == 0``), always a genuine density for any
``v > 0``. ``v`` plays the ``H_2`` role (the predictable variance level);
splitting one variance into two nearby ones via ``delta`` is literally how
excess kurtosis arises from purely Gaussian pieces -- the same mathematics
as a Student-t written as a Gaussian scale mixture, or a population that is
secretly several homogeneous sub-populations blended together (the
"homogenization" this module is named for: replacing an unresolved mix of
latent regimes with an effective, aggregate description, without ever
committing to which regime is active right now).

A small fixed grid of ``(rho, gain, delta)`` hypotheses, plus a
distinguished identity candidate (frozen at ``v=1`` forever, holding most of
the prior weight), are combined online: each carries its own scalar state
``q_t`` -- a fixed-gain, Huber-capped filter on ``x_t = H_2(z_t) = z_t^2-1``,
with a changepoint escape (a persistent run of capped surprises is read as a
genuine regime change and the cap lifts, mirroring the guard-and-escape
idiom in ``anomaly.mahalanobis``) -- and a discounted Bayesian log-weight,
updated by scoring each candidate's own already-issued prediction before
advancing its state (causal, no lookahead). Because every candidate's
mixture shares the same standard-normal reference density, pooling by
Bayesian weight is exact: the pooled density is simply the union of every
candidate's ``(scale, weight)`` pairs, no refitting required.

The pooled correction composes back onto the base skater's own predictive
distribution the same way ``residual_transform.CorrectedDist`` does:

    F~_t(y) = H_t(Phi^-1(F_t(y)))
    Q~_t(p) = F_t.quantile(Phi(H_t.quantile(p)))

with ``H_t`` the pooled scale mixture rather than a single learned family,
so there is no closed-form ``H_t`` quantile/cdf -- :class:`HomogenizedDist`
evaluates the mixture directly (log-sum-exp for the density, a weighted sum
of component cdfs, bisection for the quantile) instead of dispatching to a
:class:`~skaters.residual_transform.Family`.

Why this is a wrapper and not part of ``laplace``'s default output, despite
winning or being genuinely non-negative on every real-data arm tested
(``benchmarks/residual-transform/SCALE_CONVOLVED.md``):

- The evidence is real but still narrow -- one round of testing across
  three sample arms (generic FRED macro, M4-hourly waveform, price against
  ``garch_leaf``), not the extensive, incremental validation ``laplace``'s
  existing defaults have accumulated. The effect size is also domain-
  dependent, not uniform: a clear win on cyclic/waveform data, only a
  marginal one on generic macro data (median-of-medians barely above a
  coin flip there). A tool that helps a lot in one regime and barely at
  all in another is a good opt-in, not an obvious universal default.
- :class:`HomogenizedDist` duck-types the ``Dist`` interface but is not a
  ``Dist`` instance. Some internals (``bayesian_ensemble``, via
  ``Dist.combine()``) require genuine ``Dist`` objects; silently changing
  what ``laplace`` returns could break anything downstream that composes
  its output into a further ensemble.
- It adds an always-on pool of candidates -- extra compute on every call,
  including the Pyodide/browser deployment this library is built for,
  where that cost is not free the way it is on a server.
- Baking it into ``laplace`` would collapse the "raw vs. corrected"
  distinction this module's own research trail depends on: every existing
  and future study that measures whether this correction helps assumes
  raw ``laplace`` stays a stable baseline to compare against.

Apply it explicitly instead: ``homogenize(laplace(k=1))``.
"""

from __future__ import annotations
import math
from skaters.dist import Dist

_STD_NORMAL = Dist.gaussian(0.0, 1.0)
_EPS = 1e-12
_LOG_SQRT2PI = math.log(math.sqrt(2.0 * math.pi))

# Candidate/pool stability bounds -- experimental starting points, not
# theoretical constants.
_V_MIN, _V_MAX = 0.25, 9.0
_DELTA_MAX = 0.8
_INNOVATION_CAP = 8.0
_ADAPT_AFTER = 10

# Prequential weight-learning constants. weight_decay=0.9999 (memory
# ~10,000 ticks) was tuned up from an initial 0.995 (~200 ticks), which on
# an iid Gaussian null let the softmax mistake "coincidentally lucky this
# window" for "genuinely correct" among a multi-candidate grid: identity
# only captured ~5% of the weight and the pool scored measurably worse than
# doing nothing. 0.9999 fixes this (identity climbs past 60%) without
# hurting regime detection, since which correction style works best is a
# stable property of an entire stream -- only each candidate's own filter
# needs to react fast, on its own timescale set by its own `rho`.
_WEIGHT_DECAY = 0.9999
_LEARNING_RATE = 0.1
_SCORE_CAP = 20.0


def _clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)


def _clamp01(u: float) -> float:
    return min(max(u, _EPS), 1.0 - _EPS)


def _phi_inv(p: float) -> float:
    return _STD_NORMAL.quantile(p)


def _phi_logpdf(z: float) -> float:
    return -0.5 * z * z - _LOG_SQRT2PI


# ---------------------------------------------------------------------------
# Pooled scale-mixture density: g(z) = sum_i w_i / s_i * phi(z / s_i)
# ---------------------------------------------------------------------------

def logg(z: float, correction: dict) -> float:
    """Log-density of the pooled (or any) scale mixture at z (log-sum-exp)."""
    best = -math.inf
    terms = []
    for w, s in zip(correction["weights"], correction["scales"]):
        if w <= 0.0:
            continue
        t = math.log(w) - math.log(s) + _phi_logpdf(z / s)
        terms.append(t)
        if t > best:
            best = t
    if best == -math.inf:
        return -math.inf
    return best + math.log(sum(math.exp(t - best) for t in terms))


def g(z: float, correction: dict) -> float:
    return math.exp(logg(z, correction))


# ---------------------------------------------------------------------------
# Candidate construction
# ---------------------------------------------------------------------------

def make_candidates(rho_grid=(0.0, 0.8, 0.95, 0.99), gain_grid=(0.03, 0.12),
                     delta_grid=(0.0, 0.25, 0.50), delta_max: float = _DELTA_MAX):
    """Static candidate config grid, plus a distinguished identity candidate
    (rho=gain=delta=0, frozen at v=1 forever -- distinct from the grid's own
    rho=0 entries, which still react to every tick via a nonzero gain)."""
    candidates = [{"rho": 0.0, "gain": 0.0, "delta": 0.0, "is_identity": True}]
    for rho in rho_grid:
        for gain in gain_grid:
            for delta in delta_grid:
                candidates.append({
                    "rho": float(rho), "gain": float(gain),
                    "delta": float(_clip(delta, 0.0, delta_max)),
                    "is_identity": False,
                })
    return tuple(candidates)


def _cand_scales(v: float, delta: float):
    if delta <= 0.0:
        return (math.sqrt(v),)
    return (math.sqrt(v * (1.0 - delta)), math.sqrt(v * (1.0 + delta)))


def _cand_weights(delta: float):
    return (1.0,) if delta <= 0.0 else (0.5, 0.5)


def _cand_logpdf(z: float, v: float, delta: float) -> float:
    scales = _cand_scales(v, delta)
    weights = _cand_weights(delta)
    return logg(z, {"weights": list(weights), "scales": list(scales)})


# ---------------------------------------------------------------------------
# Online state
# ---------------------------------------------------------------------------

def _init_state(candidates) -> dict:
    n_other = max(sum(1 for c in candidates if not c["is_identity"]), 1)
    dynamic = []
    for c in candidates:
        log_weight = math.log(n_other) if c["is_identity"] else 0.0
        dynamic.append({"q": 0.0, "log_weight": log_weight, "guard_run": 0})
    return {"dynamic": dynamic, "issued": None, "n": 0}


def _update_q(d: dict, cfg: dict, x: float) -> None:
    """Fixed-gain filter on x = H_2(z) = z^2-1, Huber-capped, with a
    changepoint escape: a run of more than _ADAPT_AFTER consecutive capped
    ticks is read as a regime change and the innovation is used uncapped."""
    rho, gain = cfg["rho"], cfg["gain"]
    q_minus = rho * d["q"]
    resid = x - q_minus
    capped = abs(resid) > _INNOVATION_CAP
    d["guard_run"] = d["guard_run"] + 1 if capped else 0
    if capped and d["guard_run"] <= _ADAPT_AFTER:
        used = _clip(resid, -_INNOVATION_CAP, _INNOVATION_CAP)
    else:
        used = resid
    d["q"] = q_minus + gain * used


def _pool(candidates, dynamic) -> dict:
    """Exact Bayesian pooling: every candidate shares the same reference
    density, so the pooled mixture is the plain union of each candidate's
    (scale, weight) pairs, scaled by that candidate's own softmax weight."""
    log_weights = [d["log_weight"] for d in dynamic]
    m = max(log_weights)
    raw = [math.exp(lw - m) for lw in log_weights]
    total = sum(raw)
    omega = [r / total for r in raw]

    weights, scales = [], []
    for cfg, d, w in zip(candidates, dynamic, omega):
        v = _clip(1.0 + d["q"], _V_MIN, _V_MAX)
        for s, cw in zip(_cand_scales(v, cfg["delta"]), _cand_weights(cfg["delta"])):
            scales.append(s)
            weights.append(w * cw)
    return {"weights": weights, "scales": scales}


def candidate_weights(state: dict) -> list:
    """Current softmax weights (omega_j), same order as the candidates tuple
    passed to cell_step. A read-only accessor for diagnostics -- not used
    internally."""
    log_weights = [d["log_weight"] for d in state["dynamic"]]
    m = max(log_weights)
    raw = [math.exp(lw - m) for lw in log_weights]
    total = sum(raw)
    return [r / total for r in raw]


def cell_step(z: float, state: dict | None, candidates: tuple) -> tuple[dict, dict]:
    """Score the correction implicit in each candidate's own pre-update
    state against z, update candidate weights, update each candidate's
    latent variance deviation from H_2(z), then pool into the correction to
    be issued for the next observation.

    Returns (issued_correction, new_state). ``issued_correction`` is
    ``{"weights": [...], "scales": [...]}``, a valid Gaussian scale mixture
    ready to be evaluated by :func:`g`/:func:`logg` against the next z.
    """
    if state is None:
        state = _init_state(candidates)
    dynamic = state["dynamic"]
    x = z * z - 1.0

    # 1-2. Score each candidate's own (pre-update) implied correction
    # against the realized z, then update its discounted log-weight.
    for cfg, d in zip(candidates, dynamic):
        v = _clip(1.0 + d["q"], _V_MIN, _V_MAX)
        r = _cand_logpdf(z, v, cfg["delta"]) - _phi_logpdf(z)
        d["log_weight"] = _WEIGHT_DECAY * d["log_weight"] + _LEARNING_RATE * _clip(r, -_SCORE_CAP, _SCORE_CAP)

    # 3. Only now update each candidate's latent variance state.
    for cfg, d in zip(candidates, dynamic):
        _update_q(d, cfg, x)

    # 4. Construct (and remember) the correction issued for the next tick.
    correction = _pool(candidates, dynamic)
    state["issued"] = correction
    state["n"] += 1
    return correction, state


# ---------------------------------------------------------------------------
# HomogenizedDist: F~_t = H_t[Phi^-1(F_t(.))], H_t the pooled scale mixture
# ---------------------------------------------------------------------------

_QGRID_N = 32
_QGRID_P = [(i + 0.5) / _QGRID_N for i in range(_QGRID_N)]
_QGRID_W = 1.0 / _QGRID_N


class HomogenizedDist:
    """The base predictive ``base`` reshaped by the pooled scale-mixture
    correction ``correction`` (a ``{"weights": [...], "scales": [...]}``
    dict, as returned by :func:`cell_step`). Duck-types the ``Dist`` query
    surface, mirroring :class:`~skaters.residual_transform.CorrectedDist`.
    """

    __slots__ = ("base", "correction", "_qgrid")

    def __init__(self, base, correction: dict):
        self.base = base
        self.correction = correction
        self._qgrid = None

    def _z(self, y: float) -> float:
        return _phi_inv(_clamp01(self.base.cdf(y)))

    def _z_cdf(self, z: float) -> float:
        total = 0.0
        for w, s in zip(self.correction["weights"], self.correction["scales"]):
            total += w * _STD_NORMAL.cdf(z / s)
        return _clamp01(total)

    def _z_quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
        lo, hi = -40.0, 40.0
        for _ in range(max_iter):
            mid = 0.5 * (lo + hi)
            if self._z_cdf(mid) < p:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return 0.5 * (lo + hi)

    def cdf(self, y: float) -> float:
        return self._z_cdf(self._z(y))

    def logpdf(self, y: float) -> float:
        z = self._z(y)
        return self.base.logpdf(y) + logg(z, self.correction) - _phi_logpdf(z)

    def pdf(self, y: float) -> float:
        lp = self.logpdf(y)
        return math.exp(lp) if lp > -700.0 else 0.0

    def quantile(self, p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
        assert 0 < p < 1
        hp = self._z_quantile(p, tol=tol, max_iter=max_iter)
        u = _clamp01(_STD_NORMAL.cdf(hp))
        return self.base.quantile(u, tol=tol, max_iter=max_iter)

    def _quantile_grid(self) -> list:
        if self._qgrid is None:
            self._qgrid = [self.quantile(p) for p in _QGRID_P]
        return self._qgrid

    @property
    def mean(self) -> float:
        return sum(self._quantile_grid()) * _QGRID_W

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
        """CRPS via the quantile-form identity (Gneiting & Raftery 2007)."""
        q = self._quantile_grid()
        total = 0.0
        for p, qi in zip(_QGRID_P, q):
            ind = 1.0 if x <= qi else 0.0
            total += (qi - x) * (ind - p)
        return 2.0 * total * _QGRID_W

    def __repr__(self) -> str:
        n = len(self.correction["weights"])
        return f"HomogenizedDist(components={n}, base={self.base!r})"


# ---------------------------------------------------------------------------
# The wrapper
# ---------------------------------------------------------------------------

def homogenize(base, candidates: tuple | None = None, k: int = 1):
    """Wrap a k=1 skater with an online homogenized scale-mixture correction.

    Args:
        base: a k=1 skater callable, ``(y, state) -> (list[Dist], state)``.
        candidates: optional candidate grid from :func:`make_candidates`;
            defaults to ``make_candidates()`` if not given.
        k: forecast horizon of ``base``; only k=1 is supported.

    Returns:
        A skater callable ``(y, state) -> ([HomogenizedDist], state)``. The
        returned state additionally carries, mirroring ``residual_transform``:

        state["raw"]   F_t, the base skater's own (uncorrected) forecast for
                       y_{t+1}.
        state["cell"]  the pooled-candidate online state (see :func:`cell_step`).
    """
    assert k == 1, "homogenize currently supports k=1 only"
    candidates = candidates if candidates is not None else make_candidates()

    def _skater(y: float, state: dict | None) -> tuple[list, dict]:
        if state is None:
            state = {"base": None, "raw": None, "cell": None, "correction": None}
        s = state

        if s["raw"] is not None:
            u = _clamp01(s["raw"].cdf(y))
            z = _phi_inv(u)
            s["correction"], s["cell"] = cell_step(z, s["cell"], candidates)

        dists, s["base"] = base(y, s["base"])
        f_t = dists[0]
        s["raw"] = f_t

        corrected = f_t if s["correction"] is None else HomogenizedDist(f_t, s["correction"])
        return [corrected], s

    _skater.__name__ = f"homogenize({getattr(base, '__name__', '?')})"
    return _skater
