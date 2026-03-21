"""Portfolio of policies via Hierarchical Risk Parity.

Instead of picking one policy, run several and combine their
distributional predictions using HRP-inspired weights derived
from their online rank correlation.

The idea (from Lopez de Prado, 2016): policies that are
uncorrelated with each other provide diversification. Weight
them so that each "cluster" of similar policies contributes
equally, preventing redundant policies from dominating.

Pure Python implementation — no scipy, no numpy.
"""

from __future__ import annotations
import math
from collections import deque
from skaters.dist import Dist


def portfolio(
    policy_factories: list,
    k: int = 1,
    window: int = 200,
    rebalance_interval: int = 100,
    max_components: int = 20,
):
    """Create a portfolio of policies with HRP-inspired weighting.

    Args:
        policy_factories: list of callables, each taking k and returning
            a skater. E.g. [bachelier, laplace, yule].
        k: forecast horizon.
        window: number of recent observations for correlation estimation.
        rebalance_interval: recompute weights every N observations.
        max_components: prune combined Dist to this many components.

    Returns:
        A skater callable: (y, state) -> (list[Dist], state)
    """
    n = len(policy_factories)
    assert n > 0

    def _portfolio(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {
                "skaters": [f(k=k) for f in policy_factories],
                "sub_states": [None] * n,
                "rank_history": deque(maxlen=window),
                "weights": [1.0 / n] * n,
                "n_obs": 0,
                "prev_means": [None] * n,
            }

        state["n_obs"] += 1

        # Run all policies
        all_dists = []
        for i in range(n):
            dists_i, state["sub_states"][i] = state["skaters"][i](y, state["sub_states"][i])
            all_dists.append(dists_i)

        # Track ranks based on previous predictions
        if all(m is not None for m in state["prev_means"]):
            errors = [abs(state["prev_means"][i] - y) for i in range(n)]
            ranks = _rank(errors)  # lower error = better rank = lower number
            state["rank_history"].append(ranks)

        # Store current predictions for next step's ranking
        for i in range(n):
            state["prev_means"][i] = all_dists[i][0].mean

        # Periodically rebalance weights using rank correlation
        if (state["n_obs"] % rebalance_interval == 0
                and len(state["rank_history"]) >= 20):
            corr = _rank_correlation_matrix(state["rank_history"], n)
            state["weights"] = _hrp_weights(corr, n)

        # Combine predictions with current weights
        combined = []
        for h in range(k):
            horizon_dists = [all_dists[i][h] for i in range(n)]
            dist = Dist.combine(horizon_dists, state["weights"])
            if len(dist) > max_components:
                dist = dist.prune(max_components)
            combined.append(dist)

        return combined, state

    names = [f.__name__ if hasattr(f, '__name__') else '?' for f in policy_factories]
    _portfolio.__name__ = f"portfolio({','.join(names)})"
    return _portfolio


def _rank(values: list[float]) -> list[int]:
    """Rank values (1 = smallest)."""
    indexed = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0] * len(values)
    for r, i in enumerate(indexed):
        ranks[i] = r + 1
    return ranks


def _rank_correlation_matrix(history: deque, n: int) -> list[list[float]]:
    """Compute Spearman rank correlation from rank history."""
    T = len(history)
    if T < 2:
        return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    # Compute means
    means = [0.0] * n
    for ranks in history:
        for i in range(n):
            means[i] += ranks[i]
    means = [m / T for m in means]

    # Compute correlation matrix
    corr = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            cov = 0.0
            var_i = 0.0
            var_j = 0.0
            for ranks in history:
                di = ranks[i] - means[i]
                dj = ranks[j] - means[j]
                cov += di * dj
                var_i += di * di
                var_j += dj * dj
            if var_i > 0 and var_j > 0:
                corr[i][j] = cov / math.sqrt(var_i * var_j)
            else:
                corr[i][j] = 1.0 if i == j else 0.0
            corr[j][i] = corr[i][j]

    return corr


def _hrp_weights(corr: list[list[float]], n: int) -> list[float]:
    """Compute HRP-inspired weights from a correlation matrix.

    Simplified HRP:
    1. Compute distance matrix from correlation
    2. Single-linkage hierarchical clustering
    3. Recursive bisection with inverse-variance weighting

    For simplicity, we use a direct approach: weight each policy
    inversely proportional to its average absolute correlation with
    all others. This captures the HRP intuition (uncorrelated policies
    get more weight) without the full clustering machinery.
    """
    if n == 1:
        return [1.0]

    # Average absolute correlation with others
    avg_corr = []
    for i in range(n):
        total = sum(abs(corr[i][j]) for j in range(n) if j != i)
        avg_corr.append(total / (n - 1))

    # Inverse correlation weighting (more unique = more weight)
    raw_weights = []
    for ac in avg_corr:
        # Avoid division by zero; cap at minimum correlation
        raw_weights.append(1.0 / max(ac, 0.05))

    # Normalize
    total = sum(raw_weights)
    return [w / total for w in raw_weights]
