"""Fetch an out-of-development FRED holdout: the least-popular tail of the
daily universe, none of it ever cached or used in benchmarks. Stored in
data_holdout/ so the development cache is untouched."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fred

HOLD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_holdout")
os.makedirs(HOLD, exist_ok=True)
u = json.load(open(os.path.join(fred._CACHE, "universe_daily.json")))
cached = set(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
cands = [m for m in u if m["id"] not in cached]
cands.sort(key=lambda m: m.get("popularity", 0))   # most obscure first
got = 0
for m in cands:
    sid = m["id"]
    path = os.path.join(HOLD, f"{sid}.csv")
    if os.path.exists(path):
        got += 1
        continue
    try:
        levels = fred._fetch(sid, start="1990-01-01")
    except Exception:
        continue
    if not levels or len(levels) < 650:
        continue
    ch = fred._to_changes(levels)
    if len(ch) < 600:
        continue
    rep = sum(1 for i in range(1, len(ch)) if ch[i] == ch[i-1]) / (len(ch)-1)
    if rep >= 0.05:
        continue
    with open(path, "w") as f:
        for d, v in levels:
            f.write(f"{d},{v}\n")
    got += 1
    if got % 25 == 0:
        print(f"  {got} holdout series", flush=True)
    if got >= 300:
        break
print(f"holdout corpus: {got} series in {HOLD}")
