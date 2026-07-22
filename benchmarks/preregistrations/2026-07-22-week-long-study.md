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

## Orchestration — round-robin across strata (anytime-broad, converging)

The key scheduling rule: **breadth-first, not depth-first.** Do not finish one
model or one regime before starting the next. Instead wrap around the strata so
every checkpoint holds the whole picture at growing resolution.

- Partition the universe into **strata** = (regime x frequency x family) cells,
  which are exactly the radar axes and the frontier's regions.
- The driver runs in **ROUNDS**. Each round draws a small EQUAL sample of
  not-yet-covered series from EVERY stratum and scores the affordable models on
  it, appending to the canonical store. It fills the **thinnest cells first**, so
  coverage stays uniform across strata and models.
- After round 1 every (stratum x model) cell has a few points: broad but noisy.
  Each round deepens every cell uniformly, so the derived estimates (win/draw/
  loss rates, mean LL, each radar axis) **converge** rather than appearing one
  region at a time.
- **Every K rounds, regenerate and commit** the derived summaries plus the
  frontier and the radar (win/draw/loss). The committed charts visibly sharpen
  through the week — the star maps start noisy and settle. Anytime property: the
  run is useful and broad if stopped at any moment.
- Slow arms (TabFM, Orbit, GAS, TiRex, flowstate) take a smaller per-round
  sample per stratum, so they converge slower but never leave a stratum empty.
- **Resumable:** per-cell coverage in the canonical store IS the state; a restart
  resumes the round-robin wherever coverage is thinnest. No round redoes work.
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

## Candidate models to add (researched 2026-07-22)

Screened for open-source + genuinely probabilistic (scoreable on LL and CRPS,
not point-only) + a modeling angle we lack. Each needs a small adapter emitting
the canonical `predictions.py` schema, run in its own env (deps conflict).

Cheap adds (Tier A, `.venv-sota`, near-free):
- **UnobservedComponents** (statsmodels, BSD) — structural state-space, analytic
  Gaussian predictive density. Best value; a decomposable model we don't have.
- **EGARCH + GJR/TGARCH** (arch) — volatility asymmetry/leverage, one-line
  variants of the GARCH-t we already run (price series only).
- **AutoCES + AutoTheta** (statsforecast) — Theta won M3; CRPS-scoreable, trivial.

Novel distributional mechanisms (Tier C, own env, stratified sample):
- **Sundial** (thuml, Apache-2.0, 128M) — flow-matching generative head; the
  freshest architecture, CPU-light. Highest-novelty include.
- **GAS / score-driven** (`gasmodel`, R, via the R bridge) — time-varying-parameter
  densities (t/Gamma/Poisson…), nests GARCH. Most novel paradigm. (Python
  `pyflux` is dead; use R.)
- **Toto** (Datadog, Apache-2.0) — Student-T mixture head, largest corpus;
  flash-attn build friction, GPU for the big checkpoints.
- **TabPFN-TS** (Prior Labs, 11M, CPU, no training) — in-context Bayesian
  predictive; distinct synthetic prior. VERIFY the Prior Labs license first.
- **DeepAR** (GluonTS, Apache-2.0) — autoregressive deep-probabilistic (StudentT);
  fills the AR-deep gap vs our windowed NeuralForecast-t.
- **Orbit** DLT/LGT (Apache-2.0) — Bayesian structural ETS; heaviest install
  (CmdStan compile).

Refresh existing (upgrade, not new entries): **TimesFM 2.5** (now a quantile
head, so LL/CRPS-scoreable) and **Chronos-2**.

From the HF Hub direct search (2026-07-22), two more genuinely probabilistic,
tiny, fresh architectures:
- **TiRex** (NX-AI, 35M, xLSTM) — point + quantiles, univariate zero-shot.
  License: NXAI *community* (not plain Apache; verify like TabPFN).
- **flowstate** (IBM, ~18M, SSM + functional-basis decoder) — 9-quantile output,
  zero-shot. Apache-2.0 but *research-use only* (commercial -> Granite).

Skip: Time-MoE, IBM TTM/Granite, UniTS, base VisionTS, MOMENT — point-only or
representation, no density; Moirai-MoE / Moirai-2.0 — non-commercial license;
Kronos — probabilistic (MIT) but financial OHLCV-specific, not general univariate
(keep for a dedicated price study); TimeGPT — closed API.

License note: TabPFN-TS, TiRex, and flowstate are NOT plain-permissive — decide
per model whether the terms are acceptable before shipping any result publicly.

Priority for the week: the Tier-A cheap adds first (immediate, real new angle in
UCM), then the CPU-light novel ones (Sundial, TabPFN-TS), then Toto / DeepAR /
Orbit / GAS as env setup allows.

## Implementation (added 2026-07-22, after building)

Files:
- `predictions.py` — the one canonical per-step store + `dm_contest` (HAC-SE draw
  band), `mean_scores`, `pairwise_record`.
- `arm_adapters.py` — zero-shot adapter per arm (`laplace`, `Sundial`, `TiRex`,
  `flowstate`, `TabPFN`, `Chronos`, `TimesFM`), each -> a list of per-step
  `Dist`s, reusing foundation_study's `sample_dist`/`quantile_dist` so scoring is
  identical and comparable. Each runs in its own venv.
- `run_arm.py` — canonical runner: scores methods on a corpus arm, writes the
  per-step schema, resumable by (series, method). Tags each series' stratum
  `study = "{arm}:{regime}"` (regime = price|econ from the title).
- `build_corpus_cache.py` — pre-materializes each arm to an offline
  `preds/_corpus_<arm>.jsonl` so the week loop never re-enumerates or touches FRED.
- `week_study.py` — the breadth-first round-robin driver (grows every
  model x corpus cell each round; bounded parallel; commits summaries every K
  rounds; 7-day bound; STOP-file and duration exit; resumable).
- `summarize_canonical.py` — derives `canonical_summary_scores.csv` and
  `canonical_summary_dm.csv` (committed; the chart source).
- `launch_week_study.sh` — caffeinate + nohup launcher.

Protocol: zero-shot, fixed context CTX=128, rolling one-step test window TEST=64,
uniform across arms; laplace re-scored on the identical window is the baseline.
Roster at launch: laplace + Sundial + TiRex + flowstate + Chronos + TimesFM;
TabPFN joins when `TABPFN_TOKEN` is set (one-time license acceptance). DeepAR
(GluonTS) is trainable not zero-shot -> deferred; GAS/Orbit/Toto deferred on
install friction. The per-step store (`preds/`) is gitignored; the derived
summaries are committed.

Attribution (research use): "Built with PriorLabs-TabPFN"; TiRex under the NXAI
Community License (materials developed at NXAI); flowstate ibm-research research
checkpoint (arXiv:2508.05287), research-use only.
