# Foundation-model studies — setup & running (incl. Mac Studio / MPS)

Two studies, two protocols:

1. **Zero-shot** (`foundation_study.py`) — no weight updates; the model conditions
   on a sliding 256-step context window. **Done on CPU; results in the repo.**
2. **Fine-tuned** (`foundation_finetune.py`) — fine-tune each model on the
   series' own history, then forecast the held-out window. **GPU/MPS-bound for the
   larger models** — this is the Mac Studio job.

Both score every model through the same `Dist` as the eight-baseline study, and
re-score `laplace` on the identical window. Win-rates merge across runs via
`summarize()`.

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

> **Status:** `foundation_finetune.py` is a first draft validated only for
> import/shape on CPU — the Mac Studio will be the first real MPS/fine-tune run.
> Report any adapter errors and they're quick to fix. Fine-tuning a 200–500M model
> per series is genuinely expensive; start with `FM_N=20` to gauge wall-clock
> before scaling up.
