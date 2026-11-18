"""Affine reference frames indexed by issue time and forecast lead."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

from skaters.dist import Dist
from skaters.parade import _missing


@dataclass(frozen=True)
class AffineFrame:
    """A frozen coordinate map and its inverse, including predictive laws."""

    location: float
    scale: float

    def __post_init__(self):
        if not math.isfinite(self.location) or not math.isfinite(self.scale) or self.scale == 0:
            raise ValueError("an affine frame needs a finite location and nonzero finite scale")

    def forward(self, y):
        return (y - self.location) / self.scale

    def inverse(self, z):
        return self.location + self.scale * z

    def inverse_dist(self, predictive):
        affine = getattr(predictive, "affine", None)
        if affine is not None:
            return affine(self.scale, self.location)
        return _AffineDist(predictive, self)


@dataclass(frozen=True)
class _AffineDist:
    """Exact affine transport of a continuous predictive with general shape."""

    inner: object
    frame: AffineFrame

    def cdf(self, y):
        p = self.inner.cdf(self.frame.forward(y))
        return p if self.frame.scale > 0 else 1.0 - p

    def logpdf(self, y):
        return self.inner.logpdf(self.frame.forward(y)) - math.log(abs(self.frame.scale))

    def pdf(self, y):
        try:
            return math.exp(self.logpdf(y))
        except OverflowError:
            return math.inf

    def quantile(self, p, **kwargs):
        if not 0 < p < 1:
            raise ValueError("quantile requires 0 < p < 1")
        p = p if self.frame.scale > 0 else 1.0 - p
        return self.frame.inverse(self.inner.quantile(p, **kwargs))

    @property
    def mean(self):
        return self.frame.inverse(self.inner.mean)

    @property
    def var(self):
        return self.frame.scale**2 * self.inner.var

    @property
    def std(self):
        return abs(self.frame.scale) * self.inner.std

    def crps(self, y):
        return abs(self.frame.scale) * self.inner.crps(self.frame.forward(y))

    def affine(self, a, b):
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValueError("affine coefficients must be finite")
        if a == 0:
            return Dist.gaussian(b, 0.0)
        return _AffineDist(self.inner, AffineFrame(a * self.frame.location + b, a * self.frame.scale))


def horizon_conjugate(reference, inner, k: int):
    """Forecast each reference's h-step errors h ticks ahead.

    The reference is a skater returning k distributions. Its lead-h mean and
    standard deviation define the frame issued at t for target t+h. A zero
    scale uses unit scale. The frame is frozen until its target arrives.

    At time t, inner(k=h) consumes (y[t]-location[t-h,h])/scale[t-h,h]. Its
    h-step predictive is mapped back using the frame issued now for t+h.
    The reference supplies the forecast until a residual first matures.

    This experiment uses finite observations at regular ticks. All issue-time
    frames are immutable pairs of numbers. With picklable inner predictives,
    state is picklable and retained
    frame storage is O(k**2), plus each inner skater's own state.
    """
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError("k must be a positive integer")
    residual_skaters = [inner(k=h) for h in range(1, k + 1)]

    def step(y: float, state: dict | None = None) -> tuple[list, dict]:
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
            old_frame = AffineFrame(*frames[-h][i])
            z = old_frame.forward(y)
            residual_fan, state["inner"][i] = residual_skater(z, state["inner"][i])
            if len(residual_fan) != h:
                raise ValueError(f"inner(k={h}) must emit exactly {h} forecasts")
            forecasts[i] = AffineFrame(*current[i]).inverse_dist(residual_fan[-1])
            residuals[i] = z

        frames.append(current)
        state["residuals"] = residuals
        return forecasts, state

    step.__name__ = f"horizon_conjugate(k={k})"
    return step
