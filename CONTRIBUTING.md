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

A change that can move laplace's issued predictive (`Dist`, tails,
transforms) also needs the output-signature check. Run
`PYTHONPATH=src python parity/laplace_k1_signatures.py --write before.json`
on main, apply the change, then run it with `--compare before.json`. The
ordinary streams should stay identical or move by no more than the change's
stated tolerance; report the printed moves in the pull request. Reference
digests at main are in `parity/laplace_k1_signatures.txt`.

## Ground rules

- Pure stdlib in `src/skaters/`; dependencies belong in benchmarks only.
- Skater state is pure data: picklable, resumable, no closures.
- Strictly causal everywhere: score before update; nothing may read the
  future or whole-series statistics.
- New estimators forget: prefer EWMA-style memory to cumulative counts.
- Benchmark claims come with committed study files. If you assert a
  number, commit the harness and the summary results that produce it (see
  `benchmarks/anomaly/RESULTS.md` for the format): a README, the script that
  reproduces the numbers, and the summary tables.
- Bulky evidence does not go in this repository. Per-series results, raw
  outputs and anything over a few hundred lines are published as a release
  asset in
  [microprediction/skaters-benchmarking-data](https://github.com/microprediction/skaters-benchmarking-data/releases)
  and linked from your README with their sha256. A maintainer can host them
  for you; say so in the pull request. Do not vendor copies of scripts that
  already live here: refer to them by path.
- A numerical change reaches every port. The Python package is the
  reference; Rust and JavaScript live here, R in
  [microprediction/skaters-r](https://github.com/microprediction/skaters-r)
  and Julia in [microprediction/Skaters.jl](https://github.com/microprediction/Skaters.jl),
  all parity-checked against vectors generated from this package. Either port
  the change to all of them or say in the pull request which ports it still
  needs, so they do not drift.

## Reporting issues

Open a GitHub issue with a minimal reproducing stream where possible.
Calibration complaints are especially welcome: a PIT histogram from a
quiet stretch of your data says more than an adjective.
