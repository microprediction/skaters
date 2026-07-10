# timesfm-study skill

Run a David-v-Goliath study: `skaters.laplace` against TimesFM (or any
zero-shot time-series foundation model) on your own series, scored the same
way, with the splits and caveats that make the result mean something. The
reference study and its results live at
[skaters.microprediction.org/timesfm.html](https://skaters.microprediction.org/timesfm.html).

```
pip install skaters
pip install timesfm    # a separate env is wise; torch deps are heavy
```

## The one rule

Turn every method into the same predictive object and score it with the same
code on the same held-out points. Same target (the one-step **change**), same
context, same metrics (log-likelihood **and** CRPS). Never compare your
model's home metric to the opponent's away metric.

## Protocol

1. **Target the change stream.** First-difference (or log-difference if
   strictly positive). This is the stationary-ish object both sides can
   forecast; disclose that levels are the foundation model's training diet.
2. **Zero-shot, fixed context.** Give TimesFM a fixed window (256 works) of
   preceding changes at every test step and ask for the next one. No
   fitting. Batch all windows into one call or CPU time will hurt.
3. **Same windows for laplace.** Run `laplace(1)` over the full history but
   score only the identical test steps.
4. **One `Dist` for everyone.** TimesFM emits quantiles: reconstruct a
   smoothed mixture and FLAG the log-likelihood as tail-limited; read CRPS
   as the fairer signal for quantile models. Sample outputs: Gaussian KDE.
5. **Score both** log-likelihood and CRPS per series, per step, then
   aggregate per series. Report per-series win rates, not pooled means; one
   degenerate series must not own the average.

## The splits that keep you honest

- **Continuous vs repeat-heavy.** Compute the fraction of consecutive equal
  changes over the test window; below 0.05 is continuous. Constant and
  near-constant series (recession dummies, administered rates) reward exact
  atoms: quantile heads win those at machine precision and the ratio looks
  enormous while the scores differ in the ninth decimal. Report the splits
  separately or the repeat games will decide your headline.
- **Both metrics, both directions.** If your model wins LL and loses CRPS,
  say both. If the opponent's density is reconstructed, say that too.

## Scoring skeleton

```python
from skaters import laplace
from skaters.dist import Dist

def study(changes, fm_quantiles):        # fm_quantiles: [test_steps x q] from one batched call
    HIST, TEST, CTX = len(changes), 150, 256
    f, st, pend = laplace(1), None, None
    rows = []
    for i, y in enumerate(changes):
        step = i - (HIST - TEST)
        if pend is not None and step >= 0:
            fm = dist_from_quantiles(fm_quantiles[step])   # smoothed mixture
            rows.append((pend[0].logpdf(y), pend[0].crps(y),
                         fm.logpdf(y), fm.crps(y)))
        pend, st = f(y, st), st
        pend, st = f(y, st)
    return rows
```

(Adapt from the reference harness, which handles batching, KDE/quantile
reconstruction, and the split rule:
[foundation_study.py](https://github.com/microprediction/skaters/blob/main/benchmarks/foundation_study.py).)

## Fairness accounting, both directions

State what favours each side. Favouring laplace: the change target, full
history seen online. Favouring the foundation model: pretraining corpus,
identical scoring windows. Do not fine-tune to a single short series and
call it the foundation model's best self; that regime catastrophically
overfits and zero-shot is the intended use.

## Report

Per-series win rates by split, median per-point LL gap in nats, median CRPS
ratio, a per-series CRPS scatter with the equal line, the list of series
where the opponent wins with a one-line reason each, and the ledger of what
you did not run. Losing rows go in the table, not a drawer.
