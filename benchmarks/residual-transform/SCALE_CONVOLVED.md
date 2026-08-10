# Recursive laplace-on-scale-defect: a derivation, several wrong turns, and where it lands

This is the second residual-transform thread (see `README.md` for the first:
the M0/M1/M2 leverage study, concluded negative). This one starts from a
different idea and ends up somewhere more interesting, via several
instructive failures. Code in `laplace_on_scale.py`; real-data scripts are
`run_scale_convolved_fred.py` (the moment-matched design) and
`run_kalman_grid_fred.py` (the derived design this thread settles on).

## The starting idea

Instead of hand-building a volatility filter (what phase 1's M1/M2 and the
homogenization cell model both did), point `laplace` at its own scale
defect: form `x_t = log(z_t^2)` from the base skater's own PIT stream and
hand that derived series to a *second*, independent `laplace` instance.
Whatever structure exists in the scale-defect series (seasonal, AR,
whatever), a second general-purpose forecaster should find it for free, no
new modelling code, no new online-learning-rate to get wrong.

Combining the meta-forecast back into a corrected predictive for `y` has to
be done carefully: collapsing the meta-forecast's mixture to a point
estimate and exponentiating (`kappa = exp(mean/2)`) understates the true
correction by Jensen's inequality (`E[exp(X/2)] > exp(E[X]/2)`, since `exp`
is convex). `ScaleMetaCorrectedDist` avoids this by building the corrected
CDF directly from the meta-forecast's own exact `cdf`/`quantile`, for any
strictly increasing coordinate map `g`:

    H(z) = 1/2 + 1/2 * H_t.cdf(g(z))         z > 0
    H(z) = 1/2 * (1 - H_t.cdf(g(-z)))        z < 0

exact given `H_t`, monotone because `H_t.cdf` is.

## Wrong turn 1: coordinate choice (Wilson-Hilferty)

`g(kappa) = log(kappa^2)` is the obvious coordinate, but feeding it to a
Gaussian-mixture-based meta-forecaster fails badly: even given the *exact*
true mean/variance of `log(z^2)`, the round-trip on iid `N(0,1)` data came
back with variance ~0.86 and kurtosis ~1.86, not the ~1/~3 it should be.
Isolating it (feeding `ScaleMetaCorrectedDist` the *true* non-Gaussian law
of `log(z^2)` directly, bypassing any Gaussian approximation) reproduced
`N(0,1)` almost exactly -- so the composition math was right; the coordinate
was wrong. `log(chi-sq_1)` is substantially left-skewed, and a
Gaussian-mixture leaf (symmetric components only) cannot represent that
skew regardless of how much data it sees. That's a structural mismatch, not
an estimation problem.

The fix looked like Wilson-Hilferty: `g(kappa) = kappa^(2/3)`, the classical
near-Gaussian stabilizing transform for a chi-squared variate
(`(chi-sq_1)^(1/3) ~= N(1-2/9, 2/9)`). It worked: iid null var=0.99/kurt=3.19,
periodic-vol (a synthetic period-24 volatility stream, see
`gen_periodic_vol`) var=1.04, both close to exactly calibrated, confirmed
across 8 seeds.

**Why it was still the wrong fix.** Wilson-Hilferty solves "make the
*marginal* shape Gaussian." If scale is genuinely time-varying,
`e_t = sigma_t * xi_t`, the thing worth tracking is additive in *log*
coordinates: `log(sigma_t^2 xi_t^2) = log(sigma_t^2) + log(xi_t^2)`. A power
transform gives `sigma_t^(2/3) xi_t^(2/3)` -- still multiplicative, buys
nothing for tracking dynamics even though it helps the static shape.
`log(z^2)` was the right coordinate for *tracking* all along; what was
missing was the exact shape for the noise term.

## The exact fix: log(chi-sq_1) has a closed form

`log(z_{t+1}^2) = h_{t+1} + eps_{t+1}`, where `h_t` is the latent
log-variance state (or, in PIT space specifically, the forecaster's own
miscalibration state) and `eps_t` is *pure noise* with an exactly known law:
`E[log(chi-sq_1)] = -gamma - log(2) ~= -1.27036`,
`Var(log(chi-sq_1)) = pi^2/2 ~= 4.9348` (both exact, digamma/trigamma
identities). `ConvolvedExactLogChiSq` represents `h ~ N(h_hat, V_h)`
convolved against the *exact* raw log(chi-sq_1) law by 7-point Gauss-Hermite
quadrature (reusing `skaters.pushforward._GH7`, not a new quadrature
scheme). With `h_hat`/`V_h` taken from `laplace`'s own predictive
mean/variance on `x_t = log(z_t^2) + 1.27036` (net of the known noise
variance, `V_h = max(laplace_var - R, 0)`), this is `laplace_scale_convolved`
-- synthetic iid null var=0.90 (8-seed sd 0.009), periodic-vol var=1.00
(8-seed sd 0.013). Both stable across seeds, not a lucky draw.

## The closure non-issue, and the real remaining issue

An early framing said Gaussian mixtures aren't "closed" under squaring, so
a bespoke construction was needed. That's wrong, or at least misleading:
`skaters.pushforward.PushforwardDist` already does exact reverse-transform
reshaping elsewhere in this codebase, and `ConvolvedExactLogChiSq`'s own
noise term *is* exactly that mechanism (a standard normal pushed through
"square then log" is exactly log(chi-sq_1), no approximation). The closure
framing was a distraction from the actual remaining problem.

The real issue: `ConvolvedExactLogChiSq` collapses the meta-forecaster's own
predictive *mixture* for `h` down to a single `(mean, variance)` before
convolving -- exactly the averaging mistake `terminal_leaf_ensemble` already
exists to avoid at the output layer ("Bayesian model averaging preserves
mean and variance but washes the kurtosis out"), just committed one level
up, at the latent-state layer. `MixtureConvolvedExactLogChiSq` fixes this by
convolving each of the meta-forecaster's own components separately and
mixing the results. Tested against the moment-matched version: **worse**,
not better (iid null var 0.86 vs 0.90; periodic-vol var 0.89 vs 1.01), and a
log-score comparison confirmed it wasn't a mixture-vs-moments measurement
artifact -- the mixture version scored worse too (median delta ~0, mean
delta slightly negative, minority of ticks improved). Diagnosis: laplace's
15 candidates agreed almost exactly on the mean (`between`-component
variance was `0.000` at every tick checked) -- all the disagreement was
about width, so preserving the mixture structure bought nothing here. A
real, informative negative result, not a wasted detour.

## Real data: the moment-matched design fails, uniformly

Tested on 20 real FRED series (same loader/methodology as `README.md`'s
M0/M1/M2 study): **every single series had a negative per-series median.**
Mean of means was -0.30, dominated by one catastrophic outlier
(`RIFSPPFAAD30NB`: -5.76 on a single bad tick), but even the median of
medians (-0.0107) was consistently negative -- not noise, a real,
reproducible degradation, despite passing every synthetic check. The two
curated synthetic cases (iid null, one exactly-known clean period) simply
didn't stress-test what messy real dynamics in `log(z^2)` actually look
like.

## The derivation that actually mattered

Log-score is a *proper* scoring rule: reporting your true posterior belief
`q(x) = integral of h_raw(x-h) pi(h) dh` is provably optimal, no separate
"asymmetric adjustment" needed on top, *provided* `pi(h)` is honest. Every
design up to this point reduced `pi(h)` to a bad point estimate (laplace's
raw variance minus the known noise `R`; a hard positivity floor to test the
"never narrow" hypothesis directly, which did improve per-series medians
uniformly on the same 5 real series but hurt the periodic-vol synthetic case
by removing *correct* narrowing along with incorrect narrowing; an online
method-of-moments estimate of a Kalman filter's `(rho, tau^2)` that divided
by a near-zero quantity and produced nonsense values like `rho=643205`).

The actually-correct fix follows directly from properness: this is signal
extraction with a *known* observation-noise variance (`R`, exact) -- the
textbook solution is a Kalman filter (the classical econometric precedent
for treating `log(y_t^2)` this way is Harvey, Ruiz & Shephard 1994
quasi-ML stochastic volatility estimation), and the failure mode was never
the Kalman logic (a single hand-picked `(rho=0.98, tau=0.1)` filter already
gave the best synthetic-null result of the session, var=0.99/kurt=3.02) --
it was trying to point-estimate the hyperparameters from one noisy ratio.
The fix already used everywhere else in this codebase: don't point-estimate,
run a small **fixed grid** of `(rho, tau^2)` candidates (including a
`tau=0` "nothing to correct" baseline), combine by ordinary online
likelihood weighting (`bayesian_ensemble`'s own idiom), and use
`MixtureConvolvedExactLogChiSq` to keep the pooled result a genuine mixture
over live hypotheses rather than an averaged point. That mixture *is* an
honest `pi(h)`; properness does the rest. `laplace_scale_kalman_grid`.

## Results: the derived design, vs. the moment-matched design

Synthetic (seed 1, T=3000):

| | iid null (var/kurt) | periodic-vol (var/kurt) |
|---|---|---|
| moment-matched | 0.90 / 2.77 | 1.01 / 3.66 |
| Kalman-grid | **1.03 / 3.30** | 1.16 / 4.10 |

Kalman-grid is the closest to exactly calibrated on the null of anything
tried. Periodic-vol is now over-dispersed rather than under -- given
everything above about asymmetric cost, that's the cheap direction to be
wrong in.

Real FRED, 20 series (`run_scale_convolved_fred.py` vs `run_kalman_grid_fred.py`):

| | moment-matched | Kalman-grid |
|---|---|---|
| mean of per-series means | -0.303 | **-0.045** |
| worst single series | -5.76 | **-0.43** |
| median of per-series medians | -0.0107 | **-0.0057** |
| mean of per-series frac>0 | ~0.40 | **0.473** |
| crps delta (mean of means) | -0.00043 | -0.00027 |

The catastrophic tail case shrinks by more than 10x, and the typical
per-tick outcome moves from systematically unfavorable (~40% of ticks
improve) to close to a coin flip (~47%) -- exactly the signature of a
mechanism that stopped making occasional badly-overconfident bets and
started reporting an honest, hedged belief instead. It is **not** a clean
win: only 3 of 20 series show a net-positive median. This reads as "roughly
neutral, hovering at the boundary" rather than "still reliably harmful,"
which is a materially different and better place than every earlier design
in this thread landed, but it is not yet a positive result to ship.

### Broadened check (N=50, both fred and waveform arms)

The N=20 FRED spot-check above was encouraging but small. Broadening to
N=50 on FRED, and adding the waveform (M4-hourly) arm at N=50 for a direct
read on the regime this whole session started from ("laplace runs baggy on
near-deterministic, cyclic data") gives a materially clearer, and more
satisfying, picture:

| | fred (n=50) | waveform (n=50) |
|---|---|---|
| mean of per-series means | -0.0287 | -0.0962 |
| median of per-series medians | -0.0044 | **+0.0059** |
| frac series with positive median | 0.24 | **0.70** |
| mean of per-series frac>0 | 0.482 | **0.522** |
| crps delta (mean of means) | -0.00012 | **+0.00051** |

**FRED stays roughly neutral** at the larger sample size (median of medians
-0.0044, essentially a wash, and both the mean-of-means and CRPS delta
moved *closer* to zero than the N=20 read, -0.045 to -0.029 and -0.00027 to
-0.00012 respectively) -- consistent with the N=20 finding, not a fluke,
just confirmed with more data. Generic macro/financial FRED series don't
show a real, exploitable scale-defect signal for this mechanism to find,
and it correctly stays close to neutral there rather than doing harm.

**Waveform is a genuine, clear win.** Median of per-series medians is
positive, 70% of the 50 series show a net-positive median (up from FRED's
24%), the average per-tick frac>0 clears 0.5, and CRPS improves on average
too -- the first result in this entire investigation to be unambiguously
positive by every one of these criteria at once, not just "less negative
than before." The two large-magnitude negative means in the sample (`H208`:
-0.37, `H300`: -0.42) both still have *positive* per-series medians
(+0.028, +0.003) -- the same catastrophic-single-tick pattern as the FRED
outliers, dragging the mean down while the typical, median behavior is
still a genuine improvement.

This closes the loop back to the very first hypothesis of the session:
`laplace` really does run measurably baggy specifically on near-
deterministic, cyclic data, and a properly-derived (not point-estimated)
online scale correction is a real, if narrow, fix for exactly that regime
-- while correctly declining to do anything harmful on generic data where
there's no real signal to find.

## Is the exact-noise-law/Kalman machinery even necessary?

The Kalman-grid design above is exact but elaborate: a closed-form
log(chi-sq_1) noise law, a Gauss-Hermite convolution class, and a
hand-rolled Kalman filter per grid candidate. `skaters` already ships an
exact, invertible, time-varying-scale transform: `garch`. Composing it
directly onto the PIT-residual stream needs none of that machinery --
`conjugate(leaf(k=1), garch(omega, alpha, beta), k=1)` is already a
complete skater, and a much simpler `ZSpaceCorrectedDist` (no coordinate
map, no noise-law convolution -- `h` is already a plain `Dist` over `z`)
composes it back onto the base forecast.

A single, unhedged `garch(omega=0.05, alpha=0.1, beta=0.85)` this way gave
the best synthetic round-trip of the entire session (iid null var=1.006,
kurtosis=3.23) but was uniformly *worse* than the Kalman-grid on all 5 real
FRED series -- the identical "confidently wrong on messy data" failure
every other point-estimate design hit. Unsurprising in retrospect: one
fixed `(omega, alpha, beta)` is still a single point estimate, just phrased
in a different coordinate system.

So hedge it exactly the way the Kalman grid is hedged: a small fixed set
of `(omega, alpha, beta)` triples (`_GARCH_GRID` in `laplace_on_scale.py`),
each with unconditional variance pinned to 1 (`omega = 1 - alpha - beta`)
so they differ only in *dynamics*, plus the exact identity candidate
(`alpha = beta = 0` makes `sigma_t^2 = omega` constant, i.e. no correction
at all). Because each candidate's own output is already a plain Gaussian
`Dist`, the pool is exactly the job `bayesian_ensemble` already does --
`laplace_scale_garch_grid` is nothing more than
`bayesian_ensemble(candidates, prior_log_weights=[large-identity-prior, 0, 0, ...])`
run on the z-stream, no new mixture class required.

Synthetic behavior barely moved from the unhedged version (iid null
var=0.991/kurt=2.97; periodic-vol var=1.049/kurt=3.93 -- both still good).
Real data is where it gets interesting: on the same 5-series FRED
spot-check used throughout this document, the hedged garch-grid and the
Kalman-grid land in *genuinely different places*, not one strictly beating
the other:

| | Kalman-grid | garch-grid |
|---|---|---|
| mean of per-series means | -0.0159 | **-0.0018** |
| frac series with positive mean | 0.20 | **0.60** |
| median of per-series medians | **-0.0055** | -0.0365 |
| frac series with positive median | **0.20** | 0.00 |
| mean of per-series frac>0 | **0.472** | 0.356 |
| crps delta (mean of means) | **-0.00045** | -0.00298 |

The garch-grid wins decisively on the *mean*-based metrics and loses just
as decisively on every *median*/typical-tick metric. That split is the
real finding, not noise: `garch`'s multiplicative, directly-reactive scale
recursion is more willing to swing sharply when a real regime shift shows
up, which occasionally pays off big in log-score (mean of means turns
solidly positive-leaning, 60% of series net-positive on average) -- but the
same responsiveness makes it noisier tick-to-tick, so on the *typical* tick
it does slightly more harm than good (0/5 series have a net-positive
median, and CRPS -- which does not reward rare big wins the way log-score
does -- comes out clearly worse, dragged down by one series, `KCROROE`,
whose CRPS delta is -0.014 alone). The Kalman-grid's slower, filtered
`h`-state is the opposite trade: safer on the typical tick, less able to
capture the rare large win.

This settles the question the section title asks: the specific noise-law/
Kalman machinery is *not* what was doing the work all session -- a much
simpler invertible-transform composition does the same job, confirming
(again) that the real fix was always NFL-safe hedging (a grid including a
"do nothing" candidate, combined by online evidence) rather than any
particular mathematical framework. But the *choice* of framework still
matters for the shape of the result: for a defensive, general-purpose
correction in the spirit of the rest of this codebase (protect the typical
case, avoid single-tick catastrophes) the Kalman-grid's profile is the
better fit; the garch-grid is a legitimate alternative specifically where
occasional large regime-shift detection is worth more than typical-tick
reliability, and CRPS is not the metric that matters.

## Extended battery: broadening, ablating, and a cleaner alternative

A follow-up session ran a wider battery at proper sample sizes: the
garch-grid broadened from its earlier N=5 spot-check to the full N=50
fred/waveform samples, Kalman-grid ablations on grid resolution and
weight-decay, a new price/garch_leaf-base arm for both designs, a
dedicated diagnosis of the `THREEFY9` holdout, and a third design (the
homogenization cell model, previously validated only on synthetic data)
composed onto real data for the first time. Scripts: `run_garch_grid_fred.py`,
`run_kalman_grid_finegrid.py`, `run_weight_decay_sweep.py`,
`run_price_arm.py`, `cell_model_on_laplace.py`, `run_cell_model_fred.py`.

### garch-grid at proper scale: the small-sample read didn't hold up

The N=5 spot-check reported above showed garch-grid winning on mean-based
log-score at the cost of typical-tick metrics -- a real but narrow
trade-off. At N=50 the picture is worse than that framing suggested:

| | fred (n=50) | waveform (n=50) |
|---|---|---|
| mean of per-series means | -0.0062 | -0.0137 |
| frac series positive mean | 0.30 | 0.30 |
| median of per-series medians | -0.0312 | -0.0174 |
| frac series positive median | 0.02 | 0.30 |
| mean of per-series frac>0 | 0.368 | 0.418 |
| crps delta (mean of means) | -0.00102 | -0.00091 |

garch-grid still keeps a tamer mean-of-means than the Kalman-grid on both
arms (no single-series catastrophes), but it now **reverses the one clean
win this whole investigation had** -- the waveform arm, where Kalman-grid's
median of medians was +0.0059 with 70% of series net-positive, comes out
-0.0174 / 30% under garch-grid. The n=5 sample was not representative.

### Kalman-grid ablations: grid resolution and weight-decay

**Resolution.** A 26-candidate grid (`fine`, 5x5 rho/tau plus identity, vs.
the original 10-candidate 3x3) gives a small, consistent improvement on
waveform (median of medians +0.0064 vs +0.0059, frac positive median 0.76
vs 0.70, crps +0.00065 vs +0.00051) and an equally small one on FRED
(median of medians -0.0033 vs -0.0044, crps +0.00002 vs -0.00012, frac
positive median unchanged at 0.24) -- confirming the original grid wasn't
leaving much on the table, not that it was under-resolved. Two axis
ablations at N=30 (wide-rho: original 3 tau values x 5 rho values; wide-tau:
original 3 rho values x 5 tau values) don't clearly improve FRED over the
original grid's N=50 read (wide-rho median of medians -0.0037, wide-tau
-0.0053, vs the original's -0.0044 -- all within noise of each other at
N=30). Wide-tau's extra reactivity is actively counterproductive on
waveform's mean-of-means (-0.1450, driven by a -1.30 single-series
catastrophe) without improving its median (+0.0040 vs the original's
+0.0059) -- more headroom to overreact just costs more when it's wrong,
consistent with the THREEFY9 mechanism found below.

**Weight-decay.** Swept `{0.99, 0.995, 0.999, 0.9999, 1.0}` at N=30. Both
arms show the same shape: median-of-medians and frac-positive-median
improve monotonically as forgetting slows, plateauing at 0.9999-1.0 (fred:
median -0.0065 to -0.0034, frac-positive-median 0.13 to 0.23; waveform:
median +0.0007 to +0.0038, frac-positive-median 0.57 to 0.67), while
mean-of-means gets monotonically *more* negative over the same range. No
fragile knife-edge like the homogenization cell model's own weight-decay
tuning earlier this session -- the hardcoded default (0.999) sits close to,
but not quite at, the plateau; `0.9999` would be a marginally better
default with no observed downside.

### The price/garch_leaf arm: both designs fail, cleanly

Neither derived design had been tested against `garch_leaf` as the base --
the domain where a leverage/volatility-clustering correction is most
classically expected to pay off. Both fail, uniformly, on N=30 real
equity/fx/commodity return series:

| | Kalman-grid | garch-grid |
|---|---|---|
| mean of per-series means | -0.0718 | -0.0236 |
| frac series positive mean | 0.00 | 0.00 |
| median of per-series medians | -0.0084 | -0.0472 |
| frac series positive median | 0.07 | 0.07 |
| mean of per-series frac>0 | 0.457 | 0.323 |
| crps delta (mean of means) | -0.00018 | -0.00033 |

Zero of 30 series show a positive mean under either design. The likely
mechanism: `garch_leaf` already fits a GARCH volatility process at the base
level, so its own PIT residuals have little exploitable scale structure
left in them -- both corrections end up modelling noise rather than signal,
and (per the THREEFY9 mechanism below) a correction that reacts to noise
doesn't just fail to help, it actively costs log-score on the resulting
false-positive narrowings.

### THREEFY9, diagnosed

`THREEFY9` (FRED's 9-year Treasury instantaneous forward rate) was the
Kalman-grid's persistent worst-case series at every sample size tried. A
dedicated tick-by-tick investigation found: the series itself is clean (no
gaps, no administered-rate flat stretches, 21 years of daily log-changes,
sd~0.018) and `laplace`'s own raw forecast is already good on it in every
year except one. The damage is half systematic, half episodic: the worst 25
ticks account for about half the total loss, scattered across nearly every
year, and **every year is net-negative except 2020**, where the correction
correctly widened into the COVID Treasury-market dysfunction (+18.75 on
2020-03-10 alone). At the worst ticks, the grid had narrowed predictive
variance to 12%-56% of `laplace`'s own raw variance right before an
idiosyncratic one-day jump (a tariff headline, a taper-tantrum tail) that a
persistence-tuned grid (rho in [0.9, 0.99]) had no way to see coming. A
broader sample shows no net directional bias (the corrected/raw variance
ratio is above and below 1 about equally often) -- but log-score's
asymmetric penalty means the narrowing misses cost far more than the
widening ones save, on a series whose volatility is mostly one-day
idiosyncratic shocks with only one genuine multi-week regime event (COVID)
in 21 years to reward persistence-seeking in return. This is a real,
understood failure mode of the Kalman-grid's specific bet (persistent
regimes), not a data problem or an implementation bug.

### A cleaner design: the homogenization cell model, on real data for the first time

`benchmarks/homogenization/cell_model.py`'s pure z-space design passed its
synthetic gate earlier this session (`RESULTS.md`, verdict "go") but real-
data testing was explicitly staged as a later phase and never done. It's a
scale-mixture pool driven by a fixed-gain, Huber-capped filter on `H_2(z) =
z^2-1` (predictable conditional variance) rather than a Kalman filter on
`log(z^2)` or a `garch` recursion -- cheaper per-candidate (no Gauss-Hermite
quadrature, no exact noise-law convolution) and, per its own tuning note,
already weight-decay-hardened against the "forgets too fast" failure mode
the Kalman-grid's sweep above shows some residual sensitivity to.
`cell_model_on_laplace.py` composes it onto a real base forecaster the same
way `laplace_scale_kalman_grid`/`laplace_scale_garch_grid` do (via
`ZSpaceCorrectedDist`), with no changes to `cell_model.py` itself. Results,
same paired-scoring methodology, same series:

| | fred (n=50) | waveform (n=50) | price/garch_leaf (n=30) |
|---|---|---|---|
| mean of per-series means | **+0.0327** | **+0.0361** | **+0.0028** |
| frac series positive mean | **1.00** | **0.84** | **0.73** |
| median of per-series medians | +0.0012 | **+0.0056** | +0.0007 |
| frac series positive median | 0.56 | **0.78** | 0.63 |
| mean of per-series frac>0 | 0.507 | 0.526 | 0.509 |
| crps delta (mean of means) | +0.00019 | +0.00049 | +0.00001 |
| runtime (50/50/30 series) | 126s | 45s | 124s |

This is a categorically different result from either other design tested
today: **every one of the 50 FRED series has a positive mean log-score
delta** -- not "roughly neutral," a clean win, on the exact arm the
Kalman-grid could only manage a wash on. Waveform is a decisive win by
every metric with no catastrophic-outlier problem (mean-of-means +0.0361,
vs. the Kalman-grid's own -0.0962 on the same arm dragged down by rare
single-series blowups). And on the price/garch_leaf arm -- where both other
designs failed uniformly and hard -- the cell model is the only one to stay
genuinely non-negative: small in magnitude (as expected, since there's
little residual structure left for anything to find once `garch_leaf` has
already modelled the volatility), but real and positive on 73% of series,
not just "does no harm." It also runs faster than the Kalman-grid despite
pooling roughly 2.5x more candidates (25 vs 10), because each candidate's
own filter and mixture-density evaluation are cheap arithmetic rather than
a 7-point quadrature. On every axis that matters -- typical-case win rate,
absence of catastrophic tails, cross-domain generalization, and compute
cost -- this design outperforms both of the exact-noise-law-motivated
designs built earlier in the session.

## Honest verdict

1. The M1/M2 leverage idea (`README.md`) is closed: negative everywhere
   tested, including on actual price/GARCH data.
2. **The homogenization cell model, not the Kalman-grid, is the best design
   found this session, and it is the one to build on.** At proper sample
   sizes (N=50 fred, N=50 waveform, N=30 price/garch_leaf) it wins or is
   genuinely neutral-to-positive on every arm tested, with no
   catastrophic-outlier problem: 100% of FRED series net-positive on mean,
   a clean multi-metric win on waveform with none of the Kalman-grid's rare
   single-series blowups, and the only design of the three to stay
   non-negative on the price/garch_leaf arm where both exact-noise-law
   designs failed uniformly. It is also cheaper per candidate (plain
   arithmetic, no Gauss-Hermite quadrature) despite pooling more of them. It
   was built and synthetic-gated *before* the Kalman-grid work in this
   document but its real-data test was deliberately staged for later and
   never run until this pass -- the delay, not the mechanism, is why it
   wasn't the headline result from the start.
3. The recursive-laplace scale-defect idea, in its Kalman-grid form, is a
   **real but narrower win than it first appeared**: a genuine,
   multi-criterion win on the near-deterministic/cyclic waveform arm (70%
   of series net-positive on median at N=50, CRPS improves on average), but
   only a wash on generic FRED macro data (median of medians -0.0044), a
   clear loss on the price/garch_leaf arm (0% of series net-positive at
   N=30), and a diagnosed, understood failure mode on its own worst-case
   series (`THREEFY9`: a grid tuned to reward persistent multi-week
   volatility regimes narrows ahead of idiosyncratic one-day jumps on a
   series whose vol is almost entirely one-day noise punctuated by exactly
   one real regime event -- COVID -- in 21 years). Grid-resolution ablations
   (26 vs 10 candidates, wide-rho, wide-tau) give at most a small
   improvement on waveform and nothing conclusive on FRED; weight-decay is
   robustly, monotonically better as forgetting slows, with no fragile
   knife-edge, plateauing near 0.9999-1.0 (slightly past the hardcoded
   0.999 default).
4. What's still solid about the Kalman-grid work, independent of its
   real-data ranking: the exact noise-law composition
   (`ConvolvedExactLogChiSq`) is validated and unbiased when fed a correct
   `pi(h)`, and the grid-plus-likelihood-weighting design is the
   theoretically-derived (not guessed), numerically stable way to build
   that `pi(h)` -- it demonstrably fixed the worst failure mode of every
   point-estimate design that came before it in this thread (catastrophic
   overconfident narrowing, single-series worst case -5.76 to -0.43 at
   N=20). The cell model's win over it is a *better bet within the same
   framework* (which variance-persistence hypotheses to hedge across, and
   how cheaply), not evidence the Bayesian-hedging framework itself was
   wrong.
5. The garch-grid variant (skaters' own `garch` transform applied directly
   to the z-stream, hedged the same NFL-safe way) is now the weakest of the
   three real designs at proper scale: it reverses the Kalman-grid's one
   clean win (waveform median of medians flips from +0.0059 to -0.0174) and
   fails on the price arm as hard as the Kalman-grid does. It keeps a
   tamer mean-of-means on both fred and waveform (fewer catastrophic
   single-series blowups) but that turned out to be a weak, sample-size-
   dependent consolation, not a real trade-off worth keeping -- the earlier
   N=5 read that framed it as "wins on mean, loses on median" undersold how
   much worse it is at scale.
6. Broader methodological note that survives regardless of any specific
   mechanism's fate: point-estimating a latent parameter and plugging it
   into an otherwise-exact construction is not the same as Bayesian
   inference, even when every individual piece (the noise law, the
   composition math) is exact. The asymmetric cost of proper scoring rules
   means the *shape* of how uncertainty is estimated matters as much as
   getting any single piece of the pipeline exactly right -- and a properly
   derived, NFL-safe grid-plus-likelihood-weighting design (the same idiom
   this codebase already uses everywhere else) beat every point-estimate
   variant tried, on both the theory and the data. But this round shows the
   idiom alone doesn't determine the winner: *which* hypotheses populate
   the grid and *how cheaply* each is scored are separate, real design
   choices -- the cell model's simpler H_2-filter hypotheses, hedged the
   same way, beat the exact-noise-law machinery's more elaborate ones on
   every arm tested.
7. `laplace_scale_cell_model` has been promoted to a proper `skaters`
   primitive: `skaters.homogenize`, an explicit opt-in wrapper
   (`homogenize(laplace(k=1))`), not a change to `laplace`'s own default
   output. See the "Why this is a wrapper and not the default" note in
   `src/skaters/homogenize.py`'s module docstring for the reasoning
   (narrow-but-real evidence, domain-dependent effect size, a non-`Dist`
   output type, always-on compute cost, and preserving the raw-vs-corrected
   baseline this research trail depends on).
8. Remaining next steps: a finer cell-model candidate grid to see if the
   FRED median-based metrics (currently a small but positive +0.0012, not
   yet the clean sweep the mean-based metrics show) can be pushed further;
   re-running the THREEFY9-style diagnosis on the cell model to see if it
   avoids the Kalman-grid's specific persistence-bet failure mode or just
   fails less often; a blended grid mixing cell-model and Kalman-grid
   hypotheses in one pool; applying the correction at a different point in
   `laplace`'s own transform chain (leaf-level vs. final-output, raised but
   not explored).
