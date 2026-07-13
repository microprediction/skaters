# Statement of intended research: Prophet sandwich, full universe

Filed 2026-07-13. Chronology, stated plainly: the universe (1,367
series), arms, and scoring were frozen and committed before the run
launched (see the second addendum to `2026-07-13-tabfm-sandwich-body.md`
and the commit history). This full statement is filed while the run
executes; at filing time no result row has been read. Only the progress
log's series counts have been seen. This upgrades the addendum to a
complete statement with a frozen analysis plan; it does not alter the
arms, universe, or scoring, which were already committed.

## Research questions

1. Does the sandwich epsilon observed at 217 series (Prophet sandwiched
   lands ~0.02 nats behind plain laplace) hold on every qualifying
   non-price series (1,367), i.e., is the residual-test bound stable at
   full scale?
2. Does raw Prophet's collapse pattern (repeat-heavy series worst)
   persist, and what is its full-universe median deficit?
3. Concentration: with no family caps, do a few large FRED families
   drive either verdict? The universe file records family labels so this
   is analyzable.

## Frozen analysis plan

- Primary: median of (arm LL - laplace LL) per series, and per-series
  win rate, for prophet_raw and prophet_sandwich, over all scored
  series. No pooling of LL across series.
- Strata table: the same two statistics by repeat bin and by rho bin,
  using the recorded stratum labels.
- Concentration check: recompute the primary statistics family-weighted
  (each family's series first averaged within family, one vote per
  family), mirroring the paper's family-weighting convention. Report
  raw and family-weighted side by side.
- Series that fail to score (fit errors, insufficient length) are
  reported as a count with reasons; no imputation.
- Success criterion for Q1: the full-universe sandwich median lies
  within [-0.05, +0.01] nats; anything outside prompts a written
  diagnosis before any narrative use.

## Deviations

- (fill at read time)
