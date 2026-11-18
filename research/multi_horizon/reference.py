"""Affine reference frames indexed by issue time and forecast lead."""

from __future__ import annotations

from collections import deque
import math

from skaters.dist import Dist
from skaters.parade import _missing


def horizon_conjugate(reference, inner, k: int):
    """Forecast each reference's h-step errors h ticks ahead.

    The reference is a skater returning k distributions. Its lead-h mean and
    standard deviation define the frame issued at t for target t+h. A zero
    scale uses unit scale. The frame is frozen until its target arrives.

    At time t, inner(k=h) consumes (y[t]-location[t-h,h])/scale[t-h,h]. Its
    h-step predictive is mapped back using the frame issued now for t+h.
    The reference supplies the forecast until a residual first matures.

    This experiment uses finite observations at regular ticks. All issue-time
    frames are immutable pairs of numbers. State is picklable and retained
    frame storage is O(k**2), plus each inner skater's own state.
    """
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError("k must be a positive integer")
    residual_skaters = [inner(k=h) for h in range(1, k + 1)]

    def step(y: float, state: dict | None = None) -> tuple[list[Dist], dict]:
        if _missing(y):
            raise ValueError("horizon_conjugate currently needs a finite observation at every tick")
        if state is None:
            state = {"reference": None, "inner": [None] * k,
                     "frames": deque(maxlen=k), "residuals": [None] * k}

        direct, state["reference"] = reference(y, state["reference"])
        if len(direct) != k:
            raise ValueError(f"reference must emit exactly {k} forecasts")
        current = tuple((d.mean, d.std or 1.0) for d in direct)
        if any(not math.isfinite(loc) or not math.isfinite(scale) or scale <= 0.0
               for loc, scale in current):
            raise ValueError("reference frames need finite locations and positive finite scales")
        frames = state["frames"]
        residuals = [None] * k
        forecasts = list(direct)

        for i, residual_skater in enumerate(residual_skaters):
            h = i + 1
            if h > len(frames):
                break
            old_loc, old_scale = frames[-h][i]
            z = (y - old_loc) / old_scale
            residual_fan, state["inner"][i] = residual_skater(z, state["inner"][i])
            if len(residual_fan) != h:
                raise ValueError(f"inner(k={h}) must emit exactly {h} forecasts")
            loc, scale = current[i]
            forecasts[i] = residual_fan[-1].affine(scale, loc)
            residuals[i] = z

        frames.append(current)
        state["residuals"] = residuals
        return forecasts, state

    step.__name__ = f"horizon_conjugate(k={k})"
    return step
