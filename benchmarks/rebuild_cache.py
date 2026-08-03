"""Rebuild the FRED cache for exactly the series in gaussianize_chain.csv."""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fred

HERE = os.path.dirname(os.path.abspath(__file__))
ids = [r["series"] for r in csv.DictReader(open(os.path.join(HERE, "gaussianize_chain.csv")))]
print(f"fetching {len(ids)} series", flush=True)
ok = 0
for k, sid in enumerate(ids, 1):
    levels = fred._load_levels(sid)
    ok += bool(levels)
    if k % 50 == 0:
        print(f"{k}/{len(ids)} ({ok} ok)", flush=True)
print(f"done: {ok}/{len(ids)} cached", flush=True)
