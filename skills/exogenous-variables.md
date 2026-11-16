# exogenous-variables skill

Use this when the series to forecast comes with other series or features that
might help: weather with demand, a calendar, a leading indicator, a sibling
series, a promotion flag. `laplace` is univariate by design; it forecasts the
stream it is given and nothing else. This skill is the graduation path: how to
bring covariates in without throwing away the calibrated univariate forecast,
and how to tell whether the covariates earned their place.

## The order of operations

1. **Run `laplace` on the target alone first.** It is the yardstick. Any
   covariate model has to beat it per series, one step ahead, on log score,
   or the covariate added nothing. Keep its `state["pit"]` and `state["z"]`;
   they are the calibration check for everything below.
2. **Ask whether the covariate is known ahead.** A calendar or a planned
   promotion is known at forecast time (a future covariate). Weather or a
   sibling series is only known up to now (a past covariate). Most leakage in
   covariate forecasting is a past covariate treated as a future one.
3. **Pick one of the two routes below, or both, and score against the
   yardstick** with the per-series Diebold-Mariano test the canonical study
   uses (the `benchmark-against-laplace` skill has the harness).

## Route A: streaming ML with laplace as features (ice-skaters)

For a model that learns online from covariates, put `laplace`'s calibrated
forecast features into a `river` pipeline. `ice-skaters` wraps `laplace` as
river-compatible transformers: `LaplaceFeatures` emits the forecast mean,
spread, quantiles and calibration state as features; `LaplaceTarget` lets a
regressor model the target's deviation from laplace's forecast rather than the
raw target.

```
pip install ice-skaters
```

```python
from river import linear_model, metrics, preprocessing
from ice_skaters import LaplaceFeatures, LaplaceTarget

model = LaplaceTarget(
    regressor=preprocessing.TargetStandardScaler(
        regressor=LaplaceFeatures()
        | preprocessing.StandardScaler()
        | linear_model.LinearRegression()))

mae = metrics.MAE()
for x, y in stream:                 # x: dict of covariates, y: the target
    pred = model.predict_one(x)
    mae.update(y, pred if pred is not None else 0.0)
    model.learn_one(x, y)
```

The structure is the point: laplace carries the univariate dynamics (level,
trend, scale, seasonality, tails) and the river model only has to learn what
the covariates add on top. Swap `LinearRegression` for any river regressor.
Documentation and more pipelines: https://ice-skaters.microprediction.org

When the residual model learns nothing, the covariates were not informative at
one step ahead, and that is a result worth having before building anything
larger.

## Route B: a foundation model that takes covariates

Several pretrained models accept covariates directly, so a forecast that needs
them can come from the model that was built for it:

- **Chronos-2** (Amazon, Apache-2.0): past and future covariates and
  multivariate targets in context; 21 native quantile levels.
- **TimesFM 2.5 and 3.0** (Google): covariates through an in-context
  regression layer; nine deciles.
- **Moirai 2.0** (Salesforce) and **Toto 2.0** (Datadog): dynamic covariates
  and multivariate input; check the licence (Moirai 2.0 is non-commercial).

Run the foundation model with and without the covariates, and `laplace`
without, and score all three per series. Two findings from the canonical study
to keep in mind. Without covariates, `laplace` is ahead of every one of these
models on daily economic series and behind the larger ones by a few hundredths
of a nat on monthly and weekly series (foundationalprediction.com has the
paired tables). And feeding `laplace`'s own forecast into a foundation model as
a covariate buys nothing measurable at one step ahead (about 0.005 nats, within
noise), so the covariates that help are yours, not the yardstick's.

Keep `laplace` in the loop afterwards: a likelihood-weighted portfolio of the
covariate model and `laplace` (the `&lap` pattern in `benchmarks/`) keeps the
gains where the other model is ahead and trails `laplace` by 0.01 to 0.09 nats
at the median where it is not (the daily strata, in the canonical study). It is
the combination with the fewest losses, not a free lunch.

## Route C: covariates in the residuals

The cheapest test of all. Forecast the target with `laplace`, regress its
one-step residuals (or its `state["z"]`) on the covariates, online or in
batch, and look at the fit. If nothing is explained, stop. If something is,
Route A is that regression done properly, with calibration.

## What to report

- Per series: `laplace` alone, the covariate model, and the portfolio;
  wins, ties and losses by Diebold-Mariano on log score; the median gap.
- Coverage of the central 90% interval for each, from the PIT.
- Which covariates were future-known and which were past-only, stated
  explicitly, because that is where the leakage lives.
