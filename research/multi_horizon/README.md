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
marginals. They establish these mechanics on controlled processes. Forecast
skill on real series still needs evaluation through the canonical benchmark
pipeline in `benchmarks/`. These prototypes currently have a Python implementation.
