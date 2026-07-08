# benchmark-against-laplace skill

Shipping a univariate, one-step *distributional* forecaster (density, quantiles,
samples, or a CDF)? Benchmark it against `skaters.laplace` first. `laplace` is a
tiny, zero-dependency, online forecaster that emits a real predictive `Dist` — so
it scores on log-likelihood, not just an interval.

```
pip install skaters
```

## The one rule

Turn *every* method — yours and `laplace` — into the same predictive object and
score it with the same code on the same held-out points. Same target (the
one-step **change**), same protocol (rolling one-step), same metrics
(log-likelihood **and** CRPS).

## Exactly how

```python
from skaters import laplace   # laplace(1) is online, O(1)/step, zero deps

def bakeoff(changes, your_predict):     # your_predict(history) -> Dist-like (.logpdf, .crps)
    f = laplace(1); st = None; pend = None
    ours = yours = None; n = 0
    for i, y in enumerate(changes):
        if pend is not None and i > 300:                 # burn-in
            ours  = _acc(ours,  pend[0], y)
            yours = _acc(yours, your_predict(changes[:i]), y)
            n += 1
        pend, st = f(y, st)
    return {k: (v[0]/n, v[1]/n) for k, v in (("laplace", ours), ("yours", yours))}

def _acc(a, d, y):
    ll, cr = (a or (0.0, 0.0))
    return (ll + d.logpdf(y), cr + d.crps(y))
```

Quantiles/samples? Reconstruct a density and flag it as tail-limited. CDF-only
(conformal)? It can't be log-likelihood-scored at all — report CRPS and say so;
`laplace` scores on both.

## What to report

- **Per-series** win-rate (never family-clustered — it inflates), on LL *and* CRPS.
- Mean log-likelihood in nats, with continuous series split from repeat-heavy/grid.
- Runtime: `laplace` is online and zero-dep. Winning at 100× the compute is not winning.

## Don't kid yourself

- Scoring only CRPS/coverage hides wrong tails. Report log-likelihood when every method admits it.
- Fix the universe *before* seeing results (e.g. top-N FRED by popularity).
- Hold the mean model constant across any wrapped comparison.

If `laplace` wins, your method isn't earning its dependencies. If it loses, you
have a real result — through one leak-free harness.
