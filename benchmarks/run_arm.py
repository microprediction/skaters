"""Canonical arm runner: score one or more methods on a corpus arm and append
per-step rows in the one predictions.py schema.

Every arm (laplace, the foundation models, ...) records the SAME thing per
(series, method, step): the realized change and the predictive it was scored
against. All derived metrics (LL, CRPS, coverage, Diebold-Mariano win/draw/loss,
sandwich lift) come from that one store. Runs in whichever venv has the model;
skaters is pure-Python on PYTHONPATH so it imports everywhere.

    PYTHONPATH=src:benchmarks \
      ARM_METHODS=Sundial ARM_CORPUS=monthly PRED_OUT=preds_sundial.csv \
      FM_DEVICE=cpu .venv-sundial/bin/python benchmarks/run_arm.py

Env:
  ARM_METHODS   comma list of methods in arm_adapters.REGISTRY (e.g. "laplace",
                "Sundial,laplace"). Required.
  ARM_CORPUS    corpus arm: daily | weekly | monthly | m4-hourly. Required.
  PRED_OUT      output CSV (canonical schema). Required.
  ARM_MAX       cap series per arm (0 = all). Smoke tests.
  ARM_NSHARD / ARM_SHARDS   fleet sharding by series residue (disjoint files).
  FM_CTX / FM_TEST / FM_DEVICE / FM_SAMPLES   inference protocol (foundation_study).

Resumable: skips any (series, method) already present in PRED_OUT.
"""
from __future__ import annotations
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import corpus
import arm_adapters as aa
from predictions import PredictionWriter

_PREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preds")
_PRICE = {"equity", "fx", "commodity"}


def regime(title):
    """price vs econ, from the series title — the study's regime stratum axis."""
    try:
        import fred_universe as fu
        return "price" if fu.asset_class(title or "") in _PRICE else "econ"
    except Exception:                       # noqa: BLE001
        return "econ"


def iter_series(arm):
    """Yield (sid, title, changes) for the arm: from the offline corpus cache
    (build_corpus_cache.py) if present — no network, no re-enumeration — else
    fall back to the live corpus.iter_arm."""
    cache = os.path.join(_PREDS, f"_corpus_{arm}.jsonl")
    if os.path.exists(cache):
        with open(cache) as fh:
            for line in fh:
                r = json.loads(line)
                yield r["sid"], r["title"], r["ch"]
    else:
        yield from corpus.iter_arm(arm)

CTX, TEST = aa.CTX, aa.TEST
METHODS = [m for m in os.environ.get("ARM_METHODS", "").split(",") if m]
ARM = os.environ.get("ARM_CORPUS", "")
OUT = os.environ.get("PRED_OUT", "")
ARM_MAX = int(os.environ.get("ARM_MAX", 0))
NSHARD = int(os.environ.get("ARM_NSHARD", 1))
SHARDS = {int(s) for s in os.environ.get("ARM_SHARDS", "0").split(",") if s != ""}
MINLEN = CTX + TEST + 12                 # context + test window + lag headroom


def done_keys(path):
    if not os.path.exists(path):
        return set()
    with open(path) as fh:
        return {(r["series"], r["method"]) for r in csv.DictReader(fh)}


def main():
    if not (METHODS and ARM and OUT):
        sys.exit("set ARM_METHODS, ARM_CORPUS, PRED_OUT")
    for m in METHODS:
        if m not in aa.REGISTRY:
            sys.exit(f"unknown method {m!r}; have {sorted(aa.REGISTRY)}")
    done = done_keys(OUT)
    writer = PredictionWriter(OUT)
    series = list(iter_series(ARM))
    if ARM_MAX:
        series = series[:ARM_MAX]
    series = [(j, x) for j, x in enumerate(series) if j % NSHARD in SHARDS]
    print(f"[run_arm] {ARM}: {len(series)} series (shard {sorted(SHARDS)}/{NSHARD}), "
          f"methods={METHODS} CTX={CTX} TEST={TEST} dev={aa.DEVICE}", flush=True)

    scored = skipped = 0
    for j, (sid, title, ch) in series:
        ch = ch[-aa.fs.HIST:]
        if len(ch) < MINLEN:
            skipped += 1
            continue
        start = len(ch) - TEST
        y = ch[start:]
        todo = [m for m in METHODS if (sid, m) not in done]
        if not todo:
            continue
        study = f"{ARM}:{regime(title)}"     # stratum = frequency x regime (radar axes)
        for m in todo:
            t = time.time()
            dists = aa.REGISTRY[m](ch)
            if dists is None:
                continue
            for step, d in enumerate(dists):
                writer.step(study, sid, m, step, float(y[step]), dist=d)
            writer.flush()
            print(f"  {ARM} {j} {sid} {m} ({time.time()-t:.1f}s)", flush=True)
        scored += 1
    writer.close()
    print(f"[run_arm] done: scored {scored}, skipped {skipped} (too short)", flush=True)


if __name__ == "__main__":
    main()
