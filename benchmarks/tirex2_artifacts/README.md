# Issue 138 TiRex-2 benchmark artifacts

## Status

This directory contains a completed, reproducible TiRex-2 benchmark contribution for [Issue 138](https://github.com/microprediction/skaters/issues/138). It does **not** identify or reproduce "Table-R1" or "TwbFB"; those identifiers remain unresolved and must be supplied by the issue author.

The protocol was frozen before the full benchmark. Two H1 execution smokes preceded it. A disclosed post-run amendment records the already executed CPU/batch-128 runtime so the runner can reject protocol mismatches; no scientific choice or result changed.

## Protocol

- Model: `NX-AI/TiRex-2`
- Revision: `05e5b26db52bfb256f1ae1bdf785589850482de3`
- Checkpoint SHA-256: `184b160ffbe4c01a26beeba14015ff3507c7497e1f3577114187bbc1d19fcac1`
- Data: first 24 qualifying M4-hourly series in frozen source order
- Forecast: one step, no covariates, context 128
- Splits per series: 64 chronological validation origins, then 64 untouched test origins
- Primary comparator: Laplace reset at every origin and given exactly the same 128-value context
- Secondary comparator: causal online Laplace with up to 1,000 retained values
- TiRex-2 test-time augmentation: sign flip off, differencing off
- Density: q10..q90 reconstructed as a fixed-bandwidth Gaussian mixture; one multiplier selected by validation log score and frozen for test

The validation selector chose multiplier `3.0`, the widest predeclared candidate. Density and extrapolated q05/q95 coverage conclusions therefore depend on a boundary-selected reconstruction. The persisted native quantiles and pinball loss are the model-contract-preserving evidence.

## Test results

All aggregates below are recomputed from persisted rows.

| Method | Equal-series mean logpdf | Equal-series mean CRPS | Central 90% coverage |
|---|---:|---:|---:|
| TiRex-2 | 2.926866 | 0.008710 | 0.960938 |
| Laplace-fixed-context | 2.709418 | 0.011538 | 0.951823 |
| online Laplace | 2.814996 | 0.010226 | 0.915365 |

Primary paired result, TiRex-2 minus matched-context Laplace:

- Median per-series dLL: `+0.195903`
- Mean per-series dLL: `+0.217448`
- Median CRPS ratio: `0.847979`
- Series wins: 22/24 by mean LL and 22/24 by mean CRPS
- Per-series DM record: 15 wins, 9 draws, 0 losses

Secondary result versus full-history online Laplace:

- Median per-series dLL: `+0.089072`
- Median CRPS ratio: `0.870832`
- Per-series DM record: 2 wins, 22 draws, 0 losses

TiRex-2 mean pinball loss across q10..q90 is `0.00464260`.

These results describe only this 24-series M4-hourly panel. Pretraining overlap is unresolved, and the benchmark is not contamination-free generalization evidence.

## Files

- `protocol_issue138.json`: frozen design, chronology, metrics, and limitations
- `predictions_issue138.csv`: 4,608 canonical test score rows (24 series x 64 origins x 3 methods)
- `raw_quantiles_issue138.csv`: 3,072 TiRex-2 validation/test q10..q90 rows at 17 significant digits
- `summary_issue138.json`: persisted-row aggregates and density selection diagnostics
- `run_manifest_issue138.json`: exact execution and current-reproducer source trees, original/current protocol and output hashes, runtime, model, and source hashes
- `source_issue138.tar.gz`: deterministic frozen M4-hourly source archive
- `SHA256SUMS`: checksums for every other file in this directory

## Reproduce

```bash
uv venv .venv-tirex2 --python 3.11
uv pip sync --python .venv-tirex2/bin/python benchmarks/tirex2_requirements.lock

tar -xzf benchmarks/tirex2_artifacts/source_issue138.tar.gz -C /tmp

PYTHONPATH=src:benchmarks \
.venv-tirex2/bin/python benchmarks/tirex2_issue138.py \
  --m4-cache /tmp/issue138_sources/M4-hourly.csv \
  --protocol benchmarks/tirex2_artifacts/protocol_issue138.json \
  --output /tmp/predictions_issue138.csv \
  --raw-quantiles /tmp/raw_quantiles_issue138.csv \
  --summary /tmp/summary_issue138.json \
  --manifest /tmp/run_manifest_issue138.json \
  --source-archive /tmp/source_issue138.tar.gz \
  --series 24 --context 128 --validation 64 --test 64 \
  --max-history 1000 --batch-size 128 --device cpu
```

The pinned model revision is downloaded on the first run. Compare the regenerated predictions, raw quantiles, summary, and source archive against `SHA256SUMS`. Runtime fields in the regenerated run manifest are expected to differ.
