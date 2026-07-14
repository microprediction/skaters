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

- Read 2026-07-13. 921 of 1,367 scored. The 446 unscored series are all
  length skips, zero fit failures: the selector screened at the wide
  study's HIST (1,000 changes) while the runner inherits the front-end
  study's MIN_LEN=1500. The universe freeze and the runner requirement
  were inconsistent; the effective universe is the 921 series meeting
  both, and no result influenced which. Disclosed as a design error.
- Concentration is severe and the family-weighted view is therefore the
  primary lens, per the plan: one family (IHLI) is 438 of 921 scored
  series (48%).

## Results (first read, per the frozen plan)

Sandwich: PRIMARY median -0.0196 (77/921 wins, 8%); family-weighted
(120 families) -0.0249, 16% of families positive. The success criterion
([-0.05, +0.01]) is met on both views: the epsilon holds at full scale.
Strata: every rho bin sits between -0.011 and -0.022 except the two
lattice-dominated slices (repeat -1.23, rho~0 -0.82), where Prophet's
Gaussian head cannot express atoms even in z coordinates.

Raw: PRIMARY median -0.755 (4/921 wins); family-weighted -4.60 with 0%
of families positive, the unweighted median being flattered by the one
giant continuous family. Repeat-heavy series run at -11.3 median.
Question 2 answered: the collapse pattern persists and deepens at scale.

