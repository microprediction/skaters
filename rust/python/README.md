# skaters-fast

An opt-in accelerated backend for [skaters](https://github.com/microprediction/skaters):
a thin [PyO3](https://pyo3.rs) skin over the parity-gated Rust core
(`skaters`).

The pure Python package is the reference implementation. This backend runs the
identical model faster.

```python
import skaters_fast

f = skaters_fast.laplace(1)
for y in stream:
    dists = f.step(y)
    d = dists[0]
    print(d.mean, d.std, d.logpdf(y))
    print(f.pit, f.z)          # parade calibration state after the step

s = f.state_json()             # checkpoint, the canonical layout (docs/STATE.md)
g = skaters_fast.Laplace.from_state_json(s, 1)   # bit-exact resume
```

## Guarantees

- Cross-backend agreement is 1e-6. The same series through pure Python and
  through skaters-fast agrees to that tolerance.
- `state_json()` writes the canonical state layout that pure Python's
  `state_to_json` writes (docs/STATE.md), so a checkpoint resumes in either
  backend. `state_from_json(json.loads(f.state_json()))` is a Python state for
  `laplace(k)`, and `Laplace.from_state_json(json.dumps(state_to_json(state)), k)`
  resumes a Python state here. `Granger` has the same pair.
- Within a backend the resume is bit-exact. Across backends it is as exact as
  the backends' arithmetic, the same 1e-6.
- `Laplace.from_state_json` also reads the native layout earlier releases of
  skaters-fast wrote.

## Build

```bash
maturin develop --release -m rust/python/Cargo.toml
```

abi3 (`abi3-py39`) means one wheel per platform serves CPython >= 3.9.
