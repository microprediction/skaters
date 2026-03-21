# skaters

Fast univariate online time series models. Zero dependencies. Runs in [Pyodide](https://pyodide.org/).

## Install

```bash
pip install skaters
```

## Quick start

```python
from skaters import ensemble, envelope

# Create a precision-weighted ensemble of EMA models
f = ensemble(k=3)  # predict 3 steps ahead

state = None
for y in observations:
    x, state = f(y, state)
    # x = [float, float, float]  (forecasts for horizons 1, 2, 3)

# Want uncertainty bands? Wrap any skater with an envelope:
f = envelope(ensemble(k=3), k=3)

state = None
for y in observations:
    out, state = f(y, state)
    # out["mean"] = point forecasts
    # out["std"]  = empirical std of forecast error per horizon
```

## The skater convention

A skater is any callable with this signature:

```python
x, state = f(y, state)
```

| Argument | Type | Description |
|----------|------|-------------|
| `y` | `float` | New observation |
| `state` | `dict \| None` | Prior state (`None` on first call) |
| **Returns** | | |
| `x` | `list[float]` | Point forecasts for horizons 1..k |
| `state` | `dict` | Updated state (pass back next call) |

Skaters only predict. Uncertainty is handled separately by the [envelope](#envelope).

## Built-in skaters

### EMA

Exponential moving average. O(1) per observation.

```python
from skaters import ema

f = ema(alpha=0.1, k=1)
```

### Convenience constructors

Pre-configured EMA speeds:

```python
from skaters import rapidly, quickly, slowly, sluggishly

f = rapidly(k=1)     # alpha=0.3
f = quickly(k=1)     # alpha=0.1
f = slowly(k=1)      # alpha=0.05
f = sluggishly(k=1)  # alpha=0.01
```

### Precision-weighted ensemble

Combines multiple skaters, weighting each by 1/MSE of its forecast errors. Automatically favors models that are both accurate and unbiased.

```python
from skaters import ensemble, precision_weighted_ensemble, ema

# Default: ensemble of EMAs at different speeds
f = ensemble(k=3)

# Custom: bring your own skaters
f = precision_weighted_ensemble(
    skaters=[ema(alpha=0.05, k=3), ema(alpha=0.2, k=3)],
    k=3,
)
```

## Envelope

The envelope wraps any skater and tracks empirical forecast errors at each horizon. It is model-independent — it doesn't care how the predictions are made.

```python
from skaters import envelope, ema

# Welford's (uniform weight over all history)
f = envelope(ema(alpha=0.1, k=3), k=3)

# Exponentially weighted (forgets old errors, adapts to regime changes)
f = envelope(ema(alpha=0.1, k=3), k=3, decay=0.95)

state = None
for y in observations:
    out, state = f(y, state)
    print(out["mean"], out["std"])
```

## Writing your own skater

Any function matching the convention works:

```python
def my_skater(y: float, state: dict | None) -> tuple[list[float], dict]:
    if state is None:
        state = {"last": y}
    state["last"] = y
    return [state["last"]], state  # predict last value for k=1

# Use it standalone or in an ensemble:
from skaters import envelope, precision_weighted_ensemble

f = envelope(my_skater, k=1)
f = precision_weighted_ensemble([my_skater, ema(alpha=0.1, k=1)], k=1)
```

## Design

- **Online only** — O(1) per observation, no batch recomputation
- **Prediction and uncertainty are separate** — skaters predict, envelopes estimate error
- **Pure Python** — zero dependencies, runs anywhere Python runs
- **Pyodide compatible** — works in the browser via WebAssembly

## Lineage

This package distills ideas from [timemachines](https://github.com/microprediction/timemachines), which provided a common skater interface for dozens of time series packages. This is a from-scratch rewrite focused on speed, simplicity, and browser compatibility.
