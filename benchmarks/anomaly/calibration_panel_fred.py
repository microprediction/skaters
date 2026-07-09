"""The calibration panel on the non-price FRED universe — the decisive run.

UCR waveforms are the adversarial domain for a calendar-grid forecaster; the
non-price FRED change-series universe is the domain skaters actually claims.
This measures the same question as calibration_panel.py — "if I set the alarm
budget to alpha, do I get alpha?" — strictly prequentially, on real economic
series.

FRED has no anomaly labels, so there is no delay panel and one honest caveat:
real series contain genuine anomalies (2008, COVID), so a calibrated method
should run slightly ABOVE nominal on pooled counts. Three statistics per
method and alpha, in decreasing crisis-sensitivity:
    pooled:  total alarms / total ticks (crisis-inflated upper read)
    median:  median per-series alarm rate (a few crisis series can't move it)
    honest%: fraction of series with rate in [alpha/2, 2*alpha]

Methods as in calibration_panel.py: mah, z1 (ours), dspot, mz (raw
incumbents), dspot_z, mz_z (same heads fed the parade z — the front-end
question for job 2).

Usage:
    python benchmarks/anomaly/calibration_panel_fred.py --limit 500 --workers 10
"""

from __future__ import annotations
import argparse
import json
import math
import os
import sys
import time
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))       # for benchmarks.*
sys.path.insert(0, os.path.join(_HERE, "..", "..", "src"))
sys.path.insert(0, os.path.join(_HERE, ".."))             # for bare `fred`
sys.path.insert(0, _HERE)

from frontend_run import DSpot  # noqa: E402
from benchmarks.fred import _load_levels, _to_changes  # noqa: E402
from benchmarks import fred_universe  # noqa: E402

UNIVERSE = os.path.join(_HERE, "..", "data", "universe_daily.json")
MIN_LEN = 1000
ALPHAS = (1e-2, 1e-3, 1e-4)
# zgpd: the repair from panel v1 — POT/GPD tails on the parade z
# (skaters.anomaly.gpdtail), fed the same z stream as the other *_z heads.
METHODS = ("mah", "z1", "zgpd", "dspot", "mz", "dspot_z", "mz_z")
_PRICE = {"equity", "fx", "commodity"}


def run_one(args):
    sid, k, scale_alpha, det_alpha = args
    levels = _load_levels(sid)
    xs = _to_changes(levels) if levels else []
    n = len(xs)
    if n < MIN_LEN:
        return None
    burn = min(1000, n // 3)
    t0 = time.time()

    from skaters import laplace
    from skaters.anomaly import mahalanobis, gpdtail

    f = mahalanobis(laplace(k, scale_alpha=scale_alpha), k=k, alpha=det_alpha)
    state = None
    # gpdtail on the same z stream via a passthrough base (no second laplace)
    g = gpdtail(lambda y, s: (None, {"z": [y]}), k=1)
    gstate = None
    d = DSpot(list(xs[:burn]))
    d_z, zcal = None, []
    mz_m, mz_v, mz_n = 0.0, 0.0, 0
    mzz_m, mzz_v, mzz_n = 0.0, 0.0, 0
    MZ_ALPHA = 0.02

    alarms = {m: {a: 0 for a in ALPHAS} for m in METHODS}
    ticks = 0

    for t, y in enumerate(xs):
        ps = {}
        mz_n += 1
        a = max(MZ_ALPHA, 1.0 / mz_n)
        sd = math.sqrt(mz_v) if mz_v > 0 else 1e-8
        ps["mz"] = math.erfc((abs(y - mz_m) / sd) / math.sqrt(2.0)) \
            if mz_n > 3 else 1.0
        dd = y - mz_m
        mz_m += a * dd
        mz_v = (1 - a) * mz_v + a * dd * (y - mz_m)

        if t >= burn:
            ps["dspot"] = math.exp(-min(d.score(y), 700.0))

        _, state = f(y, state)
        p = state["pvalue"]
        ps["mah"] = p if p is not None else 1.0
        zvec = state["base"]["z"] if isinstance(state["base"], dict) else None
        z = zvec[0] if zvec else None
        ps["z1"] = math.erfc(abs(z) / math.sqrt(2.0)) if z is not None else 1.0

        zv = z if z is not None else 0.0
        _, gstate = g(zv, gstate)
        gp = gstate["pvalue"]
        ps["zgpd"] = gp if gp is not None else 1.0
        if t < burn:
            zcal.append(zv)
        else:
            if d_z is None and len(zcal) >= 10:
                d_z = DSpot(zcal)
            if d_z is not None:
                ps["dspot_z"] = math.exp(-min(d_z.score(zv), 700.0))
        mzz_n += 1
        a = max(MZ_ALPHA, 1.0 / mzz_n)
        sd = math.sqrt(mzz_v) if mzz_v > 0 else 1e-8
        ps["mz_z"] = math.erfc((abs(zv - mzz_m) / sd) / math.sqrt(2.0)) \
            if mzz_n > 3 else 1.0
        dz = zv - mzz_m
        mzz_m += a * dz
        mzz_v = (1 - a) * mzz_v + a * dz * (zv - mzz_m)

        if t >= burn:
            ticks += 1
            for m in METHODS:
                if m in ps:
                    for al in ALPHAS:
                        if ps[m] < al:
                            alarms[m][al] += 1

    res = {"sid": sid, "n": n, "ticks": ticks,
           "seconds": round(time.time() - t0, 1)}
    for m in METHODS:
        res[m] = {f"{al:g}": alarms[m][al] for al in ALPHAS}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--scale-alpha", type=float, default=0.03,
                    help="FRED-tuned forecasting default, not the UCR slow "
                         "setting: this is the home-field configuration")
    ap.add_argument("--det-alpha", type=float, default=0.02)
    args = ap.parse_args()

    metas = json.load(open(UNIVERSE))
    picked = []
    for m in metas:
        if fred_universe.asset_class(m.get("title", "")) in _PRICE:
            continue
        path = os.path.join(_HERE, "..", "data", f"{m['id']}.csv")
        if os.path.exists(path) and os.path.getsize(path) > MIN_LEN * 12:
            picked.append(m["id"])
        if len(picked) >= args.limit:
            break

    out = os.path.join(
        _HERE, f"calibration_panel_fred_zgpd_sa{args.scale_alpha}"
        f"_da{args.det_alpha}_n{len(picked)}.jsonl")

    # Crash safety + resume: append/fsync per series, skip finished sids.
    results = []
    if os.path.exists(out):
        with open(out) as fh:
            results = [json.loads(line) for line in fh if line.strip()]
        done = {r["sid"] for r in results}
        picked = [s for s in picked if s not in done]
        print(f"resuming {out}: {len(results)} done, {len(picked)} to go",
              flush=True)
    total = len(results) + len(picked)

    ofh = open(out, "a")
    with Pool(args.workers) as pool:
        for res in pool.imap_unordered(
                run_one,
                [(s, args.k, args.scale_alpha, args.det_alpha)
                 for s in picked]):
            if res is None:
                total -= 1
                continue
            results.append(res)
            ofh.write(json.dumps(res) + "\n")
            ofh.flush()
            os.fsync(ofh.fileno())
            ticks = sum(r["ticks"] for r in results)
            line = " ".join(f"{m}:{sum(r[m]['0.001'] for r in results)}"
                            for m in METHODS)
            print(f"[{len(results)}/{total}] {res['sid'][:18]:18s} "
                  f"{res['seconds']:5.1f}s  alarms@1e-3 per {ticks}: {line}",
                  flush=True)
    ofh.close()

    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        for r in sorted(results, key=lambda r: r["sid"]):
            fh.write(json.dumps(r) + "\n")
    os.replace(tmp, out)

    ticks = sum(r["ticks"] for r in results)
    print(f"\n=== FRED non-price FPR panel: {len(results)} series, "
          f"{ticks} ticks ===")
    print(f"{'method':8s}" + "".join(
        f"  pooled@{al:g} / median / honest%".ljust(34) for al in ALPHAS))
    for m in METHODS:
        row = f"{m:8s}"
        for al in ALPHAS:
            key = f"{al:g}"
            pooled = sum(r[m][key] for r in results) / ticks
            rates = sorted(r[m][key] / r["ticks"] for r in results)
            med = rates[len(rates) // 2]
            honest = sum(1 for x in rates if al / 2 <= x <= 2 * al) \
                / len(rates)
            row += f"  {pooled:.1e} / {med:.1e} / {honest:.0%}".ljust(34)
        print(row)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
