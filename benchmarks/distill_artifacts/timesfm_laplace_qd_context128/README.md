---
base_model: google/timesfm-2.5-200m-transformers
library_name: peft
license: apache-2.0
tags:
- time-series
- timesfm2_5
- peft
- lora
- knowledge-distillation
---

# TimesFM Laplace q-grid adapter — context 128

Research artifact for Issue #133. This is the corrected run; the earlier channel-0 adapter and its scores are invalid and are not retained as evidence.

## Contract

- Base: `google/timesfm-2.5-200m-transformers`
- Revision: `5a9806b9b291fad9233b5249d88263f1846304d3`
- Point forecast: `mean_predictions`, equivalent to `full_predictions[..., 5]`
- q10–q90: `full_predictions[..., [0,1,2,3,4,6,7,8,9]]`
- Horizon: one step; context: 128 values
- Objective: context-MAD-scaled Huber on teacher mean and q10–q90; realized targets are excluded
- LoRA: rank 4, alpha 8, dropout 0.05, all linear modules; seed 133; two epochs; batch 16

`adapter_config.json` pins the base revision. `run_manifest.json` preserves the training-captured source tree and separately records the current reproducer tree, plus runtime, dependency lock, output-channel contract, selected epoch, and validation loss.

## Result

On 15 held-out series and 960 origins, using canonical persisted score rows and a validation-selected density reconstruction:

- adapter minus zero-shot median dLL: **−0.155385**;
- adapter / zero-shot median CRPS ratio: **1.002855**;
- LL wins: **0/15**; CRPS wins: **7/15**;
- DM: **0 adapter / 5 zero-shot / 10 draws**.

The corrected adapter does not improve zero-shot TimesFM. It also loses to full-history Laplace by 0.557136 median dLL and to fixed-context Laplace by 0.510919 median dLL. It is negative research evidence, not a deployment candidate.

## Loading

Load the pinned base model first, then use `PeftModel.from_pretrained(base, this_directory)`. Preserve the channel mapping above. Native pre-projection q10–q90 and uncensored reconstructed log densities are stored separately; reproduce density scores by applying the protocol's row-wise PAVA ordering repair before its validation-frozen mixture reconstruction.

## Limitations

One seed; 15 deliberately composed test series; MPS-only training; no timestamped preregistration; unresolved foundation-model pretraining overlap; central quantiles do not specify explicit tails. Torch warned that an MPS accumulation operation lacks a deterministic implementation, so byte-identical retraining is not claimed. Direct Laplace remains the deployment default.
