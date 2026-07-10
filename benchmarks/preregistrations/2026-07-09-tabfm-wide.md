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
  up to 24 series per cell, numpy seed 20260709.

Result: 242 series over 14 populated cells, listed with strata in the
committed universe file. Run order interleaves strata round-robin so partial
results stay representative. 28 of the 242 overlap the first bout's universe.

## Arms (frozen)

All arms: zero-shot, context CTX=256 changes arranged as lag tables,
in-context table refreshed every STRIDE=10 steps, NE=4 ensemble members,
TEST=150 rolling one-step, scored through the same `Dist` code as every
prior study (logpdf floor -20). `laplace` re-run on identical windows.

- **clf8**: decile-bin classifier density, 8 lags. The replication arm,
  identical in design to bout 1.
- **clf16**: as clf8 with 16 lags.
- **clfew**: as clf8 but equal-width bins spanning the 1st to 99th
  percentile of training targets (outermost edges at the training min/max).
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

No direction is asserted for any hypothesis.

## Analysis plan

H1-H3: two-sided exact binomial sign tests at alpha 0.05, ties as
half-wins. H4: two-sided Fisher exact test at alpha 0.05 on the win/loss
counts of the two named bins. The full arm-by-stratum table of win rates
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
  stratification by repeat structure and martingality. 28 of this study's
  242 series overlap that universe.
- The first bout's MAE undercard had 4 smoke rows at filing (three
  degenerate ties and one laplace win); its regressor pass was still
  running and unread beyond the progress log.
- The regres residual-density design and the clf16/clfew variants have
  never been run on real data. Their only execution was a plumbing smoke
  test with stub models (fake class-frequency and mean predictors) to
  verify resume logic, which also surfaced the NASDAQ selection leak fixed
  and disclosed above.
- No TabFM weights were used in any wide-study code path before filing.

## Deviations

- (to be filled when the run starts: device, torch version, timing; and a
  real-weights smoke test on a handful of series, run after the first
  bout's process releases the checkpoint memory, results unread beyond
  confirming the harness executes)
