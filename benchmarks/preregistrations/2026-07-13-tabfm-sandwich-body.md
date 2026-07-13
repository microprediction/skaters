# Statement of intended research: TabFM sandwich and body (exploratory)

Filed 2026-07-13, before any result of this study exists. This is an
exploratory follow-up to the pre-registered wide study
(`2026-07-09-tabfm-wide.md`); it inherits that study's frozen universe,
test windows, and scoring conventions, and it is labeled exploratory
because its two hypotheses were formed after reading the wide study's
results.

## Questions

1. **Sandwich.** Does the laplace front-end lift TabFM the way it lifted
   ETS, AutoARIMA, GARCH, and Prophet (149/150 wins, the Rosenblatt
   front-end study)? Arm: TabFM's regressor on lagged parade z, its
   z-space residual density mapped back through the exact Jacobian
   log f_y(y) = log f_z(z) + log f_lap(y) - log phi(z). The front-end
   theory predicts convergence to laplace plus a small epsilon, with the
   epsilon measuring conditional-mean structure in z that laplace missed.
2. **Body.** Does TabFM's conditional mean help as a component? Arm:
   TabFM regressor points p_t on raw lags, laplace consuming the residual
   stream y_t - p_t, the predictive being laplace's residual density
   shifted by p_t. Comparison: plain laplace. The wide study's strata
   predict any gain concentrates on mean-reverting continuous series and
   any loss on repeat-heavy series, whose lattice the residual stream
   destroys.

## Method

Harness `benchmarks/tabfm_sandwich_study.py`, committed with this
statement. Frozen wide-study universe (226 series), TEST=150, regressor
arm settings from the wide harness (lags 8, stride blocks, NE=4,
RESID_ROWS residual window), logpdf floored at -20 for every method
identically. The body arm warms laplace on 300 pre-test residual steps
(TabFM points from a truncated-series pass); this shorter warm-up is a
known limitation, disclosed here. LL only; no CRPS (no closed form
through the change of variables).

Outputs: `benchmarks/results_tabfm_sandwich.csv`, one row per series:
laplace LL, sandwich LL, body LL, stratum. Raw-TabFM comparison joins
from the committed wide-study results.

## Deviations

- 2026-07-13, run start (Mac Studio): device mps, torch 2.4.1, 25s for
  series 1 (all three arms). Chained automatically behind the post-hoc
  RMSE pass. Noted from the progress line only.

## Addendum: Prophet at wide-study scale (filed 2026-07-13, before results)

Same exploratory framing: does Prophet's FRED-30 sandwich result (30/30
fronted wins, the largest median lift of the classical opponents) hold on
the frozen 226-series universe, and does its calendar machinery add
anything beyond laplace at this scale? Harness
`benchmarks/prophet_sandwich_study.py`, reusing the front-end study's
rolling-refit Prophet, Jacobian, and clamps unchanged. Output
`benchmarks/results_prophet_sandwich.csv`.
