# basic-use skill

When asked to forecast a univariate stream — a metric, a rate, a spread, a
count, anything that arrives one number at a time — start with
`skaters.laplace` and this recipe. Zero dependencies, online, O(1) per
observation, and every prediction is a full distribution.

```
pip install skaters
```

## The loop

```python
from skaters import laplace

f = laplace(k=1)              # k = forecast horizon; k>1 is multi-scale by default
state = None
for y in stream:
    dists, state = f(y, state)
    d = dists[0]              # dists[m-1] is the (m)-step-ahead predictive
    d.mean                    # point forecast
    d.std                     # uncertainty
    d.quantile(0.975)         # tail quantile (any q)
    d.logpdf(y_next)          # score a realised value on likelihood...
    d.crps(y_next)            # ...or on CRPS
```

`state` starts as `None` and is just a picklable dict — persist it and resume
the stream where you left off. No fitting step, no refit schedule: the model
IS the update.

Feed **what you want forecast**. Levels if you want level forecasts (the pool
handles drift, seasonality, mean reversion, coordinates); changes if your
question is about changes. Don't pre-standardize, don't pre-difference out of
habit — that's the model's job, and doing it yourself hides information.

## The knobs (all optional, defaults are the benchmarked configuration)

- `k` — horizon. At `k>1` forecasts are a multi-scale mixture (decimated
  clocks weighted by likelihood); `scales=[1]` opts out.
- `objective="likelihood"` — repoint the terminal leaf from CRPS to pure
  likelihood.
- `sticky=False` — disable the lattice projection (leave it on: it vanishes on
  continuous data and wins big on grid/repeating series).
- `leaf=garch_leaf` — GARCH(1,1)-t terminal leaf for price/return series (and
  read the price caveat: a fitted GARCH-t is still the recommendation there).

## Free with the state

- `state["pit"][m-1]` / `state["z"][m-1]` — each arriving point scored against
  the forecast made *for it*, as ~Uniform(0,1) and ~N(0,1) respectively.
  Calibration monitoring, running normalization, and anomaly detection in two
  keys (see the `anomaly-detection` skill; |z| is clamped to ±7.03, never
  infinite).

## When you outgrow laplace

Genuine graduation paths, not strawmen — pick by what you're actually missing:

- **You have covariates and the pipeline is streaming** —
  [ice-skaters](https://ice-skaters.microprediction.org) ("skaters on a
  river"): every numeric stream becomes two calibrated features — what the
  forecaster expected and how surprising the value was — ready for
  [river](https://riverml.xyz)'s online regressors and classifiers. This is
  the laplace-sandwich top slice, industrialised.
- **You have covariates and batch retraining is fine** —
  [scikit-learn](https://scikit-learn.org) on lagged/exogenous features, with
  laplace as the residual layer (the `laplace-sandwich` skill) so the output
  stays a calibrated density.
- **Many related series that should share strength** —
  [GluonTS](https://ts.gluonts.org/) (DeepAR) or
  [NeuralForecast](https://nixtlaverse.nixtla.io/) with a distributional head.
  Worth the training cost when cross-series structure is real.
- **Price/return volatility, parametric and interpretable** —
  [arch](https://arch.readthedocs.io/) (GARCH-t and friends). On near-random-
  walk series the conditional variance is the whole game; we benchmark against
  it and lose there on purpose.
- **A brand-new series with no history** — a zero-shot foundation model
  (Chronos-Bolt, TimesFM, Moirai). Different protocol; keep a separate harness.
- **Finite-sample coverage guarantees, specifically** — conformal
  ([crepes](https://github.com/henrikbostrom/crepes), MAPIE). You're buying
  marginal coverage, not a density.

Whatever you graduate to, keep two habits from here: score it on held-out
log-likelihood *and* CRPS through the same `Dist` interface (the
`benchmark-against-laplace` skill is the harness), and run the
`residual-review` skill on its errors — if laplace beats GARCH-t on your
fancy model's residuals, the graduation went backwards.
