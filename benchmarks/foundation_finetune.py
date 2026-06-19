"""Fine-tuned foundation-model study (phase 2; companion to foundation_study.py).

Same target and scoring as the zero-shot study, but each model is **fine-tuned on
the series' own history** (the part before the test window) before forecasting the
held-out window. This is the "give them their best shot" comparison; fine-tuning a
200-500M model per series is GPU/MPS-bound, so set FM_DEVICE=mps on a Mac Studio.

Reuses the zero-shot harness's data, scoring, Dist helpers and laplace baseline.
Writes results_finetune_<tag>.csv per run; summarize() merges them.

Status: first draft, validated for import/shape on CPU. See benchmarks/FOUNDATION.md.
Run:  FM_DEVICE=mps FM_TAG=ft_ll FM_MODELS=Lag-Llama python benchmarks/foundation_finetune.py
"""
from __future__ import annotations
import os, sys, time, warnings, glob, csv, collections
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import fred
import foundation_study as Z          # shared machinery
from foundation_study import (TEST, CTX, NUM_SAMPLES, DEVICE, sample_dist,
                              score_steps, laplace_scores, load_series)

_HERE = os.path.dirname(os.path.abspath(__file__))
FM_TAG = os.environ.get("FM_TAG", "ft")
RESULTS = os.path.join(_HERE, f"results_finetune_{FM_TAG}.csv")
FT_EPOCHS = int(os.environ.get("FT_EPOCHS", 20))   # fine-tune epochs per series


def _accel():
    return {"mps": "mps", "cuda": "gpu"}.get(DEVICE, "cpu")


# ---------------------------------------------------------------- adapters
def lagllama_ft_dists(ch):
    """Fine-tune Lag-Llama on the series history, then forecast the test window."""
    try:
        import torch, pandas as pd
        from gluonts.dataset.pandas import PandasDataset
        from huggingface_hub import hf_hub_download
        _orig = torch.load
        torch.load = lambda *a, **k: _orig(*a, **{**k, "weights_only": False})
        from lag_llama.gluon.estimator import LagLlamaEstimator
        n = len(ch); start = n - TEST
        ckpt = hf_hub_download(repo_id="time-series-foundation-models/Lag-Llama",
                               filename="lag-llama.ckpt")
        args = torch.load(ckpt, map_location="cpu")["hyper_parameters"]["model_kwargs"]
        train_ds = PandasDataset({"s": pd.DataFrame(
            {"target": np.asarray(ch[:start], np.float32)},
            index=pd.date_range("2000-01-01", periods=start, freq="D"))}, target="target")
        est = LagLlamaEstimator(
            ckpt_path=ckpt, prediction_length=1, context_length=CTX,
            input_size=args["input_size"], n_layer=args["n_layer"],
            n_embd_per_head=args["n_embd_per_head"], n_head=args["n_head"],
            scaling=args["scaling"], time_feat=args["time_feat"],
            batch_size=64, num_parallel_samples=NUM_SAMPLES,
            trainer_kwargs={"max_epochs": FT_EPOCHS, "accelerator": _accel(),
                            "devices": 1, "enable_progress_bar": False,
                            "enable_model_summary": False, "logger": False})
        predictor = est.train(train_ds, cache_data=True)
        frames = {str(k): pd.DataFrame(
            {"target": np.asarray(ch[t - CTX:t], np.float32)},
            index=pd.date_range("2000-01-01", periods=CTX, freq="D"))
            for k, t in enumerate(range(start, n))}
        fc = list(predictor.predict(PandasDataset(frames, target="target"),
                                    num_samples=NUM_SAMPLES))
        out = [None] * TEST
        for f in fc:
            out[int(f.item_id)] = sample_dist(f.samples[:, 0])
        return out
    except Exception as e:                  # noqa: BLE001
        print(f"  lag-llama(ft) failed: {e}", flush=True); return None


# Moirai / TimesFM / Chronos fine-tuning use each library's own finetune recipe
# (uni2ts MoiraiFinetune lightning module; timesfm finetuning; chronos train
# script). They are heavier; add here once the Lag-Llama path is confirmed on MPS.
_ALL = [("Lag-Llama", lagllama_ft_dists)]
_SEL = os.environ.get("FM_MODELS", "")
MODELS = [(n, f) for n, f in _ALL if not _SEL or n in _SEL.split(",")]


def run():
    series = load_series(); sids = list(series)
    print(f"FINETUNE: {len(sids)} series; TEST={TEST} CTX={CTX} epochs={FT_EPOCHS} "
          f"device={DEVICE}", flush=True)
    with open(RESULTS, "w") as fh:
        w = csv.writer(fh); w.writerow(["series", "method", "logpdf", "crps", "n"])
        for j, sid in enumerate(sids):
            ch = series[sid]; y = ch[len(ch) - TEST:]
            lp, cr = laplace_scores(ch)
            w.writerow([sid, "laplace", f"{lp:.6f}", f"{cr:.6f}", TEST])
            for name, fn in MODELS:
                t0 = time.time()
                dists = fn(ch)
                if dists is not None and all(d is not None for d in dists):
                    a, b = score_steps(dists, y)
                    w.writerow([sid, f"{name}-ft", f"{a:.6f}", f"{b:.6f}", TEST])
                print(f"  {sid} {name}-ft {time.time()-t0:.1f}s", flush=True)
            fh.flush()
    summarize()


def summarize():
    by = collections.defaultdict(dict)
    for path in sorted(glob.glob(os.path.join(_HERE, "results_finetune_*.csv"))):
        for r in csv.DictReader(open(path)):
            by[r["series"]][r["method"]] = (float(r["logpdf"]), float(r["crps"]))

    def rfrac(sid):
        ch = fred._to_changes(fred._load_levels(sid) or [])[-TEST:]
        return sum(1 for i in range(1, len(ch)) if ch[i] == ch[i - 1]) / max(len(ch) - 1, 1)
    cont = {s for s in by if rfrac(s) < 0.05}
    methods = sorted({m for d in by.values() for m in d if m != "laplace"})
    print(f"\n=== Fine-tuned foundation study: {len(by)} series "
          f"({len(cont)} continuous) ===")
    print(f"  {'model':16s}{'LL all/cont':>14s}{'CRPS all/cont':>16s}{'n':>6s}")

    def wr(m, subset, idx, lower=False):
        sub = [by[s] for s in subset if m in by[s] and "laplace" in by[s]]
        if not sub:
            return float("nan")
        if lower:
            w = sum(1 for d in sub if d["laplace"][idx] < d[m][idx])
        else:
            w = sum(1 for d in sub if d["laplace"][idx] > d[m][idx])
        return 100.0 * w / len(sub)

    for m in methods:
        n = sum(1 for s in by if m in by[s])
        ll = f"{wr(m, set(by), 0):.0f}/{wr(m, cont, 0):.0f}%"
        cp = f"{wr(m, set(by), 1, True):.0f}/{wr(m, cont, 1, True):.0f}%"
        print(f"  {m:16s}{ll:>14s}{cp:>16s}{n:>6d}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        summarize()
    else:
        run()
