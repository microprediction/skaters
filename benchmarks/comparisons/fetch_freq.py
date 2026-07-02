"""Download NON-PRICE weekly + monthly FRED series with FULL history.

The daily study truncates at 2005-01-01, which is fine for daily/weekly (enough
changes) but starves monthly series (~250 obs since 2005 < MIN_CHANGES=500). So
for these lower frequencies we fetch from 1900-01-01 to recover the long macro
histories (many monthly series run back to the 1940s-60s). Enumerates the FRED
`weekly`/`monthly` tags by popularity, keeps non-price (rates/credit/other),
fetches uncached ones into the shared cache. Needs FRED_API_KEY.

    PYTHONPATH=src python benchmarks/comparisons/fetch_freq.py [n_per_tag]
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fred
import fred_universe as fu

PRICE = {"equity", "fx", "commodity"}
START = "1900-01-01"          # full history for the low-frequency arm


def enumerate_tag(tag, n):
    key = fred._api_key()
    out, offset = [], 0
    while len(out) < n:
        url = ("https://api.stlouisfed.org/fred/tags/series?tag_names=" + tag +
               "&order_by=popularity&sort_order=desc&limit=1000&offset=" + str(offset) +
               f"&api_key={key}&file_type=json")
        try:
            rows = json.loads(urllib.request.urlopen(url, timeout=30).read()).get("seriess", [])
        except Exception as e:  # noqa: BLE001
            print(f"  enum err {tag}@{offset}: {e}"); break
        if not rows:
            break
        out += rows
        offset += 1000
        time.sleep(0.4)
    return out[:n]


def main(argv):
    n = int(argv[0]) if argv else 4000
    if not fred._api_key():
        print("no FRED_API_KEY"); return 1
    cached = {f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv")}
    got = failed = skipped = 0
    for tag in ("weekly", "monthly"):
        series = enumerate_tag(tag, n)
        nonprice = [s for s in series if fu.asset_class(s.get("title", "")) not in PRICE]
        print(f"[{tag}] enumerated {len(series)}  non-price {len(nonprice)}", flush=True)
        for i, s in enumerate(nonprice):
            sid = s["id"]
            path = os.path.join(fred._CACHE, f"{sid}.csv")
            if sid in cached or os.path.exists(path):
                skipped += 1; continue
            rows = fred._fetch(sid, start=START)     # FULL history
            if rows and len(rows) > 20:
                with open(path, "w") as f:
                    for d, v in rows:
                        f.write(f"{d},{v}\n")
                got += 1
            else:
                failed += 1
            time.sleep(0.4)
            if (got + failed) % 25 == 0 and (got + failed) > 0:
                print(f"[{tag}] {i+1}/{len(nonprice)}  new={got}  failed={failed}", flush=True)
    print(f"[freq] DONE  new={got}  skipped={skipped}  failed={failed}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
