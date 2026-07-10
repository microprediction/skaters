# Contributing to skaters

Thanks for considering a contribution. The package has strict invariants;
this page tells you what they are so your change passes review on the
first try.

## Setup and tests

```
git clone https://github.com/microprediction/skaters
cd skaters
pip install -e ".[dev]"
pytest
```

The suite must pass in full. It includes three kinds of tests beyond the
unit tests, and all three gate every release:

1. **JS parity** (`tests/test_js_parity.py`): the JavaScript twin in
   `docs/js/skaters/` must agree with Python to 1e-6 across ~100,000
   probe values. If you change numerical behavior in one language, change
   the other, then regenerate the vectors:
   `PYTHONPATH=src python parity/gen_vectors.py && node parity/check.mjs`.
2. **Adversarial gates** (`tests/test_tails_robustness.py`,
   `parity/adversarial.mjs`): the deployed default must survive constant
   series, lattices, monster spikes, scale collapse, and vol whiplash,
   and recover afterwards. If you find a new failure mode in the wild,
   add the stream to these files as part of the fix.
3. **The laplace contract** (`tests/test_laplace_contract.py`): the
   signature, state surface, determinism, and checkpoint-restore
   equivalence of `laplace` are frozen. People deploy this function.
   Changing its contract requires editing that test deliberately, plus a
   changelog entry and a version bump, in the same pull request.

## Ground rules

- Pure stdlib in `src/skaters/`; dependencies belong in benchmarks only.
- Skater state is pure data: picklable, resumable, no closures.
- Strictly causal everywhere: score before update; nothing may read the
  future or whole-series statistics.
- New estimators forget: prefer EWMA-style memory to cumulative counts.
- Benchmark claims come with committed study files. If you assert a
  number, commit the harness and results that produce it (see
  `benchmarks/anomaly/RESULTS.md` for the format).

## Reporting issues

Open a GitHub issue with a minimal reproducing stream where possible.
Calibration complaints are especially welcome: a PIT histogram from a
quiet stretch of your data says more than an adjective.
