"""Fetch raw data for the price series in a study CSV, so features can be
computed on them (the mixed price+non-price switching experiment needs the
price half's raw series, not just its scores). Network-bound, threaded.

    WARM_SRC=comparisons/_price_study.csv WARM_WORKERS=8 PYTHONPATH=src \
        .venv-sota/bin/python benchmarks/warm_price_cache.py
"""
import csv
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fred

_HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(_HERE, os.environ.get("WARM_SRC", "comparisons/_price_study.csv"))
WORKERS = int(os.environ.get("WARM_WORKERS", 8))


def warm_one(sid):
    path = os.path.join(fred._CACHE, f"{sid}.csv")
    if os.path.exists(path):
        return "skip"
    rows = fred._fetch(sid, start="1900-01-01")
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
    ids = sorted({r["series"] for r in csv.DictReader(open(SRC))})
    todo = [s for s in ids if not os.path.exists(os.path.join(fred._CACHE, f"{s}.csv"))]
    print(f"{len(ids)} price series; {len(todo)} uncached to fetch ({WORKERS} threads)", flush=True)
    got = fail = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(warm_one, s) for s in todo]
        for i, fut in enumerate(as_completed(futs)):
            r = fut.result()
            got += r == "got"
            fail += r == "fail"
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(todo)} got={got} fail={fail}", flush=True)
    print(f"[warm-price] done got={got} fail={fail}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
