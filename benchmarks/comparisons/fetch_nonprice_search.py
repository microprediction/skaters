"""Second-pass non-price downloader: reach daily-*frequency* series that lack the
`daily` tag, via FRED's search endpoint filtered to frequency=Daily over a broad
set of non-price (rates / credit / macro) seed terms. Dedups against the cache
and fetches only new non-price ids. Complements fetch_nonprice.py (which drains
the `daily` tag). Needs FRED_API_KEY.
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
SEEDS = [
    "treasury yield", "treasury constant maturity", "interest rate", "corporate bond spread",
    "mortgage rate", "repo rate", "money market", "overnight rate", "credit spread",
    "inflation expectation", "swap rate", "commercial paper rate", "discount window",
    "federal funds", "sofr", "libor", "eurodollar", "high yield spread", "option-adjusted spread",
    "bond yield", "bill rate", "note yield", "prime rate", "certificate of deposit",
    "breakeven inflation", "real interest rate", "term premium", "yield curve",
]


def main():
    key = fred._api_key()
    if not key:
        print("no FRED_API_KEY"); return 1
    cached = {f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv")}
    new_np = {}
    for term in SEEDS:
        url = ("https://api.stlouisfed.org/fred/series/search?search_text=" + urllib.parse.quote(term) +
               "&filter_variable=frequency&filter_value=Daily&order_by=popularity&sort_order=desc"
               f"&limit=1000&api_key={key}&file_type=json")
        try:
            r = json.loads(urllib.request.urlopen(url, timeout=30).read())
        except Exception as e:  # noqa: BLE001
            print(f"  err {term}: {e}"); time.sleep(1); continue
        for s in r.get("seriess", []):
            sid = s["id"]
            if sid not in cached and fu.asset_class(s.get("title", "")) not in PRICE:
                new_np[sid] = s.get("title", "")
        print(f"[search] '{term}': running new-nonprice total = {len(new_np)}", flush=True)
        time.sleep(0.4)

    print(f"[search] fetching {len(new_np)} new non-price daily series...", flush=True)
    got = failed = 0
    for i, sid in enumerate(new_np):
        if fred._load_levels(sid):
            got += 1
        else:
            failed += 1
        time.sleep(0.4)
        if (i + 1) % 20 == 0:
            print(f"[search] {i+1}/{len(new_np)}  new={got}  failed={failed}", flush=True)
    print(f"[search] DONE  new={got}  failed={failed}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
