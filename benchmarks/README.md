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

## At scale: 498 systematically-selected series (`large_study.py`)

The 42-series result invites one fair objection — *you picked the series*. So we
re-ran it on a **bias-free universe**: the top-N FRED series tagged `daily`,
ordered by FRED's own popularity ranking (`fred_universe.enumerate_daily`) — a
fixed rule chosen independently of the forecasters. Transform is automatic
(log-diff for positive levels, else first-diff); series need ≥500 changes.

Scored on **498** such series (the run targets ~2.5k; FRED fetch latency capped
this pass — it is crash-safe and resumes, so the cache keeps growing):

> **A CRPS-targeted skater beats crepes on CRPS in 90.0% of series**
> (95% bootstrap CI 87.1–92.6%, N=498).
> **Family-clustered** — collapsing each correlated curve/panel (yields by
> maturity, FX by counterparty) to one vote, 123 families — **79.9%**
> (CI 72.7–86.5%). This is the honest, de-correlated headline.

By asset class (keyword-approximate): commodity 100%, equity 96%, credit 96%,
rates 95%, other 85%, fx 76%. Ours win a large, CI-backed majority on **every**
asset class; only FX (clean, near-i.i.d. returns where the empirical conformal
CDF is hard to beat) stays close.

On **log-likelihood**, the package's actual metric, there is no contest: crepes
emits CDFs, not densities, so it scores *nothing*. Among ours, `dirac` leads with
mean logpdf **3.63** vs ~2.90 for the rest (a **+0.65-nat** lift over the best
non-`dirac` policy, positive on 54% of series), because it alone places mass on
the exact repeats that pervade administrative daily series.

(These numbers refreshed after the projection/coordinate work: the lattice
prior — atoms on every revisited value, not just consecutive repeats — and the
Yeo-Johnson coordinate axis lifted the family-clustered rate 76.6 → 79.9% and
`dirac`'s mean logpdf 3.16 → 3.63 versus the original run.)

Run it: `PYTHONPATH=src python benchmarks/large_study.py` (needs the conda env
with `crepes` + a FRED key).

## On the table

- `naive-gauss` — last value + rolling Gaussian residual.
- `conformal-PD` — the conformal foil (above).
- `scale-mix leaf` — the discrepancy-from-N(0,1) leaf over a simple EMA mean.
- `laplace` / `kahneman` / `skater` — the named policies (terminal-leaf ensemble).
