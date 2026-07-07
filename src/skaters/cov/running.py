"""Online covariance via extended Welford's algorithm.

Processes one observation vector at a time. Numerically stable.
"""

from __future__ import annotations


def running_cov(y: list[float], state: dict | None) -> tuple[list[float], list[float], dict]:
    """Update running mean and covariance with a new observation vector.

    Args:
        y: observation vector (list of floats, length n)
        state: prior state (None on first call)

    Returns:
        mean: current mean vector (length n)
        cov: current covariance matrix (flat, n*n, row-major)
        state: updated state
    """
    n = len(y)
    if state is None:
        state = {
            "n": 0,
            "mean": [0.0] * n,
            "C": [0.0] * (n * n),  # sum of (y-mean)(y-mean)^T
        }

    state["n"] += 1
    k = state["n"]
    mean = state["mean"]
    C = state["C"]

    # Welford update
    delta = [y[i] - mean[i] for i in range(n)]
    for i in range(n):
        mean[i] += delta[i] / k
    delta2 = [y[i] - mean[i] for i in range(n)]
    for i in range(n):
        for j in range(n):
            C[i * n + j] += delta[i] * delta2[j]

    # Sample covariance
    if k < 2:
        cov = [0.0] * (n * n)
    else:
        cov = [C[i] / (k - 1) for i in range(n * n)]

    return list(mean), cov, state
