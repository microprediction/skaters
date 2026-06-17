"""Overnight exhaustive CRPS comparison: skaters vs crepes.

Runs a broad universe of FRED series (one-step change), scoring every
forecaster by CRPS (and, for ours, log-likelihood too). crepes is given
several calibration windows to put its best foot forward; ours include the
likelihood policy, the likelihood leaf, and the CRPS-objective leaf.

Robust for unattended runs: every (series, forecaster) result is appended to
benchmarks/results_crps.csv immediately, and on restart already-finished
pairs are skipped. A summary prints at the end.

Run (in the conda env with crepes + a FRED key):
    PYTHONPATH=src python benchmarks/exhaustive_crps.py
"""

from __future__ import annotations
import csv
import math
import os
import sys
import time
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from crepes import ConformalPredictiveSystem

import fred
from crps_leaf import crps_leaf
from skaters.api import laplace, kahneman, dirac
from skaters.leaf import scale_mixture_leaf

_HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(_HERE, "results_crps.csv")

# A broad macro/financial universe (daily where possible). Failures are skipped.
UNIVERSE = [
    # rates
    "DGS1", "DGS2", "DGS3", "DGS5", "DGS7", "DGS10", "DGS20", "DGS30",
    "DFF", "DFEDTARU", "TB3MS", "DPRIME", "MORTGAGE30US", "DGS1MO", "DGS3MO", "DGS6MO",
    # spreads / credit
    "T10Y2Y", "T10Y3M", "T5YIE", "BAMLH0A0HYM2", "BAMLC0A0CM", "TEDRATE", "AAA", "BAA",
    "BAMLC0A4CBBB", "BAMLH0A3HYC",
    # FX
    "DEXUSEU", "DEXJPUS", "DEXUSUK", "DEXCHUS", "DEXCAUS", "DEXMXUS", "DEXKOUS",
    "DEXSZUS", "DEXBZUS", "DTWEXBGS",
    # commodities / markets
    "DCOILWTICO", "DCOILBRENTEU", "DHHNGSP", "VIXCLS", "NASDAQCOM", "SP500", "DJIA",
    "GVZCLS", "OVXCLS",
    # macro (monthly)
    "CPIAUCSL", "PCEPI", "PPIACO", "UNRATE", "PAYEMS", "INDPRO", "HOUST", "UMCSENT",
    "M2SL", "DGORDER", "RSAFS", "PERMIT",
]

GRID = list(range(2, 99, 1))
TAUS = [p / 100.0 for p in GRID]


def crepes_crps(series, window=400, burn=300):
    """Mean CRPS of crepes CPS (naive mean), via the pinball decomposition of
    its own predictive CDF — no density conversion."""
    buf = []
    tot = 0.0
    n = 0
    pend = None
    for i, y in enumerate(series):
        if pend is not None and i > burn:
            s = 0.0
            for tau, q in pend:
                s += (y - q) * (tau - (1.0 if y < q else 0.0))
            tot += 2.0 * s / len(pend)
            n += 1
        buf.append(y)
        if len(buf) > window:
            buf.pop(0)
        if len(buf) >= 60:
            cps = ConformalPredictiveSystem()
            cps.fit(np.asarray(buf, dtype=float))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                qs = np.ravel(cps.predict(y_hat=np.zeros(1), higher_percentiles=GRID))
            pend = [(t, float(qs[j])) for j, t in enumerate(TAUS) if math.isfinite(float(qs[j]))]
            if not pend:
                pend = [(0.5, 0.0)]
        else:
            pend = [(0.5, 0.0)]
    return (tot / n, n) if n else (float("nan"), 0)


def skater_scores(make, series, burn=300):
    """Mean CRPS and log-likelihood of a Dist-emitting skater."""
    f = make()
    state = None
    pend = None
    cr = 0.0
    lp = 0.0
    n = 0
    for i, y in enumerate(series):
        if pend is not None and i > burn:
            cr += pend[0].crps(y)
            v = pend[0].logpdf(y)
            lp += v if math.isfinite(v) else -20.0
            n += 1
        d, state = f(y, state)
        pend = d
    return (cr / n, lp / n, n) if n else (float("nan"), float("nan"), 0)


# forecaster name -> ("crepes", window) or ("skater", factory)
FORECASTERS = {
    "crepes-w250": ("crepes", 250),
    "crepes-w400": ("crepes", 400),
    "crepes-w750": ("crepes", 750),
    "laplace": ("skater", lambda: laplace(1)),
    "kahneman": ("skater", lambda: kahneman(1)),
    "scalemix-leaf": ("skater", lambda: scale_mixture_leaf(1)),
    "crps-leaf-0.3": ("skater", lambda: crps_leaf(eta=0.3)),
    "crps-leaf-0.6": ("skater", lambda: crps_leaf(eta=0.6)),
    "crps-leaf-1.0": ("skater", lambda: crps_leaf(eta=1.0)),
    "dirac": ("skater", lambda: dirac(1)),
}


def _done_pairs():
    done = set()
    if os.path.exists(RESULTS):
        with open(RESULTS) as f:
            for row in csv.reader(f):
                if len(row) >= 2:
                    done.add((row[0], row[1]))
    return done


def main():
    if not os.path.exists(RESULTS):
        with open(RESULTS, "w") as f:
            csv.writer(f).writerow(["series", "forecaster", "crps", "logpdf", "n"])
    done = _done_pairs()

    # build the change series once (cached by fred.py)
    series_data = {}
    for sid in UNIVERSE:
        levels = fred._load_levels(sid)
        if levels:
            ch = fred._to_changes(levels)
            if len(ch) >= 500:
                series_data[sid] = ch
    print(f"loaded {len(series_data)}/{len(UNIVERSE)} series", flush=True)

    for sid, ch in series_data.items():
        for name, spec in FORECASTERS.items():
            if (sid, name) in done:
                continue
            t0 = time.time()
            try:
                if spec[0] == "crepes":
                    crps, n = crepes_crps(ch, window=spec[1])
                    lp = ""
                else:
                    crps, lp, n = skater_scores(spec[1], ch)
            except Exception as e:  # noqa: BLE001
                print(f"  ERR {sid}/{name}: {e}", flush=True)
                continue
            with open(RESULTS, "a") as f:
                csv.writer(f).writerow([sid, name, f"{crps:.6f}",
                                        (f"{lp:.6f}" if lp != "" else ""), n])
            print(f"  {sid:14s} {name:14s} CRPS={crps:.5f}  ({time.time()-t0:.1f}s)", flush=True)

    summarize()


def summarize():
    rows = {}
    with open(RESULTS) as f:
        r = csv.reader(f); next(r, None)
        for series, fc, crps, lp, n in r:
            rows.setdefault(series, {})[fc] = float(crps)
    ours = ["laplace", "kahneman", "scalemix-leaf", "crps-leaf-0.3", "crps-leaf-0.6", "crps-leaf-1.0", "dirac"]
    creps = ["crepes-w250", "crepes-w400", "crepes-w750"]
    wins = 0; total = 0
    print("\n=== summary: best-of-ours vs best-of-crepes CRPS (lower=better) ===")
    print(f"  {'series':14s}{'ours*':>10}{'crepes*':>10}  winner")
    for s, d in sorted(rows.items()):
        o = [d[k] for k in ours if k in d and not math.isnan(d[k])]
        c = [d[k] for k in creps if k in d and not math.isnan(d[k])]
        if not o or not c:
            continue
        bo, bc = min(o), min(c)
        total += 1
        win = "OURS" if bo < bc else "crepes"
        if bo < bc:
            wins += 1
        print(f"  {s:14s}{bo:>10.5f}{bc:>10.5f}  {win}")
    if total:
        print(f"\n  ours win {wins}/{total} series on CRPS  ({100*wins/total:.0f}%)")


if __name__ == "__main__":
    main()
