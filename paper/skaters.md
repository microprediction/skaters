---
title: "Model First, Conform Last: Composable Online Distributional Time-Series Forecasting"
author:
  - Peter Cotton (Microprediction)
date: 2026
abstract: |
  We present *skaters*, a zero-dependency library for online univariate
  time-series forecasting in which **every prediction is a full probability
  distribution**, not a point. Models are built by composition: invertible
  transforms chain together, ensembles nest, and a single distributional *leaf*
  sits at the bottom of every chain. The leaf is a pluggable proper-scoring-rule
  optimiser, which lets us separate two concerns that the forecasting and
  conformal-prediction literatures usually conflate — *modelling* the conditional
  mean (judged by likelihood) and *calibrating* the predictive tail (optionally
  judged by a downstream score such as CRPS). We call the resulting recipe
  **model first, conform last**, and show on a bias-free study of 2,500 daily
  FRED series that it matches a dedicated CRPS specialist on CRPS while *improving*
  held-out log-likelihood — a free lunch. We also note a structural point about
  conformal predictive systems: a conformal CDF carries no density and therefore
  cannot be scored on likelihood at all, the decision-relevant metric.
  *(Limitation: the conformal opponent in §8 is given only a naive mean; a
  head-to-head against AutoARIMA/ETS, Prophet, and adaptive-conformal baselines
  with strong mean models is the subject of ongoing experiments and is required
  before any broad "beats state of the art" claim.)*
  We further contribute a *mean-preserving lattice
  projection* for series that revisit exact values, an online *coordinate*
  (Yeo–Johnson) search, and a committed *martingale* model whose volatility clock
  is a time-changed Brownian motion. Finally, a sequence of out-of-sample
  experiments shows that the conventional menu of "named methods" largely
  collapses: prior-only policies wash out to a single general forecaster on long
  series, leaving an API of essentially **one** forecaster plus one specialist.
  The whole library is implemented twice — pure Python and zero-dependency
  JavaScript — and verified identical to 1e-6 on ~90,000 probe values, so the
  same models run server-side or in the browser.
---

# 1. Introduction

Most deployed forecasters return a point and, perhaps, an interval bolted on
afterwards. Yet the quantity a decision-maker needs is the *predictive
distribution*: the mean for an estimate, the spread for risk, the tails for
sizing, and a density for likelihood-based evaluation and combination. Two
strands of recent work take distributions seriously but each gives something up.
Classical state-space and exponential-smoothing models are distributional but
rarely *online and composable* — adding a transform means re-deriving the filter.
**Conformal prediction** is distribution-free and online, but a conformal
predictive system outputs a *cumulative distribution function*, not a density;
it is calibrated for coverage and CRPS but **cannot be scored on log-likelihood
at all**, and an empirical conformal CDF assigns zero density (−∞ log-likelihood)
to any value outside the observed residual range.

`skaters` takes a third route. Every node — transform, ensemble, or leaf — is a
function `(y, state) -> ([Dist], state)` that consumes one observation and emits
a list of `Dist` objects, one per forecast horizon, where a `Dist` is a weighted
Gaussian mixture. Because the type is closed under composition, an entire model
is a chain of invertible transforms with one distributional leaf at the bottom,
and ensembles are just skaters that combine other skaters. This single
abstraction yields three things the paper develops in turn:

1. **A pluggable objective.** The leaf fits its mixture weights by *a* proper
   scoring rule. Point it at log-likelihood and it models honestly; point its
   *terminal* copy at CRPS while keeping a likelihood-weighted trunk and you get
   **model first, conform last** (§4) — competitive with a CRPS specialist on
   CRPS *and* better on likelihood.
2. **Distributional structure that survives composition.** A *mean-preserving
   lattice projection* (§5) places atoms on the exact values a series revisits —
   capturing quantised/administrative series — without moving the ensemble mean
   and while vanishing on continuous data; an online *coordinate* search (§6)
   learns whether a series is simple in a log, root, or linear coordinate; and a
   committed *martingale* model (§7) learns only a volatility clock.
3. **An honest, bias-free benchmark** (§8) on 2,500 systematically chosen FRED
   series, with ablations (§9) showing that most of the conventional "named
   method" menu is redundant out of sample.

# 2. The `Dist` abstraction and composable transforms

A `Dist` is a weighted mixture $\sum_i w_i\,\mathcal N(\mu_i,\sigma_i^2)$ with
$\sigma_i>0$. It exposes `mean`, `std`, `pdf`, `cdf`, `logpdf`, `quantile`, and a
closed-form `crps`, plus the affine maps (`shift`, `scale`, `affine`) and a
moment-matching `prune` needed to propagate it through transform inverses and to
bound component growth in ensembles.

A *transform* is an online bijection given by a `forward` (scalar in, scalar out)
and an `inverse_k` that maps $k$ `Dist`s in the transformed space back to the
original. Differencing, exponential smoothing, drift, Holt's linear trend,
fractional differencing, autoregression (online recursive least squares), GARCH,
seasonal differencing, power/Yeo–Johnson coordinates, and standardisation are all
transforms. *Conjugation* composes a transform with an inner skater:
$y \xrightarrow{T} y' \to \text{inner} \to D' \xrightarrow{T^{-1}} D$. Because
every step is online and the inverse propagates the full mixture, multi-step
uncertainty accumulates correctly (e.g. variance growing as $\sum_h\sigma_h^2$
under differencing).

> **Numerical note.** Mixture variance is computed in centred form,
> $\operatorname{Var}=\sum_i w_i\,(\sigma_i^2 + (\mu_i-\bar\mu)^2)$, rather than
> $\mathbb E[X^2]-\mathbb E[X]^2$, which catastrophically cancels when a tight
> component sits at a large mean and silently produces $\sigma=0$ — an invalid
> predictive.

# 3. The terminal-leaf ensemble: model first

Bayesian model averaging over a heterogeneous pool combines full predictive
distributions, which preserves the combined mean and variance but *washes out
higher moments*: a heavy-tailed leaf used inside the pool collapses to Gaussian
shape at the output. We therefore use the candidate models only as **mean
forecasters**, weight them online by predictive likelihood (with a learning-rate
shrinkage and a per-depth complexity penalty, in the spirit of gradient
boosting), combine their means, and model the distribution of the *combined
residual* with a **single terminal leaf**:

$$ y \;\to\; \hat\mu = \textstyle\sum_i w_i\,\hat\mu_i,\qquad r = y-\hat\mu \;\to\;
   \text{leaf} \;\to\; D,\qquad \hat D = D\;\text{shifted by}\;\hat\mu. $$

Because exactly one leaf reaches the output, its shape (heavy tails, learned
online) survives undiluted. This is the *model first* half of the recipe: a
likelihood-weighted trunk that gets the conditional mean right.

# 4. Metric-agnostic leaves: conform last

The leaf is itself a fixed Gaussian *scale mixture* — components
$\mathcal N(0, c_k\,\hat\sigma)$ over a fixed log-spaced dictionary $\{c_k\}$,
with $\hat\sigma$ an EWMA scale — whose only learned quantities are the mixture
weights. A Gaussian scale mixture *is* a Student-t in the limit, so this
approximates heavy tails by construction while remaining a plain `Dist`. The
weights are fit online by **a proper scoring rule**:

* `likelihood` — recency-weighted EM on the responsibilities;
* `crps` — exponentiated-gradient descent on the simplex minimising the
  closed-form mixture CRPS (the gradient is exact, since the mixture CRPS is a
  sum of $\mathbb E\,|N(m,s^2)|$ terms).

Putting the CRPS leaf at the *terminal* of a likelihood-weighted trunk gives
**model first, conform last**. The trunk's job is to model — and the honest
objective for modelling is likelihood, a proper, tail-sensitive score;
corrupting it to chase CRPS would be the conformal mistake of discarding the
density. The tail's job is to be shaped, and that is the only place a downstream
metric should get a vote. §8 shows this dominates a pure-likelihood policy on
CRPS *and* on likelihood.

# 5. The lattice projection

Administrative and grid-quoted series (policy rates, posted prices) revisit a
small set of exact values; a continuous predictive cannot place mass there. We
add a *projection*: a recency-weighted frequency table of exact values, with
near-Dirac atoms on the values revisited above a noise floor, each carrying its
frequency as probability. The atom is **mean-preserving** — the continuous part
is recentred so the atoms add mass without moving the ensemble mean. Two
properties make it a safe default: on continuous data nothing is revisited, no
atom fires, and the projection vanishes; and unlike a last-value spike it
captures values that recur often but never consecutively. The mean/pull (the
tendency of the level to persist) is left to the trunk, where the random-walk
candidate earns its weight by likelihood — keeping the projection a pure
statement about *mass*, not *mean*.

# 6. Coordinate learning

Whether a series is simple in a linear, log/multiplicative, or root coordinate is
itself learnable. We add a coarse grid of **Yeo–Johnson** $\lambda$ candidates
(the signed Box–Cox family, defined on all reals) to the pool, so the ensemble
learns the coordinate online rather than committing up front. This is
No-Free-Lunch-safe: a wrong coordinate is simply down-weighted. The same
mechanism expresses a non-negativity prior ($\lambda=0$, log) — though we note
that because the `Dist` is a Gaussian mixture, the inverse is the delta-method
linearisation, so non-negativity is *approximate*, not exact.

# 7. A martingale with a learned volatility clock

For near-martingale *levels* we provide a committed model: the mean is pinned to
the last value (a driftless martingale) and only the volatility clock is learned,
as a Bayesian average over martingale predictives that differ in their volatility
model (constant, GARCH, slowly varying, heavy-tailed). Because every candidate
shares the same mean, plain averaging blends the clocks *without* washing out
kurtosis — the committed mean is exactly what makes BMA the right tool. By the
Dambis–Dubins–Schwarz theorem a continuous martingale is a time-changed Brownian
motion, so the model is literally "Brownian motion on a stochastic clock". It
beats the general forecaster on near-martingale levels by committing the mean and
spending capacity on the clock; on mean-reverting series the prior is wrong and
it gives ground — a deliberately sharp instrument.

# 8. Experiments

**Universe.** To avoid a hand-picked series list, we take the top-$N$ FRED series
tagged *daily* by FRED's own popularity ranking, auto-transform to one-step
changes (log-difference for strictly positive levels, else first difference),
keep those with $\geq 500$ changes, and score every step after a burn-in. This
yields **2,501** series. The opponent is the `crepes` conformal-predictive-system,
given its three best calibration windows and scored on its own CDF via the
pinball decomposition of CRPS.

> **Limitation (important).** This opponent is given only a *naive* (random-walk,
> zero-mean) point model, so these results establish superiority over
> *naive-mean conformal* only. They do **not** establish superiority over
> AutoARIMA/ETS, Prophet, or conformal *paired with a strong mean model*
> (AutoARIMA-mean + conformal, adaptive conformal/ACI, EnbPI) — none of which are
> run here. Because ARIMA/ETS/Prophet emit prediction intervals (densities), they
> *can* be scored on likelihood, so they are the genuinely hard test; that
> head-to-head is ongoing and is a precondition for any broad
> "beats state of the art" statement.

**Read the CRPS numbers honestly.** A single eye-catching figure — *best of our
forecasters, 91.4 %* — is post-hoc selection. The honest, de-correlated number
collapses each correlated curve/panel (yields by maturity, FX by counterparty) to
one vote (195 families). Per-policy:

| forecaster (same structure) | CRPS, raw | CRPS, family | mean logpdf |
|---|---|---|---|
| `laplace` — likelihood trunk + likelihood leaf | 82.6 % | 48.7 % | 2.96 |
| **log trunk + CRPS leaf** (*model first, conform last*) | 89.5 % | **60.1 %** | **3.01** |
| bare CRPS leaf (no trunk) | 80.8 % | 60.3 % | 2.96 |

A *general* likelihood policy is essentially even with conformal on CRPS — its
home metric — over independent families. Repointing only the terminal-leaf
objective to CRPS lifts that to 60 % *and* raises likelihood: matching the CRPS
specialist while modelling honestly.

**The win that is not on CRPS.** Every skater emits a density and is scored
(`laplace` $\approx 2.96$ nats/obs; the lattice policy $\approx 3.49$); conformal
emits a CDF and scores *nothing*. On the economically grounded, tail-sensitive
metric — log-likelihood, the Kelly/log-growth criterion — conformal cannot take
the field, and skaters can.

# 9. Ablations: the menu collapses

**Priors wash out.** Across 25 series with $\geq 2000$ changes, the conventional
prior-flavoured policies (trend, long-memory, drift, minimax, fast/slow) are
within **0.0006 nats** of the uniform-prior general forecaster on the *second
half* of each series; the first-half winner beats the general forecaster on the
second half only **44 %** of the time — worse than chance. Strong priors help
warm-up, not steady state; they have no out-of-sample niche.

**Conform-last is a near-free default.** On idealised light-tailed processes
(Gaussian white noise, AR(1), random walk, sine-plus-noise) the CRPS leaf costs
$\sim 0.005$–$0.007$ nats versus the likelihood leaf; on heavy-tailed and
stochastic-volatility processes it *helps* (up to $+0.04$). Real data lives in
the second regime.

**The lattice projection is free when unused.** On continuous series it is
indistinguishable from the base forecaster; on repeating series it is a large
win.

Together these justify a radical simplification: the package's user-facing API is
**one** general forecaster (uniform prior, CRPS leaf, lattice projection, and
coordinate learning, all on by default) plus **one** committed martingale
specialist. The remaining structural ideas — adaptive search, prior bundles — do
not pay their way out of sample.

# 10. Discussion

The unifying theme is No-Free-Lunch taken seriously. Every "method" is a prior;
averaged over all series none dominates. The correct response is not to pick one
but to make the priors explicit, weight them online, and let the cost of a wrong
prior be bounded by how fast the weighting abandons it. Read that way, the named
methods are convenience bundles, and the honest object is a single adaptive
ensemble with two orthogonal terminal knobs — *which proper scoring rule the leaf
optimises*, and *whether a lattice projection is active* — neither of which is a
prior over the trunk.

# 11. Heritage and reproducibility

`skaters` is a from-scratch rewrite distilling ideas from `timemachines`, the
competition-winning forecasting package by Peter Cotton, and builds on years of
running live distributional-prediction contests at Microprediction, where
forecasts are scored continuously as full distributions. The library is
implemented twice — pure Python and zero-dependency JavaScript — and a parity
suite checks ~90,000 probe values to 1e-6 on every run, so results are
reproducible across both runtimes and in the browser via Pyodide.

# References

*(To be completed — Matheson & Winkler 1976; Gneiting & Raftery 2007 on proper
scoring rules; Vovk, Gammerman & Shafer 2005 on conformal prediction; Box & Cox
1964 and Yeo & Johnson 2000 on power transforms; Doob 1953, Dambis 1965, Dubins &
Schwarz 1965 on the martingale time change; Engle 1982, Bollerslev 1986 on GARCH;
Welford 1962; Ledoit & Wolf 2004.)*
