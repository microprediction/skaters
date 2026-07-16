# laplace vs. markov (regime-switching drift)

Preserved tape from the `markov_drift` study (PR #116): a machine-generated
Markov regime-switching forecaster, offered as an **opt-in candidate** in
`laplace`'s pool, measured against `laplace` on 500 one-step non-price FRED
change-series, scored on log-likelihood and CRPS by the one scorer. The
opponents are defined in `benchmarks/opponents.py` (`markov`, `markov-mix`,
`markov-nudge`, `laplace+markov`, and the coupled variants). Raw per-series
tape: `results.csv`.

## Results

Median over the 500 series, with `laplace`'s per-series win-rate against each
arm (log-likelihood; higher is better):

| method | median logpdf | median CRPS | laplace wins |
|---|---|---|---|
| laplace | +3.438 | 0.00523 | — |
| markov (standalone) | +3.016 | 0.00591 | 355 / 500 |
| markov-mix | +3.380 | 0.00530 | 272 / 500 |
| markov-nudge | +3.363 | 0.00523 | 222 / 487 |
| laplace+markov | +3.439 | 0.00524 | 211 / 500 |
| laplace\*markov | +3.438 | 0.00523 | 169 / 500 |
| markov-nudge-pre | +3.438 | 0.00524 | 157 / 500 |
| laplace-nostick | +3.162 | 0.00538 | 259 / 500 |

## Reading

The standalone Markov forecaster trails `laplace` by about 0.10 nats median and
loses on 355 of 500 series. Its mixture (`markov-mix`) closes most of that gap.
Coupling Markov into `laplace`'s candidate pool (`laplace+markov`,
`markov-nudge-pre`) lands at parity: the medians differ by a few ten-thousandths
of a nat in either direction, within noise. Markov therefore ships as an opt-in
candidate, not a default. The transform, its documentation, and its tests are
in PR #116.
