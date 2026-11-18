"""Online forecasts that are revised as their target dates approach.

For a target at lead h, let F be its issued CDF. The arriving observation
supplies z, the normal score under the issued one-step forecast. Conditional
on z, the target's old normal score has mean rho[h] * z and variance
1 - rho[h]**2. Composing these Gaussian copula updates keeps the target's
original CDF and just two parameters. The farthest target gets a fresh
forecast from a base skater.

Integrating a revised CDF over the issued one-step law recovers the old CDF.
Replaying this same update with normal innovations gives a joint path law
whose marginals are the issued forecasts on a fully observed stream.

With tail probability a, the Gaussian copula acts on the central interval
[a, 1-a] rescaled to [0, 1]. When either rank is outside that interval, the
conditional CDF equals the original rank. Both margins are uniform, so the
revision retains coherence without clipping the encoded scores.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from functools import cached_property
import math
import random
from statistics import NormalDist

from skaters.api import laplace
from skaters.cov import ema_cov
from skaters.dist import Dist
from skaters.parade import _NO_INFO_STD, _missing
from skaters.pushforward import _quantile_rule


_NORMAL = NormalDist()
_SQRT2 = math.sqrt(2.0)
_LOG_SQRT2PI = 0.5 * math.log(2.0 * math.pi)
_LOG_HALF = math.log(0.5)
_GRID = _quantile_rule(65)


def _phi(z):
    return 0.5 * math.erfc(-z / _SQRT2)


def _log_phi(z):
    if z > -37.0:
        return math.log(_phi(z))
    # Mills ratio expansion before the normal tail underflows in binary64.
    r = (1.0 / z) ** 2
    correction = -r + 3 * r**2 - 15 * r**3 + 105 * r**4 - 945 * r**5
    return -0.5 * z * z - math.log(-z) - _LOG_SQRT2PI + math.log1p(correction)


def _log_mixture_cdf(components, x, sign):
    """Log CDF at x for the mixture reflected when sign is -1."""
    terms = [math.log(w) + _log_phi((x - sign * m) / s) for w, m, s in components]
    top = max(terms)
    if top == -math.inf:
        return top
    return top + math.log(math.fsum(math.exp(term - top) for term in terms))


def _invert_increasing(fn, target, lo, hi):
    for _ in range(100):
        mid = 0.5 * lo + 0.5 * hi
        if not lo < mid < hi:
            return mid
        value = fn(mid)
        if value == target:
            return mid
        if value < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * lo + 0.5 * hi


def _mixture_score(components, y):
    if len(components) == 1:
        _, m, s = components[0]
        return (y - m) / s
    log_p = _log_mixture_cdf(components, y, 1)
    sign = 1
    if log_p > _LOG_HALF:
        log_p = _log_mixture_cdf(components, -y, -1)
        sign = -1
    if log_p > -700.0:
        return sign * _NORMAL.inv_cdf(math.exp(log_p))
    if log_p == -math.inf:
        return -sign * math.inf
    # This bound follows from Phi(-x) <= exp(-x*x / 2) for x >= 0.
    lo = -_SQRT2 * math.sqrt(-log_p)
    return sign * _invert_increasing(_log_phi, log_p, lo, 0.0)


def _mixture_quantile(components, z):
    if len(components) == 1:
        _, m, s = components[0]
        return m + s * z
    # Solve in the smaller tail. The component quantiles bracket the solution
    # at any rank, including ranks whose probabilities round to zero or one.
    sign = -1 if z > 0.0 else 1
    z = -abs(z)
    quantiles = [sign * m + s * z for _, m, s in components]
    log_p = _log_phi(z)
    return sign * _invert_increasing(
        lambda x: _log_mixture_cdf(components, x, sign),
        log_p, min(quantiles), max(quantiles),
    )


def _central_score(z, tail_mass):
    if tail_mass == 0.0:
        return z
    tail = _phi(-abs(z))
    if tail <= tail_mass:
        return None
    p = (tail - tail_mass) / (1.0 - 2.0 * tail_mass)
    return math.copysign(-_NORMAL.inv_cdf(p), z)


def _full_score(z, tail_mass):
    if tail_mass == 0.0:
        return z
    tail = tail_mass + (1.0 - 2.0 * tail_mass) * _phi(-abs(z))
    return math.copysign(-_NORMAL.inv_cdf(tail), z)


@dataclass(frozen=True)
class RevisedDist:
    """A predictive distribution expressed in the probit of its original CDF.

    ``probit`` and ``from_probit`` expose the causal coordinates directly.
    The CDF, quantile and density use the change of variables. Moments and
    CRPS for revised mixtures use numerical quadrature.
    """

    base: Dist
    shift: float = 0.0
    scale: float = 1.0
    tail_mass: float = 0.0

    @classmethod
    def _from_base(cls, base, tail_mass):
        if not isinstance(base, Dist):
            raise ValueError("forecast revision requires a continuous Gaussian-mixture Dist")
        components = [(w, m, s) for w, m, s in base.components if w > 0.0]
        if not components or any(s == 0.0 for _, _, s in components):
            raise ValueError("forecast revision requires positive component scales")
        return cls(Dist.trusted(components), tail_mass=tail_mass)

    def _condition(self, innovation, rho):
        if rho == 0.0:
            return self
        return RevisedDist(
            self.base,
            self.shift + self.scale * rho * innovation,
            self.scale * math.sqrt((1.0 - rho) * (1.0 + rho)),
            self.tail_mass,
        )

    @cached_property
    def _gaussian(self):
        if len(self.base.components) == 1 and (self.tail_mass == 0.0 or self._is_unrevised):
            _, m, s = self.base.components[0]
            return Dist.gaussian(m + s * self.shift, s * self.scale)
        return None

    def probit(self, y: float) -> float:
        if not math.isfinite(y):
            return y
        if self._gaussian is not None:
            _, m, s = self._gaussian.components[0]
            return (y - m) / s
        old_z = _mixture_score(self.base.components, y)
        if not self._is_unrevised:
            central = _central_score(old_z, self.tail_mass)
            if central is not None:
                return _full_score((central - self.shift) / self.scale, self.tail_mass)
        return old_z

    def from_probit(self, z: float) -> float:
        if not math.isfinite(z):
            raise ValueError("decoding needs a finite normal score")
        if self._gaussian is not None:
            _, m, s = self._gaussian.components[0]
            return m + s * z
        if not self._is_unrevised:
            central = _central_score(z, self.tail_mass)
            if central is not None:
                z = _full_score(self.shift + self.scale * central, self.tail_mass)
        return _mixture_quantile(self.base.components, z)

    def cdf(self, y: float) -> float:
        return _phi(self.probit(y))

    def quantile(self, p: float) -> float:
        if not 0.0 < p < 1.0:
            raise ValueError("quantile requires 0 < p < 1")
        return self.from_probit(_NORMAL.inv_cdf(p))

    def logpdf(self, y: float) -> float:
        if self._gaussian is not None:
            return self._gaussian.logpdf(y)
        log_base = self.base.logpdf(y)
        if not math.isfinite(log_base) or self._is_unrevised:
            return log_base
        old_z = _central_score(_mixture_score(self.base.components, y), self.tail_mass)
        if old_z is None:
            return log_base
        new_z = (old_z - self.shift) / self.scale
        return log_base + 0.5 * (old_z - new_z) * (old_z + new_z) - math.log(self.scale)

    def pdf(self, y: float) -> float:
        log_p = self.logpdf(y)
        try:
            return math.exp(log_p)
        except OverflowError:
            return math.inf

    @property
    def _is_unrevised(self):
        return self.shift == 0.0 and self.scale == 1.0

    @cached_property
    def _quantiles(self):
        return tuple((self.quantile(p), p, weight) for p, weight in _GRID)

    @cached_property
    def mean(self) -> float:
        if self._gaussian is not None:
            return self._gaussian.mean
        if self._is_unrevised:
            return self.base.mean
        return math.fsum(q * weight for q, _, weight in self._quantiles)

    @cached_property
    def var(self) -> float:
        if self._gaussian is not None:
            return self._gaussian.var
        if self._is_unrevised:
            return self.base.var
        return math.fsum(weight * (q - self.mean)**2 for q, _, weight in self._quantiles)

    @property
    def std(self) -> float:
        return math.sqrt(self.var)

    def crps(self, y: float) -> float:
        if self._gaussian is not None:
            return self._gaussian.crps(y)
        if self._is_unrevised:
            return self.base.crps(y)
        return 2.0 * math.fsum(
            weight * max(p * (y - q), (1.0 - p) * (q - y))
            for q, p, weight in self._quantiles
        )


class ForecastRevision:
    """A skater with k live target dates and Gaussian copula revisions.

    Call ``forecasts, state = model(y, state)``. The base skater supplies k
    continuous Gaussian-mixture forecasts at initialization and the new
    farthest forecast at each subsequent tick. The default base is
    ``laplace(k=k, sticky=False, tails="gaussian")``.

    Supply ``correlations`` for fixed correlations for horizons 2 through k.
    Otherwise the model learns each correlation from normal score pairs
    measured in the forecasts from the same origin. Each update uses only
    pairs whose target has matured. ``alpha`` is the EWMA learning rate.
    ``tail_mass`` reserves that much probability in each tail, where ranks
    are independent. Set it to zero for the full Gaussian copula.

    State is picklable. The path methods fork an initialized state and replay
    the same updates as live observations. Encode and decode use finite
    observations and normal scores, respectively.
    """

    def __init__(self, k: int, *, base=None, correlations=None, alpha: float = 0.03,
                 tail_mass: float = 0.025):
        if not isinstance(k, int) or k < 1:
            raise ValueError("k must be a positive integer")
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be between zero and one")
        if not 0.0 <= tail_mass < 0.5:
            raise ValueError("tail_mass must be at least zero and smaller than 0.5")
        if correlations is not None:
            correlations = tuple(correlations)
            if len(correlations) != k - 1 or any(not -1.0 < r < 1.0 for r in correlations):
                raise ValueError("provide k-1 correlations in (-1, 1) for leads 2 through k")
        self.k = k
        self.base = laplace(k=k, sticky=False, tails="gaussian") if base is None else base
        self.correlations = correlations
        self.alpha = alpha
        self.tail_mass = tail_mass

    def _init_state(self):
        learn = self.correlations is None and self.k > 1
        return {
            "base": None,
            "forecasts": None,
            "correlations": (0.0,) * (self.k - 1) if learn else self.correlations or (),
            "innovation": None,
            "pending": deque(maxlen=self.k) if learn else None,
            "covariance": [{"mean": [0.0, 0.0], "cov": [1.0, 0.0, 0.0, 1.0], "n": 0}
                           for _ in range(self.k - 1)] if learn else None,
            "skipped": 0,
        }

    def _learn(self, y, state):
        pending = state["pending"]
        correlations = list(state["correlations"])
        for lead in range(2, len(pending) + 1):
            fan, arrival = pending[-lead]
            if arrival is None:
                continue
            target = _central_score(fan[lead - 1].probit(y), self.tail_mass)
            if target is None:
                continue
            # Bound influence in the estimator. Path coordinates use the
            # original normal scores.
            pair = [min(max(z, -8.0), 8.0) for z in (arrival, target)]
            i = lead - 2
            _, cov, state["covariance"][i] = ema_cov(pair, state["covariance"][i], self.alpha)
            scale = math.sqrt(cov[0] * cov[3])
            if scale > 0.0:
                correlations[i] = min(max(cov[1] / scale, -0.95), 0.95)
        state["correlations"] = tuple(correlations)

    def __call__(self, y: float, state: dict | None = None) -> tuple[list[RevisedDist], dict]:
        if state is None:
            state = self._init_state()
        old = state["forecasts"]
        innovation = None
        central = None
        if _missing(y):
            state["skipped"] += 1
            if old is None:
                wide = RevisedDist(Dist.gaussian(0.0, _NO_INFO_STD))
                return [wide] * self.k, state
            # Age the outstanding targets without an observation to condition
            # on. Use the last available forecast for the far edge during gaps.
            fan = old[1:] + old[-1:]
        else:
            if old is not None:
                innovation = old[0].probit(y)
                if not math.isfinite(innovation):
                    raise ArithmeticError("normal score is outside floating-point range")
                central = _central_score(innovation, self.tail_mass)
            direct, base_state = self.base(y, state["base"])
            if len(direct) != self.k:
                raise ValueError(f"base must emit exactly {self.k} forecasts")
            if old is None:
                fan = tuple(RevisedDist._from_base(d, self.tail_mass) for d in direct)
            else:
                farthest = RevisedDist._from_base(direct[-1], self.tail_mass)
                # These correlations belonged to the old issue time. Learning
                # from y below can change only the next issue's correlations.
                remaining = old[1:]
                if central is not None:
                    remaining = tuple(d._condition(central, rho)
                                      for d, rho in zip(remaining, state["correlations"]))
                fan = remaining + (farthest,)
            state["base"] = base_state

        pending = state["pending"]
        if pending is not None:
            if innovation is not None:
                self._learn(y, state)
                pending[-1] = (old, central)
            pending.append((fan, None))
        state["innovation"] = innovation
        state["forecasts"] = fan
        return list(fan), state

    def encode(self, observations, state: dict) -> list[float]:
        """Encode a path as successive normal scores from a fitted state."""
        branch = self._fork(state)
        scores = []
        for y in observations:
            if _missing(y):
                raise ValueError("encoding needs finite observations")
            _, branch = self(y, branch)
            scores.append(branch["innovation"])
        return scores

    def decode(self, scores, state: dict) -> list[float]:
        """Invert normal scores by replaying the online forecast updates."""
        branch = self._fork(state)
        path = []
        for z in scores:
            y = branch["forecasts"][0].from_probit(z)
            if not math.isfinite(y):
                raise ArithmeticError("decoded observation is outside floating-point range")
            path.append(y)
            _, branch = self(y, branch)
        return path

    def sample_path(self, state: dict, *, rng=None, steps: int | None = None) -> list[float]:
        """Sample a path from a fitted state, defaulting to k steps."""
        rng = random if rng is None else rng
        steps = self.k if steps is None else steps
        return self.decode((rng.gauss(0.0, 1.0) for _ in range(steps)), state)

    @staticmethod
    def _fork(state):
        if state is None or state["forecasts"] is None:
            raise ValueError("initialize the model with a finite observation before replaying a path")
        return deepcopy(state)
