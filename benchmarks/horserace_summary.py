"""Summarize the overnight horse race with the honest breakdown.

Reads benchmarks/results_overnight.csv and reports, for laplace vs each baseline:
  * raw and family-clustered win-rates (LL and CRPS) on the continuous subset
  * the price-vs-non-price split for GARCH-t (the No-Free-Lunch story:
    laplace wins non-price, GARCH-t wins price/returns)
  * mean continuous log-likelihood per method

    PYTHONPATH=src python benchmarks/horserace_summary.py
"""
from __future__ import annotations
import os, sys, csv, math
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from study import _cfg, _rfrac
from fred_universe import family

RESULTS = os.environ.get("STUDY_RESULTS", "benchmarks/results_overnight.csv")
# price-like FRED prefixes (equity / fx / commodity / crypto / rate-level proxies)
PRICE = ("DEX", "DCOIL", "DHOIL", "DDFUEL", "DHHNG", "CB", "NASDAQ", "SP", "DJIA",
         "VIX", "RVX", "EVZ", "GVZ", "OVX", "WILL", "GOLD", "DTWEX", "BAML",
         "DGS", "DPRIME", "DAAA", "DBAA", "DTB", "DCP", "T10", "T5", "DSWP")
isprice = lambda s: any(s.startswith(p) for p in PRICE)


def winrate(rows, series, method, idx, lower):
    """laplace vs `method` on metric idx over `series`: (raw%, family%, n)."""
    per, byfam = [], defaultdict(list)
    for s in series:
        if method not in rows[s] or "laplace" not in rows[s]:
            continue
        lv, mv = rows[s]["laplace"][idx], rows[s][method][idx]
        if math.isnan(lv) or math.isnan(mv):
            continue
        win = 1.0 if ((lv < mv) if lower else (lv > mv)) else 0.0
        per.append(win); byfam[family(s)].append(win)
    if not per:
        return float("nan"), float("nan"), 0
    raw = 100 * np.mean(per)
    fam = 100 * np.mean([np.mean(v) for v in byfam.values()])
    return raw, fam, len(per)


def main():
    rows = {}
    with open(RESULTS) as fh:
        for r in csv.DictReader(fh):
            lp = float(r["logpdf"]) if r["logpdf"] not in ("", "nan") else float("nan")
            rows.setdefault(r["series"], {})[r["method"]] = (lp, float(r["crps"]))
    cont = [s for s in rows if "laplace" in rows[s] and _rfrac(s) < 0.05]
    fams = {family(s) for s in cont}
    print(f"results: {RESULTS}")
    print(f"continuous series: {len(cont)}  ->  {len(fams)} families  "
          f"(total series scored: {len(rows)})\n")

    methods = sorted({m for s in cont for m in rows[s] if m != "laplace"})
    print(f"laplace win-rate vs each baseline (continuous):")
    print(f"  {'method':22s}{'LL raw/fam':>14s}{'CRPS raw/fam':>15s}{'meanLL':>9s}{'N':>7s}")
    for m in methods:
        lr, lf, n = winrate(rows, cont, m, 0, False)
        cr, cf, _ = winrate(rows, cont, m, 1, True)
        vals = [rows[s][m][0] for s in cont if m in rows[s] and not math.isnan(rows[s][m][0])]
        has_ll = bool(vals)
        ll = f"{lr:.0f}/{lf:.0f}%" if has_ll else "— (CDF)"
        mll = f"{np.mean(vals):+.2f}" if has_ll else "—"
        print(f"  {m:22s}{ll:>14s}{f'{cr:.0f}/{cf:.0f}%':>15s}{mll:>9s}{n:>7d}")
    lapvals = [rows[s]["laplace"][0] for s in cont]
    print(f"  {'laplace (mean LL)':22s}{'':>14s}{'':>15s}{np.mean(lapvals):+9.2f}{len(lapvals):>7d}")

    if any("GARCH-t" in rows[s] for s in cont):
        print("\nGARCH-t — the No-Free-Lunch split (laplace vs GARCH-t):")
        price = [s for s in cont if isprice(s) and "GARCH-t" in rows[s]]
        nonp = [s for s in cont if not isprice(s) and "GARCH-t" in rows[s]]
        for label, sub in [("NON-PRICE (rates/macro)", nonp), ("PRICE/returns", price)]:
            lr, lf, n = winrate(rows, sub, "GARCH-t", 0, False)
            lap = np.mean([rows[s]["laplace"][0] for s in sub]) if sub else float("nan")
            gt = np.mean([rows[s]["GARCH-t"][0] for s in sub]) if sub else float("nan")
            nf = len({family(s) for s in sub})
            print(f"  {label:24s} n={n:4d} ({nf} fam)  laplace LL-win raw {lr:.0f}% / family {lf:.0f}%"
                  f"   mean LL  laplace {lap:+.2f} vs GARCH {gt:+.2f}")


if __name__ == "__main__":
    main()
