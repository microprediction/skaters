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
RESUME = os.environ.get("LT_RESUME", "")                   # checkpoint to continue from
SHUFFLE = int(os.environ.get("LT_SHUFFLE", 1))             # seeded order so families mix
HIST = ra.aa.fs.HIST
FLOOR = -20.0


def train_series():
    series = [(sid, title, ch) for sid, title, ch in ra.iter_series(CORPUS)
              if ra.regime(title) == "econ" and split_of(sid) == "train"]
    series = [x for x in series if len(x[2][-HIST:]) >= ra.MINLEN]
    if SHUFFLE:
        import random
        random.Random(SEED).shuffle(series)
    return series[:MAX] if MAX else series


def save(model, opt, series, epoch, done, history, path=OUT):
    torch.save({"state_dict": model.state_dict(), "opt_state": opt.state_dict(),
                "k": K, "pi_lap": PI_LAP, "corpus": CORPUS, "n_series": len(series),
                "window": WINDOW, "lr": LR, "epochs": epoch, "done": done, "history": history,
                "series": [sid for sid, _, _ in series], "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")},
               path + ".tmp")
    os.replace(path + ".tmp", path)


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
                    torch.nn.utils.clip_grad_norm_(model.trainable_parameters(), CLIP)
                    opt.step()
                    model.project_()
                loss = torch.zeros((), dtype=torch.float64)
                steps_in_window = 0
                state = detach_state(state)
                pend = [[_detach(d) for d in ds] for ds in pend]
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
    if RESUME and os.path.exists(RESUME):
        ck = torch.load(RESUME, map_location="cpu", weights_only=False)
        model.load_state_dict(ck["state_dict"])
        if "opt_state" in ck:
            opt.load_state_dict(ck["opt_state"])
        history = list(ck.get("history", []))
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
        print(f"[learned_train] epoch {epoch}: learned {lrn:+.4f} laplace {lap:+.4f} "
              f"delta {lrn - lap:+.4f} nats/step (in-sample); checkpoint -> {OUT}", flush=True)
    with open(OUT + ".json", "w") as fh:
        json.dump(history, fh, indent=1)


if __name__ == "__main__":
    main()
