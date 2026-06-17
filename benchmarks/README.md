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

## Headline result: skaters vs crepes, on CRPS (`exhaustive_crps.py`)

The skater is a *pluggable proper-scoring-rule optimizer* — the leaf fits its
scale-mixture weights, and the ensemble weights its candidates, by **a** score.
Point it at log-likelihood and it dominates; point it at CRPS (`crps_leaf.py`,
online CRPS-gradient on the simplex) and it beats the CRPS specialist on its own
metric. Conformal has no density, so it is **metric-locked** to coverage/CRPS.

Exhaustive run over **42 FRED series** (crepes given three calibration windows;
scored on its own CDF via the pinball decomposition of CRPS):

> **A CRPS-targeted skater beats crepes on CRPS in 39 / 42 series (93%).**

The 3 losses — `DFEDTARU`, `DFF`, `DPRIME` (fed-funds target, effective fed
funds, prime rate) — are administrative step-rates whose one-step change is a
near **point mass at 0**: the empirical conformal CDF parks ~all its mass at 0,
which a smooth mixture can't match. Conformal wins only where the distribution
is degenerate, not where there's forecasting skill.

And crepes produces no log-likelihood at all (its docs: a CPS outputs *CDFs*),
so on the economically-grounded, tail-sensitive metric it cannot compete; on
CRPS, the metric it is built for, it still loses 93% of the time once we aim at
it. Run it yourself: `PYTHONPATH=src python benchmarks/exhaustive_crps.py`.

## On the table

- `naive-gauss` — last value + rolling Gaussian residual.
- `conformal-PD` — the conformal foil (above).
- `scale-mix leaf` — the discrepancy-from-N(0,1) leaf over a simple EMA mean.
- `laplace` / `kahneman` / `skater` — the named policies (terminal-leaf ensemble).
