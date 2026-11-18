# Multi-horizon reference frames

These Python experiments forecast a target in coordinates chosen at its
forecast origin. A seasonal reference can remove a known period's estimated
shape at leads several cycles away. A second experiment updates outstanding
target distributions as new observations arrive and supplies a path sampler.

`horizon_conjugate(reference, inner, k)` keeps a frozen location and scale
for each issue time and lead. If the frame issued at t for lead h is
`(m[t,h], s[t,h])`, the inner target is

\[
Z^{(h)}_{t+h} = \frac{Y_{t+h}-m_{t,h}}{s_{t,h}}.
\]

At time t the latest observed label for that inner stream is
`(Y[t] - m[t-h,h]) / s[t-h,h]`. An inner skater created with `inner(k=h)`
uses that stream to forecast its h-step marginal. The wrapper applies
`m[t,h] + s[t,h] * Z` to the inner predictive. Each frame uses information
available when it was issued. Changing the reference estimate later does
not change that frozen frame.

With an inner density r, the forecast density at the original target is
`r((y-m)/s) / s`. An arbitrary future path can be encoded and decoded at a
single chosen lead by keeping its initial history and replaying the same
reference updates. Returning marginals for several leads leaves their joint
dependence unspecified.

`AffineFrame` exposes `forward`, `inverse`, and `inverse_dist` explicitly.
For two maps A followed by B, the inverse predictive passes through B's
inverse and then A's inverse. Tests compose this layer and the existing
exact logarithmic transform in both orders, checking CDFs, quantiles, and
the density Jacobian. A general continuous predictive is retained through
affine transport when its distribution class has no native affine method.

If an existing outer transform mixes future times, its inverse needs their
joint law. For example, inverting differencing sums all future increments.
Their marginal distributions leave the distribution of that sum unspecified.
Full path conjugation for such a node needs a joint forecast and replayable
transform state. The fixed-lead scalar wrapper supplies marginal forecasts.

`seasonal_reference(period, k, alpha=1)` uses the last observed value of each
seasonal phase. `alpha=0.2` averages observations of each phase with an EWMA.
Its forecast at every lead uses the current estimate for the target's phase,
including when the target is several periods away. Its fixed `scale` sets
the residual's units. The inner skater estimates its predictive spread.
The reference's Gaussian is used until the first residual matures at a lead.

```python
from research.multi_horizon import horizon_conjugate, seasonal_reference
from skaters import scale_mixture_leaf

k = 168
reference = seasonal_reference(period=24, k=k, alpha=0.2)
model = horizon_conjugate(reference, scale_mixture_leaf, k=k)
state = None

# One call per regularly sampled observation.
for y in observed_loads:
    forecasts, state = model(float(y), state)

next_day = forecasts[23]
next_week = forecasts[167]
```

For a fixed seasonal pattern with independent noise,
`Y[t] = seasonal[t % period] + epsilon[t]`, the naive reference gives
`Z[t+h] = epsilon[t+h] - epsilon[tau]` in unit scale, where tau is the last
observed tick of the target phase at issue time. The seasonal component
cancels at every lead. The pooled error variance in this example is
`2 * Var(epsilon)`, regardless of how many periods away the target is.
Conditional on the observed history the anchor error is already fixed.
The noisy seasonal estimate remains part of the residual problem.

An evolving seasonal pattern can leave substantial uncertainty and structure
in those residuals. The experiment fixes the period in advance. It uses one
inner model per lead, with O(k**2) retained frame storage plus the inner
models' state. Nested wrappers also compose, with a corresponding increase
in state and computation. The affine wrapper currently requires finite
observations at every tick so the inner streams keep the intended clock.
The inner skater receives the residual history at its lead. Reference state
and raw history may contain additional predictive information, so forecast
accuracy still depends on what the inner model can learn from its inputs.

`ForecastRevision` maintains one live distribution per target date. It turns
the arriving observation into the issued one-step normal score and revises
the outstanding targets with a Gaussian copula. Each tick it also introduces
a new farthest target using the base skater's prediction. The base may be a
`horizon_conjugate` instance returning continuous Gaussian mixtures.

For lead h, let U be the arriving observation's rank under the old one-step
forecast and V the farther target's rank under its old forecast. If
`G[h](v | u)` is their conditional copula CDF, the revision is

\[
F_{t+1,h-1}(y) = G_{t,h}(F_{t,h}(y)\mid U).
\]

The uniform copula margins imply
`integral(G[h](v | u), u=0..1) = v`. Averaging the revised forecast over the
issued one-step law therefore recovers the old forecast. Replaying the
same live updates with independent normal scores constructs a path law
whose marginals agree with the fan issued at the starting state.
`encode`, `decode`, and `sample_path` fork a fitted state.

```python
from random import Random
from research.multi_horizon import ForecastRevision

model = ForecastRevision(k=6)
state = None
for y in (1.0, 1.3, 1.1, 1.6, 1.5):
    forecasts, state = model(y, state)
path = model.sample_path(state, rng=Random(42))
scores = model.encode(path, state)
recovered = model.decode(scores, state)
```

The default revision reserves independence in each 2.5% tail. This prevents
an extreme arrival from moving every outstanding forecast through an
unbounded Gaussian update. `tail_mass=0` selects the full Gaussian copula.
Mixture moments and CRPS after a revision use numerical quadrature.
Path coherence and round-trip claims here concern fully observed finite
paths. The revision class's missing-tick handling ages the fan as a heuristic.

The Gaussian rank update is Eq. (12) of Hahn, Martin, and Walker,
[*On Recursive Bayesian Predictive Distributions*](https://arxiv.org/abs/1508.07448).
Their recursive density estimator applies that update to a predictive shared
by future draws. Here the recursion has a separate distribution for each
target date and admits a new target at every tick. Copula updates and their
predictive martingale property are also developed by Fong, Holmes, and
Walker in [*Martingale Posterior Distributions*](https://arxiv.org/abs/2103.15671).

From the repository root, run the synthetic correctness tests with

```sh
PYTHONPATH=src python -m pytest -q research/multi_horizon
```

Tests cover seasonal removal through seven 24-step cycles, noisy and changing
seasonal estimates, frozen frames, nested affine frames, checkpoint replay,
Gaussian random walks and signed AR(1), copula averaging, and sampled-path
marginals. These prototypes currently have a Python implementation.

A canonical M4 Hourly run compares the affine conjugations with CSP on all
414 series. Each method predicts the same final 64 rolling targets in each
series, using at most the last 1,000 changes. The corpus supplies hourly
changes, using log differences for positive series. At lead 48 the target is
one hourly change 48 ticks ahead. A forecast of the load level or a complete
48-hour load path would require its own evaluation.

The configurations were fixed before the run. `MHSeasonal-naive` uses the
last observed value of each phase and a scale-mixture residual leaf.
`MHSeasonal-ema` smooths each phase with alpha 0.2 and uses that same leaf.
`MHSeasonal-laplace` uses alpha 0.2 and Laplace as the inner skater.
All three use period 24. The 48-step run evaluates the two residual-leaf
variants. The forecast-revision model has its synthetic correctness tests.

The table reports median per-series log-score difference and CRPS ratio
against a fresh CSP run. Positive log-score differences and CRPS ratios
below one favour the conjugated model. Win/draw/loss are the canonical
per-series Diebold-Mariano verdicts on log score.

| Lead | Model | Series | Median log-score gain | Median CRPS ratio | Win/draw/loss |
| --- | --- | --- | --- | --- | --- |
| 1 | MHSeasonal-naive | 414 | -0.2888 | 1.1893 | 7 / 113 / 294 |
| 1 | MHSeasonal-ema | 414 | -0.0933 | 1.0123 | 30 / 226 / 158 |
| 1 | MHSeasonal-laplace | 414 | +0.0022 | 0.9833 | 70 / 210 / 134 |
| 1 | laplace | 414 | -0.0572 | 1.0229 | 20 / 250 / 144 |
| 48 | MHSeasonal-naive | 414 | -0.2563 | 1.1984 | 8 / 148 / 258 |
| 48 | MHSeasonal-ema | 414 | -0.0193 | 0.9581 | 67 / 206 / 141 |

The smoothed seasonal conjugation with an inner Laplace is competitive on
median one-step scores, with more significant log-score losses than wins.
At lead 48 the smoothed seasonal leaf improves median CRPS while losing
median log score. The simple seasonal-naive leaf trails CSP at both leads.

The opponent is csp-forecaster 0.2.0 at commit
`529d91865b2c8c6c0c08192c1a2ea35cfb94877c`, with 256 samples, a trailing
750-change fitting window, and the canonical deterministic per-origin seeds.
The run used Python 3.12.14 and NumPy 2.5.5. The raw Hourly-train.csv input
has SHA-256 `ea59b7783573c49077a835ab6465c7d66f1474783360f310988a9a737fbca62f`.
The small score and coverage tables are the `results_*_vs_CSP.csv` files here.
Per-step rows remain regenerable under the ignored `benchmarks/preds/` tree.

The adapters are registered in `benchmarks/arm_adapters.py` and the runner
delegates scoring and summary calculations to the existing canonical pipeline.
Install CSP at the pinned commit in `benchmarks/csp_requirements.lock`, then
reproduce from the repository root with

```sh
PYTHONPATH=.:src:benchmarks python research/multi_horizon/run_m4.py
PYTHONPATH=.:src:benchmarks python research/multi_horizon/run_m4.py --horizon 48 --methods MHSeasonal-naive,MHSeasonal-ema,CSP
```
