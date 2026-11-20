# Skater state: the canonical layout

A skater is a fold, `(y, state) -> (predictives, state)`, so its state is the
whole of what it remembers. That state is plain JSON data with one layout,
defined here, so a checkpoint written by one port can be read by another.
Python is the reference: its layout is the canonical one, and the ports read
and write it.

```python
import json
from skaters import laplace, state_to_json, state_from_json

f = laplace(k=1)
state = None
for y in history:
    _, state = f(y, state)
text = json.dumps(state_to_json(state))          # checkpoint

state = state_from_json(json.loads(text))        # restore, here or in another port
dists, state = f(next_y, state)
```

JS has the same pair, `stateToJSON` and `stateFromJSON` in
`docs/js/skaters/state.mjs`, and writes the same layout, so a checkpoint
written by either port resumes in the other.

## Values

State holds only:

- `null` (Python `None`), booleans, strings;
- finite numbers. JSON has no literal for NaN or infinity, so they never
  appear in state; "not yet known" is `null`. A number is an IEEE double.
  Python keeps the int/float distinction (`3` and `3.0`), JS does not, so a
  reader must accept either for any numeric field;
- lists. Every sequence is a list, including queues and pairs. Python writes
  a tuple as a list;
- objects with string keys;
- distributions, encoded as below.

No closures, class instances, sets, deques, or non-string keys. Closures are
configuration and live in the skater the factory returned, never in state.
`state_to_json` raises `ValueError` naming the path of anything else, and
`assert_plain_state` checks without converting.

## Keys

- Keys are snake_case, exactly as Python writes them: `leaf_state`,
  `leaf_pred`, `mean_q`, `t_state`, `s_state`, `phi_used`, `log_w`, `n_obs`.
- A table indexed by an integer uses the integer's decimal string as key:
  multiscale's per-stride tables (`"1"`, `"3"`), the period detector's
  per-lag `cross` (`"7"`, `"12"`).
- Readers must not depend on key order.

## Distributions

A `Dist` (Gaussian mixture) is

```json
{"components": [[w, mean, std], ...]}
```

with weights summing to one. A reader keeps the components bit for bit when
the weights sum to one within 1e-9 of the compensated sum, and normalises
otherwise (`Dist.from_dict`, `Dist.fromDict`). Renormalising an already
normalised mixture can move the last bit and break an exact resume.

A GPD-spliced predictive (`SplicedDist`) is

```json
{"spliced": true, "body": {"components": [...]},
 "t_lo": ..., "t_up": ..., "zeta_lo": ..., "zeta_up": ...,
 "g_lo": ..., "s_lo": ..., "g_up": ..., "s_up": ...}
```

On restore, an object is a distribution if it has `"spliced": true`, or if
`components` (a list) is its only key. No other state object may have that
shape.

## Queues

A queue is a list, oldest first. A bounded queue holds at most its bound; a
push beyond it drops the front. The bound is configuration (the horizon `k`,
a window length), not state.

## Layouts

Per-wrapper fields, outermost first as `laplace` nests them
(`parade(gpdtails(sticky(terminal_leaf_ensemble(...))))`, with `multiscale`
between `gpdtails` and `sticky` when `k > 1`).

| skater | fields |
|---|---|
| `parade` | `base`; `pending`: queue (bound `k`) of issued predictive lists; `pit`, `z`: lists of length `k`, `null` until horizon m matures; `skipped`: count of missing ticks |
| `gpdtails` | `base`; `pending`, `tails`: lists |
| `multiscale` | `t`; `phase`, `pending`, `score`: objects keyed by stride string, `phase["s"]` and `pending["s"]` lists of length s; `latest`: object keyed by stride string |
| `sticky` | `base`; `counts`: list of `[value, weight]` pairs in first-seen order |
| `terminal_leaf_ensemble` | `sub`: child states; `qdist`: per child, a queue of one-step Dists; `log_w`; `leaf_state`, `leaf_pred`: per horizon; `mean_q`: per horizon, a queue (bound h+1) of combined means; `adapt`: `null`, or an object with `log_eta`, `pit_ewma`, `loss_fast`, `loss_slow` and `pred_q` (a queue) when adaptive temperature is on |
| `bayesian_ensemble` | `sub`; `queues[i][h]`: queue (bound h+1) of Dists; `log_w[i][h]`; `n_obs` |
| `precision_weighted_ensemble` | `sub`; `queues[i][h]`: queue (bound h+1) of means; `stats[i][h]` |
| `conjugate` | `t_state` (the transform's), `s_state` (the inner skater's) |
| `leaf` | `var`: `{n, mean, m2}` |
| `garch_leaf` | `h`, `s2`, `n`, `omega`, `alpha`, `beta`, `w`, `last_r2`; `buf`: queue bounded by `window` |
| `search` / `dantzig` | `pool`: list of entries `{s, depth, recipe, cost, age, warmed, log_w, queues, dists}`; `n_obs`; `buffer`: queue bounded by `replay_buffer`; `pd_state`; `detected_periods`: list in detection order. A pool skater is rebuilt from its `recipe`; no closure is stored |
| `period_detector` | `buffer`, `n`, `mean`, `var`; `cross`: object keyed by lag string |
| `granger` | `lap`, `learned`: child states; `pend`: queue (bound `k`) of `[laplace predictives, learned predictives]` pairs; `cum`, `t`, `z`, `repeat_frac`, `abs_z_mean`, `n`, `last_y` |
| `homogenize` | `base`, `raw`, `pending` (queue, bound `k`); `cell`: per horizon, `null` or `{dynamic, issued, n}` with `dynamic` one `{q, log_weight, guard_run}` per candidate; `correction`: per horizon, `null` or `{weights, scales}` |
| `residual_transform` | `base`, `raw`, `z`; `learner`: `null` for `m0`, else `{ell, a, c, ea, ec, g2a, g2c}` plus `b`, `eb`, `g2b` for `m2`; `theta` |
| `zbank` | `t`; `sub`: one list of phase copies per (sigma, stride), sigma-major; `z` |

Transforms keep their own small objects under `t_state`; see each transform's
source. `gaussianize` stores its knots as a list `[cs, zs, ts]`, `ts` being
`null` for the unsmoothed variant.

## Old JS checkpoints

Before this layout, the JS port wrote six keys in camelCase: `tState`,
`sState`, `leafState`, `leafPred`, `meanQ` and `phiUsed`, and
`terminalLeafEnsemble` state had no `adapt`. `stateFromJSON` renames the keys
on read and the ensemble adds `adapt: null` on its next step, so those
checkpoints still resume.

## Old Python checkpoints

Before this layout, Python state used `collections.deque` for queues, a
float-keyed dict for sticky's counts, int keys for multiscale and the period
detector, tuple keys for `zbank`, and closures in `search`'s pool. Those
checkpoints still resume: each skater rewrites its part of an old state on its
next step (a multiscale phase copy is rewritten when it next runs). They are
pickle-only; `state_to_json` refuses them until they have been stepped.

## Tests

- `tests/test_state_json.py`: every exported skater is checkpointed through
  JSON at several points, including after laplace's GPD splice is live, and
  must resume bit-exactly; old layouts must resume.
- `parity/roundtrip.mjs`: the same gate for the JS port, plus an old
  camelCase JS checkpoint that must resume.
- `tests/test_js_state_resume.py`: Python checkpoints every exported skater
  JS has at several points, JS resumes them and must match Python's next 20
  outputs to 1e-6, and Python resumes JS's checkpoints likewise. JS state must
  have exactly Python's key layout.
- `parity/gen_vectors.py` restores through JSON at the burn-in step of every
  parity scenario.

Within a port a resume is bit-exact. Across ports it is as exact as the
ports' arithmetic: the parity suite holds them to 1e-6, and a resumed
stream differs from the reference by no more than a stream run from scratch.
