# Week-long study: one canonical benchmark, everything derivable

Filed 2026-07-22, before running. Goal: over ~7 days of compute, learn as much
as we can about where each forecaster wins, draws, loses, and helps — on the
largest, most diverse FRED universe we can cache, recording PREDICTIONS in one
canonical schema so every metric (now and future) derives from a single source.

## Principle

Run each expensive model ONCE, store its per-step predictions
(`benchmarks/predictions.py` schema: `study, series, method, step, y, mean, std,
q05, q50, q95, logpdf, crps`), and derive LL, CRPS, coverage, Diebold-Mariano
**win/draw/loss**, sandwich lifts, and the meta-feature map from that store. No
per-study summary formats. This is the fix for the format sprawl and the thing
that makes draws computable at all.

## Universe

All cached FRED series qualifying under the study filters (`MIN_CHANGES`, scope
screen), across both regimes and frequencies:
- **non-price** (economic): daily, weekly, monthly — the general universe.
- **price** (equity/fx/commodity returns): GARCH-t's home turf.
Target size after the cache enlargement now running: aim for 20k-40k series.
Every series carries its regime and frequency tag (for stratified analysis, not
as a model input).

## Models, tiered by cost (a week is dominated by the slow arms)

**Tier A — fast, O(1) online, WHOLE universe, k=1.** laplace and variants
(`laplace`, `-ll`, `-nostick`, `garch_leaf`), GARCH-t, statsforecast@25
(AutoARIMA / AutoETS / +conformal / +ACI), SARIMAX, ETS-sm, dantzig, CSP. This
is the backbone; days of compute on a large universe by itself.

**Tier B — medium.** The PyMC-laplace **sandwich** (`solo`, ~2s/series) on a
large stratified sample (~5k), both regimes, to build the sandwich-lift table.

**Tier C — slow, own environments (process-decoupled, emit canonical
predictions, merge).** TabFM (`.venv-fm`), the R suite (auto.arima, thetaf,
ADAM, nnetar, bsts), Prophet — each on a stratified sample (~1-2k). R and
Prophet run with hard per-series TIMEOUTS (they deadlocked the pool before);
skip-on-timeout, never block.

**Horizons.** k=1 across the universe; k=5 and k=20 for laplace + the top few
arms on a ~3k sample, to characterize horizon decay and the multi-scale default.

## Analyses (derived from the one store, re-run cheaply as data accrues)

1. **Win/draw/loss matrix** by DM (HAC SE, draw band |d̄| ≤ z·SE) for every model
   pair, split by regime and frequency. The honest replacement for argmax
   win-rates.
2. **Sandwich-lift table**: for each external model, LL of raw vs sandwiched, by
   regime. Expect lift on non-price, none on price.
3. **Calibration/coverage** at scale: PIT histograms and interval coverage per
   model per regime, from the stored quantiles.
4. **Meta-feature map**: features (spectral entropy, martingality, variance
   ratio, zero/repeat fraction, length, ARCH) vs the DM verdict — does a cheap
   online read predict regime and the win/draw/loss, and can laplace's own
   ensemble state stand in for it.
5. **Allocation vs selection**: does a covariance-aware long-only blend of the
   arms beat always-laplace, where hard selection did not (the flat-LL-surface
   finding)? Per-step store makes the blend's log-score exact.

## Pre-registered expectations (so we can be wrong on the record)

- H1: DM **draws dominate** laplace-vs-GARCH-t (non-price) and laplace-vs-sandwich
  contests — most "wins" are ties.
- H2: hard **selection still does not beat always-laplace** in LL even at this
  scale (replicates `switching-doesnt-pay`).
- H3: the **sandwich lifts external models on non-price, not on price**.
- H4: cheap features (spectral entropy, martingality, zero-fraction) **predict
  regime** well; laplace's ensemble-weight entropy is a near-free proxy.
- H5: a covariance-aware **blend gives a small but real lift** where selection
  did not — the open question worth the week.

## Orchestration

- Driver cycles the tiers in priority order (A, then B, then C, then horizons),
  each a **resumable** append-mode run keyed on (series, method) done-sets.
- **7-day caffeinate.** Everything survives kill/restart.
- Tier C arms run in their own venvs and emit the same canonical predictions;
  a merge step unifies them (no shared environment, `Dist`/scores are the wire).
- **Data policy (the lost-run lesson):** the per-step store is large and
  regenerable, so gitignore it; **commit the derived summaries, the DM
  win/draw/loss records, and the calibration tables** (small), plus the driver
  and schema. Commit as they grow.

## Deliverables at week's end

- The largest committed win/draw/loss matrix we have, both regimes, with draws.
- The sandwich-lift table across every arm.
- Calibration/coverage at scale.
- The meta-feature → verdict map (the arm-selection prior, honestly evaluated).
- A verdict on H5 (does blending pay where selecting did not).
- Rebuilt frontier and radar off the single loader, showing win/draw/loss.
