# benchmarks

A **development-only** harness. It is *not* part of the `skaters` package, is
not imported by it, and adds no dependency — the deployed package stays
zero-dependency and pure Python.

```bash
python benchmarks/bench.py
```

Everything is judged by **held-out predictive log-likelihood** (higher is
better). Coverage is deliberately not a criterion: a method can hit nominal
coverage with a terrible density.

## The conformal foil

The harness includes a **conformal predictive distribution** as a baseline,
implemented here (not imported — the package ships no conformal code). It's the
recency-unweighted empirical CDF of residuals, smoothed to a density. By
log-likelihood it loses to the scale-mixture policies on heavy-tailed and
non-stationary data, for two reasons: a raw conformal CDF assigns **zero density
(−∞ logpdf) outside the observed residual range**, and even smoothed its kernel
tails are thin and its window can't track drift (it assumes exchangeability).

## Optional SOTA opponents (gated)

Loaded only if already installed (`try/except`, never required):

```bash
pip install crepes        # Conformal Predictive Systems — outputs CDFs, the
                          # fair likelihood opponent (run windowed for time series)
pip install scikit-learn  # for SPCI-style quantile-of-residuals baselines
pip install statsforecast # AutoARIMA/ETS mean models to pair conformal with
```

The script prints which it found. These need network + heavy deps, so they are
intentionally absent from the package's `pyproject.toml`.

## On the table

- `naive-gauss` — last value + rolling Gaussian residual.
- `conformal-PD` — the conformal foil (above).
- `scale-mix leaf` — the discrepancy-from-N(0,1) leaf over a simple EMA mean.
- `laplace` / `kahneman` / `skater` — the named policies (terminal-leaf ensemble).
