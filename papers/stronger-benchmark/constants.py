"""Every number in the paper, computed from the store. Nothing is retyped.

    python papers/stronger-benchmark/constants.py            # human-readable
    python papers/stronger-benchmark/constants.py --json     # machine-readable

The paper cites values by key. A referee re-runs this and diffs against the
prose. The rule exists because hand-typed claims drifted from the store once
before and a referee caught it.

Sources, all version-controlled:
  benchmarks/canonical_summary_vs_laplace.csv   head-to-head, derived from the
                                                tidy store by summarize_canonical.py
  benchmarks/_nozzle_study.log                  reconstruction run record,
                                                produced by nozzle_study.py
"""
from __future__ import annotations
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SUMMARY = os.path.join(ROOT, "benchmarks", "canonical_summary_vs_laplace.csv")
SRC = os.path.join(ROOT, "src")
NOZZLE_LOG = os.path.join(ROOT, "benchmarks", "_nozzle_study.log")

STRATA = ["daily:econ", "daily:price", "weekly:econ", "monthly:econ", "m4-hourly:econ"]
PRETTY = {
    "daily:econ": "daily, economic",
    "daily:price": "daily, price/returns",
    "weekly:econ": "weekly, economic",
    "monthly:econ": "monthly, economic",
    "m4-hourly:econ": "M4-hourly, seasonal",
}


def _rows():
    with open(SUMMARY) as fh:
        return list(csv.DictReader(fh))


def head_to_head(model="TimesFM3"):
    """Raw and portfolio-wrapped results per stratum, straight from the store."""
    by = {(r["study"], r["model"]): r for r in _rows()}
    out = {}
    for s in STRATA:
        raw = by.get((s, model))
        wrapped = by.get((s, model + "&lap"))
        if raw is None:
            continue
        rec = {
            "label": PRETTY[s],
            "n_series": int(raw["n_series"]),
            "win": int(raw["win"]), "draw": int(raw["draw"]), "loss": int(raw["loss"]),
            "med_dLL": float(raw["med_dLL"]),
            "loss_rate": int(raw["loss"]) / int(raw["n_series"]),
        }
        if wrapped is not None:
            nw = int(wrapped["n_series"])
            rec |= {
                "wrapped_n_series": nw,
                "wrapped_win": int(wrapped["win"]),
                "wrapped_draw": int(wrapped["draw"]),
                "wrapped_loss": int(wrapped["loss"]),
                "wrapped_med_dLL": float(wrapped["med_dLL"]),
                "wrapped_loss_rate": int(wrapped["loss"]) / nw,
            }
        out[s] = rec
    return out


def nozzle():
    """Reconstruction spread: the run record from nozzle_study.py."""
    txt = open(NOZZLE_LOG).read()
    g = lambda pat: float(re.search(pat, txt).group(1))
    n_pts = int(re.search(r"(\d+) scored points", txt).group(1))
    n_ser = int(re.search(r"scored points, (\d+) series", txt).group(1))
    methods = {m: g(rf"\n  {m}: mean logpdf ([-+][\d.]+)")
               for m in ("grid", "local", "narrow", "wide")}
    return {
        "n_points": n_pts,
        "n_series": n_ser,
        "methods": methods,
        "mean_spread": g(r"mean per-point nozzle spread \(max-min logpdf\): ([\d.]+)"),
        "median_spread": g(r"median per-point nozzle spread: ([\d.]+)"),
        "local_vs_grid": g(r"local vs grid, mean logpdf diff: ([-+][\d.]+)"),
        "narrow_vs_grid": g(r"narrow vs grid, mean logpdf diff: ([-+][\d.]+)"),
        "worst_gap": abs(g(r"narrow vs grid, mean logpdf diff: ([-+][\d.]+)")),
    }


def package_size():
    """Bytes of pure-Python source that ship in the package.

    The paper quotes this, so it is measured rather than remembered. Counts
    every .py under src/, excluding bytecode caches. An earlier draft carried a
    figure that appears nowhere in this repository.
    """
    total = n = 0
    for dirpath, dirnames, filenames in os.walk(SRC):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if fn.endswith(".py"):
                total += os.path.getsize(os.path.join(dirpath, fn))
                n += 1
    return {"bytes": total, "kb": total / 1024, "kb_rounded": round(total / 1024),
            "n_files": n}


def derived(h2h, noz):
    """Cross-claims the prose makes. Each is checked, not asserted."""
    worst_stratum_gap = max(abs(r["med_dLL"]) for r in h2h.values())
    return {
        "loses_majority_every_stratum": all(r["loss"] > r["win"] for r in h2h.values()),
        "wrapped_still_negative_every_stratum":
            all(r["wrapped_med_dLL"] < 0 for r in h2h.values() if "wrapped_med_dLL" in r),
        "worst_stratum_median_gap": worst_stratum_gap,
        "nozzle_spread_exceeds_every_stratum_gap": noz["mean_spread"] > worst_stratum_gap,
        "max_loss_rate_drop": max(
            r["loss_rate"] - r["wrapped_loss_rate"]
            for r in h2h.values() if "wrapped_loss_rate" in r),
    }


def main():
    h2h = head_to_head()
    noz = nozzle()
    der = derived(h2h, noz)
    pkg = package_size()
    if "--json" in sys.argv:
        print(json.dumps({"head_to_head": h2h, "nozzle": noz, "derived": der,
                          "package": pkg}, indent=2))
        return
    print("HEAD TO HEAD, TimesFM3 vs laplace (source: canonical_summary_vs_laplace.csv)\n")
    print(f"{'stratum':22s} {'n':>6s}  {'w/d/l':>18s}  {'med dLL':>8s}  {'loss%':>6s}")
    for r in h2h.values():
        wdl = f"{r['win']}/{r['draw']}/{r['loss']}"
        print(f"{r['label']:22s} {r['n_series']:6d}  {wdl:>18s}  {r['med_dLL']:+8.4f}  {r['loss_rate']:6.1%}")
    print("\nWRAPPED in a never-worse portfolio (TimesFM3&lap)\n")
    print(f"{'stratum':22s} {'n':>6s}  {'w/d/l':>18s}  {'med dLL':>8s}  {'loss%':>6s}")
    for r in h2h.values():
        if "wrapped_med_dLL" not in r:
            continue
        wdl = f"{r['wrapped_win']}/{r['wrapped_draw']}/{r['wrapped_loss']}"
        print(f"{r['label']:22s} {r['wrapped_n_series']:6d}  {wdl:>18s}  "
              f"{r['wrapped_med_dLL']:+8.4f}  {r['wrapped_loss_rate']:6.1%}")
    print(f"\nRECONSTRUCTION SPREAD ({noz['n_points']} points, {noz['n_series']} series, TimesFM3 fixed)\n")
    for m, v in noz["methods"].items():
        print(f"  {m:8s} mean logpdf {v:+.4f}")
    print(f"  mean per-point spread   {noz['mean_spread']:.4f}")
    print(f"  median per-point spread {noz['median_spread']:.4f}")
    print(f"  local vs grid           {noz['local_vs_grid']:+.4f}")
    print(f"  narrow vs grid          {noz['narrow_vs_grid']:+.4f}")
    print(f"\nPACKAGE SIZE\n\n  {pkg['n_files']} .py files, {pkg['bytes']} bytes "
          f"= {pkg['kb_rounded']} KB\n")
    print("DERIVED CLAIMS\n")
    for k, v in der.items():
        print(f"  {k:46s} {v}")


if __name__ == "__main__":
    main()
