# Foundation-model studies — setup & running (incl. Mac Studio / MPS)

The studies use separate protocols:

- **Zero-shot** (`foundation_study.py`) — no weight updates; the model conditions
  on a sliding 256-step context window. **Done on CPU; results in the repo.**
- **Per-series fine-tuned** (`foundation_finetune.py`) — fine-tune each model
  on one series, then forecast its held-out window. **GPU/MPS-bound for larger
  models.**
- **Cross-series Laplace distillation** (`laplace_distill.py`,
  `timesfm_distill.py`) — train one TimesFM LoRA adapter on predictive soft
  targets from many complete series, then test on disjoint series.

Every study maps model output to the same `Dist` and canonical prediction
contracts and re-scores `laplace` on identical forecast origins. The original
zero-shot and per-series harnesses merge win-rates with `summarize()`. Studies
that persist per-origin predictions derive paired and Diebold-Mariano summaries
from those stores.

## Why separate conda envs

The four models have mutually conflicting pins (`gluonts`, `torch`, `jax`,
`transformers`). Each gets its own env; the harness writes one
`results_foundation_<tag>.csv` per run and `summarize()` globs them all.

| Model | env | install |
|---|---|---|
| Chronos-Bolt | `skaters-fm` | `pip install chronos-forecasting` |
| Moirai | `skaters-fm` | `pip install uni2ts` |
| Lag-Llama | `skaters-ll` | `pip install git+https://github.com/time-series-foundation-models/lag-llama.git` |
| TimesFM | `skaters-tf` | `pip install "timesfm[torch]"` |

```bash
conda create -y -n skaters-fm python=3.11 && conda activate skaters-fm
pip install numpy pandas torch chronos-forecasting uni2ts
# (repeat for skaters-ll / skaters-tf as above)
```

`skaters` itself is zero-dependency pure Python, imported from source via
`PYTHONPATH=src` — it needs nothing installed.

## Data

The harness reads cached FRED series from `benchmarks/data/` (146 MB, gitignored).
Either copy that directory to the target machine, or set a `FRED_API_KEY` and let
it fetch on first run.

## Running on the Mac Studio (MPS)

Set `FM_DEVICE=mps` (and keep `PYTORCH_ENABLE_MPS_FALLBACK=1`, which the script
exports). First confirm MPS works with a quick zero-shot re-run:

```bash
conda activate skaters-fm && export PYTHONPATH=src
FM_DEVICE=mps FM_N=20 FM_TEST=40 FM_TAG=mps_smoke FM_MODELS=Chronos,Moirai \
  python benchmarks/foundation_study.py
```

If that runs clean, the fine-tune study (below) is the real MPS job.

## Fine-tune study

```bash
# Lag-Llama (skaters-ll) — cleanest fine-tune path, native Student-t
conda activate skaters-ll && export PYTHONPATH=src
FM_DEVICE=mps FM_TAG=ft_ll FM_MODELS=Lag-Llama FT_EPOCHS=20 \
  python benchmarks/foundation_finetune.py

# Moirai (skaters-fm), TimesFM (skaters-tf) — heavier; same pattern, own env+tag
```

Knobs: `FM_N` (series), `FM_TEST` (window), `FM_CTX` (context), `FT_EPOCHS`
(fine-tune epochs per series), `FT_REFIT` (re-fine-tune cadence; default = once
per series). Merge + print the table:

```bash
python benchmarks/foundation_finetune.py summarize
```

> **Finding — don't bother fine-tuning per series.** A small test (Lag-Llama, 5
> epochs, 2 continuous series) showed naive per-series fine-tuning
> **catastrophically overfits**: held-out logpdf collapsed from `+1.5` (zero-shot)
> to `−118`, CRPS got worse, and it ran ~15× slower. Adapting a pretrained model
> to one short univariate stream is not its design regime — zero-shot, or
> domain-level fine-tuning across *many* series, is the intended use. The
> `foundation_finetune.py` harness is kept for completeness, but the zero-shot
> study is the headline and per-series fine-tuning is **not worth GPU time**
> without heavy per-series regularization (which defeats the purpose).

## Cross-series Laplace distillation

Issue #133 tested the domain-level alternative to failed per-series fine-tuning.
The student is TimesFM 2.5 (200M) with a 5.57 MB LoRA adapter. Teacher records
contain the mean, q10–q90, and complete predictive; whole-series splitting keeps
train, validation, and test disjoint.

The first pilot decoded the TimesFM head incorrectly and is invalid. Fresh
context-128 and context-256 adapters use channel 5 as the mean and channels
`[0,1,2,3,4,6,7,8,9]` as q10–q90. The corrected primary result is negative:
distilled minus zero-shot median dLL is **−0.155385**, median CRPS ratio is
**1.002855**, and the adapter wins 0/15 series by LL. Context 256 does not
reverse the decision. Direct Laplace remains the default.

The corrected report, chronology, exact commands, limitations, checksums,
teacher corpora, both fresh adapters, raw quantiles, and canonical predictions
are in [`ISSUE133.md`](ISSUE133.md) and
[`distill_artifacts/`](distill_artifacts/).
