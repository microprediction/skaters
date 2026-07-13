"""Prophet sandwich at wide-study scale: exploratory follow-up.

Statement: benchmarks/preregistrations/2026-07-13-tabfm-sandwich-body.md
(Prophet addendum). Prophet was the sharpest classical opponent in the
FRED-30 front-end study (largest median lift when fronted, calendar
machinery laplace cannot represent); this reruns it raw and sandwiched on
the frozen 226-series wide universe, reusing the front-end study's
machinery verbatim (rolling refit, exact Jacobian, identical clamps).

Usage:
    PYTHONPATH=src:benchmarks/anomaly python benchmarks/prophet_sandwich_study.py
"""
import csv
import os
import sys
import time
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, os.path.join(_HERE, "anomaly"))
sys.path.insert(0, _HERE)

from frontend_loglik import (  # noqa: E402
    laplace_pass, roll_prophet, _clamp, BURN, MIN_LEN, N_MAX,
)
from tabfm_wide_study import load_universe  # noqa: E402
from benchmarks.fred import _load_levels, _to_changes  # noqa: E402

OUT = os.path.join(_HERE, "results_prophet_sandwich.csv")


def run_one(args):
    sid, stratum = args
    levels = _load_levels(sid)
    ys = _to_changes(levels) if levels else []
    if len(ys) < MIN_LEN:
        return None
    dates = [d for d, _ in levels][1:]
    ys, dates = ys[-N_MAX:], dates[-N_MAX:]
    n = len(ys)
    t0 = time.time()
    zs, jac, lap_ll = laplace_pass(ys)
    lap = sum(_clamp(v) for v in lap_ll[BURN:]) / (n - BURN)
    try:
        raw = roll_prophet(ys, dates)
        p_raw = sum(_clamp(v) for v in raw[BURN:]) / (n - BURN)
        onz = roll_prophet(zs, dates)
        p_z = sum(_clamp(onz[t] + jac[t]) for t in range(BURN, n)) / (n - BURN)
    except Exception as e:
        print(f"  FAIL {sid}: {e!r}", flush=True)
        return None
    return [sid, lap, p_raw, p_z, n, stratum,
            round(time.time() - t0, 1)]


def main():
    universe = load_universe()
    done = set()
    if os.path.exists(OUT):
        done = {r["series"] for r in csv.DictReader(open(OUT))}
    todo = [(s, st) for s, st in universe if s not in done]
    new = not os.path.exists(OUT)
    fh = open(OUT, "a", newline="")
    w = csv.writer(fh)
    if new:
        w.writerow(["series", "ll_laplace", "ll_prophet_raw",
                    "ll_prophet_sandwich", "n", "stratum"])
        fh.flush()
    k = 0
    with Pool(6) as pool:
        for res in pool.imap_unordered(run_one, todo):
            if res is None:
                continue
            k += 1
            w.writerow(res[:-1])
            fh.flush()
            os.fsync(fh.fileno())
            print(f"  pr {k}/{len(todo)} {res[0]} lap={res[1]:+.3f} "
                  f"raw={res[2]:+.3f} sand={res[3]:+.3f} ({res[-1]}s)",
                  flush=True)
    fh.close()

    rows = list(csv.DictReader(open(OUT)))
    n = len(rows)
    med = lambda v: sorted(v)[len(v) // 2]  # noqa: E731
    for col, label in (("ll_prophet_raw", "raw"),
                       ("ll_prophet_sandwich", "sandwich")):
        d = [float(r[col]) - float(r["ll_laplace"]) for r in rows]
        print(f"prophet {label} vs laplace: median {med(d):+.4f}, "
              f"wins {sum(1 for x in d if x > 0)}/{n}")


if __name__ == "__main__":
    main()
