"""User-facing API.

One named forecaster, ``laplace`` — the general forecaster: a likelihood-weighted
ensemble over the full candidate population, with a CRPS terminal leaf (*model
first, conform last*) and the lattice projection for repeating series, both on by
default. Everything else (transforms, leaves, ensembles) is a composable building
block; mean-reversion and GARCH-style behaviour are reachable by composition
(``ou_transform``, ``garch_leaf``) and the multi-step pool already includes an
Ornstein--Uhlenbeck group.

    from skaters import laplace

    f = laplace(k=3)
    state = None
    for y in observations:
        dists, state = f(y, state)
        print(dists[0].mean, dists[0].std)
"""

from __future__ import annotations
import math
from functools import partial
from skaters.dist import _gaussian_pdf, _gaussian_cdf
from skaters.leaf import leaf, scale_mixture_leaf, crps_leaf
from skaters.conjugate import conjugate
from skaters.transform import (
    difference, fractional_difference, standardize, ema_transform, ou_transform,
    garch, power_transform, drift, holt_linear, ar, theta,
    seasonal_difference, seasonal_anchor, yeo_johnson,
)
from skaters.terminal import terminal_leaf_ensemble
from skaters.multiscale import multiscale
from skaters.parade import parade as _parade   # PIT/z calibration state
from skaters.sticky import sticky as _project  # lattice projection (handles repeats)
from skaters.tails import gpdtails as _gpdtails  # GPD tail splice (conditional tail fit)


def _objective_leaf(objective: str, scale_alpha: float = 0.03):
    """Terminal-leaf factory for a policy's objective. ``crps`` is the default:
    *model first* (likelihood-weighted trunk) then *conform last* (CRPS-fit leaf).
    Pass ``"likelihood"`` for the scale-mixture leaf instead. ``scale_alpha`` is the
    terminal leaf's residual-variance EWMA rate (see :func:`laplace`)."""
    if objective == "crps":
        return partial(crps_leaf, scale_alpha=scale_alpha)
    if objective == "likelihood":
        return partial(scale_mixture_leaf, scale_alpha=scale_alpha)
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

    # Depth 1: Hedged seasonal anchor — phase-EMA blended 50/50 with the
    # seasonal-naive. The naive adapts instantly but is one noisy draw; the
    # phase-EMA averages same-phase noise but lags shifts; the hedge beats
    # either alone on genuinely seasonal series (median −8% CRPS on M4-Hourly)
    # at unmeasurable cost elsewhere (see comparisons/laplace-vs-csp/).
    for period in [7, 12, 24]:
        candidates.append(conjugate(leaf_fn(k=k), seasonal_anchor(period), k=k))
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

    # Mean-reversion prior (Ornstein-Uhlenbeck), MULTI-STEP ONLY. The reversion
    # edge over a random walk grows with horizon (1 - phi^h); at one step it is
    # redundant with the ema/random-walk mix and only adds cost, so it is gated on
    # k > 1 to leave the one-step pool (and its speed) byte-identical. Composed
    # under the sqrt (CIR) and log (geometric) coordinates. NFL-safe: a wrong
    # reversion speed is down-weighted. See benchmarks/cir_ablation.py.
    groups["mean_revert"] = []
    if k > 1:
        for L in (0.0, 0.5):
            for kappa in (0.03, 0.1, 0.3):
                candidates.append(
                    conjugate(conjugate(leaf_fn(k=k), ou_transform(kappa, 0.02), k=k),
                              yeo_johnson(L), k=k)
                )
                depths.append(2)
                groups["mean_revert"].append(len(candidates) - 1)

    return candidates, depths, groups


# ---------------------------------------------------------------------------
# Diffuse floor: an always-on heavy-tailed escape hatch on an ABSOLUTE scale.
# ---------------------------------------------------------------------------
# The leaf's scale dictionary is relative to the running sigma, so on a
# near-constant run sigma -> 0 and every mixture component collapses with it;
# a later jump then meets a near-zero-variance predictive and the log-score
# detonates. Splicing a tiny-weight (eps) heavy tail on an ABSOLUTE, ratcheting
# scale W bounds that: a catastrophic point costs ~tens of nats, not 1e20+,
# while normal points are unchanged to ~eps. It cannot predict the FIRST jump on
# an all-constant series (nothing can), only bound the damage once any scale has
# been seen (W ratchets up with max|y|); prior_scale seeds W for the cold start.
#
# This is a PRODUCTION safety net, not a scoring trick. In a study it would be
# unfair to let it rescue laplace's log-score unless every opponent got the same
# floor, so benchmarks instead ELIMINATE out-of-scope series (see benchmarks/
# README, "Out-of-scope series"): asking any model to predict when only one
# value has ever been realized is meaningless, not a contest anyone can win.
_DIFFUSE_DECADES = 3   # wide Gaussians at W, 10W, 100W approximate a heavy tail


class _FloorDist:
    """A base predictive with a total-weight-eps heavy tail mixed in for density
    evaluation only. The tail is `_DIFFUSE_DECADES` Gaussians at W, 10W, 100W
    centered at the base mean; it bounds ``logpdf`` (and shows in ``cdf``) so a
    collapsed predictive meeting a jump can no longer detonate the log-score.
    The point forecast, interval, and CRPS are the base's unchanged: the floor
    is a log-score safety net, not a wider stated band. Type-agnostic so it wraps
    a plain ``Dist`` or a ``SplicedDist`` alike."""
    __slots__ = ("base", "eps", "comps")

    def __init__(self, base, W, eps):
        self.base = base
        self.eps = eps
        m0 = base.mean
        per = eps / _DIFFUSE_DECADES
        self.comps = [(per, m0, W * (10.0 ** j)) for j in range(_DIFFUSE_DECADES)]

    @property
    def mean(self):
        return self.base.mean

    @property
    def std(self):
        return self.base.std

    def quantile(self, p):
        return self.base.quantile(p)     # eps-mass tail is beyond any practical p

    def crps(self, y):
        return self.base.crps(y)

    def cdf(self, y):
        c = (1.0 - self.eps) * self.base.cdf(y)
        for w, m, s in self.comps:
            c += w * _gaussian_cdf(y, m, s)
        return c

    def logpdf(self, y):
        terms = [math.log(1.0 - self.eps) + self.base.logpdf(y)]
        for w, m, s in self.comps:
            p = _gaussian_pdf(y, m, s)
            if p > 0.0:
                terms.append(math.log(w) + math.log(p))
        hi = max(terms)
        return hi + math.log(sum(math.exp(t - hi) for t in terms))


def _add_diffuse(d, W, eps):
    """Wrap d with the heavy-tailed floor on absolute scale W. No-op when W or
    eps is non-positive (e.g. no scale seen yet and no prior_scale set)."""
    if W <= 0.0 or eps <= 0.0:
        return d
    return _FloorDist(d, W, eps)


def _with_diffuse(f, prior_scale, eps):
    """Wrap a skater so every issued predictive carries the diffuse floor, with W
    ratcheting on the largest |y| seen (never collapsing) and floored at
    prior_scale for the cold start."""
    def g(y, state):
        st = state if state is not None else {}
        inner = st.get("inner")
        scale = st.get("scale", 0.0)
        ay = abs(y)
        if ay > scale:
            scale = ay
        dists, inner2 = f(y, inner)
        W = prior_scale if prior_scale > scale else scale
        out = [_add_diffuse(d, W, eps) for d in dists]
        return out, {"inner": inner2, "scale": scale}
    return g


# ---------------------------------------------------------------------------
# The named forecaster
# ---------------------------------------------------------------------------

def _laplace_single_scale(k, objective, sticky, leaf, scale_alpha):
    """One laplace instance on one clock: the likelihood-weighted trunk with a
    terminal leaf, plus the lattice projection."""
    candidates, depths, _ = _build_candidates(k)
    f = terminal_leaf_ensemble(
        candidates, k=k,
        leaf_fn=leaf if leaf is not None else _objective_leaf(objective, scale_alpha),
        learning_rate=0.8,
        complexity_penalty=0.005,
        depths=depths,
        max_components=20,
        # Geometric forgetting keeps the ensemble adaptive to regime change; on
        # held-out FRED change-series 0.99 lifts mean log-likelihood ~+0.02 nats
        # over pure cumulative updating (1.0) at negligible steady-state cost.
        forget=0.99,
    )
    if sticky:
        f = _project(f, k=k)
    return f


def laplace(k: int = 1, objective: str = "crps", sticky: bool = True, leaf=None,
            scales: list[int] | None = None, scale_alpha: float = 0.03,
            tails: str = "gpd", diffuse: float = 1e-12, prior_scale: float = 0.0):
    """The general forecaster.

    A likelihood-weighted Bayesian ensemble over the full candidate population
    (*model first*), with a CRPS terminal leaf (*conform last*) and the lattice
    projection for repeating values — both on by default. After Pierre-Simon
    Laplace: a uniform prior, let the data speak.

    At multi-step horizons (``k > 1``) the ensemble is **multi-scale** by
    default: one full instance runs per decimation stride (default
    ``{1, ceil(sqrt(k)), k}``) and each horizon mixes the eligible scales'
    predictive distributions under likelihood softmax weights, so the horizon
    selects its effective sampling granularity online (see
    :mod:`skaters.multiscale`). At ``k == 1`` there is only one scale and no
    wrapper. Pass ``scales=[1]`` for the single-scale (native fan-out) variant.

    Args:
        k: forecast horizon.
        objective: terminal-leaf objective — ``"crps"`` (default) or
            ``"likelihood"``.
        sticky: lattice projection for repeating values (default True; free on
            continuous data, a large win on grid/repeating series).
        leaf: optional terminal-leaf factory overriding ``objective`` — e.g.
            ``laplace(leaf=garch_leaf)`` for a GARCH(1,1) conditional variance on
            price/return series. A factory ``leaf(k=...) -> skater``.
        scales: decimation strides for the multi-scale mixture (stride s serves
            horizons h >= s). Default ``{1, ceil(sqrt(k)), k}``; ``[1]`` opts
            out of multi-scale.
        scale_alpha: residual-variance EWMA rate of the terminal leaf — how fast
            the predictive scale tracks changing volatility (effective memory
            ~``1/scale_alpha`` steps). Default ``0.03``; on the continuous FRED
            universe this beats the older ``0.01`` on held-out log-likelihood
            (~+0.02 nats, ~79% of series) *and* CRPS (~80% of series), on both
            non-price and price series. Pass ``scale_alpha=0.01`` to reproduce
            the earlier default. Ignored when a custom ``leaf`` is given.
        tails: ``"gpd"`` (default) splices censored-ML generalized-Pareto
            tails into every issued predictive — the conditional tail fit.
            The body's own matured PIT defines a frozen tail region per
            horizon; exceedances fit a GPD per side; the predictive keeps the
            body's density in the interior and the GPD beyond. Worth ~+0.02
            nats/tick of held-out log-likelihood on 96% of non-price FRED
            series, and makes the parade z calibrated in the tails (a
            stated 1e-3 alarm rate approximately comes true — see
            ``benchmarks/anomaly/RESULTS.md`` sections 5-6). ``"gaussian"``
            disables the splice. Costs ~5% runtime.
        diffuse: weight of an always-on heavy-tailed *floor* on the issued
            predictive (default ``1e-12``; ``0`` disables). It bounds the
            log-score when the predictive scale collapses on a near-constant run
            and a jump arrives (otherwise ~1e20+); at ``1e-12`` normal series
            shift by ~1e-3 nats and a collapse is capped near −35 instead of
            detonating. A production safety net only: studies eliminate
            out-of-scope series rather than rely on it (they would have to floor
            every model alike to compare fairly).
        prior_scale: cold-start width for the diffuse floor before any move is
            seen (default ``0``: the floor activates once ``max|y| > 0``, since
            an all-constant history offers no scale to anchor a width on).

    The returned state also carries calibration diagnostics, resolved online
    against the predictions previously made for each arriving point:
    ``state["pit"][m-1]`` is the PIT of y under the m-step-ahead predictive
    issued m steps ago (roughly Uniform(0,1) when calibrated) and
    ``state["z"][m-1]`` the same through the standard-normal quantile (roughly
    N(0,1)); ``None`` until horizon m has matured. See :mod:`skaters.parade`.
    """
    assert tails in ("gpd", "gaussian")
    f = multiscale(lambda kk: _laplace_single_scale(kk, objective, sticky, leaf, scale_alpha),
                   k=k, scales=scales)
    if tails == "gpd":
        f = _gpdtails(f, k=k)     # conditional tail fit: body -> region -> tail
    if diffuse > 0.0:
        f = _with_diffuse(f, prior_scale, diffuse)  # absolute heavy-tailed floor
    f = _parade(f, k=k)           # PIT/z read against the (floored, spliced) predictive
    f.__name__ = f"laplace(k={k})"
    return f


def dantzig(k: int = 1, **kwargs):
    """Adaptive-search skater: grow the model space online instead of fixing it.

    Where :func:`laplace` weights a *fixed* candidate population, ``dantzig``
    explores a growing one: beam search over the transform grammar — expand
    the top performers with new transforms (including seasonal differences at
    periods its online detector actually finds), replay recent history so new
    candidates join warm, prune the losers. Use it when the structure is
    unknown and possibly drifting, or under a compute budget
    (``cost_budget``); on the benchmarked FRED and UCR regimes the fixed
    population of ``laplace`` remains the stronger default.

    This restores the policy's original roster name (the generic ``search``
    remains exported as the underlying machinery): Dantzig 1947 — the simplex
    method explores a combinatorial space by walking from vertex to better
    neighbouring vertex, never enumerating the polytope, which is precisely
    the expand-and-prune walk this skater takes through the model grammar.

    Accepts :func:`skaters.search.search`'s keyword arguments.
    """
    from skaters.search import search as _search
    f = _search(k=k, **kwargs)
    f.__name__ = f"dantzig(k={k})"
    return f
