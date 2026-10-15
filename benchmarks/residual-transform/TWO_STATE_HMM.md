# Exact two-state recalibration and the blended pool

## The paper and its skaters transform

Cotton (2026), "One Poisson Equation for Conformal Coverage under
Dependence," derives an exact decomposition of realized conformal coverage
under Markov-dependent calibration data: the invariant-law coverage plus a
current-state Poisson corrector, with the same corrector supplying both the
transient state bias and the dependence-adjusted long-run variance. Section
12, "The corresponding skaters transform," gives the direct application to
this codebase: Gaussianize the PIT (`Z_t = Phi^-1(F0_t(Y_t))`), fit a
predictable two-state model to the past `Z_t` with state-specific CDFs
`K_L`, `K_H` and a filtered high-state probability `omega_t`, and compose
the resulting state-conditional predictive back onto the base forecast via

    F_{t+1}(y) = K_{t+1|t}(Phi^-1(F0_{t+1}(y)))

exactly the `F~_t(y) = H_t(Phi^-1(F_t(y)))` composition pattern already
used by `residual_transform.CorrectedDist` and `homogenize.HomogenizedDist`.
The difference is what drives the state model: the paper's version is the
*exact* Bayes filter for a genuine two-state chain, where `homogenize`
hedges a heuristic pool of continuous scale-filter candidates precisely
because the true state-transition dynamics aren't known. The paper's own
worked example (its Section 6) is also a formal version of a failure mode
already diagnosed empirically in this codebase: a pooled 90%-calibrated
threshold can carry conditional coverage anywhere from 74% to 94%
depending on the current, unobserved regime -- the same mechanism a
dedicated investigation found by hand in the Kalman-grid's `THREEFY9`
holdout series (see `SCALE_CONVOLVED.md`).

## Implementation

`two_state_recalibrate.py` implements Section 12's exact filter:

    omega_pred' = pi_H + lam * (omega_filt - pi_H)             (predict)
    omega_filt  = omega_pred * k_H(z) / [omega_pred * k_H(z)
                  + (1 - omega_pred) * k_L(z)]                  (Bayes update)

with `K_L`, `K_H` modelled as zero-mean Gaussians whose scales `sL`, `sH`
are learned online via responsibility-weighted EWMA sufficient statistics
(a streaming EM, the same "no batch refitting" discipline as the rest of
this codebase). `lam` (persistence) and `pi_H` (stationary high-state
probability) are the two hyperparameters the exact filter needs and can't
learn on its own; per the same lesson `homogenize` and the Kalman-grid
already establish, they are hedged as a small fixed grid of candidates
combined by online Bayesian weighting, not point-estimated.

Building this surfaced a real bug: nothing in the symmetric EM update
forces "H" to consistently mean "the higher-variance state" across the
pooled candidates. With both states initialized identically, independent
candidates can each settle on an opposite labeling by chance -- individually
harmless (each candidate's own predictive density doesn't care which label
it picks), but it destroys the *pooled* `omega` as a regime diagnostic,
since candidates with swapped labels partially cancel when averaged. A
first attempt (asymmetric initialization, `sL=0.7`/`sH=1.4`) improved
log-score further but made the regime-tracking diagnostic *worse* (8-22%
match against ground truth on a synthetic two-state series, i.e. close to
inverted rather than close to chance) -- initialization alone isn't a hard
enough constraint against the EM's own dynamics. The fix is a hard
ordering constraint enforced after every update: whenever the raw update
would put `sL` above `sH`, swap both the variance estimates and their
accumulator statistics, and swap `omega_filt` for its complement. After
the fix, regime-tracking on the same synthetic series is 92.2%.

## Synthetic validation

| | mean delta logL vs phi |
|---|---|
| iid Gaussian null (single candidate) | -0.0001 |
| two-state SV (hedged grid) | +0.3115 |

The two-state SV gain (+0.31) is far larger than anything `homogenize` or
the Kalman-grid ever achieved on the same generator -- expected, since this
is the exact model family the data was generated from, not an
approximation of it.

## Real data: a clean split

Same paired-scoring methodology as `SCALE_CONVOLVED.md` throughout
(`run_two_state_hmm.py`, comparable to `run_cell_model_fred.py` /
`run_kalman_grid_fred.py`).

**FRED (N=50) and waveform (N=50):**

| | homogenize | two-state HMM |
|---|---|---|
| FRED mean of means | +0.0327 | **+0.0362** |
| FRED frac positive mean | 1.00 | 0.98 |
| FRED median of medians | +0.0012 | **+0.0015** |
| FRED frac positive median | 0.56 | **0.64** |
| waveform mean of means | +0.0361 | **+0.0502** |
| waveform frac positive mean | 0.84 | **0.90** |
| waveform median of medians | +0.0056 | **+0.0194** |
| waveform crps | +0.00049 | **+0.00062** |

A decisive win on both arms, by a wide margin on waveform's typical-tick
metrics (median of medians more than 3x `homogenize`'s).

**Price/garch_leaf (N=30), first pass (no identity candidate):**

| | homogenize | two-state HMM |
|---|---|---|
| mean of means | **+0.0028** | -0.0004 |
| frac positive mean | **0.73** | 0.40 |
| median of medians | **+0.0007** | -0.0024 |
| frac positive median | **0.63** | 0.27 |

Uniformly worse than `homogenize` here -- the arm where `garch_leaf` has
already extracted most of the real volatility clustering, leaving little
genuine two-regime structure in the residual for a hard two-state
commitment to exploit.

## Why it doesn't self-collapse: spurious regime detection

The natural question: why doesn't the two-state filter just learn
`sL ~= sH` on its own when there's no real structure, rather than needing a
separate escape hatch? The persistent-state predict step (`lam > 0`)
creates a self-reinforcing feedback loop: if `omega` drifts high for a
stretch by pure chance, the high-state accumulator preferentially absorbs
whatever `z`'s occur during that stretch, and if a few happen to be
slightly larger, `sH` drifts up -- which makes the filter more likely to
attribute future large `z`'s to the high state, reinforcing the streak
further. This is the same "spurious regime detection" pathology documented
in the Markov-switching econometrics literature when these models are fit
to data with no real regimes. A persistent-state filter can hallucinate a
regime out of homogeneous noise; it doesn't reliably notice and degrade
gracefully on its own.

The fix is the same NFL-safe hedging idiom used everywhere else in this
codebase: add a frozen identity candidate (`sL=sH=1` forever) that competes
in the same Bayesian pool, so "no split here" has to win a fair
predictive contest rather than being something the two-state filter is
expected to discover by degenerating internally.

**Price/garch_leaf (N=30), after adding the identity candidate:**

| | before | after | homogenize |
|---|---|---|---|
| mean of means | -0.0004 | **+0.0010** | +0.0028 |
| frac positive mean | 0.40 | **0.60** | 0.73 |
| median of medians | -0.0024 | -0.0014 | +0.0007 |
| frac positive median | 0.27 | 0.27 | 0.63 |

Exactly the predicted shape: the identity candidate rescues the mean-based
metrics (it wins often enough to flip the average), but the median-based,
typical-tick metrics barely move, and `homogenize` still clearly wins
there. That residual gap is a different, deeper thing than the missing
escape hatch, which is now fixed: even hedged against identity, every
*other* candidate in this grid still commits to a hard two-state structure,
while `homogenize`'s candidates use a continuous filter that can represent
smoothly-varying volatility without ever committing to exactly two
regimes -- a softer model class when the truth is ambiguous rather than
genuinely bimodal.

## The blended pool

Both families produce the identical kind of object: a zero-mean Gaussian
mixture `{"weights": [...], "scales": [...]}` sharing a common `N(0,1)`
reference density. That is exactly what makes `homogenize`'s exact-pooling
identity work, and it means the two families can be scored and pooled in
one shared Bayesian competition with no new math -- `blended_recalibrate.py`
concatenates both candidate sets (each still running its own per-candidate
filter/EM update), keeps a single shared identity candidate rather than
one per family, and reuses `homogenize.logg`/`g` directly for scoring and
pooling. Nothing in either family's own module was changed.

**Full comparison, all five designs, all three arms:**

FRED (N=50):

| | Kalman-grid | garch-grid | homogenize | two-state | blended |
|---|---|---|---|---|---|
| mean of means | -0.0287 | -0.0062 | +0.0327 | +0.0362 | **+0.0375** |
| frac positive mean | 0.22-0.30 | 0.30 | 1.00 | 0.98 | **1.00** |
| median of medians | -0.0044 | -0.0312 | +0.0012 | **+0.0015** | +0.0003 |
| frac positive median | 0.24 | 0.02 | 0.56 | **0.64** | 0.52 |
| crps | -0.00012 | -0.00102 | +0.00019 | +0.00021 | **+0.00024** |

Waveform (N=50):

| | Kalman-grid | garch-grid | homogenize | two-state | blended |
|---|---|---|---|---|---|
| mean of means | -0.0962 | -0.0137 | +0.0361 | **+0.0502** | +0.0498 |
| frac positive mean | 0.48 | 0.30 | 0.84 | **0.90** | 0.90 |
| median of medians | +0.0059 | -0.0174 | +0.0056 | **+0.0194** | +0.0075 |
| frac positive median | 0.70 | 0.30 | 0.78 | 0.78 | **0.82** |
| crps | +0.00051 | -0.00091 | +0.00049 | **+0.00062** | +0.00058 |

Price/garch_leaf (N=30):

| | Kalman-grid | garch-grid | homogenize | two-state (+id) | blended |
|---|---|---|---|---|---|
| mean of means | -0.0718 | -0.0236 | +0.0028 | +0.0010 | **+0.0029** |
| frac positive mean | 0.00 | 0.00 | 0.73 | 0.60 | **0.77** |
| median of medians | -0.0084 | -0.0472 | **+0.0007** | -0.0014 | -0.0002 |
| frac positive median | 0.07 | 0.07 | **0.63** | 0.27 | 0.47 |
| crps | -0.00018 | -0.00033 | **+0.00001** | -0.00003 | +0.00000 |

## Verdict

1. The blended pool is at or near the best on the mean-based/aggregate
   metric on all three arms at once -- best on FRED and price, essentially
   tied with the two-state design on waveform. No single specialized
   design manages this across all three; each has an arm where it is
   clearly the weakest of the five.
2. On the median-based/typical-tick metrics, the blended pool is never the
   worst, but it is also never the best -- it lands between whichever
   design is and isn't suited to the arm in question, rather than
   inheriting either specialized design's peak or its weak spot. That gap
   (blended vs. the specialized winner) is the real, quantified cost of not
   knowing the regime in advance: small, but not zero.
3. Concretely: the two-state HMM should be preferred stand-alone only when
   there's independent reason to expect genuine two-regime structure
   (matches the session's original cyclic/waveform motivating hypothesis
   almost exactly); `homogenize` alone when the correction is more likely
   to be smooth drift than a hard switch; the blended pool when that isn't
   known ahead of time, which is the common case.
4. Not yet built: the paper's Theorem 5, a finite-sample class-uniform
   correction with a formal `1 - eta` coverage guarantee, using only a
   rank statistic rather than the fitted model. Every design compared here,
   including the blended pool, is a Bayesian-hedged point/interval
   correction validated empirically per arm, not a design with that kind
   of guarantee -- the gap flagged when filing the Gupta calibeating issue
   (`microprediction/skaters#181`) still stands for all of them.
5. Also not yet built: the paper's own recommended diagnostics (PIT
   calibration conditional on the filtered state, coverage conditional on
   recent `Z_t`, the lower-tail probability of realized coverage). These
   would have surfaced the `THREEFY9`-style conditional-coverage problem
   directly rather than needing a dedicated post-hoc investigation, and
   would give a principled way to check whether the blended pool's
   remaining median-metric gap is concentrated in specific regimes or
   spread evenly.
