# Issue 133 corrected distillation artifacts

## Status

These are the corrected artifacts for [Issue 133](https://github.com/microprediction/skaters/issues/133). The earlier adapter and score files were removed because they used the wrong TimesFM 2.5 output channels.

Both committed adapters use channel 5 as the mean and channels 0, 1, 2, 3, 4, 6, 7, 8, 9 as q10..q90. They were trained from scratch after the channel defect was corrected.

**Result:** neither corrected adapter improves zero-shot TimesFM or beats Laplace. Retain them as negative research evidence, not as production models.

Read [`../ISSUE133.md`](../ISSUE133.md) for the protocol, results, interpretation, limitations, and commands.

## Context 128

- Teacher records: `teacher_issue133_context128.jsonl.gz`
- Producer manifest: `teacher_issue133_context128_manifest.json`
- Adapter: `timesfm_laplace_qd_context128/`
- Raw q10..q90: `raw_quantiles_issue133_context128.csv`
- Canonical scores: `predictions_issue133_context128.csv`
- Persisted-row summary: `summary_issue133_context128.json`
- Distilled minus zero-shot median dLL: `-0.155385`
- Distilled/zero-shot median CRPS ratio: `1.002855`

## Context 256

- Teacher records: `teacher_issue133_context256.jsonl.gz`
- Producer manifest: `teacher_issue133_context256_manifest.json`
- Adapter: `timesfm_laplace_qd_context256/`
- Raw q10..q90: `raw_quantiles_issue133_context256.csv`
- Canonical scores: `predictions_issue133_context256.csv`
- Persisted-row summary: `summary_issue133_context256.json`
- Distilled minus zero-shot median dLL: `-0.134628`
- Distilled/zero-shot median CRPS ratio: `1.002412`

## Shared files

- `protocol_issue133.json`: source, split, channel, training, density, evaluation, chronology, and limitation contract
- `source_issue133.tar.gz`: deterministic archive of the frozen M4/FRED source bytes
- `SHA256SUMS`: SHA-256 checksums for every other artifact

Each adapter directory contains exactly the two PEFT runtime files, its source/runtime/training manifest, and a model card. The pinned base checkpoint is not duplicated.

## Integrity

```bash
cd benchmarks/distill_artifacts
shasum -a 256 -c SHA256SUMS
```

The teacher producer manifests record canonical JSONL digests independently of gzip bytes. The native pre-projection quantile channels retain 17 significant digits; canonical scores apply the protocol's PAVA ordering repair and use the repository's six-decimal schema. Summaries are derived from the persisted stores.

Each teacher and adapter run manifest keeps `source_tree` as the tree captured by its producer runtime and records the current contribution under `reproducer_source_tree`; the two are intentionally not conflated.
