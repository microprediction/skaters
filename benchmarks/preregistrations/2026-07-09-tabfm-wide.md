# Statement of intended research: TabFM wide study

Filed 2026-07-09, evening EDT, before any result of this study exists.
Harness: `benchmarks/tabfm_wide_study.py`, committed with this statement.
Universe: `benchmarks/preregistrations/tabfm_wide_universe.txt`, generated
deterministically and committed with this statement. The run will execute on
a different machine (a Mac Studio) over the following days; this repository
commit precedes it.

## Research questions

The first TabFM bout (see `2026-07-09-tabfm.md`) ran one design on the
120-series foundation-model universe. This study asks three wider questions:

1. Does the first bout's result replicate on a larger, deliberately
   stratified non-price universe?
2. Does the way TabFM is used matter: lag depth, binning scheme, and a
   residual-based density from its regressor rather than a binned density
   from its classifier?
3. Does relative performance depend on series character, in particular
   martingality (lag-1 autocorrelation of changes) and repeat structure?

## Universe (frozen)

All cached FRED series satisfying every rule below, characterized on the
pre-test history only (the final TEST=150 changes never inform selection):

- Non-price: the standing title-based classifier (`fred_universe.asset_class`
  not in {equity, fx, commodity}), plus a supplemental title/id screen for
  names the standing classifier misses (nasdaq, coinbase, bitcoin, ethereum,
  litecoin, s&p, dow jones, wilshire, gold, silver, crude, "price index
  for"). Series whose title is unknown are excluded because they cannot be
  classified. This screen exists because the plumbing smoke test surfaced a
  NASDAQ index leaking through; that was observed before any model result
  and is disclosed below.
- At least 1000 changes; the last 1000 are used. Pre-test history must not
  be constant (constant series measure the fallback convention, not the
  model, a lesson from bout 1).
- Stratified sample: 5 martingality bins (lag-1 autocorrelation of changes:
  below -0.2, -0.2 to -0.05, -0.05 to 0.05, 0.05 to 0.2, above 0.2) crossed
  with 3 repeat bins (repeat fraction below 0.05, 0.05 to 0.35, above 0.35),
  up to 48 series per cell, numpy seed 20260709.
- Family diversity: within each cell, selection round-robins across FRED
  families (the leading capital run of the id, the standing `family` rule)
  with at most 2 series per family per cell, so a yield curve or panel of
  near-duplicates cannot crowd out diversity.

Result: 226 series over 14 populated cells and 112 distinct families, with
per-series characteristics (family, lag-1 autocorrelation, repeat fraction,
excess kurtosis 0.2 to 845, volatility clustering -0.16 to 0.90) recorded in
the committed universe file. Run order interleaves strata round-robin so
partial results stay representative.

## Arms (frozen)

All arms: zero-shot, context CTX=256 changes arranged as lag tables,
in-context table refreshed every STRIDE=10 steps, NE=4 ensemble members,
TEST=150 rolling one-step, scored through the same `Dist` code as every
prior study, except that the per-point logpdf floor of -20 applies to any
value below it, not only non-finite ones, for every method identically,
laplace included (see the amendment note). `laplace` re-run on identical
windows.

- **clf8**: decile-bin classifier density, 8 lags. The replication arm,
  identical in design to bout 1.
- **clf16**, **clf32**: as clf8 with 16 and 32 lags (lag depth).
- **clfew**: as clf8 but equal-width bins spanning the 1st to 99th
  percentile of training targets (outermost edges at the training min/max).
- **clf2g**: two staggered decile grids (the second offset half a decile),
  densities averaged: roughly 20 effective bins under the model's 10-class
  ceiling (bin resolution).
- **clfx100**: clf8 run on 100x the series, scored on 100x the targets, then
  adjusted back by the exact affine change of variables (logpdf plus
  log 100, CRPS over 100). Equal to clf8 if and only if the pipeline is
  scale-invariant; the per-series deviation measures scale sensitivity.
- **clf8h5**, **clf8h20**: clf8 forecasting the change 5 and 20 steps
  ahead (features end h steps before the target, in training rows and test
  rows alike), scored against laplace's native 5- and 20-step predictives,
  the h-th element of its k-step list emitted h observations earlier. The
  horizons match the standing multi-step study (1, 5, 20).
- **blr8**, **blr2**: controls, not TabFM. Conjugate Bayesian linear
  regression (evidence-maximised ridge) on the identical 8-lag and a minimal
  2-lag table, predictive Gaussian per step. If a closed-form linear
  posterior matches TabFM on the same table, the in-context learning added
  nothing.
- **regres**: the regressor. Per block, fit on all but the last 40 training
  rows, predict those 40 held-out rows and the block's test rows in one
  call; the density is a Gaussian-KDE of the 40 held-out residuals centred
  on each test prediction. Its raw point predictions also feed the MAE
  undercard against the median of laplace's predictive.

Bar-distribution smoothing as in bout 1: one Gaussian per bin at the bin
centre, bandwidth 0.29 of bin width, probability floor 1e-6. Degenerate
constant training windows fall back to an atom with bandwidth 1e-9.

## Hypotheses

- H1 (replication): on the continuous stratum (repeat fraction below 0.05),
  the per-series log-likelihood win rate of `laplace` over clf8 differs
  from 50%.
- H2: same, CRPS.
- H3 (undercard): over all scored series, the MAE win rate of laplace's
  median over the regres points differs from 50%.
- H4 (martingality interaction): among continuous series, the clf8
  log-likelihood win rate of `laplace` differs between the strongest
  mean-reversion bin (autocorrelation below -0.2) and the near-martingale
  bin (-0.05 to 0.05).
- H5 (control): on the continuous stratum, the per-series log-likelihood
  win rate of clf8 over blr8 differs from 50%.
- H6 (horizon): on the continuous stratum, the per-series log-likelihood
  win rate of laplace's 5-step predictive over clf8h5 differs from 50%.
  The 20-step horizon is reported descriptively.

No direction is asserted for any hypothesis. Scale invariance (clfx100 vs
clf8) and all other arm-vs-arm contrasts are reported descriptively.

## Analysis plan

H1-H3, H5 and H6: two-sided exact binomial sign tests at alpha 0.05, ties as
half-wins. H4: two-sided Fisher exact test at alpha 0.05 on the win/loss
counts of the two named bins. Family-weighted win rates (one vote per FRED
family, the standing robustness check) are reported alongside raw rates for
every named hypothesis. The full arm-by-stratum table of win rates
and median log-likelihood gaps is reported descriptively for every arm and
every populated cell, wins and losses alike. Arm-vs-arm comparisons and
everything not named above are exploratory and will be labelled so. Nothing
is added after results are read.

## Resumability and partial results

Every (series, arm) result is appended and flushed as it completes; the
harness skips finished pairs on restart and was kill-tested (35 rows,
kill -9, restart, exact completion, no duplicates). If the weekend ends
with the run incomplete, the analysis uses all completed series as of the
cutoff and says so; the round-robin stratum order keeps a truncated sample
representative by design.

## Environment

`tabfm` 1.0.0 with the safetensors-to-bin conversion of snapshot
`77cb9cc1b4fd3a9c77fbb9552c218200bb4dab83`. The run machine is a Mac Studio;
device (cpu or mps), torch version and per-series timing will be recorded in
the deviations section when the run starts, before any result is read.
Numerical results on mps will be accepted as-is; any mps/cpu discrepancy
discovered later is reported, not silently reconciled.

## Observed before filing (full disclosure)

- The first bout's classifier-arm results are fully known at filing:
  laplace won log-likelihood on 85 of 120 series (62 of 69 continuous,
  median continuous gap 0.24 nats) and CRPS on 63 of 120 (41 of 69
  continuous), with TabFM ahead on the repeat-heavy split and on six
  commercial-paper amount/volume series. This directly motivated the
  stratification by repeat structure and martingality. 47 of this study's
  226 series overlap that universe (recomputed after the family-diversity
  amendment reshaped the sample; 28 under the original 242-series draft).
- The first bout's MAE undercard had 4 smoke rows at filing (three
  degenerate ties and one laplace win); its regressor pass was still
  running and unread beyond the progress log.
- The regres residual-density design and the clf16/clfew variants have
  never been run on real data. Their only execution was a plumbing smoke
  test with stub models (fake class-frequency and mean predictors) to
  verify resume logic, which also surfaced the NASDAQ selection leak fixed
  and disclosed above.
- No TabFM weights were used in any wide-study code path before filing.

## Amendments (2026-07-09, later the same evening, still pre-run)

Made after first filing but before any real TabFM inference in this study;
no TabFM weights had touched any wide-study code path at amendment time.

1. Universe cap raised from 24 to 48 per cell and the family-diversity rule
   added (at most 2 per family per cell), on the author's direction to
   widen the sample and take greater care over diversity. The universe file
   was regenerated once under the amended rule: 226 series, 112 families.
2. Arms added on the author's direction: clf32 (more lags), clf2g (more
   effective bins), clfx100 (scale invariance), blr8/blr2 (Bayesian linear
   regression controls).
3. Horizon arms clf8h5 and clf8h20 added with hypothesis H6, on the
   author's observation that every arm so far was one-step-ahead ("we kinda
   forgot about k>1"). Horizons follow the standing multi-step study.
4. Scoring floor amended: the stub-model sweep over the full universe
   exposed administered-rate step series (IOER, IORR) where a policy jump
   lands far outside a 1e-9-bandwidth atom and the finite per-point logpdf
   reaches -5e14, letting a single point decide a series. The -20 floor now
   applies to any lower value, every method identically. No real model
   output informed this: the affected scores came from stub predictors.

## Smoke log (2026-07-10, pre-run)

- Real-weights CPU smoke: 2 series (RIMLPBAARNB, SOFR1) through every arm
  then available; all rows present, resume intact. Run before the horizon
  arms existed.
- Full-universe stub sweep rerun after the horizon arms: 226 series x 14
  methods, full coverage, no duplicates, no below-floor scores.
- Real-weights MPS smoke: first attempt crashed because Apple's MPS
  framework has no float64 and the tabfm wrapper moves numpy arrays to the
  device as-is. Fixed with a harness-level shim active only on mps that
  casts float64 arrays to float32 on the way in; the cpu path is untouched.
  Rerun: 1 series through all 14 methods on mps, exit clean. Timing on the
  16 GB development machine: 382s for the eight classifier-pass TabFM arm
  units, 39s for the regressor pass, roughly 2.5x the cpu pace, projecting
  about 26 hours for the full universe at this machine's pace; the Mac
  Studio should improve on that.
- All smoke result rows were deleted after verifying execution and
  coverage; no score was read beyond what the progress log prints.

## Deviations

- 2026-07-10, run start (Mac Studio): device mps, torch 2.4.1, python
  3.11.15. First logged timings: clf pass 95s (series 1, RIMLPBAARNB) and
  91s (series 2, SOFR1), roughly 4x the 16 GB laptop's smoke pace. Recorded
  from the progress log only; no result row read.
- The checkout executing the run is skaters 0.13.0 (PR #98 branch), which
  postdates this statement: laplace predictives carry GPD tails by default
  as of 2026-07-09. This changes the laplace opponent arm relative to the
  smoke-tested laplace only in its tail shape; arms, universe, and scoring
  are untouched. Noted before any result is read.
- Environment deviation from the runbook: no conda on the Studio; a uv
  python 3.11 venv with the same package set was used instead. tabfm's
  pip metadata omits absl-py and jaxtyping; both installed explicitly.
