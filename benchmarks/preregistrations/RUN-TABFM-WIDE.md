# Running the TabFM wide study on the Mac Studio

The pre-registered study is `2026-07-09-tabfm-wide.md`; the harness is
`benchmarks/tabfm_wide_study.py`. Everything below assumes the repo root.

## One-time setup

1. `git pull` first. The MPS float64 shim landed 2026-07-10; without it
   `TB_DEVICE=mps` crashes on the tabfm wrapper's float64 arrays.
2. Environment: python 3.11 with torch, scikit-learn, scipy, pandas, and
   `pip install --no-deps tabfm` plus `pip install "typeguard<3"`. Cloning
   the laptop's `skaters-fm` conda env works; torch 2.4.1 is known good.
3. Weights: the pip loader wants `pytorch_model.bin` but the HF repo ships
   safetensors. Convert once (downloads ~13 GB from
   `google/tabfm-1.0.0-pytorch`, then writes `~/.cache/tabfm_bin`):

   ```python
   import os, torch
   from huggingface_hub import snapshot_download
   from safetensors.torch import load_file
   snap = snapshot_download(repo_id="google/tabfm-1.0.0-pytorch")
   out = os.path.expanduser("~/.cache/tabfm_bin")
   for kind in ("classification", "regression"):
       os.makedirs(os.path.join(out, kind), exist_ok=True)
       sd = load_file(os.path.join(snap, kind, "model.safetensors"))
       torch.save(sd, os.path.join(out, kind, "pytorch_model.bin"))
   ```

4. Data: `benchmarks/data` must hold the FRED cache (2,600+ csv files plus
   `universe_daily.json`). If the Studio checkout lacks it, copy the
   directory from the laptop; the frozen universe file only names series,
   the csvs carry the values.

## The run

```bash
TB_DEVICE=mps PYTHONPATH=src python benchmarks/tabfm_wide_study.py
```

- If mps misbehaves, drop `TB_DEVICE` (cpu is the default) at roughly 2.5x
  the wall-clock.
- Expected scale: 226 series x 14 methods. At the 16 GB laptop's mps pace
  (382s classifier pass + 39s regressor pass per series) the whole thing is
  ~26 hours; the Studio should do better.
- The two passes load one 6.5 GB checkpoint at a time (classifier first,
  then regressor). Peak process memory stays under ~10 GB.

## Resume, kill, monitor

- Kill it any time (`kill -9` included); rerunning the same command skips
  every finished (series, arm) pair. This was kill-tested.
- Progress: `tail -f` the console, or count rows in
  `benchmarks/results_tabfm_wide.csv`.
- Interim summary any time:
  `PYTHONPATH=src python benchmarks/tabfm_wide_study.py summarize`
- `results_tabfm_wide.csv` and `results_tabfm_wide_mae.csv` are the resume
  state. Do not sync or commit them mid-run from any machine; commit them
  from the Studio when the run ends (they are gitignored, use `git add -f`).

## When the run starts

Record in the Deviations section of `2026-07-09-tabfm-wide.md`: device
(mps or cpu), `torch.__version__`, and the first logged per-series timing.
Before any result is read. Committing that note from the Studio is fine, or
ask the session on the laptop to do it.

## If something looks wrong

Do not edit arms, universe, or scoring; the statement freezes them. Log the
problem and the fix in the Deviations section with the date. A partial
weekend is fine by design: the run order interleaves strata, and the
analysis plan already covers truncation.
