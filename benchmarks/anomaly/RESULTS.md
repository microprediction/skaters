# The Rosenblatt front-end: results log

Working results for the anomaly/front-end study (issues #88, PR branch
`proto/anomaly-mahalanobis`). Thesis under test:

> `laplace` defines a causal bijection on paths (the Rosenblatt transform
> z_t = Phi^-1(F_t(y_t))). In its coordinates, other people's detectors and
> forecasters get better — and our own detection head emits calibrated
> p-values no score-based method can.

All runs: strictly causal scores (no whole-series normalisation), defaults
unless stated, one pass. Protocols in `RESEARCH.md`; harnesses in this
directory. Updated 2026-07-07.

## 1. Detector front-end — FINAL (UCR-60, argmax protocol)

Same detector, same series; only the input changes (raw y vs parade z from
`laplace(3)`). `frontend_run.py`, n = 60 shortest UCR series.

| detector | raw | laplace-fronted | lift |
|---|---|---|---|
| DSPOT (EVT thresholding, KDD 2017) | 6/60 = 0.100 | **31/60 = 0.517** | **5.2x** |
| RRCF (random cut forest, ICML 2016) | 15/60 = 0.250 | **27/60 = 0.450** | **1.8x** |

Reading: DSPOT = weak normaliser + excellent GPD tail head; its stationarity
premise starves on raw waveforms and feasts on z. The front-end gives its
theorem the stream it assumes.

### Full 250 (FINAL 2026-07-09)

| detector | raw | fronted | by length (raw -> z) |
|---|---|---|---|
| DSPOT | 30/250 = 0.120 | **58/250 = 0.232** | <10k: 5->28; 10-50k: 15->22; >=50k: 10->8 |
| RRCF | 61/250 = 0.244 | 59/250 = 0.236 | <10k: 15->25; 10-50k: 32->20; >=50k: 14->14 |

DSPOT's lift survives scale (~2x overall, 5.6x on <10k) but decays with
length; RRCF is a wash overall — 42 series gained, 44 lost, and the flips
are family-structured: z loses the ECG/heartbeat families (ECG2/3/4,
ltstdbs), gains the drift/scale-dominated ones (InternalBleeding, GP711,
respiration, STAFFIII, air temperature). The mechanism is coherent with
the own-head result: the front-end inherits the forecaster's competence.
Where laplace models the stream (drift, scale, slow structure), its z
hands any detector a cleaner exam; on high-frequency waveforms the fixed
calendar grid can't forecast, z is noise-plus-clamp and destroys exactly
the periodic template structure RRCF's shingles exploit on raw data.
The forecaster's periodicity gap is the single root cause across both
studies — fix that and both the own head and the front-end move together.

### Matrix-profile head (DAMP-style left discord) — the strong head says no

`frontend_damp.py` (stumpy.stumpi left profile = DAMP scores without the
pruning; m=100 fixed for both conditions), n = 150 shortest, 2026-07-09:

| head | raw | laplace-fronted |
|---|---|---|
| left-discord matrix profile | **88/150 = 0.587** | 64/150 = 0.427 |

Prediction confirmed: the front-end HURTS a structural similarity-search
head. Matrix profile z-normalizes every subsequence internally (it has its
own local normalizer) and feeds on repeated templates — z whitens exactly
that structure. Raw DAMP at 0.587 with one fixed window also confirms the
harness: it lands in the published good-classical band on this subset.

Sweet-spot synthesis across the three heads: the front-end lifts
DISTRIBUTIONAL heads (DSPOT: assumes stationarity, gets it, 2-5x), is a
wash for a WEAK-STRUCTURAL head (RRCF), and hurts a STRONG-STRUCTURAL head
(DAMP). We add value where the alarm decision needs a calibrated,
stationarised stream — not where detection is subsequence similarity
search. Position accordingly: the differentiator is job 2 (when to alarm),
not job 1 (where is the anomaly).

## 2. Forecaster front-end — FINAL (FRED-30, exact change of variables)

One-step log-likelihood in y-space; z-space scores mapped back through the
exact Jacobian log f_t(y_t) - log phi(z_t). Per-tick losses clamped to
[-20, 20] for every method symmetrically (bounded loss; one degenerate
predictive must not own a series mean). `frontend_loglik.py`, n = 30 FRED
series, rolling refit every 200 on trailing 1000.

| opponent | raw | fronted | mean lift | median | wins |
|---|---|---|---|---|---|
| ETS (statsmodels Holt, damped) | 1.642 | 3.680 | **+2.04** | +0.79 | **30/30** |
| AutoARIMA (statsforecast) | 1.646 | 3.719 | **+2.07** | +0.76 | **30/30** |
| GARCH(1,1) (arch) | 1.732 | 3.703 | **+1.97** | +0.77 | **30/30** |
| Prophet (real calendar dates) | 1.636 | 3.702 | **+2.07** | **+0.85** | **30/30** |
| EWMA-Gauss (control head) | 2.243 | 3.795 | +1.55 | +0.51 | 29/30 |
| *laplace alone (reference)* | | *3.674* | | | |

Bijection prediction verified: fronted opponents converge to laplace + eps
(AutoARIMA adds +0.045 nats over laplace alone — laplace had already
extracted ~98% of the structure ARIMA can model). The control head on z
reproduces laplace's own score, confirming the Jacobian accounting.

Prophet is the sharpest row: its calendar machinery (weekday/yearly from
real dates — structure laplace's integer-lag seasonal block cannot
represent) earns the largest median lift when fronted, yet adds only
+0.03 nats over laplace alone: even the calendar model finds almost
nothing left in the residuals. FINAL: five opponents, 149/150 wins.

## 3. Own head on UCR (argmax, their home turf)

`ucr_run.py`. Scorers: mah (Mahalanobis p-value, single tick), mahS (scan,
windowed mean of -log10 p, w in {8,64}), z1 (per-horizon 1-step |z|,
ablation), zU (union min-p), mz (trivial EWMA z-score control).

| config | subset | best scorer | accuracy |
|---|---|---|---|
| defaults (sa 0.03 / da 0.02) | n=40 shortest | z1 | 0.650 |
| slow memory (sa 0.01 / da 0.005) | n=40 shortest | **mahS** | **0.675** |
| slow memory | n=60 shortest | mahS | 0.583 |
| defaults | full 250 | z1 | 0.276 |
| slow memory | full 250 | mahS | 0.304 — FINAL |
| search() engine (adaptive periods) | n=100 | z1 | 0.390 — worse; dropped |
| zbank sigma-grid | n=60 | z1 / mahS | 0.550 / 0.533 — no lift over slow laplace |
| trivial control (mz) | n=60 / full 250 | | 0.283 / 0.216 |

FINAL full-250 read (2026-07-08): the n=60 story does not survive scale.
By length bucket, slow-mem mahS hits 32/53 (<10k), 32/97 (10-50k), 12/100
(>=50k); defaults z1 collapses the same way (14/100 on >=50k). The bleed is
concentrated in the long high-frequency waveform families (ECG, gait,
power demand), whose periods the fixed calendar grid cannot represent —
consistent with the search() finding that periodicity discovery, not
memory, is the missing ingredient there. Union of the two configs' best
scorers reaches 95/250 = 0.38 (oracle ceiling on this axis: parameter
diversity buys real coverage). Own head sits at the top of the trivial
band, well under good classical (0.50-0.60); the UCR credibility row
should quote the n<=50k subset (64/150 = 0.43) alongside the full-archive 0.304.

Context bands (full 250, published): trivial 0.30-0.40; good single classical
methods 0.50-0.60; DAMP/matrix-profile 0.65-0.75; 2021 contest ensembles
0.70-0.80. Long ECG/periodic blocks are where we bleed; slow memory makes the
multivariate scan clearly beat the per-horizon rule at scale (65 vs 52 at
158/250). UCR is the credibility row, not the differentiator: argmax scoring
is blind to calibration by construction.

Findings that came out of this study regardless of scores:
- horizon-misalignment bug in `search()` candidate scoring (third instance
  of the pattern; fixed, parity regenerated);
- effective-rank collapse of the z scatter -> empirical null (Satterthwaite)
  + factor scatter with exact Sherman-Morrison/Woodbury inverse;
- masking through the null's second moment -> winsorised null updates;
- the sigma-memory axis (user hypothesis) lifts mahS by +6/40 on the subset.

## 4. FRED injection (argmax) — protocol needs v2

`fred_anomaly.py`, n=100 real FRED change series, planted spike/burst/shift.
Interim (~73/100): everyone weak (~0.14 best), orderings inside binomial
noise. Diagnosis: real backgrounds contain genuine unlabeled anomalies
(2008, COVID); argmax scores "which real crisis did you prefer", a
confounded measure. v2: score the planted window's rank percentile in the
full score ordering (robust to dominant natural events), and/or mask known
crisis windows. Keep argmax row for reference.

## 5. Calibration panel — FRED home field (FINAL 2026-07-09)

`calibration_panel_fred.py`: empirical false-alarm rate vs nominal alpha,
strictly prequential, 379 non-price FRED change series (1.02M ticks after
burn-in), forecasting defaults. Median per-series rate / fraction of series
within [alpha/2, 2*alpha]:

| method | @1e-2 | @1e-3 | @1e-4 |
|---|---|---|---|
| mah | 2.7e-2 / 8% | 1.1e-2 / 1% | 5.9e-3 / 0% |
| z1 | 2.3e-2 / 31% | 8.3e-3 / 5% | 3.7e-3 / 0% |
| dspot (raw) | 1.6e-2 / 37% | **2.3e-3 / 24%** | 6.3e-4 / 0% |
| mz | 2.2e-2 / 27% | 8.7e-3 / 4% | 4.6e-3 / 0% |
| dspot_z | 2.1e-2 / 40% | **2.5e-3 / 22%** | **4.6e-4** / 0% |
| mz_z | **1.8e-2 / 55%** | 6.0e-3 / 6% | 2.6e-3 / 0% |

The home-field run does NOT vindicate the current head. Medians are
crisis-robust, so this is genuine miscalibration, not 2008/COVID: the
parade z is calibrated in the bulk (the coverage study's 90% interval) but its
1e-3 tail fires ~8x nominal — the predictive tails are too thin at 3+
sigma — and the Mahalanobis empirical-null machinery amplifies (11x) rather
than repairs it. The pattern across methods is the finding: z-fronting wins
the bulk (mz_z best at 1e-2), the GPD tail wins the deep tail (dspot/dspot_z
best at 1e-3/1e-4, ~2.3-4.6x), and nobody holds its stated rate at 1e-4. Conclusion:
calibrated alarms need BOTH halves — the forecaster to manufacture
stationarity, EVT to convert the tail. The concrete ticket: a GPD/POT tail
head on the parade z (the planned `pickands`/`siffer`), replacing erfc and
the chi-square null for |z| beyond ~2.5.

### The repair, measured (zgpd, same run, FINAL 2026-07-09)

`skaters.anomaly.gpdtail`: POT/GPD tails on the parade z (per-tail
thresholds at the 98% quantile, method-of-moments fit over the last 1000
exceedances, consistent exceedance rate, two-sided p). Same 379 series:

| method | @1e-2 | @1e-3 | @1e-4 |
|---|---|---|---|
| **zgpd** | **9.8e-3 / 85%** | **1.4e-3 / 50%** | **2.9e-4 / 0%** |
| best other (dspot) | 1.6e-2 / 37% | 2.3e-3 / 24% | 6.3e-4 / 0% |

At 1e-2 the promise is kept essentially exactly. At 1e-3 the median is
1.4x nominal with half the universe inside the 2x band — and the residual
overshoot is bounded below by the genuine-anomaly base rate: ~300 true
crisis ticks per 1M would add 3e-4 to every rate, negligible at 1e-2,
dominant at 1e-4. So the deep-tail read (2.9e-4 at nominal 1e-4) is
consistent with a calibrated detector on data that genuinely contains
anomalies — unfalsifiable to push further without labels. Synthetic
(regime-switching, no anomalies): 1.0e-2 / 1.1e-3 / 1.8e-4, at nominal at
all three. The z-clamp (|z|<=7.03) truncates exceedances; p-values below
~1e-6 remain out of reach until the clamp is lifted for the tail head.

Verdict: forecaster-manufactured stationarity + EVT tail = the first
method in the table that keeps its stated alarm budget. Next: censored-ML
fit (the proper-score twin of this head — CSL scoring), lift the z-clamp
for exceedances, UCR waveform column for the scope statement.

## 6. The conditional tail fit (FINAL 2026-07-09)

`tail_splice_study.py`: skater (i) = laplace defines a predictable tail
region (parade z beyond frozen warmup-quantile thresholds); a trailing
tail skater models the exceedances; the spliced density is scored
prequentially against plain laplace on 370 non-price FRED series.
Decoupling rules for propriety: region frozen and exogenous to the
evaluee, skater (i) never tuned on downstream scores, no feedback into
the body, score-before-update, binary exceedance term always charged.

| tail | overall LL (median, wins) | per tail tick | CSL |
|---|---|---|---|
| GPD splice, MoM | +0.0199, 339/370 | +0.688 | +0.0199 |
| GPD splice, censored ML | **+0.0219, 356/370** | **+0.840** | **+0.0219** |

Censored ML beats MoM on 238/370 (median +0.0009 CSL) — a modest but
consistent edge, and principled: the head is then fitted by the same
proper score it is judged by. The headline: repairing the Gaussian z
tail is worth ~+0.02 nats/tick on the WHOLE likelihood (96% of series
win) and +0.84 nats per tail tick — the single largest free improvement
measured on this branch. Implication: this belongs in the library as a
predictive-tail option (splice at the leaf in z-space, conjugation
carries it everywhere: density, CRPS, VaR, and calibrated tail PITs at the
source — which would make erfc-on-z calibrated and gpdtail a consumer
of an already-corrected stream). Cost: the JS twin (1e-6 parity) must
implement the splice too.

## 7. Shipped: GPD tails default-on (0.13.0, 2026-07-09)

`skaters.tails.gpdtails` now sits between the body and the parade in
`laplace` (both languages; `tails="gaussian"` opts out). Acceptance on 85
non-price FRED series, new default vs old, same series, prequential:
median dLL +0.0271 nats/tick (84/85 wins); erfc-on-parade-z empirical rate
at nominal 1e-2: 2.4e-2 -> 1.05e-2; at 1e-3: 8.4e-3 -> 1.38e-3. The z
stream the anomaly skill documents now delivers approximately its stated
rates.
Parity 105,658 values across 54 scenarios incl. a splice-active scenario.

UCR fronted calibration panel (full 250, for the record): fronting DSPOT
moves its deep-tail rate toward nominal on waveforms too (1e-3: 4.6e-3 raw ->
2.9e-3 fronted; 1e-4: 1.6e-3 -> 6.0e-4), but at 1e-3 every method still
drowns in false alarms on the periodic families — waveforms remain out of
scope (section 3; skaters#91).

### Hardening + full acceptance (same day)

Three review gaps fixed: the exceedance rate now FORGETS (EWMA of the
exceedance indicator, rate_alpha=0.002 — cumulative zeta would never
re-calibrate after a regime shift against the frozen thresholds, and the
adapting rate is also what makes frozen thresholds safe); intake is
winsorised at the fitted 1-in-1000 excess with a changepoint escape after
10 consecutive caps (the DSPOT masking failure, not inherited); and
SplicedDist round-trips through Dist.from_dict in both languages
(checkpoint-restore). Acceptance v2, 59 non-price FRED series, new vs
tails="gaussian":

|  | k=1 | k=3 (horizon 3) |
|---|---|---|
| dLL median | +0.0293 (58/59) | +0.0271 (58/59) |
| z@1e-3 | 9.4e-3 -> 1.7e-3 | 9.0e-3 -> 1.4e-3 |
| CRPS | wash (median -7e-6, ~0.07%) | |
| pinball@5% | wash (5% is interior; splice starts ~2%) | |

The multi-step story holds: the splice fixes horizon-3 tails as well as
one-step. CRPS — the default leaf objective — is untouched to within
noise, disclosed as a tiny negative median. Downside benefit lives beyond
the ~2% boundary; pinball at 1% or 0.5% is where to look for it.

## 8. Post-ship panel recheck (87 series, new default, 2026-07-09)

With the splice in the forecaster, the panel harness confirms the product
claim end-to-end: **plain erfc on state["z"] now keeps its stated rate**
— median 1.0e-2 at nominal 1e-2 (89% of series in the 2x band), 1.3e-3 at
1e-3 (59% in band). Two negative findings with design consequences:

* **mah did NOT heal** (median 9.2e-3 at 1e-3, unchanged ~9x): the
  Mahalanobis layer's overconfidence is its own defect — the
  Satterthwaite empirical null / EWMA scatter machinery — not inherited
  from the thin z tails. Its repair is a separate ticket in anomaly.py;
  until then the multivariate geometry is for RANKING (argmax), not for
  calibrated alarming.
* **Do not stack gpdtail on the new laplace** (double splice): median is
  fine but a few series blow up (thin exceedances of already-corrected z fit
  near-degenerate GPDs), dragging pooled rates above nominal. With
  tails="gpd" (the default), threshold erfc(|z|/sqrt2) directly; the
  gpdtail head remains useful only over gaussian-tail bodies.

## 9. Price series and the downside (2026-07-09, autonomous session)

Price acceptance (109 equity/fx/commodity change series): the splice
carries over — dLL +0.0176 (107/109), z@1e-3 7.4e-3 -> 1.33e-3. The
four-cell stack study answers "does the vol-dynamics leaf stack with the
tail-shape fix":

| cell | median LL |
|---|---|
| plain, gaussian tails | +3.0242 |
| **plain, gpd tails (the default)** | **+3.0537** |
| garch leaf, gaussian | +3.0327 |
| garch leaf, gpd | +3.0308 |

They do NOT stack: garch_gpd - garch_gauss = -0.0006, and garch_gpd loses
to plain_gpd on 85/109 (median -0.0130). The leaf's conditional variance
and the splice compete for the same signal (vol clustering explains much
of what reads as tail mass), and the splice wins. The new DEFAULT is the
best within-library configuration measured on price series — the garch
leaf advice should be retired pending a rematch vs a true GARCH-t
opponent (arch), which this does not replace.

Downside quantiles (59 non-price series): pinball@1% is a wash (-0.10%
median, 28/59), pinball@0.5% modestly better (+1.01%, 38/59). The
splice's value is density height at extreme ticks (log-lik) and alarm
calibration — tail QUANTILE location moves only slightly. Report it that
way; do not oversell the VaR angle.

## 10. Tail coverage: the 99.9% interval that is actually 99.9%

`benchmarks/tail_coverage.py`, 142 non-price series, median empirical
central coverage, prequential:

| nominal | gaussian tails | gpd tails (default) |
|---|---|---|
| 90% | 89.17% | 90.08% |
| 99% | 97.62% | **98.93%** |
| 99.9% | 99.13% | **99.85%** |

The gaussian 99.9% interval breaches 8.7x its budget; the spliced one is
within 0.05 points of nominal. This extends the coverage study's claim
from the bulk to the deep tail and is the one-sentence public version of
the whole 0.13.0 feature.

## 11. Still to come

- slow-alpha full-250 (running); zbank-60 and default-250 (running,
  detached).
- FRED v2 with rank-percentile scoring.
- The calibration panel — empirical false-alarm rate vs nominal alpha,
  prequential protocol, detection delay; the verified literature gap
  (RESEARCH.md section 2) and the method's actual differentiator.
- GPD/EVT tail for the detector's extreme p-values (steal DSPOT's tail
  theorem for our head); unclamped -logpdf surprise channel (the z-clamp
  saturates at |z|=7.03, erasing 20-sigma vs 100-sigma distinctions).
- TSB-AD-U leaderboard run (VUS-PR; top is 0.42, simple methods lead).

## Reproduce

```
python benchmarks/anomaly/ucr_run.py --limit 60 --workers 8 [--scale-alpha 0.01 --det-alpha 0.005 | --base zbank]
python benchmarks/anomaly/frontend_run.py --limit 60 --workers 4
python benchmarks/anomaly/frontend_loglik.py --limit 30 --workers 3
python benchmarks/anomaly/fred_anomaly.py --limit 100 --workers 4
```
UCR data: see RESEARCH.md (download + extract into `data/UCR_Anomaly_FullData`).
FRED data: cached under `benchmarks/data/` (see `benchmarks/fred.py`).
