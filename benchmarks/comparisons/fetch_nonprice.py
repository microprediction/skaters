"""Background downloader: deepen the NON-PRICE daily FRED universe.

The default enumeration (universe_daily.json) is popularity-ranked, so its head
is equity/fx indices — price series laplace isn't for. This paginates deeper into
FRED's `daily` tag (past the popular indices, where rates/credit/macro live) and
fetches every NON-PRICE series (asset_class not in equity/fx/commodity) that
isn't already cached. Cached CSVs are then available to study.py on its next scan.

    PYTHONPATH=src python benchmarks/comparisons/fetch_nonprice.py [n_candidates]

Needs FRED_API_KEY (read from .env by fred._api_key). Polite 0.4s between fetches.
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))  # benchmarks/

import fred
import fred_universe as fu

PRICE = {"equity", "fx", "commodity"}


def main(argv):
    n_cand = int(argv[0]) if argv else 30000
    if not fred._api_key():
        print("no FRED_API_KEY (checked env + .env) — cannot fetch")
        return 1
    print(f"[fetch] enumerating up to {n_cand} daily series (deep paginate)...", flush=True)
    uni = fu.enumerate_daily(n_candidates=n_cand, refresh=True)
    nonprice = [s for s in uni if fu.asset_class(s.get("title", "")) not in PRICE]
    print(f"[fetch] universe={len(uni)}  non-price candidates={len(nonprice)}", flush=True)

    got = skipped = failed = 0
    for i, s in enumerate(nonprice):
        sid = s["id"]
        if os.path.exists(os.path.join(fred._CACHE, f"{sid}.csv")):
            skipped += 1
            continue
        levels = fred._load_levels(sid)   # fetches + caches on miss
        if levels:
            got += 1
        else:
            failed += 1
        time.sleep(0.4)
        if (got + failed) % 25 == 0 and (got + failed) > 0:
            print(f"[fetch] {i+1}/{len(nonprice)} scanned  new={got}  cached={skipped}  failed={failed}", flush=True)
    print(f"[fetch] DONE  new={got}  already-cached={skipped}  failed={failed}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
