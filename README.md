# skaters

Fast univariate online time series models. Zero dependencies. Runs in [Pyodide](https://pyodide.org/).

## Install

```bash
pip install skaters
```

## Quick start

```python
from skaters import skater

f = skater(k=3)
state = None
for y in observations:
    dists, state = f(y, state)
    dists[0].mean              # point forecast
    dists[0].std               # uncertainty
    dists[0].quantile(0.975)   # 95th percentile
    dists[0].logpdf(y)         # log-likelihood
    dists[0].cdf(y)            # CDF at y
```

Every skater returns `list[Dist]` -- a Gaussian mixture for each horizon. Point forecasts, uncertainty, density evaluation, and quantiles are all part of the same object.

## Named search policies

Every named function builds a Bayesian ensemble over the same full candidate population. The names represent different **search strategies** -- different priors, learning rates, and complexity penalties -- not different models.

```python
from skaters import brown, holt, hosking, laplace, wald

f = brown(k=1)     # trust simplicity
f = holt(k=1)      # expect trends
f = hosking(k=1)   # expect long memory
f = laplace(k=1)   # maximum ignorance -- let the data decide
f = wald(k=1)      # minimax caution
```

| Policy | Prior | Learning rate | Complexity penalty | Philosophy |
|--------|-------|---------------|-------------------|------------|
| `brown` | Favors depth 0-1 | Low | High | Simplicity until proven otherwise |
| `holt` | Favors differencing | Moderate | Moderate | Trends are likely |
| `hosking` | Favors frac diff | Moderate | Low | Long memory is likely |
| `laplace` | Uniform | High | Minimal | No opinion, let data speak |
| `wald` | Favors depth 0 | Very low | Very high | Assume adversarial |

Or tune directly:

```python
from skaters import skater

f = skater(k=3, aggressiveness=0.9)  # fast adapter
f = skater(k=3, aggressiveness=0.1)  # conservative
```

## Architecture

Everything is transforms all the way down, with a distributional leaf at the bottom.

```
observation
  -> Transform (diff, frac, standardize, ema_transform)
    -> Transform (...)
      -> leaf()  <- estimates N(0, sigma) from residuals via Welford's
```

Every node returns `list[Dist]`. There is no separate "point forecast" vs "uncertainty" -- both are aspects of the same `Dist`.

### The key insight

Every "model" is really a transform. An EMA doesn't "predict" -- it subtracts a running level, leaving simpler residuals. The prediction comes from inverting the transform chain applied to the leaf's distributional estimate.

## The Dist type

A weighted Gaussian mixture. Pure Python (`math.erf`, `math.exp`).

```python
from skaters import Dist

d = Dist.gaussian(5.0, 2.0)
d.mean                  # 5.0
d.std                   # 2.0
d.pdf(5.0)              # density at x
d.cdf(3.0)              # P(X <= 3)
d.logpdf(5.0)           # log-likelihood
d.quantile(0.975)       # inverse CDF

# Exact mixture combination (for ensembles)
mix = Dist.combine([d1, d2, d3], weights=[0.5, 0.3, 0.2])

# Propagate through transform inverses
d.shift(10.0)           # translate
d.scale(2.0)            # scale location and spread
d.affine(2.0, 3.0)      # x -> 2x + 3

# Bound component growth
d.prune(max_components=10)
```

## Transforms

Online bijective maps with `forward` (scalar) and `inverse_k` (Dist-aware).

| Transform | Forward | Inverse | Use case |
|-----------|---------|---------|----------|
| `ema_transform(a)` | Subtract running level | Shift Dist by level | Remove level |
| `difference()` | y - y\_{t-1} | Cumulative sum with growing variance | Remove trend |
| `fractional_difference(d)` | (1-B)^d filter | Invert filter | Remove long memory |
| `standardize(a)` | (y - mu) / sigma | Affine: sigma * x + mu | Remove scale |

## Conjugation

Transforms compose via conjugation. The pipe `|` reads left-to-right (outermost transform first):

```python
from skaters import conjugate, ema, difference, standardize

# diff removes trend, EMA predicts the differenced series
f = conjugate(ema(alpha=0.1, k=3), difference(), k=3)

# Chain: standardize, then difference, then EMA
f = conjugate(
    conjugate(ema(alpha=0.1, k=3), difference(), k=3),
    standardize(),
    k=3,
)
```

## Ensembles

### Precision-weighted (MSE)

```python
from skaters import precision_weighted_ensemble, ema

f = precision_weighted_ensemble([
    ema(alpha=0.05, k=1),
    ema(alpha=0.2, k=1),
], k=1)
```

### Bayesian (log-likelihood with XGBoost-inspired regularization)

```python
from skaters import bayesian_ensemble, ema

f = bayesian_ensemble(
    [ema(alpha=0.05, k=1), ema(alpha=0.2, k=1)],
    k=1,
    learning_rate=0.5,       # shrinkage: prevents over-concentrating
    complexity_penalty=0.02, # penalizes deeper transform chains
    depths=[1, 1],           # declared depth of each model
)
```

### Adaptive search (beam search over transform grammar)

```python
from skaters import search

f = search(
    k=1,
    expand_interval=100,  # expand top performers every 100 obs
    max_depth=3,          # maximum transform chain depth
    replay_buffer=500,    # warm-start new candidates on recent history
    max_pool=30,          # cap active candidates
)
```

The search starts with simple models, expands winners by conjugating with new transforms, and prunes losers. New candidates are replayed through recent history so they compete immediately.

## Spec system

Serialize and rebuild any pipeline:

```python
from skaters import (
    build, spec_name, to_json, from_json,
    ema_spec, conjugate_spec, ensemble_spec, diff_spec,
)

spec = ensemble_spec(
    conjugate_spec(ema_spec(0.1, k=1), diff_spec()),
    ema_spec(0.3, k=1),
    k=1,
)

spec_name(spec)     # "ensemble(diff|ema(0.1),ema(0.3))"
j = to_json(spec)   # JSON string
f = build(from_json(j))  # live skater
```

## Writing a custom transform

```python
def my_transform():
    def forward(y, state):
        if state is None:
            return 0.0, {"anchor": y}
        transformed = y - state["anchor"]
        return transformed, {"anchor": y}

    def inverse_k(dists, state):
        return [d.shift(state["anchor"]) for d in dists]

    return forward, inverse_k
```

## Design

- **Online only** -- O(1) per observation, no batch recomputation
- **Distributional** -- every prediction is a `Dist`, not a point estimate
- **Composable** -- transforms chain, ensembles nest, everything returns `Dist`
- **Pure Python** -- zero dependencies, only `math.erf` and `math.exp`
- **Pyodide compatible** -- runs in the browser via WebAssembly

## Lineage

This package distills ideas from [timemachines](https://github.com/microprediction/timemachines), which provided a common skater interface for dozens of time series packages. This is a from-scratch rewrite focused on speed, distributional predictions, and browser compatibility.
