"""Bayesian model averaging ensemble with XGBoost-inspired regularization.

Weights models by cumulative log-likelihood of their distributional
predictions, with two regularization mechanisms borrowed from gradient
boosting:

1. Learning rate (shrinkage): log_w_i += η * logpdf_i(y) instead of
   the full logpdf. Prevents over-concentrating on one model, keeps
   the ensemble adaptive to regime changes. Analogous to XGBoost's
   learning rate which dampens each tree's contribution.

2. Complexity penalty: each model can declare a "depth" (number of
   transforms in its chain). Deeper models get a per-step penalty
   subtracted from their log-likelihood, analogous to XGBoost's
   γ * n_leaves regularization. This forces deeper chains to capture
   genuine structure, not just overfit noise.

The ensemble uses Dist.combine() for exact mixture combination —
no information is lost.
"""

from __future__ import annotations
import math
from collections import deque
from skaters.dist import Dist


def bayesian_ensemble(
    skaters: list,
    k: int = 1,
    learning_rate: float = 0.5,
    complexity_penalty: float = 0.0,
    depths: list[int] | None = None,
    max_components: int = 20,
):
    """Create a Bayesian model-averaging ensemble.

    Args:
        skaters: list of skater callables
        k: forecast horizon
        learning_rate: η in (0, 1]. Smaller = more conservative, more
            robust to regime change. At η=1, this is exact Bayesian
            updating. At η→0, weights stay uniform.
        complexity_penalty: λ ≥ 0. Per-step penalty per unit of depth.
            At λ=0, no complexity penalty. Larger values favor simpler
            models more aggressively.
        depths: optional list of model depths (one per skater). If not
            provided, all depths are assumed 0 (no penalty).
        max_components: prune the combined Dist to this many components
            to prevent unbounded growth.

    Returns:
        A skater callable: (y, state) -> (list[Dist], state)
    """
    n = len(skaters)
    assert n > 0
    assert 0 < learning_rate <= 1
    assert complexity_penalty >= 0

    if depths is None:
        depths = [0] * n

    def _skater(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {
                "sub": [None] * n,
                # Per-model, per-horizon: queued Dist predictions awaiting resolution
                "queues": [[deque() for _ in range(k)] for _ in range(n)],
                # Per-model, per-horizon: cumulative log-weight
                "log_w": [[0.0] * k for _ in range(n)],
                "n_obs": 0,
            }

        state["n_obs"] += 1

        # Run all sub-models
        all_dists = []
        for i, f in enumerate(skaters):
            dists_i, state["sub"][i] = f(y, state["sub"][i])
            all_dists.append(dists_i)

        # Resolve pending predictions: score each model's past Dist against y
        for i in range(n):
            for h in range(k):
                q = state["queues"][i][h]
                if q:
                    past_dist = q.popleft()
                    lp = past_dist.logpdf(y)
                    # Clamp logpdf to prevent a single bad prediction from
                    # permanently killing a model. This is the "mixability"
                    # trick from online learning — bounded losses.
                    lp = max(lp, -20.0)
                    # XGBoost-inspired: shrunk log-likelihood minus complexity penalty
                    state["log_w"][i][h] += (
                        learning_rate * lp
                        - complexity_penalty * depths[i]
                    )

        # Enqueue current predictions for future scoring
        for i in range(n):
            for h in range(k):
                state["queues"][i][h].append(all_dists[i][h])

        # Compute softmax weights per horizon, then combine
        combined = []
        for h in range(k):
            log_ws = [state["log_w"][i][h] for i in range(n)]

            # Numerically stable softmax
            max_lw = max(log_ws)
            if math.isfinite(max_lw):
                weights = [math.exp(lw - max_lw) for lw in log_ws]
            else:
                weights = [1.0] * n  # fallback to uniform

            horizon_dists = [all_dists[i][h] for i in range(n)]
            dist = Dist.combine(horizon_dists, weights)

            # Prune to bound component growth
            if len(dist) > max_components:
                dist = dist.prune(max_components)

            combined.append(dist)

        return combined, state

    _skater.__name__ = f"bayesian_ensemble(n={n}, k={k}, η={learning_rate})"
    return _skater
