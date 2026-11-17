# skaters

Home of **Laplace**, a light, fast, automatic **distributional** univariate time-series prediction algorithm. It also improves other time-series models, including Prophet. Recommended for non-price economic time series.

One call, zero dependencies, every prediction a full probability *distribution* computed online in O(1).

**Documentation, live demos and results: [skaters.microprediction.org](https://skaters.microprediction.org/)**

<p align="center">
  <a href="https://skaters.microprediction.org/"><img src="https://img.shields.io/badge/docs%20%26%20live%20demos-skaters.microprediction.org-4a3aff?style=for-the-badge" alt="Documentation and live demos"></a>
  <a href="https://skaters.microprediction.org/languages.html"><img src="https://img.shields.io/badge/implementations-Python%20%7C%20JS%20%7C%20R%20%7C%20Julia%20%7C%20Rust-1a8c4a?style=for-the-badge" alt="Python, JavaScript, R, Julia and Rust"></a>
</p>

## Quick start

```bash
pip install skaters
```

```python
from skaters import laplace

f = laplace(k=3)
state = None
forecast = None            # the fan issued LAST tick, aimed at this y
for y in observations:
    if forecast is not None:
        forecast[0].logpdf(y)          # one-step-ahead log score
        forecast[0].cdf(y)             # one-step-ahead PIT
    forecast, state = f(y, state)
    forecast[0].mean                   # point forecast for the NEXT tick
    forecast[0].std                    # uncertainty
    forecast[0].quantile(0.975)        # upper edge of the central 95% band
```

- Each call takes one observation and returns a predictive distribution (`Dist`) per horizon, `h = 1, ..., k`.
- A `Dist` carries the mean, spread, quantiles and density at once.
- Score a forecast only against values that arrive after it was issued.
- `state["pit"]` and `state["z"]` give a calibrated surprise for every point.

The release on PyPI is 0.16.0. `granger`, `flesaker` and `log_transform` arrive in the next release; until then, `pip install git+https://github.com/microprediction/skaters`.

## Laplace and foundational models

Laplace was written to monitor hundreds of thousands of private and public economic series, because we couldn't find anything better. It is tiny, dependency-free and takes microseconds per update. Some foundational models are slightly better on monthly, weekly and hourly series, but far less usable at present. It leads on daily economic series. [Where each is better →](https://skaters.microprediction.org/#where-fms-are-better)

<p align="center">
  <img src="https://skaters.microprediction.org/assets/laplace-foundational-models.gif" alt="A cyclist pops a wheelie on a mountain bike alongside a professional peloton; the peloton is labelled Foundational Models and the wheelie rider Laplace." width="420">
</p>

## One general forecaster?

| | what it is |
|---|---|
| `laplace(k)` | the general forecaster, fully autonomous: no training, no tuning; multi-step to `k=12` |
| `granger(frequency=...)` | `laplace` with hyperparameters trained per frequency (monthly, weekly, hourly), never more than log 4 behind it |
| `flesaker(lower=0)` | experimental: `laplace` on `log(y - lower)`, for series with a known bound |

Everything else is a building block you can compose: transforms, leaves and ensembles ([methodology](https://skaters.microprediction.org/guide.html)).

## Documentation

| | |
|---|---|
| [Demos](https://skaters.microprediction.org/demos/) | the forecaster running live in your browser |
| [FAQ](https://skaters.microprediction.org/faq.html) | what it is for, how not to use it |
| [Examples](https://skaters.microprediction.org/examples.html) | runnable recipes |
| [Methodology](https://skaters.microprediction.org/guide.html) | how `laplace` and `granger` are built |
| [Scope](https://skaters.microprediction.org/scope.html) | prior knowledge, horizons, units |
| [Metrics](https://skaters.microprediction.org/metrics.html) | why log likelihood is the default score |
| [Skills](https://skaters.microprediction.org/skills.html) | copyable instructions for AI assistants |
| [Primer](https://skaters.microprediction.org/#conversation) | paste into any chat assistant to discuss your series |
| [Ports](https://skaters.microprediction.org/languages.html) | [Python](https://skaters.microprediction.org/ports/python.html), [torch](https://skaters.microprediction.org/ports/torch.html), [Rust](https://skaters.microprediction.org/ports/rust.html), [JavaScript](https://skaters.microprediction.org/ports/javascript.html), [R](https://skaters.microprediction.org/ports/r.html), [Julia](https://skaters.microprediction.org/ports/julia.html), parity-checked to 1e-6 |
| [Papers](https://skaters.microprediction.org/papers.html) | the methods paper, the benchmark paper and technical notes |
| [Leaderboards](https://foundationalprediction.com/) | paired results against foundational models |
| [REFERENCE.md](REFERENCE.md) | the detailed reference: architecture, `Dist`, transforms, ensembles, specs, `skaters.torch` |

## Cite

Please cite the first paper listed, *Transforms all the way down* ([SSRN 7220478](https://papers.ssrn.com/abstract=7220478)), as it explains the methodology.

```bibtex
@misc{cotton2026skaters,
  title  = {Transforms All the Way Down --- Automatic Online Distributional
            Forecasting by Conjugation},
  author = {Cotton, Peter},
  year   = {2026},
  note   = {SSRN 7220478, https://skaters.microprediction.org}
}
```

## Heritage

skaters distils ideas from [timemachines](https://github.com/microprediction/timemachines), which gave dozens of time-series packages a common interface. It is a from-scratch rewrite for speed, distributional prediction and the browser.
