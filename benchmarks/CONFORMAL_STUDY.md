# The conformal constraint study

**Question.** What does the conformal pattern cost a forecaster that is otherwise
free? Not on a chain built to make the point, but on the forecaster that already
leads this benchmark, with one constraint imposed and everything else held fixed.

**The paper this feeds is two numbers.**

| | number | source |
| --- | --- | --- |
| prevalence | share of the conformal literature that stops at the empirical map | the 686-paper frame in `conformalprediction/papers/grammar/survey/` |
| price | held-out log-likelihood lost when `laplace` is made to obey that pattern | this study |

Neither half is worth much alone. A price with no prevalence is a curiosity; a
prevalence with no price is a complaint. Together they say what the convention
costs the field.

**The paper stands on the grammar paper and re-derives nothing.** *Conformal
Prediction as a Transform within a Grammar* already defines the object (the
fence-post empirical map), gives the typing, and establishes that a guarantee
attaches to a position in a chain. *Marginally Useful* already prices the pooled
shape as `I(R;X)`. This paper cites both and adds only two measurements: how many
papers occupy which position, and what the dominant position costs. No new theory,
no new identity, no re-litigation. That is what keeps it short and what makes it
checkable by a referee in an afternoon.

---

## The arms

Three points on one dial, plus the existing opponents for context.

1. **`laplace`** — unconstrained. Already registered.
2. **`laplace_conformal`** — laplace's *point forecast*, with the predictive shape
   replaced by a pooled empirical residual law. This is the conformal pattern:
   model the location however you like, then quote one shape for every state.
3. **`laplace_homogenize`** — laplace plus the `homogenize` rung (`skaters.homogenize`,
   PR #182), which corrects the residual stream for conditional scale and
   unresolved heterogeneity. The other end of the dial.

Arm 2 is the one that matters, and it is deliberately the *narrowest possible*
version of the constraint. It holds the location model fixed and changes only
whether the residual law may depend on the state, which is exactly the hypothesis
of the identity in *Marginally Useful* ("fix the location predictor..."). So the
measured gap is an end-to-end estimate of `I(R;X)` plus estimation cost, on real
series, with a strong location model rather than a toy one.

---

## Implementation

`bench_core.conformal_dist(point, resid_window, scale=1.0, nq=41)` already exists
and is what the `AutoARIMA+conformal` foil uses. `Dist` exposes `.mean()`. So the
new arm is a wrapper around the existing laplace factory:

```python
# opponents.py, near the other _laplace_* factories

def _laplace_conformal(window):
    """laplace's location, conformal's shape. The predictive is the pooled
    empirical law of the base model's own recent residuals, re-levelled to
    laplace's point forecast. No state-dependence in the shape: that is the
    constraint."""
    def factory():
        base = <the same factory _ours("laplace", ...) uses>
        resid = collections.deque(maxlen=window)
        def skate(y=None, **kw):
            d = base(y=y, **kw)               # laplace's own predictive
            point = d.mean()
            if y is not None:
                resid.append(y - _prev_point[0])
            _prev_point[0] = point
            if len(resid) < 30:               # warm-up: fall back to the base
                return d
            return bc.conformal_dist(point, list(resid))
        return skate
    return factory

CONFORMAL_CONSTRAINED = [_ours(f"laplace_conformal({w})", _laplace_conformal(w))
                         for w in (250, 400, 750)]
```

Register the list alongside `CONFORMAL_NAIVE`, and add a preset:

```python
"conformal-constraint": [op.name for op in OURS]
                      + [op.name for op in CONFORMAL_CONSTRAINED + CONFORMAL_NAIVE],
```

The sketch is a sketch: check the residual bookkeeping against
`bc.roll_dist_scores`, which owns the stepping convention, and make sure the
residual recorded at step *t* is the one the predictive issued at *t-1* was
graded on. Getting that off by one silently flatters or damns the arm.

---

## Fairness constraints, all of which must hold

The comparison is only worth running if the constrained arm is crippled in
*exactly one* way.

- **Same location model.** `laplace_conformal` must use laplace's own point
  forecast, not a cheaper mean. Otherwise the gap mixes location error with the
  constraint.
- **Same corpus, warm-up, and out-of-scope rules.** Everything in `study.py`
  `_in_scope` and the two degenerate patterns in `README.md` applies unchanged.
- **Report every window.** Run 250, 400 and 750 and report all three. Picking the
  best window after the fact is the same error the paper accuses others of.
- **Same scorer.** `bc.roll_dist_scores`, held-out predictive log-likelihood, with
  CRPS reported beside it.

---

## Pre-registration

Write this down before looking at any output, because the corpus numbers have
already moved once.

- **Primary comparison:** `laplace` minus `laplace_conformal(400)`, per-series
  paired, held-out log-likelihood, on the `daily` arm.
- **Secondary:** the same on CRPS; the same across all three windows; the same on
  `weekly` and `monthly`.
- **Control:** an iid null suite where the residual law genuinely does not depend
  on the state. The gap must be approximately zero there. If it is not, the
  measurement is picking up estimation cost rather than the constraint, and the
  main number is not interpretable.
- **Honest secondary that should be reported whatever it says:** does
  `laplace_conformal` still beat AutoARIMA, AutoETS and the other external
  baselines? If it does, say so. The claim is that the pattern leaves something on
  the table, not that it is bad.

---

## Pitfalls that have already bitten this corpus

1. **The standardize bug.** A rung that divided by a post-update EWMA standard
   deviation self-normalised the emission and silently bounded the coordinate.
   It reversed a headline. Check that no arm gets a bounding effect the others
   lack.
2. **Survivorship.** The grammar campaign ran on 572 of 701 series, and the 129
   that dropped out had roughly double the effect. State the corpus rule up
   front and report what did not run.
3. **Selecting the headline after the fact.** State the primary comparison first.

---

## Running it

```bash
cd skaters
PYTHONPATH=src python benchmarks/study.py conformal-constraint
PYTHONPATH=src python benchmarks/study.py conformal-constraint summarize
```

Freeze the output CSV in `benchmarks/` next to the others, with a log naming the
corpus arm, the date, and the git SHA of both `skaters` and the paper repo.

## What to report back

A single table: arm, N series, mean held-out log-likelihood, mean CRPS, and the
per-series paired win rate against unconstrained `laplace`. Plus the null-suite
row, which is the one that says whether the rest can be believed.
