"""Prophet sandwich, really wide: every qualifying non-price series.

Statement: benchmarks/preregistrations/2026-07-13-tabfm-sandwich-body.md
(second addendum, filed before results). Universe: every cached FRED
series passing the wide study's screens (non-price including the
supplemental title screen, >=1000 changes, non-degenerate pre-test
history), with NO stratified cap and NO family cap; family and strata
labels are recorded per series so concentration can be analyzed rather
than prevented. Deterministic; the universe file is committed before the
run. Arms and scoring identical to prophet_sandwich_study.py.

Usage:
    PYTHONPATH=src:benchmarks/anomaly python benchmarks/prophet_wide_study.py
"""
import csv
import os
import re
import sys
import time
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, os.path.join(_HERE, "anomaly"))
sys.path.insert(0, _HERE)

import fred  # noqa: E402
import fred_universe as fu  # noqa: E402
from tabfm_wide_study import (  # noqa: E402
    _titles, characterize, _rho_bin, _rf_bin, PRICE, HIST, TEST,
)
from prophet_sandwich_study import run_one  # noqa: E402

UNIVERSE = os.path.join(_HERE, "preregistrations",
                        "prophet_wide_universe.txt")
OUT = os.path.join(_HERE, "results_prophet_wide.csv")


def select():
    tmap = _titles()
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE)
                 if f.endswith(".csv"))
    extra_price = re.compile(
        r"nasdaq|coinbase|bitcoin|ethereum|litecoin|s&p|dow jones|wilshire|"
        r"gold|silver|crude|price index for", re.I)
    out = []
    for sid in ids:
        title = tmap.get(sid)
        if title is None:
            continue
        if fu.asset_class(title) in PRICE or extra_price.search(title) \
                or extra_price.search(sid):
            continue
        lv = fred._load_levels(sid)
        if not lv:
            continue
        ch = fred._to_changes(lv)
        if len(ch) < HIST:
            continue
        rf, rho1, kurt, vcl = characterize(ch[-HIST:][:-TEST])
        if rho1 is None:
            continue
        out.append((sid, f"{_rho_bin(rho1)}|{_rf_bin(rf)}", fu.family(sid)))
    return out


def main():
    if not os.path.exists(UNIVERSE):
        sel = select()
        with open(UNIVERSE, "w") as fh:
            for sid, stratum, fam in sel:
                fh.write(f"{sid},{stratum},{fam}\n")
        print(f"universe frozen: {len(sel)} series -> {UNIVERSE}")
        print("Commit the universe file, then rerun to start scoring.")
        return

    sel = [tuple(l.strip().split(",")) for l in open(UNIVERSE)]
    done = set()
    if os.path.exists(OUT):
        done = {r["series"] for r in csv.DictReader(open(OUT))}
    todo = [(s, st) for s, st, _f in sel if s not in done]
    new = not os.path.exists(OUT)
    fh = open(OUT, "a", newline="")
    w = csv.writer(fh)
    if new:
        w.writerow(["series", "ll_laplace", "ll_prophet_raw",
                    "ll_prophet_sandwich", "n", "stratum"])
        fh.flush()
    k = 0
    t00 = time.time()
    with Pool(8) as pool:
        for res in pool.imap_unordered(run_one, todo):
            if res is None:
                continue
            k += 1
            w.writerow(res[:-1])
            fh.flush()
            os.fsync(fh.fileno())
            if k % 25 == 0:
                print(f"  pw {k}/{len(todo)} ({time.time() - t00:.0f}s)",
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
