"""User-facing API.

Most users should just use `skater()`:

    from skaters import skater

    f = skater(k=3)
    state = None
    for y in observations:
        dists, state = f(y, state)
        print(dists[0].mean, dists[0].std)

Under the hood this builds a Bayesian ensemble of candidates at
various depths, with XGBoost-inspired regularization. The right
model complexity emerges from the data.
"""

from __future__ import annotations
from skaters.ema import ema
from skaters.leaf import leaf
from skaters.conjugate import conjugate
from skaters.transform import difference, fractional_difference, standardize, ema_transform
from skaters.ensemble import precision_weighted_ensemble
from skaters.bayesian import bayesian_ensemble


# ---------------------------------------------------------------------------
# The default: one function, good defaults
# ---------------------------------------------------------------------------

def skater(k: int = 1, aggressiveness: float = 0.5) -> object:
    """Create a general-purpose online forecaster.

    This is the recommended entry point. It builds a Bayesian ensemble
    of models at different depths and lets the data decide which
    complexity is appropriate.

    Args:
        k: forecast horizon (steps ahead). Default 1.
        aggressiveness: float in (0, 1). Controls adaptation speed.
            - 0.1: very conservative, slow to change, robust to noise
            - 0.5: balanced (default)
            - 0.9: aggressive, adapts fast, risks overfitting short-term

    Returns:
        A skater callable: (y, state) -> (list[Dist], state)

    Usage:
        from skaters import skater

        f = skater(k=3)
        state = None
        for y in observations:
            dists, state = f(y, state)
            # Point forecast
            print(dists[0].mean)
            # Uncertainty band
            print(dists[0].quantile(0.025), dists[0].quantile(0.975))
            # Log-likelihood
            print(dists[0].logpdf(y))
    """
    assert 0 < aggressiveness < 1

    # Map aggressiveness to learning rate and complexity penalty
    # Higher aggressiveness → higher learning rate (faster to concentrate)
    # Higher aggressiveness → lower complexity penalty (willing to go deep)
    learning_rate = 0.1 + 0.8 * aggressiveness  # [0.18, 0.82]
    complexity_penalty = 0.05 * (1 - aggressiveness)  # [0.025, 0.0]

    candidates, depths = _build_candidates(k)

    f = bayesian_ensemble(
        candidates, k=k,
        learning_rate=learning_rate,
        complexity_penalty=complexity_penalty,
        depths=depths,
        max_components=20,
    )
    f.__name__ = f"skater(k={k}, aggressiveness={aggressiveness})"
    return f


def _build_candidates(k: int):
    """Generate a diverse population of candidate models.

    Returns (candidates, depths) where depth is the number of
    transform layers in each candidate's chain.
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

    # Depth 1: differencing + leaf (predicts changes are ~zero)
    candidates.append(conjugate(leaf(k=k), difference(), k=k))
    depths.append(1)

    # Depth 2: differencing + EMA (predicts trend in changes)
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
            conjugate(conjugate(leaf(k=k), ema_transform(0.1), k=k), fractional_difference(d=d, window=30), k=k)
        )
        depths.append(2)

    return candidates, depths


# ---------------------------------------------------------------------------
# Named models (after the ideas they embody)
# ---------------------------------------------------------------------------

def brown(k: int = 1):
    """Robert G. Brown's exponential smoothing (1956). Fast-adapting EMA."""
    f = ema(alpha=0.3, k=k)
    f.__name__ = f"brown(k={k})"
    return f


def holt(k: int = 1):
    """Charles Holt's trend-following via differencing + EMA (1957)."""
    f = conjugate(ema(alpha=0.1, k=k), difference(), k=k)
    f.__name__ = f"holt(k={k})"
    return f


def hosking(k: int = 1):
    """Jonathan Hosking's fractional differencing + EMA (1981)."""
    f = conjugate(ema(alpha=0.1, k=k), fractional_difference(d=0.3, window=30), k=k)
    f.__name__ = f"hosking(k={k})"
    return f


def gauss(k: int = 1):
    """Carl Friedrich Gauss — standardize then predict in z-score space."""
    f = conjugate(ema(alpha=0.1, k=k), standardize(), k=k)
    f.__name__ = f"gauss(k={k})"
    return f


def laplace(k: int = 1):
    """Pierre-Simon Laplace — Bayesian ensemble, lets the data decide."""
    f = skater(k=k, aggressiveness=0.5)
    f.__name__ = f"laplace(k={k})"
    return f


# ---------------------------------------------------------------------------
# Speed-named aliases (backward compatibility)
# ---------------------------------------------------------------------------

def rapidly(k: int = 1):
    """EMA with alpha=0.3 — reacts fast to changes."""
    return ema(alpha=0.3, k=k)


def quickly(k: int = 1):
    """EMA with alpha=0.1 — moderate reactivity."""
    return ema(alpha=0.1, k=k)


def slowly(k: int = 1):
    """EMA with alpha=0.05 — smooth, slow-moving."""
    return ema(alpha=0.05, k=k)


def sluggishly(k: int = 1):
    """EMA with alpha=0.01 — very slow adaptation."""
    return ema(alpha=0.01, k=k)


def ensemble(k: int = 1):
    """Precision-weighted ensemble of EMA models at different speeds."""
    return precision_weighted_ensemble(
        skaters=[rapidly(k), quickly(k), slowly(k), sluggishly(k)],
        k=k,
    )
