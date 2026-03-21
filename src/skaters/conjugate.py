"""Conjugation: change of reference frame for a skater.

Given an invertible transform T and a skater f, conjugation produces
a new skater that:

    1. Transforms each observation:  y' = T.forward(y)
    2. Feeds y' to f to get k-step predictions in transformed space
    3. Inverts the predictions:  x = T.inverse_k(x')

This lets f predict a simpler series (e.g., stationary residuals)
while the conjugated skater predicts in the original space.

Everything is online: T.forward processes one observation at a time,
f is an online skater, and T.inverse_k maps k predictions back.
"""

from __future__ import annotations


def conjugate(skater, transform, k: int = 1):
    """Conjugate a skater with an invertible transform.

    Args:
        skater: any skater callable (y, state) -> (list[float], state)
        transform: a (forward, inverse_k) pair from transform.py
        k: forecast horizon (must match the skater's k)

    Returns:
        A skater callable: (y, state) -> (list[float], state)
    """
    forward, inverse_k = transform

    def _conjugated(y: float, state: dict | None) -> tuple[list[float], dict]:
        if state is None:
            state = {"t_state": None, "s_state": None}

        # Forward transform
        y_prime, state["t_state"] = forward(y, state["t_state"])

        # Predict in transformed space
        x_prime, state["s_state"] = skater(y_prime, state["s_state"])

        # Invert predictions back to original space
        x = inverse_k(x_prime, state["t_state"])

        return x, state

    _conjugated.__name__ = f"conjugate({getattr(skater, '__name__', '?')})"
    return _conjugated
