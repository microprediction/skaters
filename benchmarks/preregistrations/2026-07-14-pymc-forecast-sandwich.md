# Statement of intended research: PYMC-Forecast sandwich and pooling

Filed 2026-07-14, before any full-settings result of this study exists.
Harness: `benchmarks/pymc_forecast_sandwich_study.py`, committed with this
statement. The study inherits the frozen wide-study universe
(`benchmarks/preregistrations/tabfm_wide_universe.txt`, 226 series), its
TEST=150 windows, and its scoring conventions.

## Background

PYMC-Forecast (`pymc-forecast` 0.0.1, PyMC Labs) is a Bayesian time-series
forecasting toolkit released on 2026-07-13, the day before this filing. It
is batch-refit only, produces posterior predictive distributions, and lets
the user specify the generative model and priors. That makes it a new kind
of challenger for the sandwich program: the Rosenblatt front-end fixes the
marginal of the z stream at N(0,1) by construction, so for once a Bayesian
model's priors are not guesswork, and pooling across series becomes
well-posed because every series is reduced to the same coordinate system.

## Questions

1. **Raw.** How does a straightforward PYMC-Forecast model on raw changes
   fare against `laplace` under the standing prequential protocol?
2. **Coordinates.** Does moving the identical model into `laplace`'s
   z coordinates lift it, as it lifted ETS, AutoARIMA, GARCH, Prophet, and
   TabFM?
3. **Convergence.** Does the sandwiched arm land at `laplace` plus or
   minus a small epsilon, as the front-end theory predicts?
4. **Pooling.** Does one hierarchical fit across all 226 series' z streams
   beat the identical model fit per series? This is the first challenger
   arm with access to cross-series information; the parade makes series
   exchangeable, which is the precondition for partial pooling.

## Arms (frozen)

All arms are scored on the same TEST=150 test points per series as every
prior study, log-likelihood only, per-point logpdf floored at -20 for
every method identically. CRPS is not scored (no closed form through the
change of variables, as in the TabFM sandwich study). The shared model is
a Student-t regression on LAGS=8 lagged values: alpha ~ Normal(0, 0.2),
beta ~ Normal(0, 0.2) per lag, sigma ~ LogNormal(0, 0.5),
nu ~ Gamma(2, 0.1), fit with the package's `Forecaster` (mean-field ADVI,
Adam lr 0.01, NUM_STEPS=5000), M=500 posterior draws per fit, seeds
derived deterministically from 20260714 by crc32 of (seed, series, arm,
block).

- **laplace**: plain `laplace(1)`, re-run on identical windows.
- **raw**: the model on raw changes, refit each 10-step block on the
  trailing 248 lag-rows (CTX=256, STRIDE=10, mirroring the TabFM studies),
  each block standardized by its training mean and standard deviation with
  the exact affine adjustment (-log s) taking the density back to y units.
  Constant training windows fall back to the standing 1e-9 atom.
- **sand**: the identical blockwise design on the parade z stream
  (z_t = Phi^{-1} of `laplace`'s PIT, clamped at 1e-12), its z-space
  density mapped back through the exact Jacobian
  log f_y(y) = log f_z(z) + log f_lap(y) - log phi(z).
- **solo**: the same z-space model fit once per series on all pre-test z
  (targets 9..849), frozen through the test window, predictions from live
  lag rows. The no-pooling control for hier.
- **hier**: the same z-space model with non-centred hierarchical priors,
  fit once jointly across every series in the universe (per-series alpha,
  beta, log-sigma partially pooled: mu_a ~ Normal(0, 0.1),
  tau_a ~ HalfNormal(0.1), mu_b ~ Normal(0, 0.1) and
  tau_b ~ HalfNormal(0.1) per lag, m_s ~ Normal(0, 0.2),
  t_s ~ HalfNormal(0.3), shared nu ~ Gamma(2, 0.1); ADVI, 20000 steps).
  Scored exactly like solo. hier vs solo isolates pooling: same window,
  same freeze, same model form, only the priors differ.

Every predictive density is computed exactly as the posterior-draw mixture
of Student-t densities, which is the distribution the package's forecast
sampler draws from; the two were verified against each other once on
synthetic data before filing (moments agreed within Monte Carlo error).
All arms are strictly causal: every feature row ends before its target.

## Hypotheses

- H1 (raw): the per-series log-likelihood win rate of `laplace` over raw
  differs from 50%.
- H2 (coordinates): the per-series win rate of sand over raw differs
  from 50%.
- H3 (convergence): the per-series win rate of `laplace` over sand differs
  from 50%. The front-end theory predicts near-parity with a small median
  gap; the median absolute per-series gap of sand vs `laplace` against
  that of raw vs `laplace` is reported descriptively as the convergence
  measure.
- H4 (pooling): the per-series win rate of hier over solo differs from
  50%. This is the headline question.

No direction is asserted for any hypothesis.

## Analysis plan

H1-H4: two-sided exact binomial sign tests at alpha 0.05, ties as
half-wins. Family-weighted win rates (one vote per FRED family) are
reported alongside raw rates for every named hypothesis. The full
arm-by-stratum table of win rates and median gaps is reported
descriptively for every populated cell, wins and losses alike. Everything
else (including solo vs sand, which confounds refresh cadence with
training-window length) is exploratory and will be labelled so. Nothing
is added after results are read.

## Resumability

Every (series, arm) result is appended and flushed as it completes;
restarts skip finished pairs. The hier rows are written in one pass after
the joint fit, and the joint fit always spans the full universe regardless
of restart state, so the pooled posterior never depends on how the run was
interrupted.

## Environment

pymc-forecast 0.0.1, pymc 5.26.1, pytensor 2.35.1, numpy 2.4.2, scipy
1.17.0, arviz pinned to 0.23.4 because arviz 1.x removes `InferenceData`
and breaks pymc import (dependency conflict observed at install, the
package being one day old). Apple M4, 16 GB, python 3.12.9, CPU ADVI, venv
`~/.venvs/skaters-pymc`. The skaters checkout is 0.13.0-era main
(GPD tails on by default), branch `proto/pymc-forecast-sandwich`.

## Observed before filing (full disclosure)

- All committed TabFM, foundation-model, and horserace results were fully
  known at filing, including the TabFM sandwich result (sandwiching closed
  most of TabFM's gap; its discrete head beat `laplace` on repeat-heavy
  series). The convergence prediction in H3 and the choice to pre-register
  a pooling arm were formed with that knowledge.
- API and timing validation ran on synthetic Student-t data only:
  one-block fits, posterior-draw extraction, and one comparison of the
  analytic mixture against `fc.forecast()` samples.
- A plumbing smoke of the committed harness ran on the first 2 universe
  series (RIMLPBAARNB, SOFR1) at reduced settings (PF_STEPS=500 versus the
  frozen 5000). Its progress lines and summary were observed: at those
  reduced settings, on those 2 series, `laplace` led every arm, sand led
  raw, and hier led solo. No full-settings result existed at filing. The
  smoke rows were deleted; the run starts from an empty results file.
- The smoke also validated resume (rerun skipped both series exactly).

## Outputs

`benchmarks/results_pymc_forecast_sandwich.csv`, one row per (series,
arm): series, method, mean floored logpdf, n, stratum.

## Deviations

(recorded here as they occur, before results are read)
