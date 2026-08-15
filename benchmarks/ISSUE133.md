# Issue 133: corrected Laplace-to-TimesFM distillation

## Status and decision

This contribution implements and audits the experiment requested in [Issue 133](https://github.com/microprediction/skaters/issues/133).

**Measured decision:** the corrected q-grid LoRA does not improve zero-shot TimesFM and does not beat Laplace. Keep both corrected adapters only as negative, reproducible research evidence. Direct `laplace` remains the deployment default.

The earlier pilot result is invalid. It trained on the wrong TimesFM output channels by interpreting channel 0 as the mean and channels 1..9 as q10..q90. The pinned TimesFM 2.5 contract instead uses:

- channel 5: mean;
- channels 0, 1, 2, 3, 4, 6, 7, 8, 9: q10..q90.

No score, adapter, or claim from that pilot is retained. The artifacts in `distill_artifacts/` come from two fresh corrected training runs.

## Questions answered

1. Can online Laplace predictives produce a causal teacher corpus? **Yes.**
2. Can the native TimesFM quantile head be adapted to teacher mean plus q10..q90? **Yes.**
3. Does the corrected adapter transfer to held-out series? **Not beneficially in this panel.**
4. Does it improve held-out LL or CRPS over zero-shot TimesFM? **No.**
5. Does it match Laplace under equal or unequal context? **No.**
6. Should it replace direct Laplace? **No.**

## Implementation contract

The benchmark-only implementation remains outside the zero-dependency package:

- `laplace_distill.py` builds and audits causal teacher records;
- `timesfm_distill.py` trains, evaluates, reconstructs density, and persists raw/canonical predictions;
- `distill_requirements.lock` freezes the deep-learning runtime;
- `tests/test_laplace_distill.py` and `tests/test_timesfm_distill.py` defend chronology, producer provenance, output-channel decoding, target exclusion, density selection, persistence, and adapter size.

Each teacher record contains its series/regime/split/origin, a context ending immediately before the realized target, that target, the teacher mean and q10..q90, and the complete serialized Laplace predictive. Whole-series split assignment prevents the same series from crossing train, validation, and test. Adjacent rows must exhibit the complete one-step context shift.

The consumer reruns the full teacher audit before training and evaluation. The realized `y` is excluded from `_teacher_targets`; it is used only for held-out scoring.

## Frozen data

Both contexts use the same 56 series and whole-series assignment:

| split | rows | series |
|---|---:|---:|
| train | 2,240 | 35 |
| validation | 384 | 6 |
| test | 960 | 15 |

The panel combines 24 deterministic synthetic series, 24 M4-hourly series, and 8 frozen FRED-core series. Context-128 and context-256 corpora are generated separately from the same source snapshot. Their canonical record digests are:

- context 128: `20d44cc31d9d860ac9d56daa5cac40962c712469ba005b89eda806d0df58f9c2`;
- context 256: `13559dd8b286c4b6f135d9eaf96bf08663b429d38f75020cf605bec14e546a12`.

`source_issue133.tar.gz` freezes the exact M4 and FRED source bytes. Teacher and adapter manifests preserve the source tree captured by their producer runtime separately from the current contribution/reproducer tree, alongside runtime versions, source contracts, settings, and the student output-channel contract.

## Student and training

- Base model: `google/timesfm-2.5-200m-transformers`
- Revision: `5a9806b9b291fad9233b5249d88263f1846304d3`
- Base checkpoint SHA-256: `b53f6d52114e2ad786890f3c4637ce05f580b7800d6e24401f88b398b76035ef`
- Horizon: one step
- Target: teacher mean plus q10..q90
- Objective: context-MAD-scale Huber, NumPy-linear median
- LoRA: rank 4, alpha 8, dropout 0.05, all linear modules
- Seed: 133
- Epochs: 2, batch 16, learning rate 0.0001

Separate adapters were trained for context 128 and context 256. The context-128 run selected epoch 2; context 256 selected epoch 1. Each runtime adapter is exactly two PEFT files totaling 5,566,182 bytes. The base checkpoint is not duplicated.

Torch reported that an MPS accumulation operation has no deterministic implementation. Frozen adapter evaluation is byte-reproducible on this workstation; byte-identical retraining is not claimed.

## Density reconstruction

TimesFM supplies nine central quantile channels, not a native likelihood or explicit tails. For canonical LL/CRPS scoring, each native q10..q90 row is first ordered by PAVA isotonic projection, then reconstructed as a fixed-bandwidth Gaussian mixture.

One global spacing multiplier was selected solely on the 384 validation rows by equal-series mean logpdf with a -20 floor. Candidate multipliers were `0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3`; validation selected `2.0`. That multiplier was frozen for both corrected test evaluations.

The native, pre-projection q10..q90 channels are persisted at 17 significant digits. Crossings occur in 960/960 zero-shot and 958/960 distilled context-128 rows, and all 960 rows of both context-256 methods. Canonical scores apply the declared PAVA repair, are persisted at six decimals, and are reloaded before summaries are reported. The sidecars therefore preserve the model head exactly while density metrics describe explicit post-processing, not a native TimesFM density.

## Corrected held-out results

All methods score the same 960 test targets. `Laplace-fixed-context` resets per origin and receives exactly the same context as TimesFM. Lower-case `laplace` is the causal online forecaster with its retained history and is therefore an unequal-information deployment comparator.

### Context 128

| method | equal-series mean LL | equal-series mean CRPS |
|---|---:|---:|
| online Laplace | 2.261238 | 0.240799 |
| Laplace fixed context | 2.236675 | 0.238599 |
| zero-shot TimesFM | 1.661515 | 0.245274 |
| corrected distilled TimesFM | 1.458529 | 0.244720 |

Corrected distilled minus zero-shot TimesFM:

- median dLL: `-0.155385`;
- median CRPS ratio: `1.002855`;
- LL wins: 0/15;
- CRPS wins: 7/15;
- LL DM record: 0 wins, 10 draws, 5 losses.

Corrected distilled minus matched-context Laplace:

- median dLL: `-0.510919`;
- median CRPS ratio: `1.038273`;
- LL wins: 0/15;
- CRPS wins: 4/15;
- LL DM record: 0 wins, 4 draws, 11 losses.

Against full-history online Laplace, the corrected adapter loses all 15 series by mean LL and 13/15 by mean CRPS; the median dLL is `-0.557136`.

### Context 256 sensitivity

| method | equal-series mean LL | equal-series mean CRPS |
|---|---:|---:|
| online Laplace | 2.261238 | 0.240799 |
| Laplace fixed context | 2.211666 | 0.241104 |
| zero-shot TimesFM | 1.559731 | 0.249222 |
| corrected distilled TimesFM | 1.462480 | 0.249533 |

Corrected distilled minus zero-shot TimesFM:

- median dLL: `-0.134628`;
- median CRPS ratio: `1.002412`;
- LL wins: 4/15;
- CRPS wins: 6/15;
- LL DM record: 1 win, 9 draws, 5 losses.

Corrected distilled minus matched-context Laplace:

- median dLL: `-0.488755`;
- median CRPS ratio: `1.035595`;
- LL wins: 1/15;
- CRPS wins: 3/15;
- LL DM record: 0 wins, 3 draws, 12 losses.

Context 256 does not reverse the decision.

## Controls and interpretation

With the validation-frozen multiplier, the teacher q-grid oracle remains close
to complete Laplace: median dLL `+0.000498` and median CRPS ratio `0.998405`.
The exact teacher GMM body is similarly close (`+0.003764`, `0.998025`).
Thus, the corrected panel does not identify q-grid reconstruction as the main
measured deficit. The adapted mean/quantile outputs themselves failed to
transfer beneficially. A native mixture-density head would preserve explicit
tail semantics, but these results do not show that it would fix this student.

This is a negative result, not evidence that distillation is impossible. It establishes that this small q-grid LoRA, one seed, and this 15-series test do not justify replacing Laplace.

## Cost

Measured on the Apple M4 workstation:

| item | context 128 | context 256 |
|---|---:|---:|
| corrected training | 214.11 s | 184.77 s |
| zero-shot evaluation | 6.43 s | 11.25 s |
| adapter evaluation | 6.24 s | 11.33 s |
| fixed-context Laplace evaluation | 35.88 s | 69.64 s |
| adapter runtime bytes | 5,566,182 | 5,566,182 |

The TimesFM base checkpoint is 925,187,448 bytes. Direct Laplace needs neither that checkpoint nor Torch/Transformers/PEFT serving infrastructure.

## Reproduce

Verify artifact integrity and teacher chronology:

```bash
cd benchmarks/distill_artifacts
shasum -a 256 -c SHA256SUMS
cd ../..

PYTHONPATH=src:benchmarks python3 benchmarks/laplace_distill.py \
  --audit benchmarks/distill_artifacts/teacher_issue133_context128.jsonl.gz \
  --context 128

PYTHONPATH=src:benchmarks python3 benchmarks/laplace_distill.py \
  --audit benchmarks/distill_artifacts/teacher_issue133_context256.jsonl.gz \
  --context 256

PYTHONPATH=src:benchmarks python3 -m pytest -q \
  tests/test_laplace_distill.py tests/test_timesfm_distill.py
```

Create the pinned model environment:

```bash
uv venv .venv-distill --python 3.11
uv pip sync --python .venv-distill/bin/python benchmarks/distill_requirements.lock
```

Re-evaluate a frozen adapter without overwriting committed artifacts:

```bash
PYTHONPATH=src:benchmarks HF_HUB_OFFLINE=1 \
.venv-distill/bin/python benchmarks/timesfm_distill.py evaluate \
  --data benchmarks/distill_artifacts/teacher_issue133_context128.jsonl.gz \
  --adapter benchmarks/distill_artifacts/timesfm_laplace_qd_context128 \
  --revision 5a9806b9b291fad9233b5249d88263f1846304d3 \
  --output /tmp/predictions_issue133_context128.csv \
  --quantiles-output /tmp/raw_quantiles_issue133_context128.csv \
  --summary /tmp/summary_issue133_context128.json \
  --batch-size 32
```

The context-256 command changes the three context-specific paths. Frozen evaluation reproduces the canonical prediction CSV byte-for-byte. Runtime fields are not scientific outputs and may differ.

## Frozen artifacts

`benchmarks/distill_artifacts/` contains:

- both causal teacher corpora and producer manifests;
- both corrected PEFT adapters and training manifests;
- raw q10..q90 and canonical prediction stores for both contexts;
- independent persisted-row summaries;
- the protocol, deterministic source archive, and checksums.

The top-level artifact README lists every file and its role.

## Limitations

1. One seed, 15 held-out series, and 64 origins per series.
2. Context 128 is the corrected primary configuration but was not independently preregistered; context 256 is a corrected sensitivity run.
3. Foundation-model pretraining overlap with the FRED/M4 panel is unresolved.
4. Central quantiles omit explicit tail laws and cross before ordering repair on almost every TimesFM row; reconstructed LL depends on the declared PAVA and validation-frozen density convention.
5. Full-history Laplace and fixed-context TimesFM are not equal-information comparisons; the matched-context Laplace row addresses that gap.
6. MPS retraining is not claimed byte-deterministic.
7. No native GMM/GPD student head was implemented.
8. FRED upstream data can change; the committed source archive, not a later live fetch, defines this run.

## Conclusion

The corrected experiment completes the causal teacher-to-student-to-canonical-score path and produces auditable negative evidence. The q-grid LoRA underperforms zero-shot TimesFM and both Laplace comparisons at context 128; context 256 does not rescue it. Direct Laplace remains smaller, operationally simpler, and more accurate in this test.
