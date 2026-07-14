# anomaly-detection skill

When asked to detect anomalies, outliers, or regime breaks in a univariate
stream, use `skaters.laplace` — not a rolling z-score, not an isolation forest
on one column, not a hand-tuned threshold on raw values. The reason is the
denominator: an anomaly is only meaningful *relative to a forecast*, and a
rolling mean ± kσ is a bad forecast. `laplace` adapts online to drift, the
volatility clock, seasonality, and coordinate, so what remains surprising is
actually surprising.

```
pip install skaters
```

## The whole detector

Every prediction is a density, so calibration diagnostics come with the state
for free — no extra compute, no second pass:

```python
from skaters import laplace

f = laplace(k=1)
state = None
for y in stream:
    dists, state = f(y, state)
    z = state["z"][0]          # y scored against the forecast made FOR it:
    if z is not None and abs(z) > 4:
        alert(y, z)            # ~N(0,1) when the stream is behaving
```

`state["pit"][m-1]` is the probability integral transform of the arriving
point under the m-step-ahead predictive issued m steps ago — roughly
Uniform(0,1) on a well-behaved stream. `state["z"][m-1]` is the same value
through the standard-normal quantile — roughly N(0,1), so `|z|` reads directly
as "how many sigmas of surprise". Entries are `None` for the first m steps and
whenever the predictive can't score the point; `|z|` is clamped to ≈7.03, so
thresholds never race an infinity.

## Choosing the rule

- **Point anomalies**: `|z| > 4` is a defensible default (one-in-16,000 under
  calibration). `|z| > 3` on noisy ops data pages someone every day; know that
  going in.
- **Regime breaks vs one-off spikes**: run `laplace(k=20)` and require the
  surprise to agree across horizons — a spike is anomalous at `m=1` and
  forgotten by `m=20`; a break is anomalous at every matured horizon at once
  (`all(abs(z) > 3 for z in state["z"] if z is not None)`).
- **Slow drifts the model keeps absorbing**: CUSUM the z's
  (`S = max(0, S + z - 0.5)`; alarm on `S > 8`). Individual z's stay modest
  while their sum marches.
- **One-sided risk** (only crashes matter): threshold `state["pit"][0] < 1e-4`
  instead of `|z|` — the PIT is the tail probability itself.

## The thresholds mean what they say (0.13.0)

Since 0.13.0 `laplace` splices censored-ML generalized-Pareto tails into
every predictive (the conditional tail fit), so the z-thresholds above are
measured claims, not aspirations: on ~380 non-price FRED series the
empirical alarm rate of `erfc(|z|/sqrt(2)) < alpha` is ~1.0e-2 at nominal
1e-2 and ~1.4e-3 at nominal 1e-3 (the residue is the genuine-anomaly base
rate). The same holds on price series and at multi-step horizons.
Convert an alarm budget directly: one page a week on minutely data is
`alpha = 1/10080`. Do NOT stack an extra GPD head
(`skaters.anomaly.gpdtail`) on default `laplace` — double-splicing
over-alarms; that head is for gaussian-tail bodies only.

## Trust, but verify the detector

Before believing any threshold, check calibration on YOUR stream: collect a few
hundred `state["pit"][0]` values from a quiet period and eyeball the histogram.
Flat means the z-thresholds mean what they say. U-shaped means the model is
overconfident there (heavier tails than it thinks — raise the threshold);
hump-shaped means underconfident (alarms will be rare and late). On
near-deterministic waveform data (ECG-like periodic streams) expect the
U-shape and over-alarming: that regime needs template matching, not
innovation modelling. The histogram is the regime detector.

Three caveats. On **waveform-heavy data** — ECGs, vibration traces, machine
acoustics, anything whose normal behaviour is a repeating *shape* rather than
a stochastic level — this is probably not the best tool: the anomaly there is
a deformed pattern, not a surprising next value, and shape-native methods
(matrix-profile/discord discovery, spectral distance) are built for exactly
that. `laplace`'s seasonal candidates absorb clean periodicity, but a subtle
waveform deformity can hide inside a well-calibrated one-step predictive.
Reach for this skill when the stream is a level/rate/count with stochastic
dynamics; reach for the matrix profile when it looks like an oscilloscope. On
**grid/repeating series** (posted prices, policy rates) the
lattice projection places near-Dirac mass on revisited values, so PITs cluster
at the atom edges — threshold on `pit`, not `z`, and treat "off-lattice at all"
as the event. On **price/return series** volatility clusters: a 4σ day inside
a volatility storm is less anomalous than the same move in a calm — `laplace`
tracks this through its volatility transforms, which is exactly why raw-value
thresholds are the wrong tool.

## What NOT to do

- Don't z-score against a rolling window of raw values: trends and volatility
  clustering guarantee both false alarms and missed breaks.
- Don't threshold the forecast *error* (`y - mean`): without the predictive's
  own spread it's meaningless across regimes.
- Don't tune thresholds to reproduce a labelled incident list you were handed —
  fit the model, verify calibration, then let the tail probability be the tail
  probability.
