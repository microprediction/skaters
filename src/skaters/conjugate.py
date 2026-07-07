"""Conjugation: change of reference frame for a skater.

Given an invertible transform T and a skater f, conjugation produces
a new skater that:

    1. Transforms each observation:  y' = T.forward(y)
    2. Feeds y' to f to get k Dist predictions in transformed space
    3. Inverts the predictions:  dists = T.inverse_k(dists')

This lets f predict a simpler series (e.g., stationary residuals)
while the conjugated skater predicts in the original space.
"""

from __future__ import annotations
from skaters.dist import Dist


def conjugate(skater, transform, k: int = 1):
    """Conjugate a skater with an invertible transform.

    Args:
        skater: any skater callable (y, state) -> (list[Dist], state)
        transform: a (forward, inverse_k) pair from transform.py
        k: forecast horizon (must match the skater's k)

    Returns:
        A skater callable: (y, state) -> (list[Dist], state)
    """
    forward, inverse_k = transform

    def _conjugated(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {"t_state": None, "s_state": None}

        # Forward transform
        y_prime, state["t_state"] = forward(y, state["t_state"])

        # Predict in transformed space (returns list[Dist])
        dists_prime, state["s_state"] = skater(y_prime, state["s_state"])
        assert len(dists_prime) == k, (
            f"conjugate(k={k}) wraps a skater emitting {len(dists_prime)} horizons; "
            "k must match the wrapped skater's k"
        )

        # Invert predictions back to original space
        dists = inverse_k(dists_prime, state["t_state"])

        return dists, state

    _conjugated.__name__ = f"conjugate({getattr(skater, '__name__', '?')})"
    return _conjugated
