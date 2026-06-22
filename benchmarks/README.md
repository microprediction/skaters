# benchmarks

A **development-only** harness. It is *not* part of the `skaters` package, is
not imported by it, and adds no dependency — the deployed package stays
zero-dependency and pure Python.

```bash
python benchmarks/bench.py
```

## One harness, many presets (`study.py`)

There is a *single* study. Everything below is the same machine — one FRED
change-series loader, one one-step `Dist` scorer (`bench_core.py`), one opponent
registry (`opponents.py`) — differing only in **which opponents** and **how big a
universe** (which is set by what the opponents can afford). Conformal isn't a
separate study; it's `conformal(mean=…)` — naive-mean (cheap, scales to the whole
universe) or AutoARIMA-mean (a refit per step, so small-N). Slow methods carry a
per-method `max_series` budget: they cover fewer series (N reported), but always
score a covered series fully — never a within-series shortcut (Prophet refits at
*every* step, because reusing a fit scores multi-step-ahead as one-step).

```bash
PYTHONPATH=src python benchmarks/study.py conformal-scale   # ours vs naive-mean crepes, whole daily universe
PYTHONPATH=src python benchmarks/study.py sota              # ours vs the heavy baselines, small universe
PYTHONPATH=src python benchmarks/study.py <preset> summarize
```

The sections below describe each preset's opponents and the published numbers.
(The older per-study entry points are being folded into `study.py`.)

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
Prophet and longer horizons are left for later. Zero-shot foundation models get
their own protocol — see the next section. Run it (parallel across cores):
`PYTHONPATH=src python benchmarks/sota_study.py` (conda env with `statsforecast`,
`arch`, `statsmodels`, `neuralforecast`, and a FRED key).

## Zero-shot foundation models (`foundation_study.py`)

A **different protocol** from the eight-baseline study. Pretrained time-series
foundation models are used **zero-shot**: at each step we feed a fixed-length
context window (256) of the preceding one-step *changes* and ask for the next
change — no fitting, no refit. All test windows for a series are batched into one
inference call. Every predictive is turned into the same `Dist` (native Student-t
for Moirai/Lag-Llama; sample/quantile reconstruction for Chronos-Bolt/TimesFM)
and scored on log-likelihood and CRPS; `laplace` is re-scored on the identical
window. On 120 FRED change-series (69 continuous), per-series win-rate of
`laplace`:

| model | density | LL (all / cont) | CRPS (all / cont) | mean LL (cont) |
|---|---|---|---|---|
| Moirai (1.1-R-small) | native Student-t | 98 % / **97 %** | 94 % / 93 % | 0.92 |
| Lag-Llama | native Student-t | 67 % / **99 %** | 65 % / 94 % | 0.39 |
| Chronos-Bolt (small) | quantile\* | 76 % / **100 %** | 67 % / 88 % | −1.96 |
| TimesFM (2.5-200M) | quantile\* | 75 % / **100 %** | 58 % / 72 % | −1.18 |

*\*quantile-reconstructed log-likelihood — tail-limited, so read CRPS as the
fairer signal for these two. `laplace` mean continuous logpdf: **1.51**.*

> **On continuous series, `laplace` beats all four foundation models — zero-shot
> — on both metrics** (97–100 % LL, 72–94 % CRPS). The native-density models
> (Moirai, Lag-Llama) are the meaningful likelihood opponents and the closest, but
> still lose per-series. On **repeat-heavy / grid** series the foundation models are
> competitive or better — Lag-Llama even beats `laplace` on mean LL across the
> *full* universe (6.54 vs 4.52) by placing tight mass on revisited values, the
> same trick as the lattice projection — which is why the continuous split matters.

This is the honest scope: zero-shot, no refit, fixed context, forecasting the
*change* stream (not the levels these models were chiefly trained on).
**Fine-tuning may close the gap** — that is a separate study (`foundation_study`
with per-series refit, GPU/MPS-bound for the larger models). Each model needs its
own env (conflicting `gluonts`/`torch`/`jax` pins); the harness writes one
`results_foundation_<tag>.csv` per run and `summarize()` merges them:
`FM_MODELS=Chronos,Moirai FM_TAG=cm PYTHONPATH=src python benchmarks/foundation_study.py`.

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

## At scale: 10,822 systematically-selected series (`large_study.py`)

The 42-series result invites one fair objection — *you picked the series*. So we
re-ran it on a **bias-free universe**: every FRED series tagged `daily`, ordered
by FRED's own popularity ranking (`fred_universe.enumerate_daily`) — a fixed rule
chosen independently of the forecasters. Transform is automatic (log-diff for
positive levels, else first-diff); series need ≥500 changes; each is scored on its
most recent 6,000 changes.

The opponent is `crepes` with a **naive (zero-change) mean** — the cheapest mean
model, which is why this arm scales to ten thousand series. (A *fitted*-mean
conformal — AutoARIMA + conformal — is the tougher CRPS opponent; it costs a refit
per step, so it lives in the smaller `sota_study.py`. Same opponent family,
different mean model, different feasible universe size.)

### Read the CRPS numbers honestly — a single fixed policy, not best-of-ours

We report the **fixed default policy `laplace`** — not "best-of-ours," which would
be post-hoc per-series cherry-picking and is not a win-rate. We give the *opponent*
its best shot: `laplace` (one fixed config) beats crepes even when crepes is handed
its **best calibration window per series**:

> **`laplace` beats best-of-crepes on 96.6% of series** (95% CI 96.3–96.9), and
> **64.8% family-clustered** (198 families, each correlated curve/panel counted
> once; CI 58–72). It also beats each *fixed* window head-to-head — w250 96.6%,
> w400 96.9%, w750 97.0% (family 64.8 / 66.7 / 66.8%) — so no retrospective choice
> is doing the work.

Per-policy (current 0.8.0 set; each a single fixed config), CRPS vs best-of-crepes:

| policy | CRPS raw | CRPS family | mean logpdf |
|---|---|---|---|
| `laplace` — log trunk + **CRPS** tail + sticky *(the default)* | **96.6%** | **64.8%** | **2.988** |
| `laplace-ll` — log trunk + **log** tail (`objective="likelihood"`) | 92.1% | 55.6% | 2.968 |
| `laplace-nostick` — CRPS tail, lattice **off** (`sticky=False`) | 96.2% | 60.2% | 2.848 |
| bare `crps-leaf` (CRPS objective, no trunk) | 92.6% | 61.0% | 2.824 |

The point is the **first two rows**: same machine, repoint only the objective.
The likelihood policy (`laplace-ll`) already edges crepes on CRPS — 55.6% of
families — even though it is not aimed at CRPS. Swap the terminal leaf's objective
to CRPS — keeping the likelihood-weighted trunk — and it climbs to **64.8% of
families**, matching the dedicated CRPS specialist while *also* lifting likelihood
(2.968 → 2.988). That is metric-agnosticism in one line: the objective is a knob,
not a fixed cost.

**Model first, conform last.** The trunk's job is to *model* — get the mean and
structure right — and the honest objective for that is likelihood (a proper,
tail-sensitive score); corrupting it to chase CRPS would be the conformal
mistake of throwing away the density. The *tail's* job is to shape the residual,
and that is the only place a downstream metric (CRPS) should get a vote. Doing
both — likelihood trunk, CRPS leaf — beats the likelihood-only policy on **every**
axis (CRPS raw, CRPS family, *and* likelihood): a CRPS-fit leaf is more
outlier-robust, so it even generalises slightly better on likelihood. No trade.

This is the **0.8.0 default**: `laplace(k)` *is* the top row (CRPS tail + sticky);
`laplace(k, objective="likelihood")` is the log-tail row; `laplace(k,
sticky=False)` turns off the lattice projection (the `laplace-nostick` row).

By asset class (laplace vs the hardest fixed window, keyword-approximate): equity
98.6% (n=7125), fx 97.5% (n=1503), credit 97.2% (n=106), commodity 96.0% (n=25),
rates 94.7% (n=323), other 88.1% (n=1740).

### Crepes cannot be rescued by its calibration window

The obvious objection — *did you give crepes a wide enough window?* — we tested.
Crepes' mean CRPS is **U-shaped** in window length with a flat optimum near **250**
(worse both shorter, where the empirical CDF goes noisy, and wider, where stale
residuals can't track drift). On a 250-series sample, `laplace` beats crepes'
*best-of-{60, 120, 200, 250, 350, 500, 750, 1500}* per series on **96.4%** — the
same as against the three production windows. Widening or narrowing the window
moves crepes by thousandths of a nat; the deficit is **structural** (recency-
unweighted, exchangeability-assuming, no learned volatility clock), not a tuning
choice.

### The win that is *not* on CRPS

CRPS was never our metric. The robust, un-spinnable fact is on **log-likelihood**:

- every skater emits a proper predictive *density* and is scored — `laplace`
  ≈ **2.99 nats/obs**. The lattice projection (`sticky`, on by default) places
  near-Dirac mass on exact repeats; it is worth **+0.141 nats** over
  `laplace-nostick`, realised on the **22%** of series that revisit values and
  free (zero lift, no cost) on the continuous rest;
- crepes emits a *CDF*, not a density, so it scores **nothing** — it cannot be
  evaluated on likelihood at all.

So the real result is not "we beat crepes by X% on CRPS." It is: **on the
economically-grounded, tail-sensitive metric (log-likelihood = Kelly growth),
conformal predictive systems cannot take the field, and skaters can** — while
*also* matching the CRPS specialist on its own metric, by conforming the tail
last without touching the model.

Run it: `PYTHONPATH=src python benchmarks/large_study.py` (needs a venv with
`crepes` + a FRED key).

## On the table

- `naive-gauss` — last value + rolling Gaussian residual.
- `conformal-PD` — the conformal foil (above).
- `scale-mix leaf` — the discrepancy-from-N(0,1) leaf over a simple EMA mean.
- `laplace` / `kahneman` / `skater` — the named policies (terminal-leaf ensemble).
