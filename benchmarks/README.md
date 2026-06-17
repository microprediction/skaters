# benchmarks

A **development-only** harness. It is *not* part of the `skaters` package, is
not imported by it, and adds no dependency — the deployed package stays
zero-dependency and pure Python.

```bash
python benchmarks/bench.py
```

It compares the named skaters policies and conformal recalibration against
classical baselines and split-conformal prediction, scoring both point
accuracy (**MASE**) and distributional quality (**CRPS**, 90/95% interval
**coverage**, mean **log-likelihood**), across synthetic regimes (trend,
seasonal, random walk, heavy-tailed t₃, slowly-varying heteroskedastic noise).

## Offline by design

The baselines (naive, drift, EWMA) and the **conformal** comparison are
implemented here in pure Python, so the harness runs with only `skaters`
installed. There is nothing to download.

## Optional external comparisons

`bench.py` will additionally use these packages **iff they are already
installed** (loaded behind `try/except`, never required):

```bash
pip install statsforecast statsmodels river   # point/interval baselines
pip install mapie crepes                       # conformal prediction libraries
```

The script prints which optional packages it found. Keep these in your own
environment — they are intentionally absent from the package's
`pyproject.toml`.

## What to read from the output

- **CRPS** is the headline proper score (lower is better) — robust, unlike
  log-likelihood which is dominated by the tails.
- **coverage** should sit near the nominal 90/95%. Conformal variants exist to
  pull coverage back to nominal on miscalibrated (e.g. heavy-tailed) data; the
  trade is a worse log-likelihood, since conformal targets coverage, not
  density.
