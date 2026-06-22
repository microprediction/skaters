---
title: "Model First, Conform Last: A Composition-Based Automatic Online Distributional Forecaster"
author:
  - Peter Cotton (Microprediction)
date: 2026
abstract: |
  The Python package *skaters* performs online univariate time-series forecasting
  in which every prediction is a full probability distribution rather than a
  point. A forecaster is built by composition: invertible transforms chain
  together above a single distributional leaf, and ensembles combine such chains.
  The leaf fits its shape by optimising a proper scoring rule, so its objective is
  a choice rather than a fixed property of the method. This separates two concerns
  the forecasting and conformal-prediction literatures tend to merge: fitting the
  model, judged by likelihood, and conforming the predictive tail to a downstream
  score such as CRPS. We call the arrangement *model first, conform last*. The library is written twice, in pure Python and in zero-dependency
  JavaScript that agrees to within 1e-6, so the same model runs on a server or in
  a browser. We evaluate it against classical, neural, and pretrained
  foundation-model baselines on FRED series.
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
3. **An honest, bias-free benchmark** (§8) on 10,822 systematically chosen FRED
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

The clock candidates have a Bayesian reading. Each is a *score-driven* update
(Creal, Koopman, and Lucas 2013; Harvey 2013): the GARCH variance recursion
$h_t = h_{t-1} + (1-\delta)(y_t^2 - h_{t-1})$ is, term for term, the
inverse-Fisher-scaled conditional score, and Hansen and Tong (2026) show via
Tweedie's formula that under a conjugate prior and local precision discounting it
is the *exact* Bayesian posterior-mean correction for the variance — with the
same smoothing factor $\alpha = 1-\delta$ that governs the exponential-smoothing
and GARCH-style transforms, and the Gaussian-location case recovering the Kalman
filter. Averaging the candidates thus blends a family of (approximate) Bayesian
volatility filters.

# 8. Experiments

**Universe.** To avoid a hand-picked series list, we take the top-$N$ FRED series
tagged *daily* by FRED's own popularity ranking, auto-transform to one-step
changes (log-difference for strictly positive levels, else first difference), and
score every step after a burn-in.

## 8.1 Against state-of-the-art forecasters

On **500** such series we compare `laplace` against every distributional
one-step baseline we could assemble: `statsforecast`'s **AutoARIMA** and
**AutoETS**; `statsmodels` **SARIMAX** and simple exponential smoothing (exact
closed-form Gaussian predictives); a constant-mean **GARCH(1,1)-t** (the `arch`
package — the heavy-tail/vol-clustering SOTA); a **NeuralForecast** MLP with a
**Student-t** head; and **AutoARIMA paired with conformal** residual quantiles
(split-conformal and adaptive-conformal/ACI). The protocol is *fair rolling
one-step-ahead*: each baseline is fit on an expanding/rolling window with periodic
refit, and every method — ours and theirs — is turned into the same `Dist` and
scored on held-out log-likelihood and CRPS over the same window. All but the
conformal pair emit genuine densities, so this is a real likelihood contest. We
report **per-series** win-rates and additionally restrict to the **309 continuous
series** (< 5 % exactly-repeating changes), since on repeating/grid series the
lattice projection (§5) gives a large but metric-specific edge.

| baseline | LL (all / cont) | CRPS (all / cont) | mean LL (cont) |
|---|---|---|---|
| AutoARIMA | **78 % / 64 %** | 51 % / 47 % | 2.09 |
| AutoETS | **92 % / 88 %** | 68 % / 67 % | 2.20 |
| SARIMAX (statsmodels) | **82 % / 72 %** | 53 % / 49 % | 2.13 |
| ETS (statsmodels) | **93 % / 89 %** | 69 % / 68 % | 2.12 |
| GARCH(1,1)-t (`arch`) | **79 % / 67 %** | 76 % / 66 % | 2.72 |
| NF-StudentT (NeuralForecast) | **100 % / 100 %** | 78 % / 76 % | 0.82 |
| AutoARIMA + conformal | **84 % / 75 %** | 37 % / 29 % | 1.47 |
| AutoARIMA + ACI | **87 % / 80 %** | 36 % / 28 % | 1.89 |

*(`laplace`: mean continuous logpdf **2.855**.)*

The honest reading. **`laplace` wins the per-series likelihood race against all
eight**, on the full universe and the continuous subset — including the two
exact-Gaussian references (SARIMAX, statsmodels ETS). **GARCH-t is the real
test**: as the heavy-tail specialist it is *supposed* to win on financial change
series, and it is indeed the tightest race (67 % of continuous series; mean
continuous logpdf 2.855 vs 2.72 — a genuine but narrow +0.14 nats). The heavy-tail
claim holds *against the heavy-tail specialist*, which is the point. **The
NF-StudentT 100 % is not a scalp**: that is NeuralForecast in the *matched online
univariate one-step* regime (a tiny per-series MLP, periodic refit) — its weak
regime. NF is built for *global cross-series* training; this says nothing about
DeepAR-style models in their home setting, and we don't claim it does (the NF
densities are well-formed — median logpdf 0.50, none floored — so the 100 % is a
real calibration gap, not a degenerate score). On **CRPS** the picture is mixed:
it beats AutoETS/ETS/GARCH-t/NF, roughly ties AutoARIMA/SARIMAX, and *loses* to
the conformal variants, which are CRPS-optimised. Likelihood is the metric where a
faithful density wins; CRPS is conformal's home turf.

*(Per-series, not family-clustered: on this universe the family heuristic inflated
the figures. Scope: 500 change-series, one-step horizon; Prophet, levels, longer
horizons, and zero-shot foundation models — Chronos, TimesFM, Moirai, Lag-Llama,
a different no-refit protocol — are left for an extended study.)*

## 8.2 Repointing the objective: model first, conform last

On a larger **10,822**-series sweep (every daily-tagged FRED series by
popularity) we isolate the effect of the terminal-leaf objective against the
`crepes` conformal-predictive-system (scored on its own CDF via the pinball
decomposition of CRPS). Here the conformal opponent uses a naive (zero-change)
mean, so we read this as an *ablation of our own objective knob* rather than a
SOTA claim — the fitted-mean (AutoARIMA) conformal is a separate, smaller study.

**Read the CRPS numbers honestly — one fixed policy, not best-of-ours.** We report
the single fixed `laplace` default (a per-series best-of would be post-hoc
selection), and give the opponent its best window per series. De-correlating each
correlated curve/panel (yields by maturity, FX by counterparty) to one vote (198
families):

| forecaster (same structure) | CRPS, raw | CRPS, family | mean logpdf |
|---|---|---|---|
| likelihood trunk + likelihood leaf (`objective="likelihood"`) | 92.1 % | 55.6 % | 2.97 |
| **`laplace` — log trunk + CRPS leaf + sticky** (*model first, conform last; the default*) | **96.6 %** | **64.8 %** | **2.99** |
| bare CRPS leaf (no trunk) | 92.6 % | 61.0 % | 2.82 |

`laplace` beats best-of-crepes (crepes given its best window per series) on
**96.6 %** of series, and each fixed window head-to-head (96.6 / 96.9 / 97.0 %) —
no retrospective choice does the work. A *general* likelihood policy already edges
conformal on CRPS over independent families (55.6 %); repointing only the
terminal-leaf objective to CRPS lifts that to 64.8 % *and* raises likelihood
(2.97 → 2.99): matching the CRPS specialist while modelling honestly. Crepes' CRPS
is U-shaped in window length (optimum ≈250); widening or narrowing moves it by
thousandths of a nat — the gap is structural, not a tuning choice.

**The win that is not on CRPS.** Every skater emits a density and is scored
(`laplace` $\approx 2.99$ nats/obs, the lattice projection on by default — worth
$+0.14$ nats on the 22 % of series that revisit values, free elsewhere);
conformal emits a CDF and scores *nothing*. On the economically grounded,
tail-sensitive metric — log-likelihood, the Kelly/log-growth criterion —
conformal cannot take the field, and skaters can.

## 8.3 Against zero-shot foundation models

Pretrained foundation models use a different protocol — applied **zero-shot**,
conditioning on a context window with no fitting. We evaluate four — **Chronos-Bolt**,
**TimesFM 2.5**, **Moirai**, **Lag-Llama** — on 120 change-series (69 continuous):
each receives a fixed 256-length window of preceding changes and predicts the next
change (all windows batched into one call), turned into the same `Dist` (native
Student-t for Moirai/Lag-Llama; sample/quantile reconstruction for
Chronos-Bolt/TimesFM), with `laplace` re-scored on the identical window.

| model | density | LL (all / cont) | CRPS (all / cont) | mean LL (cont) |
|---|---|---|---|---|
| Moirai (1.1-R-small) | native t | 98 % / **97 %** | 94 % / 93 % | 0.92 |
| Lag-Llama | native t | 67 % / **99 %** | 65 % / 94 % | 0.39 |
| Chronos-Bolt (small) | quantile\* | 76 % / **100 %** | 67 % / 88 % | −1.96 |
| TimesFM (2.5-200M) | quantile\* | 75 % / **100 %** | 58 % / 72 % | −1.18 |

*\*quantile-reconstructed logpdf, tail-limited — read CRPS as the fairer signal.
`laplace` mean continuous logpdf: **1.51**.*

On the **continuous** series `laplace` beats all four foundation models, zero-shot,
on both metrics (97–100 % LL, 72–94 % CRPS). The native-density models (Moirai,
Lag-Llama) are the meaningful likelihood opponents and the closest, but still lose
per-series. On **repeat-heavy** series the foundation models are competitive or
better — Lag-Llama even beats `laplace` on mean LL over the *full* universe (6.54
vs 4.52) by placing tight mass on revisited values, the lattice trick — which is
why the continuous split matters. Honest scope: zero-shot, no refit, fixed context,
forecasting the *change* stream (not the levels these models were trained on).

> **Footnote — fine-tuning doesn't rescue them.** Naively fine-tuning Lag-Llama on
> a single series' history (5 epochs) *catastrophically overfits*: held-out logpdf
> collapses from +1.5 to below −100, while taking ~15× longer. That's the expected
> failure mode — adapting a pretrained model to one short univariate stream is not
> its design regime. Zero-shot (or domain-level fine-tuning across many series) is
> the intended use, so the zero-shot result is the headline.

# 9. Preliminary ablations (design rationale)

*The observations in this section motivate the design and the API simplification;
like §8 they are preliminary and not a substitute for the planned full
evaluation.*


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
Creal, Koopman & Lucas 2013 and Harvey 2013 on score-driven models, Hansen & Tong
2026 on their Tweedie/Bayesian interpretation; Welford 1962; Ledoit & Wolf 2004.)*
