"""User-facing API.

Two named forecasters:

* ``laplace`` — the general forecaster: a likelihood-weighted ensemble over the
  full candidate population, with a CRPS terminal leaf (*model first, conform
  last*) and the lattice projection for repeating series, both on by default.
* ``doob`` — a committed martingale with a learned volatility clock, for
  near-martingale *levels*.

    from skaters import laplace

    f = laplace(k=3)
    state = None
    for y in observations:
        dists, state = f(y, state)
        print(dists[0].mean, dists[0].std)
"""

from __future__ import annotations
import math
from skaters.leaf import leaf, scale_mixture_leaf, crps_leaf
from skaters.conjugate import conjugate
from skaters.bayesian import bayesian_ensemble
from skaters.transform import (
    difference, fractional_difference, standardize, ema_transform,
    garch, power_transform, drift, holt_linear, ar, theta,
    seasonal_difference, yeo_johnson,
)
from skaters.terminal import terminal_leaf_ensemble
from skaters.sticky import sticky as _project  # lattice projection (handles repeats)


def _objective_leaf(objective: str):
    """Terminal-leaf factory for a policy's objective. ``crps`` is the default:
    *model first* (likelihood-weighted trunk) then *conform last* (CRPS-fit leaf).
    Pass ``"likelihood"`` for the scale-mixture leaf instead."""
    if objective == "crps":
        return crps_leaf
    if objective == "likelihood":
        return scale_mixture_leaf
    raise ValueError(f"objective must be 'crps' or 'likelihood', got {objective!r}")


# ---------------------------------------------------------------------------
# Candidate population (shared by all search policies)
# ---------------------------------------------------------------------------

def _build_candidates(k: int, leaf_fn=leaf):
    """Generate the full candidate population.

    Every search policy considers ALL of these. The policy only
    affects how they are weighted, not which ones are included.

    The terminal distribution of every candidate is ``leaf_fn`` — by default
    the Gaussian scale-mixture leaf, which models the residual's departure
    from N(0,1). Pass ``leaf_fn=leaf`` for the plain Gaussian leaf.

    Returns (candidates, depths, groups), where groups maps a logical
    block name to the list of candidate indices in that block. Policies
    express priors by boosting a named group instead of magic indices.
    """
    candidates = []
    depths = []
    groups: dict[str, list[int]] = {}

    # Depth 0: just noise (baseline)
    candidates.append(leaf_fn(k=k))
    depths.append(0)

    # Depth 1: single EMA at various speeds
    for alpha in [0.01, 0.05, 0.1, 0.3]:
        candidates.append(conjugate(leaf_fn(k=k), ema_transform(alpha), k=k))
        depths.append(1)

    # Depth 1: differencing + leaf (pure random walk)
    groups["diff"] = []
    candidates.append(conjugate(leaf_fn(k=k), difference(), k=k))
    depths.append(1)
    groups["diff"].append(len(candidates) - 1)

    # Depth 1: drift + leaf (random walk with adaptive drift)
    # Multiple speeds: fast drift detection vs long-memory drift
    groups["drift"] = []
    for a, s in [(0.05, 0.01), (0.01, 0.002), (0.002, 0.001), (0.0005, 0.0002)]:
        candidates.append(conjugate(leaf_fn(k=k), drift(alpha=a, shrinkage=s), k=k))
        depths.append(1)
        groups["drift"].append(len(candidates) - 1)

    # Depth 1: Theta method (SES + half OLS slope)
    for a in [0.05, 0.1, 0.3]:
        candidates.append(conjugate(leaf_fn(k=k), theta(alpha=a), k=k))
        depths.append(1)

    # Depth 1: AR at depth 1 (captures mean reversion, persistence)
    candidates.append(conjugate(leaf_fn(k=k), ar(1), k=k))
    depths.append(1)
    candidates.append(conjugate(leaf_fn(k=k), ar(2, decay=1), k=k))
    depths.append(1)

    # Depth 1: Holt linear (level + trend, single transform)
    groups["holt"] = []
    for a, b in [(0.1, 0.02), (0.1, 0.05), (0.3, 0.1)]:
        candidates.append(conjugate(leaf_fn(k=k), holt_linear(alpha=a, beta=b), k=k))
        depths.append(1)
        groups["holt"].append(len(candidates) - 1)

    # Depth 1: Seasonal differencing (common periods)
    for period in [7, 12, 24]:
        candidates.append(conjugate(leaf_fn(k=k), seasonal_difference(period), k=k))
        depths.append(1)

    # Depth 2: Seasonal differencing + EMA
    for period in [7, 12, 24]:
        for alpha in [0.05, 0.1]:
            candidates.append(
                conjugate(conjugate(leaf_fn(k=k), ema_transform(alpha), k=k),
                          seasonal_difference(period), k=k)
            )
            depths.append(2)

    # Depth 2: differencing + EMA
    for alpha in [0.05, 0.1, 0.3]:
        candidates.append(
            conjugate(conjugate(leaf_fn(k=k), ema_transform(alpha), k=k), difference(), k=k)
        )
        depths.append(2)
        groups["diff"].append(len(candidates) - 1)

    # Depth 2: standardize + EMA
    for alpha in [0.05, 0.1]:
        candidates.append(
            conjugate(conjugate(leaf_fn(k=k), ema_transform(alpha), k=k), standardize(), k=k)
        )
        depths.append(2)

    # Depth 2: fractional diff + EMA
    groups["frac"] = []
    for d in [0.2, 0.4]:
        candidates.append(
            conjugate(conjugate(leaf_fn(k=k), ema_transform(0.1), k=k),
                      fractional_difference(d=d, window=30), k=k)
        )
        depths.append(2)
        groups["frac"].append(len(candidates) - 1)

    # Depth 2: drift + EMA (drift removal then level tracking)
    for a_drift, s_drift in [(0.002, 0.001), (0.0005, 0.0002)]:
        for a_ema in [0.05, 0.1]:
            candidates.append(
                conjugate(conjugate(leaf_fn(k=k), ema_transform(a_ema), k=k),
                          drift(alpha=a_drift, shrinkage=s_drift), k=k)
            )
            depths.append(2)
            groups["drift"].append(len(candidates) - 1)

    # Depth 2: drift + Holt linear (drift on top of level+trend)
    candidates.append(
        conjugate(conjugate(leaf_fn(k=k), holt_linear(0.1, 0.05), k=k),
                  drift(alpha=0.001, shrinkage=0.0005), k=k)
    )
    depths.append(2)
    groups["drift"].append(len(candidates) - 1)
    groups["holt"].append(len(candidates) - 1)

    # Depth 2: GARCH + EMA (volatility-adapted)
    candidates.append(
        conjugate(conjugate(leaf_fn(k=k), ema_transform(0.1), k=k), garch(), k=k)
    )
    depths.append(2)

    # Depth 2: power transform + EMA (tail compression)
    candidates.append(
        conjugate(conjugate(leaf_fn(k=k), ema_transform(0.1), k=k), power_transform(0.5), k=k)
    )
    depths.append(2)

    # Depth 2: "thinking fast and slow" — a fast process tracker on the
    # OUTSIDE, a slowly-varying residual scale (standardize) on the INSIDE,
    # the plain Gaussian leaf at the bottom.
    #
    #     y --[fast tracker]--> residual --[slow standardize]--> z --> leaf
    #
    # The mean reacts to every observation; the residual *distribution*
    # drifts slowly — at a timescale an order of magnitude slower than the
    # mean. The scale half-life is spread over two values so the ensemble
    # can match how fast the noise actually drifts. No new primitive is
    # needed — this is purely a composition of existing transforms.
    def _fast_trackers():
        return [
            ema_transform(0.3),
            ema_transform(0.5),
            holt_linear(alpha=0.4, beta=0.2),
            ar(1),
            drift(alpha=0.05, shrinkage=0.01),
            difference(),
        ]

    groups["fast_slow"] = []
    for scale_alpha in [0.02, 0.05]:  # slow residual scale, two timescales
        for tracker in _fast_trackers():
            slow_scale = standardize(alpha=scale_alpha)
            candidates.append(
                conjugate(conjugate(leaf_fn(k=k), slow_scale, k=k), tracker, k=k)
            )
            depths.append(2)
            groups["fast_slow"].append(len(candidates) - 1)

    # Coordinate prior (Yeo-Johnson): the same series is often simple in a
    # transformed coordinate — multiplicative/non-negative (lambda=0, log1p) or
    # mildly compressed (lambda=0.5). A coarse grid composed over the random
    # walk and a slow EMA lets the ensemble *learn the coordinate* online.
    # lambda=1 is the identity (already the rest of the pool), so we add 0 and
    # 0.5 only. NFL-safe: a wrong coordinate is simply down-weighted.
    groups["coordinate"] = []
    for L in (0.0, 0.5):
        for inner_tx in (difference(), ema_transform(0.1)):
            candidates.append(
                conjugate(conjugate(leaf_fn(k=k), inner_tx, k=k), yeo_johnson(L), k=k)
            )
            depths.append(2)
            groups["coordinate"].append(len(candidates) - 1)

    return candidates, depths, groups


# ---------------------------------------------------------------------------
# The two named forecasters
# ---------------------------------------------------------------------------

def laplace(k: int = 1, objective: str = "crps", sticky: bool = True):
    """The general forecaster.

    A likelihood-weighted Bayesian ensemble over the full candidate population
    (*model first*), with a CRPS terminal leaf (*conform last*) and the lattice
    projection for repeating values — both on by default. After Pierre-Simon
    Laplace: a uniform prior, let the data speak.

    Args:
        k: forecast horizon.
        objective: terminal-leaf objective — ``"crps"`` (default) or
            ``"likelihood"``.
        sticky: lattice projection for repeating values (default True; free on
            continuous data, a large win on grid/repeating series).
    """
    candidates, depths, _ = _build_candidates(k)
    f = terminal_leaf_ensemble(
        candidates, k=k,
        leaf_fn=_objective_leaf(objective),
        learning_rate=0.8,
        complexity_penalty=0.005,
        depths=depths,
        max_components=20,
    )
    if sticky:
        f = _project(f, k=k)
    f.__name__ = f"laplace(k={k})"
    return f


def doob(k: int = 1, objective: str = "crps"):
    """A driftless martingale with a stochastic volatility clock.

    After Joseph Doob. A committed **level-domain** model: the mean is pinned to
    the last value (a martingale — no drift, no mean reversion) and only the
    volatility clock is learned. By Dambis-Dubins-Schwarz a continuous martingale
    is a time-changed Brownian motion, so the bet is "BM on a stochastic clock".
    Because every candidate shares the same mean, plain Bayesian averaging blends
    the volatility clocks without washing out kurtosis.

    Feed it the **level** series (prices, indices, rates), not pre-differenced
    changes. It beats ``laplace`` on near-martingale levels by committing the
    mean; on mean-reverting series the prior is wrong and it gives ground.

    Args:
        k: forecast horizon.
        objective: residual-leaf objective — ``"crps"`` (default) or
            ``"likelihood"``.
    """
    lf = crps_leaf if objective == "crps" else scale_mixture_leaf
    if objective not in ("crps", "likelihood"):
        raise ValueError(f"objective must be 'crps' or 'likelihood', got {objective!r}")
    cands = [
        conjugate(lf(k=k), difference(), k=k),
        conjugate(conjugate(lf(k=k), garch(), k=k), difference(), k=k),
        conjugate(conjugate(lf(k=k), standardize(0.02), k=k), difference(), k=k),
        conjugate(conjugate(lf(k=k), garch(), k=k), difference(), k=k),
        conjugate(lf(k=k), difference(), k=k),
    ]
    f = bayesian_ensemble(cands, k=k, learning_rate=0.5, depths=[1, 2, 2, 2, 1],
                          max_components=30)
    f.__name__ = f"doob(k={k})"
    return f
