"""Covariance-aware forecast combination via HRP.

Combines multiple skaters using the online covariance matrix of
their forecast errors, weighted via Hierarchical Risk Parity
(Lopez de Prado, 2016).

HRP avoids matrix inversion (unstable for small samples) by:
1. Clustering models by error correlation
2. Recursively bisecting the tree
3. Allocating weight inversely proportional to cluster variance

This is the robust way to do Bates & Granger (1969) forecast
combination — it uses the full covariance structure without
requiring a matrix inverse.
"""

from __future__ import annotations
import math
from collections import deque
from skaters.dist import Dist
from skaters.cov.shrinkage import ledoit_wolf_cov


def hrp_ensemble(
    skaters: list,
    k: int = 1,
    alpha: float = 0.02,
    shrinkage: float = 0.3,
    max_components: int = 20,
):
    """HRP-weighted forecast combination using online error covariance.

    Args:
        skaters: list of skater callables
        k: forecast horizon
        alpha: EMA smoothing for covariance estimation
        shrinkage: Ledoit-Wolf shrinkage toward identity (0-1)
        max_components: prune combined Dist

    Returns:
        A skater callable: (y, state) -> (list[Dist], state)
    """
    n = len(skaters)
    assert n > 0

    def _skater(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {
                "sub": [None] * n,
                "queues": [[deque() for _ in range(k)] for _ in range(n)],
                "cov_states": [None] * k,
                "weights": [[1.0 / n] * n for _ in range(k)],
                "n_obs": 0,
            }

        state["n_obs"] += 1

        # Run all sub-models
        all_dists = []
        for i, f in enumerate(skaters):
            dists_i, state["sub"][i] = f(y, state["sub"][i])
            all_dists.append(dists_i)

        # Resolve pending predictions: compute error vector
        for h in range(k):
            errors = []
            have_errors = True
            for i in range(n):
                q = state["queues"][i][h]
                if q:
                    pred_mean = q.popleft()
                    errors.append(y - pred_mean)
                else:
                    have_errors = False
                    break

            if have_errors and len(errors) == n:
                # Update error covariance
                _, _, state["cov_states"][h] = ledoit_wolf_cov(
                    errors, state["cov_states"][h],
                    alpha=alpha, shrinkage=shrinkage,
                )
                # Recompute HRP weights from covariance
                if state["n_obs"] > n + 5:
                    var = state["cov_states"][h]["var"]
                    corr = state["cov_states"][h]["corr"]
                    state["weights"][h] = _hrp_from_corr(var, corr, n)

        # Enqueue current predictions
        for i in range(n):
            for h in range(k):
                state["queues"][i][h].append(all_dists[i][h].mean)

        # Combine with current weights
        combined = []
        for h in range(k):
            horizon_dists = [all_dists[i][h] for i in range(n)]
            dist = Dist.combine(horizon_dists, state["weights"][h])
            if len(dist) > max_components:
                dist = dist.prune(max_components)
            combined.append(dist)

        return combined, state

    _skater.__name__ = f"hrp_ensemble(n={n}, k={k})"
    return _skater


def _hrp_from_corr(var: list[float], corr: list[float], n: int) -> list[float]:
    """Compute HRP weights from variance and correlation.

    Simplified HRP:
    1. Distance matrix from correlation
    2. Single-linkage clustering (greedy)
    3. Recursive bisection with inverse-variance allocation

    For small n (typical: 5-20 models), this is fast enough.
    """
    if n == 1:
        return [1.0]

    # Step 1: distance matrix
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            r = corr[i * n + j]
            dist[i][j] = math.sqrt(max(0.0, 2.0 * (1.0 - r)))

    # Step 2: single-linkage clustering → ordering
    order = _quasi_diag(dist, n)

    # Step 3: recursive bisection
    weights = [0.0] * n
    _recursive_bisect(weights, order, var, corr, n)

    # Normalize
    total = sum(weights)
    if total < 1e-12:
        return [1.0 / n] * n
    return [w / total for w in weights]


def _quasi_diag(dist: list[list[float]], n: int) -> list[int]:
    """Single-linkage clustering to produce a quasi-diagonal ordering.

    Returns indices ordered so that correlated items are adjacent.
    """
    # Simple greedy nearest-neighbor ordering
    remaining = set(range(n))
    order = [0]
    remaining.remove(0)
    while remaining:
        last = order[-1]
        nearest = min(remaining, key=lambda j: dist[last][j])
        order.append(nearest)
        remaining.remove(nearest)
    return order


def _recursive_bisect(weights: list[float], order: list[int],
                       var: list[float], corr: list[float], n: int):
    """Recursive bisection: split the ordered list, allocate weight
    inversely proportional to cluster variance."""
    if len(order) == 1:
        weights[order[0]] = 1.0
        return

    mid = len(order) // 2
    left = order[:mid]
    right = order[mid:]

    # Cluster variance = average variance * (1 + average within-cluster correlation)
    v_left = _cluster_var(left, var, corr, n)
    v_right = _cluster_var(right, var, corr, n)

    # Inverse-variance allocation
    total_inv = 0.0
    if v_left > 1e-16:
        total_inv += 1.0 / v_left
    if v_right > 1e-16:
        total_inv += 1.0 / v_right

    if total_inv < 1e-16:
        alpha = 0.5
    else:
        alpha = (1.0 / v_left if v_left > 1e-16 else 0.0) / total_inv

    _recursive_bisect(weights, left, var, corr, n)
    _recursive_bisect(weights, right, var, corr, n)

    # Scale
    for i in left:
        weights[i] *= alpha
    for i in right:
        weights[i] *= (1.0 - alpha)


def _cluster_var(indices: list[int], var: list[float],
                 corr: list[float], n: int) -> float:
    """Estimate the variance of an equal-weight portfolio over a cluster."""
    m = len(indices)
    if m == 0:
        return 1e-8
    total = 0.0
    for i in indices:
        for j in indices:
            si = math.sqrt(var[i]) if var[i] > 1e-16 else 1e-8
            sj = math.sqrt(var[j]) if var[j] > 1e-16 else 1e-8
            r = corr[i * n + j]
            total += si * sj * r
    return max(total / (m * m), 1e-16)
