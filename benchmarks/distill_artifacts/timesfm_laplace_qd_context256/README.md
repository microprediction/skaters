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

# TimesFM Laplace q-grid adapter — context 256

Post-hoc sensitivity artifact for Issue #133. It uses the corrected Hugging Face TimesFM output-channel contract and must not replace the primary context-128 result.

## Contract

- Base: `google/timesfm-2.5-200m-transformers`
- Revision: `5a9806b9b291fad9233b5249d88263f1846304d3`
- Point forecast: `mean_predictions`, equivalent to `full_predictions[..., 5]`
- q10–q90: `full_predictions[..., [0,1,2,3,4,6,7,8,9]]`
- Horizon: one step; context: 256 values
- Objective: context-MAD-scaled Huber on teacher mean and q10–q90; realized targets are excluded
- LoRA: rank 4, alpha 8, dropout 0.05, all linear modules; seed 133; two epochs; batch 16

`adapter_config.json` pins the base revision. `run_manifest.json` preserves the training-captured source tree and separately records the current reproducer tree, plus runtime, dependency lock, output-channel contract, selected epoch, and validation loss.

## Result

On the same 15 held-out series and 960 origins:

- adapter minus zero-shot median dLL: **−0.134628**;
- adapter / zero-shot median CRPS ratio: **1.002412**;
- LL wins: **4/15**; CRPS wins: **6/15**;
- DM: **1 adapter / 5 zero-shot / 9 draws**.

The corrected adapter does not improve zero-shot TimesFM at the primary paired median. It loses to full-history Laplace by 0.514246 median dLL and to fixed-context Laplace by 0.488755 median dLL.

## Loading and limitations

Load the pinned base before this PEFT adapter and preserve the channel mapping above. Native pre-projection q10–q90 and uncensored reconstructed log densities are stored separately; reproduce density scores by applying the protocol's row-wise PAVA ordering repair before its validation-frozen mixture reconstruction.

This run is post-hoc, one-seed, MPS-only research evidence on 15 deliberately composed series. It is not a deployment candidate. Central quantiles do not specify explicit tails, pretraining overlap is unresolved, and byte-identical retraining is not claimed because Torch reported a nondeterministic MPS accumulation operation.
