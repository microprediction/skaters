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
from skaters.leaf import leaf
from skaters.conjugate import conjugate
from skaters.transform import (
    difference, fractional_difference, standardize, ema_transform,
    garch, power_transform, drift, holt_linear, ar, theta,
)
from skaters.search import search as adaptive_search
from skaters.bayesian import bayesian_ensemble


# ---------------------------------------------------------------------------
# Candidate population (shared by all search policies)
# ---------------------------------------------------------------------------

def _build_candidates(k: int):
    """Generate the full candidate population.

    Every search policy considers ALL of these. The policy only
    affects how they are weighted, not which ones are included.

    Returns (candidates, depths).
    """
    candidates = []
    depths = []

    # Depth 0: just noise (baseline)
    candidates.append(leaf(k=k))
    depths.append(0)

    # Depth 1: single EMA at various speeds
    for alpha in [0.01, 0.05, 0.1, 0.3]:
        candidates.append(conjugate(leaf(k=k), ema_transform(alpha), k=k))
        depths.append(1)

    # Depth 1: differencing + leaf (pure random walk)
    candidates.append(conjugate(leaf(k=k), difference(), k=k))
    depths.append(1)

    # Depth 1: drift + leaf (random walk with adaptive drift)
    # Multiple speeds: fast drift detection vs long-memory drift
    for a, s in [(0.05, 0.01), (0.01, 0.002), (0.002, 0.001), (0.0005, 0.0002)]:
        candidates.append(conjugate(leaf(k=k), drift(alpha=a, shrinkage=s), k=k))
        depths.append(1)

    # Depth 1: Theta method (SES + half OLS slope)
    for a in [0.05, 0.1, 0.3]:
        candidates.append(conjugate(leaf(k=k), theta(alpha=a), k=k))
        depths.append(1)

    # Depth 1: AR at depth 1 (captures mean reversion, persistence)
    candidates.append(conjugate(leaf(k=k), ar(1), k=k))
    depths.append(1)
    candidates.append(conjugate(leaf(k=k), ar(2, decay=1), k=k))
    depths.append(1)

    # Depth 1: Holt linear (level + trend, single transform)
    for a, b in [(0.1, 0.02), (0.1, 0.05), (0.3, 0.1)]:
        candidates.append(conjugate(leaf(k=k), holt_linear(alpha=a, beta=b), k=k))
        depths.append(1)

    # Depth 2: differencing + EMA
    for alpha in [0.05, 0.1, 0.3]:
        candidates.append(
            conjugate(conjugate(leaf(k=k), ema_transform(alpha), k=k), difference(), k=k)
        )
        depths.append(2)

    # Depth 2: standardize + EMA
    for alpha in [0.05, 0.1]:
        candidates.append(
            conjugate(conjugate(leaf(k=k), ema_transform(alpha), k=k), standardize(), k=k)
        )
        depths.append(2)

    # Depth 2: fractional diff + EMA
    for d in [0.2, 0.4]:
        candidates.append(
            conjugate(conjugate(leaf(k=k), ema_transform(0.1), k=k),
                      fractional_difference(d=d, window=30), k=k)
        )
        depths.append(2)

    # Depth 2: drift + EMA (drift removal then level tracking)
    for a_drift, s_drift in [(0.002, 0.001), (0.0005, 0.0002)]:
        for a_ema in [0.05, 0.1]:
            candidates.append(
                conjugate(conjugate(leaf(k=k), ema_transform(a_ema), k=k),
                          drift(alpha=a_drift, shrinkage=s_drift), k=k)
            )
            depths.append(2)

    # Depth 2: drift + Holt linear (drift on top of level+trend)
    candidates.append(
        conjugate(conjugate(leaf(k=k), holt_linear(0.1, 0.05), k=k),
                  drift(alpha=0.001, shrinkage=0.0005), k=k)
    )
    depths.append(2)

    # Depth 2: GARCH + EMA (volatility-adapted)
    candidates.append(
        conjugate(conjugate(leaf(k=k), ema_transform(0.1), k=k), garch(), k=k)
    )
    depths.append(2)

    # Depth 2: power transform + EMA (tail compression)
    candidates.append(
        conjugate(conjugate(leaf(k=k), ema_transform(0.1), k=k), power_transform(0.5), k=k)
    )
    depths.append(2)

    return candidates, depths


def _prior_favoring_depths(depths: list[int], favored: set[int], boost: float = 2.0) -> list[float]:
    """Compute prior log-weights that boost candidates at certain depths."""
    return [boost if d in favored else 0.0 for d in depths]


def _prior_favoring_transform(candidates: list, transform_name: str, boost: float = 3.0) -> list[float]:
    """Boost candidates that contain a specific transform in their name."""
    prior = []
    for c in candidates:
        name = getattr(c, '__name__', '')
        prior.append(boost if transform_name in name else 0.0)
    return prior


def _prior_favoring_indices(n: int, favored: set[int], boost: float = 2.0) -> list[float]:
    """Compute prior log-weights that boost specific candidate indices."""
    return [boost if i in favored else 0.0 for i in range(n)]


# ---------------------------------------------------------------------------
# The default entry point
# ---------------------------------------------------------------------------

def skater(k: int = 1, aggressiveness: float = 0.5):
    """Create a general-purpose online forecaster.

    Builds a Bayesian ensemble over a diverse candidate population
    and lets the data decide which complexity is appropriate.

    Args:
        k: forecast horizon (steps ahead).
        aggressiveness: float in (0, 1). Controls adaptation speed.
            Low = conservative (slow to change, penalizes complexity).
            High = aggressive (adapts fast, tolerates complexity).
    """
    assert 0 < aggressiveness < 1
    learning_rate = 0.1 + 0.8 * aggressiveness
    complexity_penalty = 0.05 * (1 - aggressiveness)

    candidates, depths = _build_candidates(k)
    f = bayesian_ensemble(
        candidates, k=k,
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
    candidates, depths = _build_candidates(k)
    # Boost differencing models (indices 5-8: diff+leaf and diff+EMA variants)
    prior = _prior_favoring_indices(len(candidates), favored={5, 6, 7, 8}, boost=3.0)
    f = bayesian_ensemble(
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
    candidates, depths = _build_candidates(k)
    # Boost fractional diff models (last 2 candidates)
    n = len(candidates)
    prior = _prior_favoring_indices(n, favored={n - 2, n - 1}, boost=3.0)
    f = bayesian_ensemble(
        candidates, k=k,
        learning_rate=0.5,
        complexity_penalty=0.01,
        depths=depths,
        prior_log_weights=prior,
        max_components=15,
    )
    f.__name__ = f"hosking(k={k})"
    return f


def laplace(k: int = 1):
    """Laplace's policy: maximum ignorance.

    After Pierre-Simon Laplace. Uniform prior — no preference for any
    model class. Pure Bayesian updating. Learning rate close to 1 for
    fast convergence. Minimal complexity penalty. Let the data speak.
    """
    candidates, depths = _build_candidates(k)
    f = bayesian_ensemble(
        candidates, k=k,
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
    candidates, depths = _build_candidates(k)
    prior = _prior_favoring_depths(depths, favored={0}, boost=2.0)
    f = bayesian_ensemble(
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
    """Dantzig's policy: optimize under constraints.

    After George Dantzig (1947). Uses adaptive search with a tight
    compute budget — only cheap transforms (cost <= 5 per candidate).
    Excludes fractional differencing and other expensive operations.
    Best when you need fast predictions on high-frequency data.
    """
    f = adaptive_search(
        k=k,
        learning_rate=0.5,
        complexity_penalty=0.02,
        max_pool=15,
        expand_interval=100,
        max_depth=2,
        cost_budget=5.0,
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
    candidates, depths = _build_candidates(k)

    # Build prior: strongly boost drift and holt_linear candidates
    # We identify them by their position in the candidate pool
    # (see _build_candidates for the layout)
    n = len(candidates)
    prior = [0.0] * n
    for i in range(n):
        d = depths[i]
        # Depth-1 drift and holt_linear candidates get a big boost
        # Depth-2 drift-containing candidates get a moderate boost
        # Everything else gets no boost
        if d == 1 and i >= 6:
            # drift|leaf and holt|leaf candidates (after diff|leaf at index 5)
            prior[i] = 5.0
        elif d == 2:
            prior[i] = 2.0  # depth-2 candidates that may contain drift

    f = bayesian_ensemble(
        candidates, k=k,
        learning_rate=0.4,          # moderate — fast enough to find drift
        complexity_penalty=0.01,    # mild — willing to use drift+ema
        depths=depths,
        prior_log_weights=prior,
        max_components=15,
    )
    f.__name__ = f"samuelson(k={k})"
    return f



