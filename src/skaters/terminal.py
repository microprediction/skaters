"""Terminal-leaf ensemble: mix for the mean, model the residual once.

Bayesian model averaging over a heterogeneous pool combines full predictive
distributions, which preserves the combined *mean* and *variance* but washes
out higher moments — so a heavy-tailed leaf used inside the pool collapses
back to Gaussian shape at the output (verified empirically).

This ensemble fixes that. It uses the sub-models only as **mean forecasters**:
it weights them by predictive likelihood (as in :func:`bayesian_ensemble`),
combines their means, and then models the distribution of the *combined
residual* with a single terminal leaf — **model first, conform last**. The
default terminal leaf is :func:`crps_leaf` (the residual is shaped to minimise
CRPS); pass ``leaf_fn=scale_mixture_leaf`` for the likelihood objective.
Because there is exactly one leaf at the end, its shape reaches the output
undiluted.

    y --[weighted mix of candidate means]--> mu_hat
    residual = y - mu_hat  -->  terminal leaf  -->  D
    predictive = D shifted by mu_hat

Everything still flows as :class:`Dist`; this is just *where* the residual
distribution is estimated — once, at the top, instead of once per candidate.
"""

from __future__ import annotations
import math
from collections import deque
from skaters.dist import Dist
from skaters.leaf import crps_leaf


def terminal_leaf_ensemble(
    skaters: list,
    leaf_fn=crps_leaf,
    k: int = 1,
    learning_rate: float = 0.5,
    complexity_penalty: float = 0.0,
    depths: list[int] | None = None,
    prior_log_weights: list[float] | None = None,
    max_components: int = 20,
    forget: float = 1.0,
):
    """Create a terminal-leaf ensemble.

    Args:
        skaters: sub-models used as mean forecasters.
        leaf_fn: factory for the terminal residual leaf (default :func:`crps_leaf`;
            pass ``scale_mixture_leaf`` for the likelihood objective).
        k: forecast horizon.
        learning_rate: eta for the likelihood-based mean weighting.
        complexity_penalty: per-depth penalty (as in bayesian_ensemble).
        depths, prior_log_weights: optional, one per sub-model.
        max_components: prune the warm-up fallback mixture to this many.
        forget: geometric discount on accumulated log-evidence per step. 1.0 is
            exact cumulative updating (the ensemble converges to a fixed winner);
            values just below 1 (e.g. 0.99) keep it adaptive to regime change at
            negligible steady-state cost.
    """
    n = len(skaters)
    assert n > 0
    depths = depths if depths is not None else [0] * n
    prior = prior_log_weights if prior_log_weights is not None else [0.0] * n

    def _skater(y: float, state: dict | None) -> tuple[list[Dist], dict]:
        if state is None:
            state = {
                "sub": [None] * n,
                "qdist": [deque() for _ in range(n)],          # h=1 Dist queue for weighting
                "log_w": [prior[i] for i in range(n)],
                "tleaf": [leaf_fn(k=1) for _ in range(k)],      # one terminal leaf per horizon
                "leaf_state": [None] * k,
                "leaf_pred": [None] * k,
                "mean_q": [deque() for _ in range(k)],          # pending combined means per horizon
            }

        # Run all sub-models; collect their k Dists.
        all_dists = []
        for i, f in enumerate(skaters):
            di, state["sub"][i] = f(y, state["sub"][i])
            all_dists.append(di)

        # Update model weights from the resolved one-step prediction. The `forget`
        # factor (< 1) geometrically discounts past log-evidence so the ensemble
        # stays adaptive to regime change and the weight gap cannot diverge; at
        # forget == 1.0 this is exact cumulative updating (the historical default).
        for i in range(n):
            q = state["qdist"][i]
            if q:
                lp = max(q.popleft().logpdf(y), -20.0)
                state["log_w"][i] = (forget * state["log_w"][i]
                                     + learning_rate * lp - complexity_penalty * depths[i])
            q.append(all_dists[i][0])

        log_w = state["log_w"]
        max_lw = max(log_w)
        w = [math.exp(lw - max_lw) for lw in log_w]
        tot = sum(w)

        combined = []
        for h in range(k):
            mu_h = sum(w[i] * all_dists[i][h].mean for i in range(n)) / tot

            # Resolve the h-step-ahead combined-mean prediction made (h+1) steps
            # ago into a residual, and update this horizon's terminal leaf.
            mq = state["mean_q"][h]
            if len(mq) >= h + 1:
                r = y - mq.popleft()
                ld, state["leaf_state"][h] = state["tleaf"][h](r, state["leaf_state"][h])
                state["leaf_pred"][h] = ld[0]

            if state["leaf_pred"][h] is not None:
                pred = state["leaf_pred"][h].shift(mu_h)
            else:
                # Warm-up: fall back to the candidate mixture until the leaf has data.
                pred = Dist.combine([all_dists[i][h] for i in range(n)], w)
                if len(pred) > max_components:
                    pred = pred.prune(max_components)
            combined.append(pred)
            mq.append(mu_h)

        return combined, state

    _skater.__name__ = f"terminal_leaf_ensemble(n={n}, k={k})"
    return _skater
