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

Every skater returns `list[Dist]` — a weighted Gaussian mixture for each horizon $h = 1, \ldots, k$. Point forecasts, uncertainty, density evaluation, and quantiles are all aspects of the same object.

## Named search policies

Every named function builds a Bayesian ensemble over the same full candidate population. The names represent different **search strategies** — different priors, learning rates, and complexity penalties — not different models.

```python
from skaters import brown, holt, hosking, laplace, wald

f = brown(k=1)     # trust simplicity
f = holt(k=1)      # expect trends
f = hosking(k=1)   # expect long memory
f = laplace(k=1)   # maximum ignorance — let the data decide
f = wald(k=1)      # minimax caution
```

| Policy | Prior | Learning rate $\eta$ | Complexity penalty $\lambda$ | Philosophy |
|--------|-------|---------------------|----------------------------|------------|
| `brown` | Favors depth 0–1 | Low | High | Simplicity until proven otherwise |
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

Everything is transforms all the way down, with a distributional leaf at the bottom:

$$y \;\xrightarrow{T_1}\; y' \;\xrightarrow{T_2}\; y'' \;\xrightarrow{\cdots}\; \text{leaf} \;\rightarrow\; \hat{D}$$

The leaf estimates $\hat{D} = \mathcal{N}(0, \hat\sigma^2)$ from residuals via Welford's algorithm. The prediction in the original space is obtained by inverting the transform chain:

$$\hat{D}_{\text{original}} = T_1^{-1}\bigl(T_2^{-1}\bigl(\cdots\bigl(\hat{D}\bigr)\bigr)\bigr)$$

Every node returns `list[Dist]`. There is no separate "point forecast" vs "uncertainty" — both are aspects of the same $\hat{D}$.

### The key insight

Every "model" is really a transform. An EMA doesn't "predict" — it subtracts a running level $\ell_t$, leaving simpler residuals $\varepsilon_t = y_t - \ell_t$. The prediction comes from inverting the transform chain applied to the leaf's distributional estimate.

## The Dist type

A weighted mixture of Gaussians $\sum_{i} w_i \,\mathcal{N}(\mu_i, \sigma_i^2)$. Pure Python (`math.erf`, `math.exp`).

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
d.shift(10.0)           # translate: mu -> mu + 10
d.scale(2.0)            # scale: mu -> 2*mu, sigma -> 2*sigma
d.affine(2.0, 3.0)      # x -> 2x + 3

# Bound component growth
d.prune(max_components=10)
```

## Transforms

Online bijective maps. Each has a `forward` (scalar in, scalar out) and an `inverse_k` that propagates $\text{Dist}$ objects back through the inverse.

| Transform | Forward | Inverse | Use case |
|-----------|---------|---------|----------|
| `ema_transform(`$\alpha$`)` | $y'_t = y_t - \ell_t$ | $D \mapsto D + \ell_t$ | Remove level |
| `difference()` | $y'_t = y_t - y_{t-1}$ | Cumsum with $\text{Var}$ growing as $\sum \sigma_h^2$ | Remove trend |
| `fractional_difference(`$d$`)` | $y'_t = (1-B)^d \, y_t$ | Apply $(1-B)^{-d}$ | Remove long memory |
| `standardize(`$\alpha$`)` | $y'_t = (y_t - \hat\mu_t) / \hat\sigma_t$ | $D \mapsto \hat\sigma_t \cdot D + \hat\mu_t$ | Remove scale |

## Conjugation

Transforms compose via conjugation. Given a transform $T$ and a skater $f$:

$$f_{\text{conjugated}}(y) = T^{-1}\!\bigl(f\bigl(T(y)\bigr)\bigr)$$

The pipe `|` notation reads left-to-right (outermost transform first):

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
# canonical name: std|diff|ema_t|leaf
```

## Ensembles

### Precision-weighted (MSE)

Weights by $w_i \propto 1/\text{MSE}_i$ where $\text{MSE} = \text{bias}^2 + \text{variance}$.

```python
from skaters import precision_weighted_ensemble, ema

f = precision_weighted_ensemble([
    ema(alpha=0.05, k=1),
    ema(alpha=0.2, k=1),
], k=1)
```

### Bayesian (log-likelihood, XGBoost-inspired regularization)

Each model $i$ accumulates a log-weight updated at every observation:

$$\log w_i \;\mathrel{+}=\; \eta \cdot \log p_i(y_t) \;-\; \lambda \cdot d_i$$

where $\eta$ is the learning rate (shrinkage), $\lambda$ is the complexity penalty, and $d_i$ is the model's depth. Predictions are combined via $\text{Dist.combine}$ with softmax weights.

```python
from skaters import bayesian_ensemble, ema

f = bayesian_ensemble(
    [ema(alpha=0.05, k=1), ema(alpha=0.2, k=1)],
    k=1,
    learning_rate=0.5,       # eta: prevents over-concentrating
    complexity_penalty=0.02, # lambda: penalizes deeper chains
    depths=[1, 1],
)
```

### Adaptive search (beam search over transform grammar)

Grows the candidate population online: expand top performers with new transforms, replay recent history to warm-start, prune losers.

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

Any $(T, T^{-1})$ pair where `forward` is scalar and `inverse_k` maps `list[Dist]`:

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

- **Online only** — $O(1)$ per observation, no batch recomputation
- **Distributional** — every prediction is a $\text{Dist}$, not a point estimate
- **Composable** — transforms chain, ensembles nest, everything returns $\text{Dist}$
- **Pure Python** — zero dependencies, only `math.erf` and `math.exp`
- **Pyodide compatible** — works in the browser via WebAssembly

## Lineage

This package distills ideas from [timemachines](https://github.com/microprediction/timemachines), which provided a common skater interface for dozens of time series packages. This is a from-scratch rewrite focused on speed, distributional predictions, and browser compatibility.
