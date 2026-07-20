"""Parallel FRED cache warmer for the weekly/monthly arms.

Fetching is network-bound, so this runs threaded and alongside a GPU study
without competing for compute. It enumerates the same non-price tag universe
corpus._iter_fred uses and fetches every uncached series into benchmarks/data,
so the scoring run then reads everything from local cache instead of blocking
on per-series fetches. Needs FRED_API_KEY.

    WARM_WORKERS=8 python benchmarks/comparisons/warm_freq_cache.py monthly weekly
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))   # benchmarks
sys.path.insert(0, _HERE)                     # comparisons

import fred
import fred_universe as fu
import fetch_freq

TAGS = sys.argv[1:] or ["monthly", "weekly"]
N = int(os.environ.get("WARM_N", 2000))
WORKERS = int(os.environ.get("WARM_WORKERS", 8))
START = fetch_freq.START


def warm_one(sid):
    path = os.path.join(fred._CACHE, f"{sid}.csv")
    if os.path.exists(path):
        return "skip"
    rows = fred._fetch(sid, start=START)          # retries/backoff live in _fetch
    if rows and len(rows) > 20:
        with open(path, "w") as f:
            for d, v in rows:
                f.write(f"{d},{v}\n")
        return "got"
    return "fail"


def main():
    if not fred._api_key():
        print("no FRED_API_KEY", flush=True)
        return 1
    for tag in TAGS:
        series = fetch_freq.enumerate_tag(tag, N)
        nonprice = [s["id"] for s in series
                    if fu.asset_class(s.get("title", "")) not in fetch_freq.PRICE]
        todo = [sid for sid in nonprice
                if not os.path.exists(os.path.join(fred._CACHE, f"{sid}.csv"))]
        print(f"[{tag}] {len(nonprice)} non-price, {len(todo)} uncached -> "
              f"{WORKERS} threads", flush=True)
        got = fail = 0
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = [ex.submit(warm_one, sid) for sid in todo]
            for i, fut in enumerate(as_completed(futs)):
                r = fut.result()
                got += r == "got"
                fail += r == "fail"
                if (i + 1) % 25 == 0:
                    print(f"[{tag}] {i+1}/{len(todo)} got={got} fail={fail}", flush=True)
        print(f"[{tag}] done got={got} fail={fail}", flush=True)
    print("[warm] complete", flush=True)


if __name__ == "__main__":
    sys.exit(main())
