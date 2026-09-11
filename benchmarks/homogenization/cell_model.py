"""Pure z-space homogenized cell-recalibration candidate model.

Operates entirely on a scalar PIT-normal-coordinate stream z_1, z_2, ... --
no observations y, no Dist, no skater. This is deliberate: it lets the
central research question (does a small online model of H_2/H_4 structure
in z beat doing nothing) be answered on saved z-streams alone, before any
of the machinery that would compose it back into a predictive distribution
is built (see the design note / research spec for the staged rollout).

Each candidate j represents a hypothesis about how the *next* residual's
conditional variance deviates from 1 (H_2, resolved) and how much unresolved
variance heterogeneity remains (H_4, via a two-point scale split). Its
predictive density for the next z is the two-scale Gaussian mixture

    g_j(z) = 1/2 * N(0, v_j(1-delta_j))(z) + 1/2 * N(0, v_j(1+delta_j))(z)

(a single N(0, v_j) when delta_j == 0), which is a globally valid, always-
monotone-CDF, always-positive-density object for any v_j > 0 -- unlike a
truncated Hermite correction phi(z)[1 + a*H_2(z) + b*H_4(z)], which is not
guaranteed positive and whose CDF is not guaranteed monotone in the tails.

v_j is driven by a fixed-gain, Huber-capped scalar filter on X_t = H_2(z_t)
= z_t^2 - 1 (the classic "does last tick's squared surprise predict this
tick's variance" signal); a persistent run of capped surprises is read as a
regime change and escapes the cap, mirroring the guard-and-escape idiom in
skaters.anomaly.mahalanobis. delta_j is a fixed per-candidate hyperparameter
(how much unresolved heterogeneity that candidate assumes), not itself
filtered in this version.

Because every candidate shares the same standard-normal reference density,
pooling candidates by their online Bayesian weights is *exact*: the pooled
mixture is simply the union of each candidate's (scale, weight) pairs,
re-weighted by the candidate's own pooled weight (see `_pool`). No
approximation, no re-fitting.

Event order within cell_step is load-bearing (see the module's design note,
section 6): every candidate's *own* pre-update q is what "was issued" for
it -- scoring against the realized z must happen before that candidate's q
is advanced, and weights must be updated before q, not after, so that
next tick's pooled correction reflects this tick's evidence exactly once.
"""

from __future__ import annotations
import math

_LOG_SQRT2PI = math.log(math.sqrt(2.0 * math.pi))

# Candidate/pool stability bounds (spec section 4 -- experimental starting
# points, not theoretical constants).
_V_MIN, _V_MAX = 0.25, 9.0
_DELTA_MAX = 0.8
_INNOVATION_CAP = 8.0
_ADAPT_AFTER = 10

# Prequential weight-learning constants (spec section 5). weight_decay is
# tuned up from the spec's suggested starting point of 0.995: at that rate
# the weight-selection layer has an effective memory of only ~200 ticks,
# which on iid Gaussian data is nowhere near enough for the softmax to tell
# "genuinely correct" from "coincidentally lucky this window" apart among a
# ~25-candidate grid -- identity only captured ~5% of the weight and the
# pool scored measurably *worse* than doing nothing (-0.005 nats/tick),
# failing the no-regret gate outright. 0.9999 (memory ~10,000 ticks) fixes
# this (identity climbs to >60% weight, loss shrinks to -0.0002) without
# hurting regime detection: which correction style works best is a stable
# property of an entire stream, so the *selection* layer doesn't need fast
# adaptation -- only each candidate's own internal filter does, and that
# reacts on its own faster timescale set by its own `rho`.
_WEIGHT_DECAY = 0.9999
_LEARNING_RATE = 0.1
_SCORE_CAP = 20.0


def _clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)


def _phi_logpdf(z: float) -> float:
    return -0.5 * z * z - _LOG_SQRT2PI


def _phi_pdf(z: float) -> float:
    return math.exp(_phi_logpdf(z))


# Public alias -- callers outside this module (the synthetic-experiment
# harness, tests) need phi's log-density too, to form Delta-logL against the
# pool; keep the underscored name as the internal spelling used throughout.
phi_logpdf = _phi_logpdf


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
    passed to cell_step. A read-only accessor for diagnostics/tests -- not
    used internally by cell_step itself."""
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
