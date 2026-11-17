# skaters reference

The detailed reference that used to live in the README: how `laplace` is assembled, the `Dist` type, the transforms, conjugation, ensembles, `dantzig`, the scale-mixture leaf, the spec system, custom transforms, the differentiable port and the theoretical context. The [methodology guide](https://skaters.microprediction.org/guide.html) and the [examples](https://skaters.microprediction.org/examples.html) are the place to start.

## `laplace`: the general forecaster

`skaters` exposes **one general forecaster**, `laplace`, and **one trained one**,
`granger`. Everything else is a building block you can compose.
[The guide →](https://skaters.microprediction.org/guide.html)

```python
from skaters import laplace

f = laplace(k=1)
```

A likelihood-weighted Bayesian ensemble over a large candidate population (EMA,
differencing, drift, Holt, AR, fractional differencing, seasonal, a Yeo-Johnson
**coordinate** grid, a fast/slow two-systems block, and, at multi-step horizons
(`k>1`), an **Ornstein–Uhlenbeck mean-reversion** group). Three things are on by
default, each a free or near-free win:

- **model first, score-optimize last**: the trunk is weighted by **likelihood**;
  the terminal leaf is fit by **CRPS** (`objective="crps"`). On a
  2,500-series FRED study this matches a CRPS specialist on CRPS *and* lifts
  likelihood on real data. Switch back with `objective="likelihood"`.
- **lattice projection** (`sticky=True`): near-Dirac atoms on the exact values a
  series revisits. *Free* on continuous data (it vanishes), a large win on
  grid/repeating series (policy rates, posted prices).
- **coordinate learning**: a Yeo-Johnson λ-grid lets the ensemble learn whether
  the series is simple in a log/multiplicative, sqrt, or linear coordinate.

```python
f = laplace(k=1)                          # CRPS leaf + lattice, both on
f = laplace(k=1, objective="likelihood")  # pure-likelihood leaf
f = laplace(k=1, sticky=False)            # no lattice projection
```

**Calibration state, free.** Every arriving point is resolved against the
forecasts previously made *for it*: `state["pit"][m-1]` is its probability
integral transform under the m-step-ahead predictive issued m steps ago
(roughly Uniform(0,1) when calibrated) and `state["z"][m-1]` the same through
the standard-normal quantile (roughly N(0,1); z is clamped to ±7.03, never
infinite). That calibrated-surprise signal is the null model streaming anomaly
detection is built on, and that work lives in its own project:
[**timemachines**](https://timemachines.microprediction.org/): calibrated
online anomaly detection with stated false-alarm rates, built on skaters.

**Tails that keep their stated rates (v0.13.0).** Every predictive carries censored-ML
generalized-Pareto tails beyond the body's ~2% region (the *conditional tail
fit*; `tails="gaussian"` opts out). Measured prequentially on FRED: +0.03
nats/tick held-out log-likelihood (96%+ of series, price and non-price, all
horizons), and the tail probabilities keep their stated rates. The empirical
alarm rate at nominal 1e-3 is ~1.4e-3, and the nominal 99.9% interval covers
99.85% (the Gaussian read covers 99.13%). An alarm budget converts directly:
alarm when `erfc(|z|/sqrt(2)) < alpha`. Essay:
[The 99.9% interval that is actually 99.9%](https://skaters.microprediction.org/tails.html);
long form: [When to alarm](papers/when-to-alarm.md).

**Price/return series** (`garch_leaf`). The default terminal leaf tracks its scale
with an EWMA (RiskMetrics/IGARCH: no variance mean-reversion). For series with
volatility *clustering and reversion* (equity/fx/commodity returns), swap in a
GARCH(1,1)-t terminal leaf:

```python
from skaters import laplace, garch_leaf
f = laplace(k=1, leaf=garch_leaf)         # GARCH(1,1) conditional variance + Student-t tails
```

**Not for price/returns, though**: there a fitted GARCH-t still wins

### Multi-step horizons are multi-scale by default

Natively, `laplace(k)` reaches horizon `h` by fanning its one-step model out,
and on long horizons the fan-out can inflate the predictive variance. A model on
a *decimated* clock (every s-th observation) reaches the same horizon in
`round(h/s)` of its own steps and stays tight: but is blind to the skipped
points. At `k>1`, `laplace` runs a full instance per scale (default strides
`{1, ceil(sqrt(k)), k}`) and mixes their predictive `Dist`s per horizon with
likelihood softmax weights, so each horizon selects its effective granularity
online. At `k=1` it *is* `laplace(1)`; on a 150-series multi-step pilot it is
the only variant to win the likelihood race against AutoARIMA, AutoETS, GARCH-t
*and* Prophet at every horizon in {1, 5, 20}.

```python
f = laplace(k=20)                      # scales {1, 5, 20}, mixed by likelihood
f = laplace(k=20, scales=[1, 4, 20])   # or pick the clock grid yourself
f = laplace(k=20, scales=[1])          # opt out: single-scale native fan-out
```

### Specialist behaviour by composition

The named forecasters are thin wrappers; the building blocks compose into specialists when
you have a strong prior. **Mean reversion** (e.g. pairs-trading spreads): the
`ou_transform` reverts to a running mean and its edge grows with the horizon, so
feed it `k>1` —

```python
from skaters.conjugate import conjugate
from skaters.leaf import leaf
from skaters.transform import ou_transform, yeo_johnson

f = conjugate(leaf(k=10), ou_transform(kappa=0.1), k=10)                       # linear (spreads)
f = conjugate(conjugate(leaf(k=10), ou_transform(0.1), k=10), yeo_johnson(0.5, exact=True), k=10)  # positive (vol/rates)
```

`exact=True` maps the predictive back through the exact change of variables
instead of the component-wise delta method, which cannot carry the skew of the
coordinate change. The difference grows with horizon: at `h=10` on strictly
positive FRED levels it is worth a median +0.015 to +0.018 nats of held-out
log-likelihood (72–78% of series), and at `h=1` the two agree. The candidate
pool keeps the default (its one-step spreads are where they agree).

**Positive series** (rates, prices, volumes, volatilities): `flesaker()` is
`laplace` on $\log(y)$ with the predictive mapped back exactly through `exp`,
so every quantile it reports is positive. `flesaker(lower=b)` moves the bound and
`flesaker(upper=b)` makes it a ceiling. Named after Bjorn Flesaker, whose
positive-interest framework (with Hughston) builds positivity into the model
rather than hoping for it. Experimental: an example composition, not settled API. See
[`examples/positive_series.py`](examples/positive_series.py).

```python
from skaters import flesaker

f = flesaker(k=3)                    # every quantile > 0
```

`laplace(k>1)` already carries an OU group in its pool, so the general forecaster
picks up reversion automatically at multi-step horizons. The OU-on-a-coordinate
math (the CIR reading) is in [`papers/tweedie-note.md`](papers/tweedie-note.md).

## Architecture

Everything is transforms all the way down, with a distributional leaf at the bottom:

$$y \;\xrightarrow{T_1}\; y' \;\xrightarrow{T_2}\; y'' \;\xrightarrow{\cdots}\; \text{leaf} \;\rightarrow\; \hat{D}$$

The leaf estimates $\hat{D} = \mathcal{N}(0, \hat\sigma^2)$ from residuals via Welford's algorithm. The prediction in the original space is obtained by inverting the transform chain:

$$\hat{D}_{\text{original}} = T_1^{-1}\bigl(T_2^{-1}\bigl(\cdots\bigl(\hat{D}\bigr)\bigr)\bigr)$$

Every node returns `list[Dist]`. There is no separate "point forecast" vs "uncertainty": both are aspects of the same $\hat{D}$.

### The key insight

Every "model" is really a transform. An EMA doesn't "predict": it subtracts a running level $\ell_t$, leaving simpler residuals $\varepsilon_t = y_t - \ell_t$. The prediction comes from inverting the transform chain applied to the leaf's distributional estimate.

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
| `difference()` | $y'_t = y_t - y_{t-1}$ | Cumsum with $\text{Var}$ growing as $\sum \sigma_h^2$ | Random walk |
| `drift(`$\alpha, \lambda$`)` | $y'_t = \Delta y_t - \hat\mu_t$ | $y_t + h\hat\mu + \sum\varepsilon$ | Random walk + drift |
| `holt_linear(`$\alpha, \beta$`)` | $y'_t = y_t - (\ell_t + b_t)$ | $\ell_t + h \cdot b_t + \varepsilon$ | Level + trend (Holt 1957) |
| `ar(`$p$`)` | $y'_t = y_t - \sum \hat\phi_j y_{t-j}$ | AR reconstruction with variance propagation | Autoregression (online RLS) |
| `grouped_ar(`$L$`)` | Same, grouped coefficients | Same | Long-lag AR with $O(\log L)$ params |
| `fractional_difference(`$d$`)` | $y'_t = (1-B)^d \, y_t$ | $(1-B)^{-d}$ | Long memory |
| `standardize(`$\alpha$`)` | $y'_t = (y_t - \hat\mu_t) / \hat\sigma_t$ | $D \mapsto \hat\sigma_t \cdot D + \hat\mu_t$ | Remove scale |
| `garch(`$\omega, \alpha, \beta$`)` | $y'_t = y_t / \hat\sigma_t$ | $D \mapsto \hat\sigma_t \cdot D$ | Volatility clustering |
| `seasonal_difference(`$s$`)` | $y'_t = y_t - y_{t-s}$ | Shift by lagged value | Periodicity |
| `power_transform(`$p$`)` | $y'_t = \text{sign}(y_t)\|y_t\|^p$ | Delta method (`exact=True` for the pushforward) | Tail compression |
| `theta(`$\alpha$`)` | $y'_t = y_t - \text{SES}_t$ | Shift by smoothed level + drift | Theta method (M3 winner) |
| `yeo_johnson(`$\lambda$`)` | Signed Box–Cox to coordinate $\lambda$ | Delta method (`exact=True` for the pushforward) | Coordinate learning (log/root/linear) |
| `log_transform(lower=`$b$`)` | $y'_t = \log(y_t - b)$ (or $-\log(b - y_t)$ for `upper=`) | Exact pushforward through $\exp$ | One-sided bound (positive series) |
| `ou_transform(`$\kappa$`)` | Deviation from running mean, OU speed $\kappa$ | Exact OU moments (scale + shift) | Mean reversion |

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

### `dantzig`: adaptive search (beam search over transform grammar)

Where `laplace` weights a fixed candidate population, `dantzig` explores a
growing one: expand top performers with new transforms (including seasonal
differences at periods its online detector finds), replay recent history to
warm-start, prune losers. Named for Dantzig 1947: the simplex method walks
from vertex to better neighbouring vertex without enumerating the polytope,
which is exactly this expand-and-prune walk through the model grammar.
(`search` remains exported as the underlying machinery.)

```python
from skaters import dantzig

f = dantzig(
    k=1,
    expand_interval=100,  # expand top performers every 100 obs
    max_depth=3,          # maximum transform chain depth
    replay_buffer=500,    # warm-start new candidates on recent history
    max_pool=30,          # cap active candidates
)
```

## Heavy tails: the scale-mixture leaf

Everything here is judged by predictive **log-likelihood**. A plain Gaussian leaf
gets the *location* and *scale* right but the *shape* wrong on heavy-tailed
residuals (returns, macro data), and (crucially) Bayesian model averaging
preserves the mean and variance but **washes the kurtosis out**, so adding heavy
leaves to the candidate pool doesn't help.

The fix is the **scale-mixture leaf**: a fixed dictionary of zero-mean Gaussians
`N(0, aᵢ·σ)` with weights learned online (a Student-t *is* a Gaussian scale
mixture, so this approximates it). It's a plain `Dist`; the weights are the
"discrepancy from N(0,1)": all on `a=1` is Gaussian, mass on larger `a` is fat
tails. It matches the Gaussian leaf on Gaussian data and beats it as tails fatten.

```python
from skaters import scale_mixture_leaf, terminal_leaf_ensemble, leaf
```

Because mixing washes out shape, the named policies use a **terminal-leaf
ensemble**: the candidates are combined for the *mean*, then one terminal
scale-mixture leaf models the combined residual: so the leaf's shape reaches the
output undiluted. On Student-t₃ this takes `laplace` from a logpdf of ≈ −2.07
(Gaussian-collapsed) to ≈ −1.93, with no cost on Gaussian data.

`Dist.crps(y)` (closed-form CRPS) is also available as a proper score for
benchmarking.

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

## skaters.torch: the differentiable port

`pip install skaters[torch]` adds `skaters.torch`: the library on `torch`
tensors (transforms, leaves, ensembles, the lattice projection, the GPD tail
splice, the parade, search, `laplace` and `dantzig`), same arithmetic in the same
order. Not ported: `gaussianize`, the covariance estimators in `cov/`, and the
`exact=True` pushforward. The continuous hyperparameters of the transforms,
leaves, ensembles and the trunk are `nn.Parameter`s reachable from
`laplace(k).parameters()`; the lattice projection's options and search's
learning rates are plain floats. Gradients flow from a log score at the
output back through every stage, with the weight recursions truncated at
one step by default (`detach_carry`), so a streaming call without
`torch.no_grad()` keeps a bounded graph. `skaters.torch.learned` is the
training twin of `granger`: a trainable laplace with a learned gate, held under
an Aggregating-Algorithm mixture with the frozen reference `laplace`, so its
cumulative log loss can exceed laplace's by at most `log 4` nats on any stream
(#297). The trained parameters are exported to `skaters.granger` (pure Python,
Rust and JavaScript, parity-checked).

```python
from skaters.leaf import leaf
from skaters.torch import from_reference
from skaters.torch.conjugate import conjugate, reference_skater

ema = from_reference("ema_transform", alpha=0.1)          # an nn.Module
f = conjugate(reference_skater(leaf(k=1)), ema, k=1)     # laplace's depth-1 candidate
dists, state = f(y, state)                               # list[TorchDist]
loss = -dists[0].logpdf(y_next)                          # differentiable in ema.alpha
```

It is the fifth implementation held to the parity vectors: `parity/check_torch.py`
runs every scenario the JavaScript, Rust, R and Julia ports pass, including
`laplace` at k=1 and k=3, the repeat-series lattice and the missing-observation
rules, at the same 1e-6 gate (200,900 values), and each module is also checked
against the reference at 1e-9 in `tests/test_torch_*.py`. A learned model
initialised at the reference's values therefore is laplace, by the standard
check. `import skaters` does not import torch.

```python
from skaters.torch import laplace
f = laplace(k=1)                      # the same model, tensors inside
dists, state = f(y, None)
loss = -dists[0].logpdf(y_next)       # differentiable in every parameter
```

## Design

- **Online only**: $O(1)$ per observation, no batch recomputation
- **Distributional**: every prediction is a $\text{Dist}$, not a point estimate
- **Composable**: transforms chain, ensembles nest, everything returns $\text{Dist}$
- **Pure Python**: zero dependencies, only `math.erf` and `math.exp`
- **Pyodide compatible**: works in the browser via WebAssembly

## Theoretical context

The online recursions here are **score-driven updates** with a Bayesian reading.
The EMA level update $\mu_t = \mu_{t-1} + \alpha\,(y_t - \mu_{t-1})$ and the GARCH
variance update $h_t = h_{t-1} + (1-\delta)(y_t^2 - h_{t-1})$: the `ema_transform`
and `garch`/`garch_leaf` building blocks: are both inverse-Fisher-scaled
conditional-score corrections. Via **Tweedie's formula**, Hansen & Tong (2026,
[arXiv:2605.15902](https://arxiv.org/abs/2605.15902)) show these are the *exact*
Bayesian posterior-mean corrections under a conjugate prior with local precision
discounting (with the smoothing factor identified as $\alpha = 1-\delta$, the
Gaussian-location case recovering the Kalman filter), and tractable local
approximations otherwise. So the volatility transforms are (approximate) Bayesian
filters rather than ad-hoc heuristics. See also Creal, Koopman & Lucas (2013) and
Harvey (2013) for the score-driven / GAS framework.

The same identity is the backbone of modern **denoising / score-based diffusion
models**: the posterior mean of a clean signal given a noisy observation is
"observation $+\ \sigma^2 \times$ score of the marginal density," which is what
lets a diffusion denoiser be read as a score estimator (Efron 2011; Vincent 2011;
Song & Ermon 2019). Each forecast step here is the time-series analogue —
denoising the next observation toward the latent level or variance. A short essay
on this (Kalman, empirical Bayes, and diffusion as one identity) is in
[`papers/tweedie-note.md`](papers/tweedie-note.md).

