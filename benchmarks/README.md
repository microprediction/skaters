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

## Headline: vs eight distributional baselines (`sota_study.py`)

The honest head-to-head against everything we could find that claims a
*distributional* one-step forecast: `statsforecast`'s **AutoARIMA** and
**AutoETS**; `statsmodels` **SARIMAX** and **ETS** (exact closed-form Gaussian
predictives); the `arch` package's **GARCH(1,1)-t** (the classical heavy-tail /
volatility-clustering SOTA); **NeuralForecast** with a **Student-t** distribution
head; and **AutoARIMA paired with conformal residuals** (split-conformal + an
adaptive/ACI variant). Fair rolling one-step-ahead on 500 FRED change series:
each baseline is fit on an expanding/rolling window with periodic refit, and
*every* method — ours and theirs — is turned into the same `Dist` and scored on
held-out log-likelihood **and** CRPS. All but the conformal pair emit genuine
densities, so this is a real likelihood test. **Per-series** win-rate (the
fraction of series where `laplace` scores better), reported both for all 500 and
for the **309 continuous** series (< 5 % exactly-repeating changes), since on
repeating/grid series the lattice projection gives a large but metric-specific
edge that would otherwise dominate the aggregate:

| baseline | LL (all / cont) | CRPS (all / cont) | mean LL (cont) |
|---|---|---|---|
| AutoARIMA | **78 % / 64 %** | 51 % / 47 % | 2.09 |
| AutoETS | **92 % / 88 %** | 68 % / 67 % | 2.20 |
| SARIMAX (statsmodels) | **82 % / 72 %** | 53 % / 49 % | 2.13 |
| ETS (statsmodels) | **93 % / 89 %** | 69 % / 68 % | 2.12 |
| GARCH(1,1)-t (`arch`) | **79 % / 67 %** | 76 % / 66 % | 2.72 |
| NF-StudentT (NeuralForecast) | **100 % / 100 %** | 78 % / 76 % | 0.82 |
| AutoARIMA + conformal | **84 % / 75 %** | 37 % / 29 % | 1.47 |
| AutoARIMA + ACI | **87 % / 80 %** | 36 % / 28 % | 1.89 |

*(`laplace`: mean continuous logpdf **2.855**.)*

> **`laplace` wins the likelihood race, per-series, against all eight.** The two
> results that matter:
>
> - **GARCH-t is the real test** — it is the heavy-tail / vol-clustering SOTA, so
>   it is *supposed* to win on financial change-series. It is indeed the tightest
>   likelihood race (laplace wins 67 % of continuous series; mean continuous
>   logpdf **2.855 vs 2.72**, a genuine but *narrow* +0.14 nats). The heavy-tail
>   claim holds **against the heavy-tail specialist** — which is the point.
> - **The NF-StudentT 100 % is not a scalp.** It is NeuralForecast run in the
>   *matched online univariate one-step* protocol (a tiny per-series MLP, periodic
>   refit) — NF's **weak** regime. NF is built for **global cross-series** training;
>   this says nothing about DeepAR-style models in their home setting, and we
>   don't claim it does.
>
> On **CRPS** the picture is mixed (as ever): laplace beats AutoETS / ETS /
> GARCH-t / NF, roughly ties AutoARIMA / SARIMAX, and *loses* to the conformal
> variants, which are CRPS-optimised. Likelihood is the metric where a faithful
> density wins; CRPS is conformal's home turf.

We report per-series (not family-clustered) because on this universe the family
heuristic *inflated* the numbers. Scope: 500 change-series, one-step horizon;
Prophet, levels, longer horizons, and zero-shot foundation models (Chronos,
TimesFM, Moirai, Lag-Llama — a different, no-refit protocol) are left for an
extended study. Run it (parallel across cores): `PYTHONPATH=src python
benchmarks/sota_study.py` (conda env with `statsforecast`, `arch`, `statsmodels`,
`neuralforecast`, and a FRED key).

## Headline result: skaters vs crepes, on CRPS (`exhaustive_crps.py`)

The skater is a *pluggable proper-scoring-rule optimizer* — the leaf fits its
scale-mixture weights by **a** score. Point it at log-likelihood and it models
honestly; point the *terminal leaf* at CRPS (`crps_leaf.py`, online CRPS-gradient
on the simplex) while keeping the likelihood-weighted trunk — *model first,
conform last* — and it matches the CRPS specialist on CRPS without giving up
likelihood (see the scale study below). Conformal has no density, so it is
**metric-locked** to coverage/CRPS — it cannot do the reverse.

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

## At scale: 2,501 systematically-selected series (`large_study.py`)

The 42-series result invites one fair objection — *you picked the series*. So we
re-ran it on a **bias-free universe**: the top-N FRED series tagged `daily`,
ordered by FRED's own popularity ranking (`fred_universe.enumerate_daily`) — a
fixed rule chosen independently of the forecasters. Transform is automatic
(log-diff for positive levels, else first-diff); series need ≥500 changes.

### Read the CRPS numbers honestly

On **2,501** such series, CRPS win-rate against crepes (best of three calibration
windows). The single eye-catching number — *best-of-our-policies, 91.4%* — is
**post-hoc selection** (whichever policy did best on each series) and is easy to
over-read; the honest, de-correlated figure is **family-clustered** (195
families, each correlated curve/panel counted once). So read it per-policy:

| forecaster (same structure) | CRPS raw | CRPS family | mean logpdf |
|---|---|---|---|
| `laplace` — log trunk + **log** tail | 82.6% | 48.7% | 2.96 |
| **log trunk + CRPS tail** — *model first, conform last* | 89.5% | **60.1%** | **3.01** |
| bare `crps-leaf` (CRPS objective, no trunk) | 80.8% | 60.3% | 2.96 |
| best-of-all policies *(post-hoc pick per series)* | 91.4% | 64.3% | — |

The point is the **first two rows**: same machine, repoint only the objective.
A general likelihood policy (`laplace`) is essentially **even** with crepes on
CRPS — 48.7% of families, a coin flip, because it is not aimed at CRPS. Swap the
terminal leaf's objective to CRPS — keeping the likelihood-weighted trunk — and
it jumps to **60.1% of families**, matching the dedicated CRPS specialist while
*also* lifting likelihood (2.96 → 3.01). That is metric-agnosticism in one line:
the objective is a knob, not a fixed cost.

**Model first, conform last.** The trunk's job is to *model* — get the mean and
structure right — and the honest objective for that is likelihood (a proper,
tail-sensitive score); corrupting it to chase CRPS would be the conformal
mistake of throwing away the density. The *tail's* job is to shape the residual,
and that is the only place a downstream metric (CRPS) should get a vote. Doing
both — likelihood trunk, CRPS leaf — beats the likelihood-only policy on **every**
axis (CRPS raw, CRPS family, *and* likelihood): a CRPS-fit leaf is more
outlier-robust, so it even generalises slightly better on likelihood. No trade.

As of **0.8.0 this is the package default**: `laplace(k)` *is* the "log trunk +
CRPS tail" row; the "log trunk + log tail" row is `laplace(k,
objective="likelihood")`. The table's `laplace` rows were scored before the
default flipped, so they name the configuration explicitly.

By asset class (best-of-ours, keyword-approximate): equity 99% (n=1033),
commodity 100%, rates 95%, credit 94%, fx 89%, other 81%.

### The win that is *not* on CRPS

CRPS was never our metric. The robust, un-spinnable fact is on **log-likelihood**:

- every skater emits a proper predictive *density* and is scored — `laplace`
  ≈ **2.96 nats/obs**, `dirac` **3.49** (+0.46 over the best other policy,
  because it alone places mass on exact repeats);
- crepes emits a *CDF*, not a density, so it scores **nothing** — it cannot be
  evaluated on likelihood at all.

So the real result is not "we beat crepes by X% on CRPS." It is: **on the
economically-grounded, tail-sensitive metric (log-likelihood = Kelly growth),
conformal predictive systems cannot take the field, and skaters can** — while
*also* matching the CRPS specialist on its own metric, by conforming the tail
last without touching the model.

Run it: `PYTHONPATH=src python benchmarks/large_study.py` (needs the conda env
with `crepes` + a FRED key).

## On the table

- `naive-gauss` — last value + rolling Gaussian residual.
- `conformal-PD` — the conformal foil (above).
- `scale-mix leaf` — the discrepancy-from-N(0,1) leaf over a simple EMA mean.
- `laplace` / `kahneman` / `skater` — the named policies (terminal-leaf ensemble).
