# laplace-sandwich skill

When someone has an existing forecasting model — XGBoost, an LSTM, ARIMA, a
vendor black box, a spreadsheet, a human — and wants it *better calibrated or
just better*, don't rewrite it. **Sandwich it**: `laplace` as the bread, their
model as the filling. The bottom slice alone turns any point forecaster into a
calibrated distributional one and quietly recovers whatever structure the
filling missed. No retraining, no access to the model's insides required.

```
pip install skaters
```

## The bottom slice (the one that matters)

Your model's forecast errors are just another univariate stream. Forecast
them. The final predictive is laplace's residual distribution shifted by your
model's point forecast:

```python
from skaters import laplace

f = laplace(k=1)                # forecasts the RESIDUAL stream
state = None
pending_point = None

for y in stream:
    if pending_point is not None:
        r = y - pending_point           # resolve yesterday's residual
        dists, state = f(r, state)      # laplace forecasts the next one
    point = your_model_forecast(...)    # the filling, untouched
    if pending_point is not None:
        predictive = dists[0].shift(point)   # <-- the sandwich's output
        # predictive.mean      improved point forecast
        # predictive.quantile  calibrated intervals
        # predictive.logpdf    a real density
    pending_point = point
```

Why this improves rather than merely dresses up: laplace's candidate pool runs
drift, seasonality, autocorrelation, coordinate, and volatility-clock models
*on the error stream*. Any of those your model missed shows up as forecastable
residual structure, gets forecast, and moves the sandwich's **mean** — not
just its bands. Systematic bias becomes a drift candidate; missed seasonality
becomes a seasonal candidate; heteroscedastic errors become a calibrated
volatility clock instead of one frozen σ.

Measured (20-period moving-average filling on a drifting, seasonal,
vol-clocked stream, 900 held-out points): mean held-out log-likelihood
`−1.95 → −1.02` versus the same point model with a rolling Gaussian, and
point-forecast MAE `1.47 → 0.54` — the sandwich's mean is nearly three times
more accurate than the filling's, because the residual layer recovered the
seasonality the moving average couldn't see.

## The top slice (optional)

Models with stationarity assumptions (most ML) prefer well-behaved inputs.
Run the raw stream through `laplace` first and feed the filling the
calibration state instead of raw values: `state["z"][0]` is the stream
rendered as approximately N(0,1) innovations — drift, scale, seasonality and
coordinate already absorbed (see the *Running normalization* demo). Features
built from z's don't go stale when the level triples or the volatility regime
flips, so the filling retrains less and generalizes further.

## The free diagnostics

- The bottom slice **is** the `residual-review` skill running continuously: if
  laplace finds nothing in your residuals, the sandwich's predictive collapses
  to "your point + honest noise" and its mean equals your model's — that's a
  clean bill of health, not a failure.
- The sandwich's own `state["pit"]`/`state["z"]` (the parade) now monitor the
  *combined* system: a drifting PIT histogram tells you the filling's regime
  broke before the P&L does.

## The fixed point (honesty clause)

Sandwiching `laplace` itself does nothing — we tested it: stacking a second
layer on laplace's own residuals *loses* to plain laplace, because the
residual stream is already unforecastable to laplace's own pool. That is the
correct behaviour: the sandwich improves any model to the extent that model
falls short of laplace, and leaves already-clean models alone. It follows that
the lazy path is also open: skip the filling entirely and just use `laplace`.
The sandwich is for when the filling exists for reasons — covariates,
regulation, sunk cost, a colleague's feelings — and you want the calibration
and the leftovers anyway.
