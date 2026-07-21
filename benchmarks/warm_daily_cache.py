"""Enlarge the non-price DAILY FRED cache in parallel.

Network-bound, so it runs threaded and alongside a CPU study without competing.
Re-resolves the top-N daily series by popularity (growing universe_daily.json),
then fetches every uncached non-price one into benchmarks/data, with full
history, so the next cached-only study covers a much larger universe. Needs
FRED_API_KEY.

    WARM_N=8000 WARM_WORKERS=8 PYTHONPATH=src \
        .venv-sota/bin/python benchmarks/warm_daily_cache.py
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fred
import fred_universe as fu

N = int(os.environ.get("WARM_N", 8000))
WORKERS = int(os.environ.get("WARM_WORKERS", 8))
PRICE = {"equity", "fx", "commodity"}


def warm_one(sid):
    path = os.path.join(fred._CACHE, f"{sid}.csv")
    if os.path.exists(path):
        return "skip"
    rows = fred._fetch(sid, start="1900-01-01")   # retries/backoff live in _fetch
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
    metas = fu.enumerate_daily(N, refresh=True)
    todo = [m["id"] for m in metas
            if fu.asset_class(m.get("title", "")) not in PRICE
            and not os.path.exists(os.path.join(fred._CACHE, f"{m['id']}.csv"))]
    print(f"daily universe {len(metas)}; non-price uncached to fetch: {len(todo)} "
          f"({WORKERS} threads)", flush=True)
    got = fail = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(warm_one, s) for s in todo]
        for i, fut in enumerate(as_completed(futs)):
            r = fut.result()
            got += r == "got"
            fail += r == "fail"
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(todo)} got={got} fail={fail}", flush=True)
    print(f"[warm-daily] done got={got} fail={fail}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
