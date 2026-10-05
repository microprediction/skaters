# Forecastability study: runbook

Script: `benchmarks/forecastability_study.py` (its docstring states what is
measured and how to read it). Tracking issue: #250. Paper: *Marginally Useful:
Conformal Prediction Adds No Forecastability* (TAS revision).

Per (series, horizon h) it scores four predictive densities for y_{t+h}
prequentially on the same targets: `unc` (pooled KDE of y), `cps` (laplace
h-step mean + pooled KDE of raw h-step residuals), `cpsz` (mean + EWMA scale x
pooled KDE of standardized residuals) and `lap` (laplace(h)'s own density), and
reports `F_hat = L_lap - L_unc`, `X_cps`, `X_cpsz` (captured, relative to
`unc`) and `left = L_lap - L_cps`.

## 1. Setup on a fresh machine

```
cd ~/github/skaters && git fetch origin && git checkout forecastability-study
python3.12 -m venv .venv && source .venv/bin/activate && pip install -e .
pip install numpy matplotlib h5py      # summary figure; h5py only for metr-la
```

Strongly recommended: the Rust backend. It gives identical numbers (checked
here: F_hat agrees with the pure-Python reference to 1e-10) and is 10-17x
faster. Without it the script silently uses pure Python (`--backend auto`).

```
curl https://sh.rustup.rs -sSf | sh -s -- -y && source ~/.cargo/env
pip install maturin
maturin develop --release -m rust/python/Cargo.toml
python -c "import skaters_fast"        # the run log then says backend=fast
```

## 2. Data, per arm

| arm | source | fetch step | series |
|---|---|---|---|
| `fred` | 702-csv FRED cache (exact vintages of the published 572-series results) | `tar xzf fred_cache.tgz -C benchmarks/` (never refetch from the API) | 572 |
| `m4-hourly` | M4 hourly train CSV (GitHub, public) | automatic on first use (`--list`) | 412 |
| `m4-daily` | M4 daily train CSV (GitHub, public) | automatic (96 MB) | 2885 |
| `electricity` | UCI ElectricityLoadDiagrams20112014, 15-min to hourly means | automatic (261 MB zip, ~25 s parse) | 349 |
| `metr-la` | METR-LA speeds, the zip torch-spatiotemporal downloads (drive.switch.ch) | automatic, needs `h5py` | 198 |
| `returns` | daily log returns of FRED asset prices via the keyless `fredgraph.csv` endpoint (`RETURNS_IDS`: equity indices, H.10 FX, energy spot, Coinbase crypto) | automatic | 35 |

Prime each non-FRED cache first (downloads, then prints the first series):

```
for a in m4-hourly m4-daily electricity metr-la returns; do
  PYTHONPATH=src:benchmarks python benchmarks/forecastability_study.py --arm $a --list
done
```

New caches go to `benchmarks/data/forecastability/` (override with
`FORECASTABILITY_CACHE`), a subdirectory, so the `fred` arm is unaffected. (The
issue's `len(os.listdir(fred._CACHE))` check then reads 703: the extra entry is
that directory.)

Filters, all arms: at least 600 changes and under 5% exactly repeated
consecutive changes (the `fred` arm's rule). Targets are changes
(`fred._to_changes`: log-difference if strictly positive, else difference).
METR-LA: zero speed = missing; sensors with >15% missing are dropped, gaps are
linearly interpolated so the model sees a continuous stream, and only targets
whose two underlying levels were observed are scored.

TODO / not wired:
- FRED daily / weekly / monthly corpus arms (`corpus.py`): they enumerate
  through the FRED API (key needed) and write new csvs into `benchmarks/data`,
  which would silently change the `fred` arm. Wire them with a separate cache
  directory if wanted.
- Intraday asset returns: no free scriptable source found (Stooq and Yahoo now
  block scripted downloads).

## 3. Commands

Smoke test (about 6 s with `skaters_fast`, 70 s pure Python, 8 workers):

```
PYTHONPATH=src:benchmarks python benchmarks/forecastability_study.py --arm fred --horizons 1,3 --limit 5
```

Delete `benchmarks/forecastability_fred.csv` after the smoke test, or the full
run will simply resume from it (that is also fine: the cells are identical).

Full runs, one arm at a time:

```
PYTHONPATH=src:benchmarks python benchmarks/forecastability_study.py --arm fred --horizons 1,2,3,5,8,13 --workers <cores> 2>&1 | tee -a benchmarks/forecastability_fred.log
```

and the same with `--arm m4-hourly`, `m4-daily`, `electricity`, `metr-la`,
`returns`. Options: `--limit N` (evenly spaced subset), `--max-len N` (last N
changes only), `--backend python|fast`, `--out PATH`. Resumable: (series, h)
cells already in the output CSV without an error are skipped; rows are flushed
as they finish, so kill and rerun at will.

Summaries and figure (pools every `benchmarks/forecastability_*.csv`):

```
PYTHONPATH=src:benchmarks python benchmarks/forecastability_study.py --summarize
```

## 4. Runtime (measured on an M-series laptop, one core per cell)

Per scored step, including the three KDEs: about 0.7 ms (h=1) to 0.9 ms (h=3)
with `skaters_fast`; about 8 ms (h=1) to 13 ms (h=3) pure Python, rising to
~30 ms at h=13. A 5,400-step FRED series took 3.7 s (h=1) / 4.7 s (h=3) fast,
42 s / 69 s pure Python.

Estimates for all six horizons:

| arm | total steps | fast, CPU-hours | pure Python, CPU-hours |
|---|---|---|---|
| fred | 1.39 M | ~2.5 | ~40 |
| metr-la | ~6.8 M | ~12 | ~190 |
| electricity | ~10 M | ~18 | ~280 |
| m4-daily | ~7 M | ~12 | ~190 |

Divide by cores. Cells are scheduled longest first.

## 5. Outputs and what to send back

- `benchmarks/forecastability_<arm>.csv`: one row per (series, h): `n`,
  `n_scored`, `backend`, `L_unc L_cps L_cpsz L_lap`, `F_hat X_cps X_cpsz left`,
  `secs`, `error`.
- `benchmarks/forecastability_summary.csv`: per arm and horizon, mean, 90%
  bootstrap interval, median and share positive of each derived quantity, and
  the ratios of means `X_cps/F_hat`, `X_cpsz/F_hat` with intervals. The
  bootstrap resamples FRED families (`fred_universe.family`) for `fred` and
  `returns`, series otherwise; sensors and clients are cross-sectionally
  dependent, so those intervals are optimistic.
- `benchmarks/forecastability_profile.png`: per arm, F_hat(h) with X_cps(h)
  and X_cpsz(h) inside it.
- The `.log` files.

Commit all of these to `forecastability-study` and push, or attach them to #250.

## Known issue seen in the smoke test

On `EXCSRESNW` (weekly excess reserves, 818 changes) laplace(3) collapses to a
near-point mass at 0 (sd ~0.001 against a series sd ~0.2) and F_hat at h=3 is
-1.65 nats. That is laplace's multi-step behaviour on this series, not the
scaffold; expect a few negative-F_hat cells, which make the ratio-of-means
unstable on small subsets. Medians are reported for that reason.
