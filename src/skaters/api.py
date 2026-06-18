"""User-facing API.

Every named function builds a Bayesian ensemble over the SAME full
candidate population. The names represent different search policies —
different priors, learning rates, and complexity penalties — not
different models.

    from skaters import skater

    f = skater(k=3)
    state = None
    for y in observations:
        dists, state = f(y, state)
        print(dists[0].mean, dists[0].std)
"""

from __future__ import annotations
import math
from skaters.leaf import leaf, scale_mixture_leaf, crps_leaf
from skaters.conjugate import conjugate
from skaters.bayesian import bayesian_ensemble
from skaters.transform import (
    difference, fractional_difference, standardize, ema_transform,
    garch, power_transform, drift, holt_linear, ar, theta,
    seasonal_difference, yeo_johnson,
)
from skaters.search import search as adaptive_search
from skaters.terminal import terminal_leaf_ensemble
from skaters.sticky import sticky


def _objective_leaf(objective: str):
    """Terminal-leaf factory for a policy's objective. ``crps`` is the default:
    *model first* (likelihood-weighted trunk) then *conform last* (CRPS-fit leaf).
    Pass ``"likelihood"`` for the scale-mixture leaf instead."""
    if objective == "crps":
        return crps_leaf
    if objective == "likelihood":
        return scale_mixture_leaf
    raise ValueError(f"objective must be 'crps' or 'likelihood', got {objective!r}")


# ---------------------------------------------------------------------------
# Candidate population (shared by all search policies)
# ---------------------------------------------------------------------------

def _build_candidates(k: int, leaf_fn=leaf):
    """Generate the full candidate population.

    Every search policy considers ALL of these. The policy only
    affects how they are weighted, not which ones are included.

    The terminal distribution of every candidate is ``leaf_fn`` — by default
    the Gaussian scale-mixture leaf, which models the residual's departure
    from N(0,1). Pass ``leaf_fn=leaf`` for the plain Gaussian leaf.

    Returns (candidates, depths, groups), where groups maps a logical
    block name to the list of candidate indices in that block. Policies
    express priors by boosting a named group instead of magic indices.
    """
    candidates = []
    depths = []
    groups: dict[str, list[int]] = {}

    # Depth 0: just noise (baseline)
    candidates.append(leaf_fn(k=k))
    depths.append(0)

    # Depth 1: single EMA at various speeds
    for alpha in [0.01, 0.05, 0.1, 0.3]:
        candidates.append(conjugate(leaf_fn(k=k), ema_transform(alpha), k=k))
        depths.append(1)

    # Depth 1: differencing + leaf (pure random walk)
    groups["diff"] = []
    candidates.append(conjugate(leaf_fn(k=k), difference(), k=k))
    depths.append(1)
    groups["diff"].append(len(candidates) - 1)

    # Depth 1: drift + leaf (random walk with adaptive drift)
    # Multiple speeds: fast drift detection vs long-memory drift
    groups["drift"] = []
    for a, s in [(0.05, 0.01), (0.01, 0.002), (0.002, 0.001), (0.0005, 0.0002)]:
        candidates.append(conjugate(leaf_fn(k=k), drift(alpha=a, shrinkage=s), k=k))
        depths.append(1)
        groups["drift"].append(len(candidates) - 1)

    # Depth 1: Theta method (SES + half OLS slope)
    for a in [0.05, 0.1, 0.3]:
        candidates.append(conjugate(leaf_fn(k=k), theta(alpha=a), k=k))
        depths.append(1)

    # Depth 1: AR at depth 1 (captures mean reversion, persistence)
    candidates.append(conjugate(leaf_fn(k=k), ar(1), k=k))
    depths.append(1)
    candidates.append(conjugate(leaf_fn(k=k), ar(2, decay=1), k=k))
    depths.append(1)

    # Depth 1: Holt linear (level + trend, single transform)
    groups["holt"] = []
    for a, b in [(0.1, 0.02), (0.1, 0.05), (0.3, 0.1)]:
        candidates.append(conjugate(leaf_fn(k=k), holt_linear(alpha=a, beta=b), k=k))
        depths.append(1)
        groups["holt"].append(len(candidates) - 1)

    # Depth 1: Seasonal differencing (common periods)
    for period in [7, 12, 24]:
        candidates.append(conjugate(leaf_fn(k=k), seasonal_difference(period), k=k))
        depths.append(1)

    # Depth 2: Seasonal differencing + EMA
    for period in [7, 12, 24]:
        for alpha in [0.05, 0.1]:
            candidates.append(
                conjugate(conjugate(leaf_fn(k=k), ema_transform(alpha), k=k),
                          seasonal_difference(period), k=k)
            )
            depths.append(2)

    # Depth 2: differencing + EMA
    for alpha in [0.05, 0.1, 0.3]:
        candidates.append(
            conjugate(conjugate(leaf_fn(k=k), ema_transform(alpha), k=k), difference(), k=k)
        )
        depths.append(2)
        groups["diff"].append(len(candidates) - 1)

    # Depth 2: standardize + EMA
    for alpha in [0.05, 0.1]:
        candidates.append(
            conjugate(conjugate(leaf_fn(k=k), ema_transform(alpha), k=k), standardize(), k=k)
        )
        depths.append(2)

    # Depth 2: fractional diff + EMA
    groups["frac"] = []
    for d in [0.2, 0.4]:
        candidates.append(
            conjugate(conjugate(leaf_fn(k=k), ema_transform(0.1), k=k),
                      fractional_difference(d=d, window=30), k=k)
        )
        depths.append(2)
        groups["frac"].append(len(candidates) - 1)

    # Depth 2: drift + EMA (drift removal then level tracking)
    for a_drift, s_drift in [(0.002, 0.001), (0.0005, 0.0002)]:
        for a_ema in [0.05, 0.1]:
            candidates.append(
                conjugate(conjugate(leaf_fn(k=k), ema_transform(a_ema), k=k),
                          drift(alpha=a_drift, shrinkage=s_drift), k=k)
            )
            depths.append(2)
            groups["drift"].append(len(candidates) - 1)

    # Depth 2: drift + Holt linear (drift on top of level+trend)
    candidates.append(
        conjugate(conjugate(leaf_fn(k=k), holt_linear(0.1, 0.05), k=k),
                  drift(alpha=0.001, shrinkage=0.0005), k=k)
    )
    depths.append(2)
    groups["drift"].append(len(candidates) - 1)
    groups["holt"].append(len(candidates) - 1)

    # Depth 2: GARCH + EMA (volatility-adapted)
    candidates.append(
        conjugate(conjugate(leaf_fn(k=k), ema_transform(0.1), k=k), garch(), k=k)
    )
    depths.append(2)

    # Depth 2: power transform + EMA (tail compression)
    candidates.append(
        conjugate(conjugate(leaf_fn(k=k), ema_transform(0.1), k=k), power_transform(0.5), k=k)
    )
    depths.append(2)

    # Depth 2: "thinking fast and slow" — a fast process tracker on the
    # OUTSIDE, a slowly-varying residual scale (standardize) on the INSIDE,
    # the plain Gaussian leaf at the bottom.
    #
    #     y --[fast tracker]--> residual --[slow standardize]--> z --> leaf
    #
    # The mean reacts to every observation; the residual *distribution*
    # drifts slowly — at a timescale an order of magnitude slower than the
    # mean. The scale half-life is spread over two values so the ensemble
    # can match how fast the noise actually drifts. No new primitive is
    # needed — this is purely a composition of existing transforms.
    def _fast_trackers():
        return [
            ema_transform(0.3),
            ema_transform(0.5),
            holt_linear(alpha=0.4, beta=0.2),
            ar(1),
            drift(alpha=0.05, shrinkage=0.01),
            difference(),
        ]

    groups["fast_slow"] = []
    for scale_alpha in [0.02, 0.05]:  # slow residual scale, two timescales
        for tracker in _fast_trackers():
            slow_scale = standardize(alpha=scale_alpha)
            candidates.append(
                conjugate(conjugate(leaf_fn(k=k), slow_scale, k=k), tracker, k=k)
            )
            depths.append(2)
            groups["fast_slow"].append(len(candidates) - 1)

    # Coordinate prior (Yeo-Johnson): the same series is often simple in a
    # transformed coordinate — multiplicative/non-negative (lambda=0, log1p) or
    # mildly compressed (lambda=0.5). A coarse grid composed over the random
    # walk and a slow EMA lets the ensemble *learn the coordinate* online.
    # lambda=1 is the identity (already the rest of the pool), so we add 0 and
    # 0.5 only. NFL-safe: a wrong coordinate is simply down-weighted.
    groups["coordinate"] = []
    for L in (0.0, 0.5):
        for inner_tx in (difference(), ema_transform(0.1)):
            candidates.append(
                conjugate(conjugate(leaf_fn(k=k), inner_tx, k=k), yeo_johnson(L), k=k)
            )
            depths.append(2)
            groups["coordinate"].append(len(candidates) - 1)

    return candidates, depths, groups


def _prior_favoring_depths(depths: list[int], favored: set[int], boost: float = 2.0) -> list[float]:
    """Compute prior log-weights that boost candidates at certain depths."""
    return [boost if d in favored else 0.0 for d in depths]


def _prior_favoring_indices(n: int, favored: set[int], boost: float = 2.0) -> list[float]:
    """Compute prior log-weights that boost specific candidate indices."""
    return [boost if i in favored else 0.0 for i in range(n)]


# ---------------------------------------------------------------------------
# The default entry point
# ---------------------------------------------------------------------------

def skater(k: int = 1, aggressiveness: float = 0.5, objective: str = "crps"):
    """Create a general-purpose online forecaster.

    Builds a Bayesian ensemble over a diverse candidate population
    and lets the data decide which complexity is appropriate.

    Args:
        k: forecast horizon (steps ahead).
        aggressiveness: float in (0, 1). Controls adaptation speed.
            Low = conservative (slow to change, penalizes complexity).
            High = aggressive (adapts fast, tolerates complexity).
        objective: terminal-leaf objective — ``"crps"`` (default; *model first,
            conform last*) or ``"likelihood"``. CRPS wins on heavy-tailed/real
            data and costs a few thousandths of a nat on idealised Gaussian.
    """
    assert 0 < aggressiveness < 1
    learning_rate = 0.1 + 0.8 * aggressiveness
    complexity_penalty = 0.05 * (1 - aggressiveness)

    candidates, depths, _ = _build_candidates(k)
    f = terminal_leaf_ensemble(
        candidates, k=k,
        leaf_fn=_objective_leaf(objective),
        learning_rate=learning_rate,
        complexity_penalty=complexity_penalty,
        depths=depths,
        max_components=20,
    )
    f.__name__ = f"skater(k={k})"
    return f


# ---------------------------------------------------------------------------
# Named search policies
#
# All consider the same candidates. They differ in prior, learning
# rate, and complexity penalty — i.e., the search strategy.
# ---------------------------------------------------------------------------

def holt(k: int = 1):
    """Holt's policy: expect trends.

    After Charles Holt (1957). Prior favoring differencing-based models
    that capture trends. Moderate complexity penalty. Best when the
    series has persistent drift or momentum.
    """
    candidates, depths, groups = _build_candidates(k)
    # Boost the trend-capturing families: differencing, drift, Holt linear.
    trend = set(groups["diff"]) | set(groups["drift"]) | set(groups["holt"])
    prior = _prior_favoring_indices(len(candidates), favored=trend, boost=3.0)
    f = terminal_leaf_ensemble(
        candidates, k=k,
        learning_rate=0.5,
        complexity_penalty=0.02,
        depths=depths,
        prior_log_weights=prior,
        max_components=15,
    )
    f.__name__ = f"holt(k={k})"
    return f


def hosking(k: int = 1):
    """Hosking's policy: expect long memory.

    After Jonathan Hosking (1981). Prior favoring fractional differencing
    models that capture long-range dependence. Tolerates depth-2
    complexity. Best for series with slowly decaying autocorrelation.
    """
    candidates, depths, groups = _build_candidates(k)
    # Boost the fractional-differencing models (by name, not magic index)
    prior = _prior_favoring_indices(len(candidates), favored=set(groups["frac"]), boost=3.0)
    f = terminal_leaf_ensemble(
        candidates, k=k,
        learning_rate=0.5,
        complexity_penalty=0.01,
        depths=depths,
        prior_log_weights=prior,
        max_components=15,
    )
    f.__name__ = f"hosking(k={k})"
    return f


def laplace(k: int = 1, objective: str = "crps"):
    """Laplace's policy: maximum ignorance.

    After Pierre-Simon Laplace. Uniform prior — no preference for any
    model class. Pure Bayesian updating. Learning rate close to 1 for
    fast convergence. Minimal complexity penalty. Let the data speak.

    Args:
        k: forecast horizon.
        objective: terminal-leaf objective — ``"crps"`` (default; *model first,
            conform last*) or ``"likelihood"``.
    """
    candidates, depths, _ = _build_candidates(k)
    f = terminal_leaf_ensemble(
        candidates, k=k,
        leaf_fn=_objective_leaf(objective),
        learning_rate=0.8,
        complexity_penalty=0.005,
        depths=depths,
        max_components=20,
    )
    f.__name__ = f"laplace(k={k})"
    return f


def wald(k: int = 1):
    """Wald's policy: minimax caution.

    After Abraham Wald. Very conservative — high complexity penalty,
    low learning rate. Slow to commit to any model, resistant to being
    fooled by short-term patterns. Best in adversarial or highly
    non-stationary environments.
    """
    candidates, depths, _ = _build_candidates(k)
    prior = _prior_favoring_depths(depths, favored={0}, boost=2.0)
    f = terminal_leaf_ensemble(
        candidates, k=k,
        learning_rate=0.15,
        complexity_penalty=0.08,
        depths=depths,
        prior_log_weights=prior,
        max_components=10,
    )
    f.__name__ = f"wald(k={k})"
    return f


def dantzig(k: int = 1):
    """Dantzig's policy: adaptive search over the transform grammar.

    After George Dantzig (1947). Uses adaptive search that grows the
    candidate pool online — expanding top performers and pruning losers.
    """
    f = adaptive_search(
        k=k,
        learning_rate=0.3,
        complexity_penalty=0.01,
        max_pool=40,
        expand_interval=50,
        expand_top_n=5,
        max_depth=3,
        cost_budget=10.0,
    )
    f.__name__ = f"dantzig(k={k})"
    return f


def samuelson(k: int = 1):
    """Samuelson's policy: there's a drift, find it carefully.

    After Paul Samuelson (1965), who extended Bachelier's random walk
    with geometric drift for asset pricing. Strong prior on Holt
    linear and drift transforms. Moderate learning rate so the
    ensemble concentrates on the best drift tracker reasonably fast.

    Best for series with persistent but slowly varying drift — GDP,
    population, prices with inflation.
    """
    candidates, depths, groups = _build_candidates(k)

    # Strong prior on the drift and Holt-linear families (Samuelson's
    # geometric-drift random walk); a moderate prior on the remaining
    # depth-2 chains, which may compose drift with smoothing.
    prior = _prior_favoring_depths(depths, favored={2}, boost=2.0)
    for i in set(groups["drift"]) | set(groups["holt"]):
        prior[i] = 5.0

    f = terminal_leaf_ensemble(
        candidates, k=k,
        learning_rate=0.4,          # moderate — fast enough to find drift
        complexity_penalty=0.01,    # mild — willing to use drift+ema
        depths=depths,
        prior_log_weights=prior,
        max_components=15,
    )
    f.__name__ = f"samuelson(k={k})"
    return f


# ---------------------------------------------------------------------------
# Kahneman's policy: think fast and slow
# ---------------------------------------------------------------------------

def kahneman(k: int = 1, strength: float = 8.0):
    """Kahneman's policy: think fast and slow.

    A nod to the ``thinking_fast_and_slow`` skater in Cotton's
    timemachines package. This is a prior,
    not a new model — it draws on the same shared candidate population as
    every other policy. It simply places a strong prior on the candidates
    that embody the two-systems structure: a **fast** underlying-process
    tracker (System 1: reactive EMA, Holt, AR, drift) on the outside, and
    a **slowly-varying** residual scale (System 2: ``standardize`` with a
    long half-life) on the inside, over the plain Gaussian leaf.

    The point forecast reacts to every observation; the predicted
    *distribution* of the residuals drifts slowly. Because these
    candidates live in the shared pool, any policy (e.g. ``laplace``) can
    discover the pattern on its own — Kahneman just bets on it up front.

    Args:
        k: forecast horizon.
        strength: prior log-weight boost on the fast/slow candidates.
            Larger = a more committed bet on the two-systems structure. On
            slowly-varying-noise data a strong bet adapts faster than a
            uniform prior; on stationary data it costs a little early. The
            default trades these off (see examples/benchmark_kahneman.py).

    Best for series whose signal moves quickly but whose noise level is
    persistent — most financial and operational series.
    """
    candidates, depths, groups = _build_candidates(k)
    prior = _prior_favoring_indices(
        len(candidates), favored=set(groups["fast_slow"]), boost=strength
    )
    f = terminal_leaf_ensemble(
        candidates, k=k,
        learning_rate=0.5,
        complexity_penalty=0.01,
        depths=depths,
        prior_log_weights=prior,
        max_components=15,
    )
    f.__name__ = f"kahneman(k={k})"
    return f



def dirac(k: int = 1, spike_frac: float = 0.003):
    """Dirac's policy: bet on repetition.

    After Paul Dirac (the delta it collapses toward). Repetition is two distinct
    things, cleanly separated here:

    * the **projection** — actual probability *mass* on the exact repeated
      value — is handled at the terminal by :func:`sticky`, a mean-preserving
      near-Dirac atom weighted by the online repeat probability, and
    * the **pull** — the tendency of the mean to track the last value — is a
      *mean* statement and is left to the trunk, where the random-walk
      candidate earns its weight by likelihood on series that actually repeat.
      (It needs no special prior: a prior boost is a one-time initialisation
      and washes out after burn-in, so the ensemble must — and does — discover
      persistence on its own.)

    On administrative or grid-quoted series (policy rates, posted prices) that
    stay unchanged for long stretches, the projection captures the point mass
    (large likelihood, sharp intervals); on series that actually move it fades
    and ``dirac`` reduces to the ordinary skater.

    Args:
        k: forecast horizon.
        spike_frac: how hard the projection commits to the atom (smaller = harder).
    """
    f = sticky(skater(k=k), k=k, spike_frac=spike_frac)   # mean-preserving projection
    f.__name__ = f"dirac(k={k})"
    return f


def doob(k: int = 1):
    """Doob's policy: a driftless martingale with a stochastic volatility clock.

    After Joseph Doob (martingale theory). A committed **level-domain** model:
    the mean is pinned to the last value — a martingale, no drift and no mean
    reversion — and the only thing learned is how the volatility *breathes*. By
    the Dambis-Dubins-Schwarz theorem any continuous martingale is a
    time-changed Brownian motion, so the bet is exactly "BM on a stochastic
    clock".

    It is a Bayesian average over several martingale predictives that differ
    only in their volatility model (constant, GARCH, slowly-varying, and
    heavy-tailed). Because every candidate shares the *same* mean, the average
    does **not** wash out kurtosis (the usual BMA failure mode) — instead it
    blends the volatility clocks into one scale mixture and lets likelihood pick.

    Feed it the **level** series (prices, indices, rates), not pre-differenced
    changes. When the martingale prior holds — near-martingale levels — it beats
    the diffuse ``laplace`` ensemble by committing the mean and spending its
    capacity on the clock; on genuinely mean-reverting series (e.g. the VIX) the
    prior is wrong and it gives ground. A deliberately sharp instrument.
    """
    cands = [
        conjugate(leaf(k=k), difference(), k=k),                                       # constant vol
        conjugate(conjugate(leaf(k=k), garch(), k=k), difference(), k=k),              # GARCH clock
        conjugate(conjugate(leaf(k=k), standardize(0.02), k=k), difference(), k=k),    # slow clock
        conjugate(conjugate(scale_mixture_leaf(k=k), garch(), k=k), difference(), k=k),  # GARCH + heavy
        conjugate(scale_mixture_leaf(k=k), difference(), k=k),                         # EWMA + heavy
    ]
    f = bayesian_ensemble(cands, k=k, learning_rate=0.5, depths=[1, 2, 2, 2, 1],
                          max_components=30)
    f.__name__ = f"doob(k={k})"
    return f
