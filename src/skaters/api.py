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
    garch, power_transform,
)
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

    # Depth 1: differencing + leaf
    candidates.append(conjugate(leaf(k=k), difference(), k=k))
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

def brown(k: int = 1):
    """Brown's policy: trust simplicity.

    After Robert G. Brown (1956). Strong prior on smooth, simple models
    (depth 0-1). High complexity penalty. Slow to adapt. Best when you
    believe the series is stationary or nearly so.
    """
    candidates, depths = _build_candidates(k)
    prior = _prior_favoring_depths(depths, favored={0, 1}, boost=3.0)
    f = bayesian_ensemble(
        candidates, k=k,
        learning_rate=0.3,
        complexity_penalty=0.05,
        depths=depths,
        prior_log_weights=prior,
        max_components=15,
    )
    f.__name__ = f"brown(k={k})"
    return f


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
