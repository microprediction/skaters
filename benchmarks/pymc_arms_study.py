"""Run PyMC-Forecast (solo) on the seasonal/waveform radar arms.

The pre-registered sandwich study scored PyMC-Forecast only on the non-price
DAILY universe (log-likelihood), so it can't be a full shape on the challengers
radar. This scores the `solo` arm (one ADVI fit per series on the pre-test z
stream, frozen through the test window) plus laplace on the weekly, monthly and
M4-hourly corpora, reusing the exact scoring from pymc_forecast_sandwich_study.
Log-likelihood only, matching that study. Crash-safe (resume by series+arm+method).

    PF_OUT=results_pymc_arms.csv PYTHONPATH=src:benchmarks \
        ~/.venvs/skaters-pymc/bin/python benchmarks/pymc_arms_study.py

Sharding for a thread-capped CPU pool (no GPU here): each worker takes disjoint
residue classes and its own output file; the radar generator globs
results_pymc_arms*.csv. Env: PF_NSHARD, PF_SHARDS (comma), PF_OUT, PF_MAX,
PF_ARMS_CORPUS.
"""
import csv
import gc
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymc_forecast_sandwich_study as pf
import corpus

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(_HERE, os.environ.get("PF_OUT", "results_pymc_arms.csv"))
ARMS = os.environ.get("PF_ARMS_CORPUS", "weekly monthly m4-hourly").split()
# solo = PyMC on laplace's residual z-stream (a collaboration; wins by
# construction). raw = standalone PyMC-Forecast on the raw changes, blockwise
# refit (the fair head-to-head challenger). Default solo for back-compat.
PF_METHOD = os.environ.get("PF_METHOD", "solo")
PF_MAX = int(os.environ.get("PF_MAX", 0))
NSHARD = int(os.environ.get("PF_NSHARD", 1))
SHARDS = {int(s) for s in os.environ.get("PF_SHARDS", "0").split(",") if s != ""}
HIST = 1000
MINLEN = pf.TEST + 60          # need a fit window before the TEST tail


def done_keys(path):
    if not os.path.exists(path):
        return set()
    return {(r["series"], r["arm"], r["method"]) for r in csv.DictReader(open(path))}


def main():
    done = done_keys(OUT)
    mode = "a" if os.path.exists(OUT) else "w"
    fh = open(OUT, mode, newline="")
    w = csv.writer(fh)
    if mode == "w":
        w.writerow(["series", "method", "logpdf", "n", "arm"])
    print(f"[pf-arms] arms={ARMS} TEST={pf.TEST} minlen={MINLEN} "
          f"shard={sorted(SHARDS)}/{NSHARD}", flush=True)

    for arm in ARMS:
        series = list(corpus.iter_arm(arm))
        if PF_MAX:
            series = series[:PF_MAX]
        series = [(j, x) for j, x in enumerate(series) if j % NSHARD in SHARDS]
        scored = skipped = failed = 0
        for j, (sid, title, ch) in series:
            ch = ch[-HIST:]
            need_lap = (sid, arm, "laplace") not in done
            need_m = (sid, arm, PF_METHOD) not in done
            if not (need_lap or need_m):
                continue
            if len(ch) < MINLEN:
                skipped += 1
                continue
            t = time.time()
            try:
                ll_lap, lap_logf, zs = pf.series_pass(ch)
                if need_lap:
                    w.writerow([sid, "laplace", f"{ll_lap:.6f}", pf.TEST, arm])
                if need_m:
                    if PF_METHOD == "solo":
                        val = pf.solo_arm(sid, zs, lap_logf)
                    elif PF_METHOD == "raw":
                        val = pf.raw_arm(sid, ch)
                    else:
                        raise ValueError(f"unknown PF_METHOD {PF_METHOD}")
                    w.writerow([sid, PF_METHOD, f"{val:.6f}", pf.TEST, arm])
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"  FAIL {arm} {sid}: {e!r}", flush=True)
                continue
            fh.flush()
            scored += 1
            print(f"  {arm} {j+1} {sid} ({time.time()-t:.0f}s)", flush=True)
        print(f"[{arm}] scored {scored}, skipped {skipped}, failed {failed}", flush=True)

    fh.close()
    gc.collect()
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
