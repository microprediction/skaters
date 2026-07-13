# skaters-fast

An opt-in accelerated backend for [skaters](https://github.com/microprediction/skaters):
a thin [PyO3](https://pyo3.rs) skin over the parity-gated Rust core
(`skaters-core`).

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

s = f.state_json()             # checkpoint
g = skaters_fast.from_state_json(s, 1)   # bit-exact resume
```

## Guarantees

- Cross-backend agreement is 1e-6. The same series through pure Python and
  through skaters-fast agrees to that tolerance.
- Within-backend resume is bit-exact. `state_json()` round-trips through
  `from_state_json()` with no drift.
- Do not switch backends mid-stream. Resume a saved state into the same backend
  that wrote it.

## Build

```bash
maturin develop --release -m rust/python/Cargo.toml
```

abi3 (`abi3-py39`) means one wheel per platform serves CPython >= 3.9.
