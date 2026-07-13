# When to alarm: tails that keep their stated rates

*The findings and rationale behind skaters 0.13.0 (the conditional tail
fit), the calibration panel that motivated it, and the negative results
that scope it. Working log with full tables:
`benchmarks/anomaly/RESULTS.md`; literature survey:
`benchmarks/anomaly/RESEARCH.md`; annotated bibliography:
[the literature map](https://skaters.microprediction.org/anomaly-literature.html).
All numbers are strictly prequential: no whole-series statistics, no
oracle thresholds, score-before-update everywhere.*

## 1. Two jobs wearing one name

Streaming anomaly detection is two problems. **Job 1, where is the
anomaly,** is subsequence search and ranking. It is well occupied:
matrix-profile methods dominate UCR-style discord tasks (our fixed-window
DAMP replication scores 0.587 raw), and the modern leaderboard tops are
simple statistical methods. **Job 2, when to alarm,** is threshold
selection with a false-alarm rate you can state in advance and verify
afterwards.

A verified forward-citation sweep (2026-07) found this seat effectively
empty. Three academic lines circle it, in mutual isolation:
weighted conformal (W1-ACAS, ICLR 2026), conformal + online FDR
(Rebjock et al., C-PP-COAD, e-LOND/e-GAI), and e-processes (e-detectors,
PITMonitor). None cites SPOT/DSPOT, telemanom, or each other, and every
formal guarantee assumes i.i.d. or exchangeable inputs that drifting,
seasonal streams violate.

Benchmarks are no help: VUS/AUC metrics are
invariant to monotone score transforms (calibration is unmeasurable by
construction) and TAB sweeps thresholds and reports the best, which is an
oracle, not an alarm rule.

The pivotal observation: **manufacturing near-i.i.d. PITs from a
nonstationary stream is a forecasting problem.** The parade state of an
online forecaster (each arriving point resolved against the prediction
made *for it*) is exactly the input the entire calibrated-alarm
literature assumes and cannot create. That is the seam skaters lives on.

## 2. The calibration panel: re-running their benchmarks for calibration

Since no benchmark measures whether stated false-alarm rates come true,
we built the protocol on
the field's own data. The UCR Anomaly Archive certifies each series'
prefix anomaly-free, about 5M labeled-normal points; the FRED cache supplies
the economic universe skaters actually claims. Per series, prequentially:
count alarms at nominal alpha in {1e-2, 1e-3, 1e-4} on clean stretches
(calibrated means empirical ~ nominal), and detection delay at fixed
alpha on the labeled anomalies. `benchmarks/anomaly/calibration_panel*.py`.

The panel's first finding embarrassed everyone, including us. On home
field (379 non-price FRED series, median per-series rates): the parade z
under a Gaussian read fired **8x its promised rate at nominal 1e-3**; the
Mahalanobis detector head amplified that to 11x; DSPOT, the 2017 EVT
incumbent, was closest at 2.3x.

The pattern across methods was the diagnosis: z-fronted heads won the bulk (1e-2), GPD-tailed heads won the
deep tail. The parade z is calibrated in the bulk (the coverage study's 90%
interval) and too thin beyond ~3 sigma; extreme value theory exists for
precisely this failure.

## 3. Tail-weighted likelihood, done properly

"Fix the tails" invites a trap. The naive tail-weighted log score
w(y)·log f(y) (Amisano–Giacomini) is **improper**: a forecaster wins by
inflating the weighted region (Gneiting–Ranjan 2011).

The consistent version is the **censored likelihood score**
(Diks–Panchenko–van Dijk 2011): inside the region score log f(y) in full; outside, score only
log P(not region). That is the likelihood of a censored sample. Its price
is forced by a theorem: no proper score depends on tail shape alone
(Brehmer–Strokorb 2019); every consistent tail claim also pays for the
probability of *reaching* the tail.

This yields a two-skater construction that is proper by design. Skater
(i), the body, defines a **predictable tail region**: its own parade z
beyond thresholds frozen at warm-up quantiles, set before each
observation arrives. Skater (ii) trails, modelling only the exceedances,
fitted by censored ML, which factorizes exactly into the empirical
exceedance rate (the binary term) plus the conditional GPD density (the
Grimshaw profile). Propriety rests on decoupling rules, all enforced by
construction:

- the region is **predictable** (frozen before the data it judges) and
  **exogenous to the evaluee** (the body is fitted by its own ordinary
  likelihood, never on downstream tail scores);
- **no feedback**: the body's updates never see the tail's opinion, so z
  keeps its meaning and the conditional fit keeps its "given the body's
  forecast" reading;
- the **binary term is always charged**: no contestant may reshape a
  tail while lying about its mass;
- region-weighted *evaluation* (CSL league tables) uses a reference
  region common to all contestants, in the harness, never self-defined.

One subtlety worth recording: once the spliced object is evaluated by
plain log-likelihood, no region argument is needed at all: the log score
is proper for any density however assembled. The independence
requirement lives in region-weighted scoring protocols, not in the
model's internal structure. Packaging both skaters in one box couples
nothing, provided the information flow stays body → region → tail →
output.

## 4. The conditional tail fit, shipped (0.13.0)

The study preceded the feature: on 370 non-price FRED series the spliced
density beat plain laplace on **whole** held-out log-likelihood on 96% of
series (+0.022 nats/tick; +0.84 nats per tail tick), and censored ML beat
method-of-moments consistently. So it shipped, default-on, in both
languages (`skaters/tails.py`, `tails.mjs`; `tails="gaussian"` opts out),
spliced **between the body and the parade** so the correction propagates
everywhere at once: logpdf, cdf, quantile, CRPS, and `state["z"]`.

Hardening, each a review finding: the exceedance rate is an EWMA
(`rate_alpha=0.002`); a cumulative rate would never re-calibrate after a
regime shift against the frozen thresholds, and the forgetting rate is
also what makes frozen thresholds safe; intake is winsorised at the
fitted 1-in-1000 excess with a changepoint escape after 10 consecutive
caps (DSPOT's documented masking failure, not inherited); spliced
predictives round-trip through `Dist.from_dict`.

Cost: ~5% runtime,
~1e-6 JS parity maintained (105,658 values, 54 scenarios, including a
splice-active scenario).

Acceptance, all prequential, new default vs `tails="gaussian"`:

| measurement | result |
|---|---|
| held-out LL, k=1 (85 non-price series) | **+0.029 nats/tick, 84/85 wins** |
| held-out LL, k=3 horizon 3 | **+0.027 nats/tick, 58/59** |
| erfc-on-z alarm rate @ nominal 1e-3 | 8.4e-3 → **1.4e-3** (both horizons; residue ≈ genuine-anomaly base rate) |
| price series (109) | +0.018 nats/tick, 107/109; z alarm rates likewise |
| central interval coverage (142 series) | 90%: 89.17→**90.08**; 99%: 97.62→**98.93**; 99.9%: 99.13→**99.85** |
| CRPS (the default leaf objective) | wash (median −0.07%) |
| pinball @5% / @1% / @0.5% | wash / wash / +1.0% |

The one-sentence public version: **the 99.9% interval is actually
99.9%**. The Gaussian read breached its budget 8.7x. And the operator's
question now has a direct answer: an alarm budget converts as "alarm when
`erfc(|z|/√2) < alpha`", and the panel measures that the stated rate
comes true.

## 5. The negative results that scope the claim

These are load-bearing; the claim is credible because they are recorded.

- **The Mahalanobis head did not heal** on the corrected z (~9x at 1e-3
  unchanged): its overconfidence is the empirical-null machinery's own
  defect. Until repaired it is a ranking head, not an alarm head.
- **Do not stack the `gpdtail` head on the new default.** A second
  splice fits near-degenerate GPDs to the thin exceedances of
  already-corrected z and over-alarms on some series. Measured; documented
  in the head's docstring.
- **The GARCH leaf and the splice do not stack on price series.** The
  splice alone is the best within-library price configuration
  (plain-gpd beats garch-gpd on 85/109); conditional variance and
  unconditional tail shape compete for the same signal. The rematch
  against a true GARCH-t opponent under the new default is unplayed.
- **Waveforms are out of scope, and self-diagnosingly so.** On UCR's
  near-deterministic periodic families (ECG, gait) every method exceeds
  its stated alarm rate and the own head ranks at the top of the trivial
  band: that regime is template matching's game (DAMP raw 0.587;
  fronting it with z *hurts*, 0.427). The PIT histogram is the regime
  detector: flat means the calibration claims hold; U-shaped means
  switch primitive or scope out (skaters#91).
- **Quantile location moves little.** The splice buys density height at
  extreme ticks and alarm calibration, not VaR accuracy; pinball gains
  are modest and confined beyond the ~2% boundary.
- **The z-clamp still floors p-values near 1e-6**; anything below
  that await lifting the clamp for the tail path.

## 6. What this sets up

Per-tick calibrated p-values are the input the anytime-valid literature
assumes: an e-process layer over the parade (accumulate evidence, alarm
when it exceeds 1/alpha) would upgrade the per-tick guarantee to
"probability of *ever* falsely alarming ≤ alpha" under continuous
monitoring, a composition (forecaster-manufactured PITs + e-detectors /
e-GAI) that, per the verified sweep, nobody has published. The
remaining repair tickets: the Mahalanobis null, the GARCH-t rematch, and
TSB-AD-U for the job-1 credibility row.

*2026-07-10. Numbers reproduce via the harnesses named above; every
study file is committed alongside its results.*
