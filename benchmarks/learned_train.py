"""Train the learned expert of skaters.torch.learned (#297 step 3).

Prequential training, per series, with truncated backprop through time.
The forecast for y_t is issued with the parameters as they stand before y_t
arrives; y_t is scored against it; the window's loss is backpropagated and the
parameters move only at the window boundary, after which the state is
detached (values carry on, the graph does not). The objective is the learned
expert's own log score at the realised outcome, summed over horizons 1..k:
the Aggregating-Algorithm mixture around it is the safety wrapper and needs
no training. After every optimizer step `project_()` returns the transform
parameters to their valid regions.

Series come from the canonical corpus (benchmarks/preds/_corpus_<arm>.jsonl),
the train half of the family split (learned_split.split_of); scoring on the
validation half goes through run_arm.py with ARM_SPLIT=valid and the
`learned` / `learned-expert` arms (LEARNED_CKPT points at the checkpoint).

    LT_CORPUS=weekly LT_MAX=200 LT_K=1 LT_EPOCHS=1 LT_WINDOW=64 LT_LR=1e-3 \
    LT_OUT=benchmarks/learned_ckpt/weekly_k1.pt \
    PYTHONPATH=src:benchmarks .venv-kumo/bin/python benchmarks/learned_train.py

A checkpoint is written every LT_CKPT_EVERY series (default 25) and at the
end of each epoch, atomically; LT_RESUME=<ckpt> continues from the series it
stopped at, with the optimizer state. LT_SHUFFLE=1 (default) orders the
series by a seeded shuffle so families mix within the pass.

Reports, per epoch, the mean learned-expert log score against the frozen
laplace's on the same steps (the two experts inside the model), so the
training signal is read next to its floor. This number is in-sample; the
validation number is the harness's.
"""
from __future__ import annotations

import copy
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch  # noqa: E402

from learned_split import split_of  # noqa: E402
import run_arm as ra  # noqa: E402
from skaters.torch.learned import LearnedLaplace, detach_state  # noqa: E402

CORPUS = os.environ.get("LT_CORPUS", "weekly")
MAX = int(os.environ.get("LT_MAX", 200))
K = int(os.environ.get("LT_K", 1))
EPOCHS = int(os.environ.get("LT_EPOCHS", 1))
WINDOW = int(os.environ.get("LT_WINDOW", 64))
LR = float(os.environ.get("LT_LR", 1e-3))
CLIP = float(os.environ.get("LT_CLIP", 1.0))
PI_LAP = float(os.environ.get("LT_PI", 0.5))
OUT = os.environ.get("LT_OUT", f"benchmarks/learned_ckpt/{CORPUS}_k{K}.pt")
SEED = int(os.environ.get("LT_SEED", 0))
CKPT_EVERY = int(os.environ.get("LT_CKPT_EVERY", 25))     # series between checkpoints
SNAP_EVERY = int(os.environ.get("LT_SNAP_EVERY", 0))      # keep a numbered snapshot every N series (0 = off)
# running weight average (stochastic weight averaging): every LT_SWA_EVERY series
# after LT_SWA_START, fold the current weights into a running mean and save it
# as <out>_swa.pt. Averaging along the path removes the drift a constant
# learning rate leaves in any single snapshot.
SWA_EVERY = int(os.environ.get("LT_SWA_EVERY", 0))
SWA_START = int(os.environ.get("LT_SWA_START", 0))
RESUME = os.environ.get("LT_RESUME", "")                   # checkpoint to continue from
SHUFFLE = int(os.environ.get("LT_SHUFFLE", 1))             # seeded order so families mix
HIST = ra.aa.fs.HIST
FLOOR = -20.0


def train_series():
    # LT_BASE=0 skips the base corpus, so a run trains on LT_EXTRA alone (one
    # shard of a sharded run whose weights are averaged afterwards)
    if os.environ.get("LT_BASE", "1") == "0":
        series = []
    else:
        series = [(sid, title, ch) for sid, title, ch in ra.iter_series(CORPUS)
                  if ra.regime(title) == "econ" and split_of(sid) == "train"]
        series = [x for x in series if len(x[2][-HIST:]) >= ra.MINLEN]
    # LT_EXTRA: comma list of extra corpora used whole for training (never
    # validated on), e.g. weekly-aug from weekly_augment.py (leak-checked)
    for extra in [e for e in os.environ.get("LT_EXTRA", "").split(",") if e]:
        mn = int(os.environ.get("LT_EXTRA_MINLEN", ra.MINLEN))   # training needs no scoring window
        add = [x for x in ra.iter_series(extra) if ra.regime(x[1]) == "econ"
               and len(x[2][-HIST:]) >= mn]
        print(f"[learned_train] + {len(add)} training series from {extra}", flush=True)
        series += add
    if SHUFFLE:
        import random
        random.Random(SEED).shuffle(series)
    return series[:MAX] if MAX else series


def save(model, opt, series, epoch, done, history, path=OUT):
    torch.save({"state_dict": model.state_dict(), "opt_state": opt.state_dict(),
                "k": K, "pi_lap": PI_LAP, "corpus": CORPUS, "n_series": len(series),
                "window": WINDOW, "lr": LR, "epochs": epoch, "done": done, "history": history,
                "series": [sid for sid, _, _ in series], "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "swa": _SWA if _SWA["avg"] is not None else None},   # so LT_RESUME keeps the running average
               path + ".tmp")
    os.replace(path + ".tmp", path)


_SWA = {"n": 0, "avg": None}
_SKIPS = {"series": 0, "windows": 0}   # robustness counters, printed per epoch


def swa_update(model):
    sd = model.state_dict()
    if _SWA["avg"] is None:
        _SWA["avg"] = {k: v.detach().clone() for k, v in sd.items()}
        _SWA["n"] = 1
        return
    _SWA["n"] += 1
    for k, v in sd.items():
        if torch.is_tensor(v) and v.is_floating_point():
            _SWA["avg"][k] += (v.detach() - _SWA["avg"][k]) / _SWA["n"]


def save_swa(model, series, epoch, done, history):
    path = (OUT[:-3] if OUT.endswith(".pt") else OUT) + "_swa.pt"
    torch.save({"state_dict": _SWA["avg"], "k": K, "pi_lap": PI_LAP, "corpus": CORPUS,
                "n_series": len(series), "window": WINDOW, "lr": LR, "epochs": epoch, "done": done,
                "history": history, "swa_n": _SWA["n"], "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")},
               path + ".tmp")
    os.replace(path + ".tmp", path)


def _train_series(model, opt, ch, tot_lrn, tot_lap, n_scored):
    """Prequential truncated-BPTT pass over one series; returns the running totals.
    A window whose gradient is not finite is skipped (no optimizer step)."""
    state = None
    pend = []                       # learned-expert dists issued earlier (graph kept)
    pend_lap = []
    loss = torch.zeros((), dtype=torch.float64)
    steps_in_window = 0
    for t, y in enumerate(ch):
        # score matured forecasts for y_t (issued h steps earlier), horizons 1..k
        for h in range(1, K + 1):
            if len(pend) >= h and math.isfinite(y):
                lp = pend[-h][h - 1].logpdf(y)
                lp = torch.clamp(lp, min=FLOOR) if torch.isfinite(lp) else torch.as_tensor(FLOOR, dtype=torch.float64)
                loss = loss - lp
                lpl = float(pend_lap[-h][h - 1].logpdf(y))
                tot_lrn += float(lp); tot_lap += max(lpl, FLOOR) if math.isfinite(lpl) else FLOOR
                n_scored += 1
        dists, state = model(y, state)
        # the experts' own forecasts are the last entry of the pending deque
        lap_d, lrn_d = state["pend"][-1]
        pend.append(lrn_d); pend_lap.append(lap_d)
        if len(pend) > K:
            pend.pop(0); pend_lap.pop(0)
        steps_in_window += 1
        if steps_in_window >= WINDOW:
            if loss.requires_grad:
                opt.zero_grad()
                loss.backward()
                gnorm = torch.nn.utils.clip_grad_norm_(model.trainable_parameters(), CLIP)
                if torch.isfinite(gnorm):
                    opt.step()
                    model.project_()
                else:                       # a non-finite gradient would write NaN into the weights
                    opt.zero_grad()
                    _SKIPS["windows"] += 1
            loss = torch.zeros((), dtype=torch.float64)
            steps_in_window = 0
            state = detach_state(state)
            pend = [[_detach(d) for d in ds] for ds in pend]
    return tot_lrn, tot_lap, n_scored


def run_epoch(model, opt, series, epoch, start_at=0, history=None):
    """One pass over the series; returns (mean learned LL, mean laplace LL, n).
    Saves a checkpoint every CKPT_EVERY series (resumable with LT_RESUME)."""
    tot_lrn = tot_lap = 0.0
    n_scored = 0
    t0 = time.time()
    for j, (sid, title, ch) in enumerate(series):
        if j < start_at:
            continue
        ch = [float(v) for v in ch[-HIST:]]
        # one bad series must not end a multi-day run: on an exception the weights,
        # optimizer and running totals go back to where this series started
        snap = (copy.deepcopy(model.state_dict()), copy.deepcopy(opt.state_dict()),
                tot_lrn, tot_lap, n_scored)
        try:
            tot_lrn, tot_lap, n_scored = _train_series(model, opt, ch, tot_lrn, tot_lap, n_scored)
        except (ValueError, RuntimeError, FloatingPointError) as e:
            model.load_state_dict(snap[0]); opt.load_state_dict(snap[1])
            tot_lrn, tot_lap, n_scored = snap[2], snap[3], snap[4]
            _SKIPS["series"] += 1
            print(f"[skip] series {j + 1} {sid}: {type(e).__name__}: {str(e)[:120]}", flush=True)
        if (j + 1) % 10 == 0 or j + 1 == len(series):
            dt = time.time() - t0
            done_here = j + 1 - start_at
            eta = dt / max(done_here, 1) * (len(series) - j - 1) / 60
            print(f"[epoch {epoch}] {j + 1}/{len(series)} series, {n_scored} scored steps, "
                  f"learned {tot_lrn / max(n_scored, 1):+.4f} vs laplace {tot_lap / max(n_scored, 1):+.4f} "
                  f"(delta {(tot_lrn - tot_lap) / max(n_scored, 1):+.4f}), {dt / 60:.1f} min, "
                  f"eta {eta:.0f} min", flush=True)
        if CKPT_EVERY and (j + 1) % CKPT_EVERY == 0 and j + 1 < len(series):
            save(model, opt, series, epoch, j + 1, history or [])
        if SWA_EVERY and (j + 1) >= SWA_START and (j + 1) % SWA_EVERY == 0:
            swa_update(model)
            save_swa(model, series, epoch, j + 1, history or [])
        if SNAP_EVERY and (j + 1) % SNAP_EVERY == 0:
            # a snapshot that later passes never overwrite: pick the best by validation
            save(model, opt, series, epoch, j + 1, history or [],
                 path=OUT.replace(".pt", f"_e{epoch}s{j + 1}.pt"))
    return tot_lrn / max(n_scored, 1), tot_lap / max(n_scored, 1), n_scored


def _detach(d):
    from skaters.torch.learned import _detach_dist
    return _detach_dist(d)


def main():
    torch.manual_seed(SEED)
    series = train_series()
    print(f"[learned_train] {CORPUS}: {len(series)} train series (family split), k={K}, "
          f"window={WINDOW}, lr={LR}, epochs={EPOCHS}", flush=True)
    model = LearnedLaplace(k=K, pi_lap=PI_LAP)
    params = model.trainable_parameters()
    print(f"[learned_train] {sum(p.numel() for p in params)} trainable values in {len(params)} tensors", flush=True)
    opt = torch.optim.Adam(params, lr=LR)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    history, first_epoch, start_at = [], 1, 0
    if os.environ.get("LT_INIT", "") and os.path.exists(os.environ["LT_INIT"]) and not (RESUME and os.path.exists(RESUME)):
        # start a fresh pass from another run's weights (no progress or optimizer carried over)
        model.load_state_dict(torch.load(os.environ["LT_INIT"], map_location="cpu", weights_only=False)["state_dict"])
        print(f"[learned_train] weights initialised from {os.environ['LT_INIT']}", flush=True)
    if RESUME and os.path.exists(RESUME):
        ck = torch.load(RESUME, map_location="cpu", weights_only=False)
        model.load_state_dict(ck["state_dict"])
        if "opt_state" in ck:
            opt.load_state_dict(ck["opt_state"])
        history = list(ck.get("history", []))
        if ck.get("swa"):
            _SWA.update(ck["swa"])
            print(f"[learned_train] running weight average restored (n={_SWA['n']})", flush=True)
        done = int(ck.get("done", 0))
        first_epoch = int(ck.get("epochs", 1))
        if done >= len(series):          # that epoch was complete; start the next
            first_epoch, done = first_epoch + 1, 0
        start_at = done
        print(f"[learned_train] resumed from {RESUME}: epoch {first_epoch}, series {start_at}", flush=True)
    for epoch in range(first_epoch, EPOCHS + 1):
        lrn, lap, n = run_epoch(model, opt, series, epoch, start_at=start_at, history=history)
        start_at = 0
        history.append({"epoch": epoch, "learned_ll": lrn, "laplace_ll": lap, "n_scored": n})
        save(model, opt, series, epoch, len(series), history)
        # keep every epoch's end state: a later epoch's periodic checkpoints overwrite OUT
        save(model, opt, series, epoch, len(series), history, path=OUT.replace(".pt", f"_e{epoch}.pt"))
        print(f"[learned_train] skipped {_SKIPS['series']} series, {_SKIPS['windows']} non-finite gradient windows", flush=True)
        print(f"[learned_train] epoch {epoch}: learned {lrn:+.4f} laplace {lap:+.4f} "
              f"delta {lrn - lap:+.4f} nats/step (in-sample); checkpoint -> {OUT}", flush=True)
    with open(OUT + ".json", "w") as fh:
        json.dump(history, fh, indent=1)


if __name__ == "__main__":
    main()
