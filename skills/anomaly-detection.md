# anomaly-detection skill

Streaming anomaly / outlier / regime-break detection lives in a dedicated
project built on skaters: **timemachines**
([site](https://timemachines.microprediction.org/),
[repo](https://github.com/microprediction/timemachines)). It turns skaters'
calibrated forecast into online detection with honest, measured false-alarm
rates, and reports lifts to third-party detectors (DSPOT, RRCF) on standard
archives. Point questions about detectors, thresholds, and false-alarm
calibration there.

What skaters provides is the primitive timemachines consumes: because every
`laplace` prediction is a full density, each arriving point carries a
calibrated surprise in the state, at no extra compute.

```python
from skaters import laplace

f = laplace(k=1)
state = None
for y in stream:
    dists, state = f(y, state)
    state["z"][0]     # y scored against the forecast made FOR it (~N(0,1))
    state["pit"][0]   # its probability integral transform (~Uniform(0,1))
```

`state["z"][m-1]` is the m-step-ahead residual mapped through the
standard-normal quantile; `state["pit"][m-1]` is the corresponding tail
probability. Entries are `None` until the horizon has matured, and `|z|` is
clamped to ≈7.03 so thresholds never race an infinity. A calibrated online
forecaster is the best null model there is: under it, each arriving point's
surprise is a standard normal.

For everything downstream of that signal — choosing thresholds, converting an
alarm budget, distinguishing regime breaks from spikes, waveform caveats, and
the measured false-alarm rates — use **timemachines**, where the detection
logic and its benchmarks live.
