# Issue 138: TiRex-2 challenger benchmark

## Status

This contribution adds a runnable TiRex-2 challenger and completes a held-out benchmark relevant to [Issue 138](https://github.com/microprediction/skaters/issues/138).

It does **not** identify or reproduce "Table-R1" or "TwbFB". Neither identifier is defined in the issue, repository, inspected TiRex-2 sources, model card, or public searches performed on 2026-07-28. The issue author must provide a paper/table URL or citation for Table-R1 and an exact repository/model/checkpoint for TwbFB before either claim can be tested.

The completed contribution is therefore:

1. a normal challenger registration for public TiRex-2;
2. a frozen-source, persisted-row TiRex-2 versus Laplace benchmark;
3. an explicit request for the two missing identifiers.

It is not sufficient evidence to close every question implied by the original issue.

## Public model contract

- Package: `tirex-2==0.1.1`
- Model: [`NX-AI/TiRex-2`](https://huggingface.co/NX-AI/TiRex-2)
- Revision: `05e5b26db52bfb256f1ae1bdf785589850482de3`
- Checkpoint SHA-256: `184b160ffbe4c01a26beeba14015ff3507c7497e1f3577114187bbc1d19fcac1`
- Checkpoint bytes: 380,613,375
- API: `load_model(...).forecast(...)`
- Native output: q10..q90 with shape `[target, quantile, horizon]`

`arm_adapters.py` registers `TiRex-2` in the normal challenger registry. It constructs one univariate `TimeseriesType` per context, pins the model revision, disables both test-time augmentations, verifies the checkpoint's quantile levels, and rejects nonfinite or crossing outputs.

The dedicated `tirex2_issue138.py` runner persists native quantiles before reconstructing a density. Deep dependencies remain outside the core package and are pinned in `tirex2_requirements.lock`.

## Frozen protocol

The full protocol was frozen in `tirex2_artifacts/protocol_issue138.json` before the 24-series run. Two H1 execution smokes (2 and 128 final origins) preceded that file; they verified adapter execution and throughput only. This chronology is disclosed rather than presented as independent preregistration.

On 2026-07-28 after review, the file was amended to encode the already executed CPU device and batch 128 so the runner can reject runtime/protocol mismatches. The amendment changes no model, data, split, TTA, density, metric, or result choice. The runner now validates all execution-defining fields, including horizon, quantile grid, TTA, device, batch, source contract, and density candidates.

| field | value |
|---|---|
| source | frozen M4 hourly training CSV |
| selection | first 24 qualifying series in source order, H1..H24 |
| transformation | repository causal level-to-change transform |
| retained history | final 1,000 changes per series |
| context | 128 changes |
| horizon | one step |
| validation | 64 origins per series immediately before test |
| test | final 64 origins per series |
| covariates | none |
| sign-flip TTA | off |
| differencing TTA | off |
| device | CPU |
| batch | 128 |

The source file is frozen at SHA-256 `ea59b7783573c49077a835ab6465c7d66f1474783360f310988a9a737fbca62f`. `source_issue138.tar.gz` is a deterministic archive of those exact bytes.

Each context ends immediately before its realized target. Validation and test are chronological and disjoint.

## Comparators

- **TiRex-2:** native q10..q90 after exactly 128 preceding changes.
- **Laplace-fixed-context:** fresh Laplace state at every origin, updated with exactly the same 128 changes. This is the primary equal-information comparator.
- **online Laplace:** one causal state per series with up to the retained 1,000-change history. This is a secondary deployment comparator, not an equal-information comparison.

## Density and proper scores

TiRex-2 does not expose a native likelihood or explicit tails. Its ordered q10..q90 are reconstructed as a fixed-bandwidth Gaussian mixture for canonical LL, CRPS, and extrapolated q05/q95 coverage.

One global spacing multiplier was selected only from the 1,536 validation rows by equal-series mean logpdf with a -20 floor. The predeclared candidates were `0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3`; validation selected `3.0`.

That selection is at the widest boundary of the candidate grid. Reconstructed-density and q05/q95 coverage conclusions are therefore convention-dependent. The native q10..q90 and mean pinball loss are the model-contract-preserving evidence. All 3,072 validation/test quantile rows are persisted at 17 significant digits.

Canonical prediction rows use the shared `predictions.py` schema. Summaries reload that six-decimal CSV; quantile summaries reload the raw-quantile CSV.

## Held-out results

The test contains 24 series x 64 origins = 1,536 targets. The canonical store contains 4,608 rows across three methods.

| method | equal-series mean LL | equal-series mean CRPS | central 90% coverage |
|---|---:|---:|---:|
| TiRex-2 | 2.926866 | 0.008710 | 0.960938 |
| Laplace-fixed-context | 2.709418 | 0.011538 | 0.951823 |
| online Laplace | 2.814996 | 0.010226 | 0.915365 |

### Primary: TiRex-2 versus matched-context Laplace

- Median per-series dLL: `+0.195903`
- Mean per-series dLL: `+0.217448`
- Median CRPS ratio: `0.847979`
- Mean-LL series wins: 22/24
- Mean-CRPS series wins: 22/24
- Per-series LL DM record: 15 wins, 9 draws, 0 losses

### Secondary: TiRex-2 versus online Laplace

- Median per-series dLL: `+0.089072`
- Mean per-series dLL: `+0.111870`
- Median CRPS ratio: `0.870832`
- Mean-LL series wins: 19/24
- Mean-CRPS series wins: 22/24
- Per-series LL DM record: 2 wins, 22 draws, 0 losses

TiRex-2 mean pinball loss across q10..q90 is `0.00464260`.

The result is favorable on this small panel. It is not population-wide or contamination-free evidence.

## Runtime and reproducibility

Measured on the Apple M4 CPU runtime:

- TiRex-2 inference: 166.40 s for 3,072 validation/test contexts;
- total benchmark: 265.69 s, including density selection, both Laplace paths, persistence, hashing, and summaries;
- checkpoint: 380,613,375 bytes, downloaded separately;
- canonical rows, raw quantiles, deterministic source archive, and the pre-amendment summary reproduced byte-for-byte in complete reruns; the current summary differs only by the disclosed embedded runtime-protocol metadata.

The run manifest preserves the completed execution's local source tree and original protocol/output hashes, and separately records the reviewed reproducer tree plus current amended protocol/output hashes. It also records Python/platform/dependency versions, model/config hashes, source hashes, panel IDs, and timings.

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

PYTHONPATH=src:benchmarks .venv-tirex2/bin/python -m pytest -q \
  tests/test_tirex2_issue138.py

cd benchmarks/tirex2_artifacts
shasum -a 256 -c SHA256SUMS
```

The first run downloads the pinned checkpoint. Runtime fields in a regenerated run manifest will differ; prediction, raw-quantile, summary, and source-archive hashes should match.

## Limitations

1. Only 24 M4-hourly series and 64 test origins per series.
2. Only univariate, one-step, no-covariate forecasts.
3. Pretraining overlap is unresolved. The TiRex-2 model card lists broad public time-series corpora, so this benchmark cannot establish contamination-free generalization.
4. Density LL/CRPS and q05/q95 coverage depend on a validation-selected reconstruction, and the selected bandwidth is at the candidate boundary.
5. Online Laplace receives more history than TiRex-2; only the reset comparator is equal-information.
6. The protocol is repository-local, not independently timestamped, and two execution smokes preceded it.
7. Table-R1 and TwbFB remain unidentified and untested.

## Request to the issue author

Please provide all of the following before a Table-R1/TwbFB comparison is claimed:

- the exact Table-R1 paper/report URL and table number;
- the TwbFB repository, package, model ID, and immutable checkpoint revision;
- expected inputs, outputs, context, horizon, covariates, and any test-time adaptation;
- the intended source panel/split and score definitions.

Until then, this contribution supports a public TiRex-2 challenger result only.
