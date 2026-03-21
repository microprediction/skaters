"""Calibrated envelope: auto-selects decay to match target coverage.

Runs multiple envelope candidates (different decay rates) in parallel
over the same prediction stream. Each candidate tracks its own empirical
coverage — what fraction of resolved errors fall within ±1σ. The
candidate whose coverage is closest to the target (default 68.27% for
a Gaussian 1σ band) gets the most weight.

The skater only runs once per observation. The overhead is proportional
to the number of candidates, not the number of observations.
"""

from __future__ import annotations
import math
from collections import deque
from skaters.runstats import running_var_init, running_var_update, running_std_get
from skaters.envelope import _ew_update, _ew_std

# Default candidate decay rates (None = Welford/all-history)
DEFAULT_DECAYS = [None, 0.995, 0.99, 0.95, 0.9, 0.8]

# 1σ Gaussian coverage
GAUSSIAN_1SIGMA = 0.6827


def calibrated_envelope(
    skater,
    k: int = 1,
    target: float = GAUSSIAN_1SIGMA,
    decays: list[float | None] | None = None,
):
    """Wrap a skater with a self-calibrating envelope.

    Args:
        skater: any skater callable (y, state) -> (list[float], state)
        k: forecast horizon
        target: desired fraction of errors within ±1σ (default 68.27%)
        decays: candidate decay rates to try. None entries use Welford's.

    Returns:
        A callable: (y, state) -> (x_dict, state) where x_dict contains
        "mean", "std", and "coverage" (current empirical coverage of the
        selected blend).
    """
    if decays is None:
        decays = list(DEFAULT_DECAYS)
    n_cand = len(decays)

    def _calibrated(y: float, state: dict | None) -> tuple[dict, dict]:
        if state is None:
            state = {
                "inner": None,
                # Per-candidate, per-horizon: prediction queues and std queues
                "pred_queues": [[deque() for _ in range(k)] for _ in range(n_cand)],
                "std_queues": [[deque() for _ in range(k)] for _ in range(n_cand)],
                # Per-candidate, per-horizon: error variance tracking
                "welford": [[running_var_init() for _ in range(k)] for _ in range(n_cand)],
                "ew": [
                    [{"mean": 0.0, "var": 0.0, "n": 0} for _ in range(k)]
                    if d is not None else None
                    for d in decays
                ],
                # Per-candidate, per-horizon: coverage tracking
                "hits": [[0 for _ in range(k)] for _ in range(n_cand)],
                "total": [[0 for _ in range(k)] for _ in range(n_cand)],
            }

        # Run the skater once
        x, state["inner"] = skater(y, state["inner"])

        # Resolve pending predictions for each candidate
        for c in range(n_cand):
            for h in range(k):
                pq = state["pred_queues"][c][h]
                sq = state["std_queues"][c][h]
                if pq:
                    predicted = pq.popleft()
                    std_at_pred = sq.popleft()
                    error = y - predicted

                    # Update error stats for this candidate
                    if decays[c] is not None:
                        _ew_update(state["ew"][c][h], error, decays[c])
                    else:
                        state["welford"][c][h] = running_var_update(
                            state["welford"][c][h], error
                        )

                    # Update coverage: was |error| within ±1σ?
                    if math.isfinite(std_at_pred) and std_at_pred > 0:
                        state["total"][c][h] += 1
                        if abs(error) <= std_at_pred:
                            state["hits"][c][h] += 1

        # Compute current std for each candidate
        cand_stds = []
        for c in range(n_cand):
            if decays[c] is not None:
                stds = [_ew_std(state["ew"][c][h]) for h in range(k)]
            else:
                stds = [running_std_get(state["welford"][c][h]) for h in range(k)]
            cand_stds.append(stds)

        # Enqueue predictions and current std for each candidate
        for c in range(n_cand):
            for h in range(k):
                state["pred_queues"][c][h].append(x[h])
                state["std_queues"][c][h].append(cand_stds[c][h])

        # Blend candidates per horizon, weighted by coverage accuracy
        blended_std = []
        for h in range(k):
            weights = []
            for c in range(n_cand):
                total = state["total"][c][h]
                if total < 2 or not math.isfinite(cand_stds[c][h]):
                    weights.append(1.0)  # equal weight during burn-in
                else:
                    coverage = state["hits"][c][h] / total
                    gap = abs(coverage - target) + 1e-4
                    weights.append(1.0 / gap)

            w_total = sum(weights)
            s = sum(
                w * cand_stds[c][h]
                for c, w in enumerate(weights)
                if math.isfinite(cand_stds[c][h])
            )
            w_finite = sum(
                w for c, w in enumerate(weights)
                if math.isfinite(cand_stds[c][h])
            )
            if w_finite > 0:
                blended_std.append(s / w_finite)
            else:
                blended_std.append(float("inf"))

        return {"mean": x, "std": blended_std}, state

    _calibrated.__name__ = f"calibrated_envelope({getattr(skater, '__name__', '?')})"
    return _calibrated
