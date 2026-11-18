"""Causal conditional centering from a bounded archive of past transitions.

There is one scalar residual stream: z[t+1] = y[t+1] - center(state[t]).
The center depends on level and delayed slopes, so revisiting a level while
rising need not have the same predicted movement as revisiting it while
falling. No period or forecast horizon enters the forward transform.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from heapq import nsmallest
import math
import random

from skaters.cov.ema_cov import ema_cov
from skaters.dist import Dist
from skaters.pushforward import PushforwardDist


def _translate(x, offset):
    return x + offset


def _zero_log_jacobian(z):
    return 0.0


def _translated_moments(mean, std, offset):
    return mean + offset, std


def _shift(dist, offset):
    affine = getattr(dist, "affine", None)
    if affine is not None:
        return affine(1.0, offset)
    return PushforwardDist(dist, inv_fn=partial(_translate, offset=offset),
                           fwd_fn=partial(_translate, offset=-offset),
                           log_jacobian_fn=_zero_log_jacobian,
                           component_moments_fn=partial(_translated_moments, offset=offset))


@dataclass(frozen=True)
class OrbitTransform:
    """An ordinary (forward, inverse_k) transform with an exact path inverse.

    ``memory`` bounds the transition archive. ``lags`` describe the state,
    not a seasonal period. Distances use EWMA feature variances. Among the
    ``neighbors`` nearest past states, inverse-distance and age weights
    estimate the next increment. Until a complete state has been observed,
    the center is the last value (zero before the first observation).

    One-step distribution inversion is an exact translation. At longer
    horizons, ``inverse_k`` assumes independent residual marginals, samples
    ``paths`` future residual paths, and moment-matches the recovered
    marginals to Gaussians. This is an explicit distributional approximation;
    ``inverse_path`` itself is exact and imposes no independence assumption.
    Simulation is deterministic, leaves the supplied state alone, and uses
    the same simulated prefixes regardless of the requested horizon.
    """

    memory: int = 512
    neighbors: int = 8
    lags: tuple[int, ...] = (1, 4)
    alpha: float = 0.02
    forget: float = 0.995
    paths: int = 64
    seed: int = 1729

    def __post_init__(self):
        for name in ("memory", "neighbors", "paths"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.paths < 2 or self.paths % 2:
            raise ValueError("paths must be even and at least two")
        if (not isinstance(self.lags, tuple) or not self.lags
                or any(type(lag) is not int or lag < 1 for lag in self.lags)
                or tuple(sorted(set(self.lags))) != self.lags):
            raise ValueError("lags must be a strictly increasing tuple of positive integers")
        if not 0 < self.alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        if not 0 < self.forget <= 1:
            raise ValueError("forget must be in (0, 1]")
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")

    def __iter__(self):
        # The existing conjugate() unpacks exactly this pair.
        yield self.forward
        yield self.inverse_k

    def _empty(self):
        return {"history": deque(maxlen=max(self.lags) + 1),
                "archive": deque(maxlen=self.memory),
                "feature": None, "stats": None, "n": 0}

    @staticmethod
    def _fork(state):
        # Archive entries and feature tuples are immutable, so share those.
        return {"history": state["history"].copy(),
                "archive": state["archive"].copy(),
                "feature": state["feature"], "stats": deepcopy(state["stats"]),
                "n": state["n"]}

    def center(self, state):
        """Next center, using only observations already in ``state``."""
        if state is None or not state["history"]:
            return 0.0
        last = state["history"][-1]
        query = state["feature"]
        if query is None or not state["archive"]:
            return last
        dim = len(query)
        cov = state["stats"]["cov"]
        variances = [cov[i * dim + i] for i in range(dim)]
        floor = max(max(variances) * 1e-12, 1e-24)
        inv_var = [1.0 / max(v, floor) for v in variances]

        def distance(record):
            return sum((a - b) ** 2 * v
                       for a, b, v in zip(query, record[0], inv_var)) / dim

        nearest = nsmallest(self.neighbors,
                            ((distance(row), row) for row in state["archive"]),
                            key=lambda item: item[0])
        log_forget = math.log(self.forget)
        logs = [(log_forget * (state["n"] - 1 - row[2])
                 - 2.0 * math.log(d + 1e-6), row[1]) for d, row in nearest]
        top = max(w for w, _ in logs)
        weights = [(math.exp(w - top), move) for w, move in logs]
        move = sum(w * m for w, m in weights) / sum(w for w, _ in weights)
        return last + move

    def _observe(self, y, state):
        history = state["history"]
        # The previous feature's label becomes available only NOW.
        if state["feature"] is not None:
            state["archive"].append((state["feature"], y - history[-1],
                                      state["n"] - 1))
        history.append(y)
        state["n"] += 1
        if len(history) > max(self.lags):
            feature = (y,) + tuple(y - history[-lag - 1] for lag in self.lags)
            state["feature"] = feature
            _, _, state["stats"] = ema_cov(list(feature), state["stats"], self.alpha)

    def forward(self, y, state):
        """Subtract the previously available center, then learn this transition."""
        if not math.isfinite(y):
            raise ValueError("orbit forward needs a finite observation; wrap the skater in parade")
        if state is None:
            state = self._empty()
        residual = y - self.center(state)
        self._observe(y, state)
        return residual, state

    def inverse_path(self, residuals, state):
        """Recover a whole path, advancing a private copy of the SAME state.

        Recovered observations also update the private transition archive.
        Nothing learned on a simulated path is committed to the live state.
        """
        branch = self._empty() if state is None else self._fork(state)
        out = []
        for residual in residuals:
            if not math.isfinite(residual):
                raise ValueError("residual path must be finite")
            y = self.center(branch) + residual
            self._observe(y, branch)
            out.append(y)
        return out

    @staticmethod
    def _sample_pair(dist, rng):
        u = max(rng.random(), 2.0 ** -53)
        if not isinstance(dist, Dist):
            # A PushforwardDist's components are only a compatibility view.
            # Sample its actual CDF, preserving the nonlinear inner map.
            return dist.quantile(u), dist.quantile(1.0 - u)
        z = rng.gauss(0.0, 1.0)

        def draw(p, normal):
            cumulative = 0.0
            for weight, mean, std in dist.components:
                cumulative += weight
                if p < cumulative:
                    return mean + std * normal
            _, mean, std = dist.components[-1]
            return mean + std * normal

        return draw(u, z), draw(1.0 - u, -z)

    def inverse_k(self, dists, state):
        """Exact at h=1; independent-path Gaussian approximation thereafter."""
        if not dists:
            return []
        first = _shift(dists[0], self.center(state))
        if len(dists) == 1:
            return [first]
        recovered = []
        for pair in range(self.paths // 2):
            rng = random.Random(self.seed + pair)
            samples = [self._sample_pair(dist, rng) for dist in dists]
            recovered.append(self.inverse_path([v[0] for v in samples], state))
            recovered.append(self.inverse_path([v[1] for v in samples], state))
        out = [first]
        for h in range(1, len(dists)):
            values = [path[h] for path in recovered]
            mean = math.fsum(values) / self.paths
            variance = math.fsum((v - mean) ** 2 for v in values) / self.paths
            out.append(Dist.gaussian(mean, math.sqrt(variance)))
        return out


def orbit_transform(**kwargs):
    """Return a transform accepted directly by ``skaters.conjugate``."""
    return OrbitTransform(**kwargs)
