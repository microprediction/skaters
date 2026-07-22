"""Pre-materialize each corpus arm to a compact offline cache, once.

corpus.iter_arm enumerates the FRED universe (network) and runs per-series
frequency checks every call. The week-long driver would pay that on every
(model x corpus) subprocess, every round, and would depend on FRED being
reachable for a week. This writes the fully qualified (sid, title, changes) list
per arm to benchmarks/preds/_corpus_<arm>.jsonl so run_arm.py reads it offline
and instantly. Run once (network available):

    PYTHONPATH=src:benchmarks .venv-sota/bin/python benchmarks/build_corpus_cache.py

Re-run to refresh after enlarging the cache. Gitignored (regenerable, large).
"""
from __future__ import annotations
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus

PREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preds")
ARMS = os.environ.get("CORPUS_ARMS", "daily weekly monthly m4-hourly").split()
LIMIT = int(os.environ.get("CORPUS_LIMIT", "4000"))


def main():
    os.makedirs(PREDS, exist_ok=True)
    for arm in ARMS:
        path = os.path.join(PREDS, f"_corpus_{arm}.jsonl")
        t0 = time.time()
        n = 0
        with open(path, "w") as fh:
            for sid, title, ch in corpus.iter_arm(arm, limit=LIMIT):
                fh.write(json.dumps({"sid": sid, "title": title,
                                     "ch": [float(x) for x in ch]}) + "\n")
                n += 1
                if n % 200 == 0:
                    print(f"  [{arm}] {n} ...", flush=True)
        print(f"[{arm}] cached {n} series in {time.time()-t0:.0f}s -> {path}", flush=True)


if __name__ == "__main__":
    main()
