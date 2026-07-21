"""Score the PyMC-laplace sandwich (solo) + fresh laplace on the frontier's
non-price series, at the frontier's one-step window (TEST=300), so the sandwich
can be placed on the accuracy-vs-speed frontier alongside the SOTA baselines.

Series come from an existing SOTA results CSV (default results_sota.csv). laplace
and the sandwich are recomputed here (current laplace) so they are same-version
and directly comparable; the other baselines keep their SOTA rows.

    FM_TEST=300 FR_OUT=results_frontier_pymc.csv PYTHONPATH=src:benchmarks \
        ~/.venvs/skaters-pymc/bin/python benchmarks/pymc_frontier_solo.py

Sharding: FR_NSHARD, FR_SHARDS (comma), FR_OUT, FR_SRC.
"""
import csv
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymc_forecast_sandwich_study as pf
import fred

_HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(_HERE, os.environ.get("FR_SRC", "results_sota.csv"))
OUT = os.path.join(_HERE, os.environ.get("FR_OUT", "results_frontier_pymc.csv"))
NSHARD = int(os.environ.get("FR_NSHARD", 1))
SHARDS = {int(s) for s in os.environ.get("FR_SHARDS", "0").split(",") if s != ""}
MINLEN = pf.TEST + 60


def done_keys(path):
    if not os.path.exists(path):
        return set()
    return {(r["series"], r["method"]) for r in csv.DictReader(open(path))}


def main():
    series = sorted({r["series"] for r in csv.DictReader(open(SRC))})
    series = [s for i, s in enumerate(series) if i % NSHARD in SHARDS]
    done = done_keys(OUT)
    mode = "a" if os.path.exists(OUT) else "w"
    fh = open(OUT, mode, newline="")
    w = csv.writer(fh)
    if mode == "w":
        w.writerow(["series", "method", "logpdf", "n"])
    print(f"[fr] {len(series)} series, TEST={pf.TEST}, shard {sorted(SHARDS)}/{NSHARD}", flush=True)
    scored = skipped = failed = 0
    for j, sid in enumerate(series):
        if (sid, "PyMC-sandwich") in done and (sid, "laplace") in done:
            continue
        try:
            ch = fred._to_changes(fred._load_levels(sid))[-1000:]
        except Exception:
            ch = []
        if len(ch) < MINLEN:
            skipped += 1
            continue
        t = time.time()
        try:
            ll_lap, lap_logf, zs = pf.series_pass(ch)
            solo = pf.solo_arm(sid, zs, lap_logf)
            w.writerow([sid, "laplace", f"{ll_lap:.6f}", pf.TEST])
            w.writerow([sid, "PyMC-sandwich", f"{solo:.6f}", pf.TEST])
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  FAIL {sid}: {e!r}", flush=True)
            continue
        fh.flush()
        scored += 1
        if scored % 20 == 0:
            print(f"  {j+1}/{len(series)} scored={scored} ({time.time()-t:.0f}s last)", flush=True)
    fh.close()
    print(f"[fr done] scored {scored}, skipped {skipped}, failed {failed}", flush=True)


if __name__ == "__main__":
    main()
