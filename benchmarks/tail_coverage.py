"""Tail coverage: is the 99% interval actually 99%? The 99.9%?

The coverage study established the 90% claim. The GPD tail splice (0.13.0)
is specifically a claim about further out — this measures empirical central
coverage at nominal 90 / 99 / 99.9% from the parade PIT, new default
(tails="gpd") vs tails="gaussian", strictly prequentially on the non-price
FRED universe. A calibrated method's shortfall (nominal - empirical) is ~0;
thin tails show up as positive shortfall growing with the nominal level.

Usage:
    PYTHONPATH=src:benchmarks python benchmarks/tail_coverage.py
"""
import json, math, os, sys
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _HERE)

from benchmarks.fred import _load_levels, _to_changes  # noqa: E402
from benchmarks import fred_universe  # noqa: E402

_PRICE = {"equity", "fx", "commodity"}
LEVELS = (0.90, 0.99, 0.999)
BURN = 600


def run_one(sid):
    xs = _to_changes(_load_levels(sid) or [])
    if len(xs) < 1500:
        return None
    from skaters import laplace
    out = {"sid": sid}
    for name, tails in (("gpd", "gpd"), ("gauss", "gaussian")):
        f = laplace(1, tails=tails)
        st = None
        n = 0
        hits = {lv: 0 for lv in LEVELS}
        for t, y in enumerate(xs):
            _, st = f(y, st)
            u = st["pit"][0]
            if u is not None and t >= BURN:
                n += 1
                for lv in LEVELS:
                    a = (1.0 - lv) / 2.0
                    hits[lv] += a <= u <= 1.0 - a
        out[name] = {f"{lv:g}": hits[lv] / n for lv in LEVELS}
        out["n"] = n
    return out


def main():
    metas = json.load(open(os.path.join(_HERE, "data", "universe_daily.json")))
    picked = []
    for m in metas:
        if fred_universe.asset_class(m.get("title", "")) in _PRICE:
            continue
        pth = os.path.join(_HERE, "data", f"{m['id']}.csv")
        if os.path.exists(pth) and os.path.getsize(pth) > 12000:
            picked.append(m["id"])
        if len(picked) >= 200:
            break
    rows = []
    with Pool(10) as pool:
        for r in pool.imap_unordered(run_one, picked):
            if r:
                rows.append(r)
                print(len(rows), r["sid"], flush=True)
    n = len(rows)
    med = lambda name, k: sorted(r[name][k] for r in rows)[n // 2]  # noqa: E731
    print(f"\n=== tail coverage, {n} non-price series (median empirical) ===")
    print(f"{'nominal':>9s} {'gaussian tails':>16s} {'gpd tails (default)':>20s}")
    for lv in LEVELS:
        k = f"{lv:g}"
        print(f"{lv:9.1%} {med('gauss', k):16.4%} {med('gpd', k):20.4%}")


if __name__ == "__main__":
    main()
