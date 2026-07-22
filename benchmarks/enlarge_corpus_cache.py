"""Enlarge the offline corpus caches in place, append-only.

FRED popularity is a live ranking, so re-running build_corpus_cache.py with a
bigger limit can reorder the file prefix and reshuffle what each round's cap
covers. This script preserves the existing file order exactly: it loads the
sids already cached, enumerates the arm deeper, and appends only unseen series
at the end. The merged file is written to a temp path and os.replace()d, so a
concurrently running run_arm job sees the old file or the new one, never a
partial line. m4-hourly is a fixed competition file and is skipped.

    PYTHONPATH=src:benchmarks CORPUS_LIMIT=10000 \
        .venv-sota/bin/python benchmarks/enlarge_corpus_cache.py
"""
from __future__ import annotations
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus

PREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preds")
ARMS = os.environ.get("CORPUS_ARMS", "daily weekly monthly").split()
LIMIT = int(os.environ.get("CORPUS_LIMIT", "10000"))


def main():
    for arm in ARMS:
        path = os.path.join(PREDS, f"_corpus_{arm}.jsonl")
        have = set()
        if os.path.exists(path):
            with open(path) as fh:
                for line in fh:
                    have.add(json.loads(line)["sid"])
        t0 = time.time()
        fresh = []
        for sid, title, ch in corpus.iter_arm(arm, limit=LIMIT):
            if sid in have:
                continue
            fresh.append(json.dumps({"sid": sid, "title": title,
                                     "ch": [float(x) for x in ch]}))
            if len(fresh) % 200 == 0:
                print(f"  [{arm}] +{len(fresh)} new ...", flush=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as out:
            if os.path.exists(path):
                with open(path) as fh:
                    for line in fh:
                        out.write(line)
            for line in fresh:
                out.write(line + "\n")
        os.replace(tmp, path)
        print(f"[{arm}] {len(have)} kept + {len(fresh)} appended "
              f"in {time.time()-t0:.0f}s -> {path}", flush=True)


if __name__ == "__main__":
    main()
