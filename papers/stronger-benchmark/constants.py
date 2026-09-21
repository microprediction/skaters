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
SHARED = os.path.join(ROOT, "benchmarks", "comparisons", "_shared_R25_nonprice.csv")

# The arms these foundation-model studies actually carry, as named in this
# project's own horse race. The paper reports laplace against exactly these.
CLASSIC_ARMS = {
    "AutoARIMA@25": "AutoARIMA (statsforecast)",
    "AutoETS@25": "AutoETS (statsforecast)",
    "Theta-R@25": "Theta (R forecast)",
    "auto.arima-R@25": "auto.arima (R forecast)",
}
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


def classic_baselines():
    """laplace against the classic arms, through the existing horse-race helper.

    Reuses benchmarks/horserace_summary.py rather than re-deriving win rates:
    that module owns the continuity filter and the family clustering, and a
    hand-rolled scoring loop in this file would be a second definition free to
    drift from the one the rest of the repository uses.
    """
    import csv as _csv
    import math as _math
    sys.path.insert(0, os.path.join(ROOT, "benchmarks"))
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import horserace_summary as hs
    from study import _rfrac
    from fred_universe import family

    rows = {}
    with open(SHARED) as fh:
        for r in _csv.DictReader(fh):
            lp = float(r["logpdf"]) if r["logpdf"] not in ("", "nan") else float("nan")
            rows.setdefault(r["series"], {})[r["method"]] = (lp, float(r["crps"]))
    cont = [s for s in rows if "laplace" in rows[s] and _rfrac(s) < 0.05]

    out = {}
    for key, pretty in CLASSIC_ARMS.items():
        ll_raw, ll_fam, n = hs.winrate(rows, cont, key, 0, False)
        cr_raw, cr_fam, _ = hs.winrate(rows, cont, key, 1, True)
        vals = [rows[s][key][0] for s in cont
                if key in rows[s] and not _math.isnan(rows[s][key][0])]
        out[key] = {"label": pretty, "n_series": n,
                    "ll_raw": ll_raw, "ll_fam": ll_fam,
                    "crps_raw": cr_raw, "crps_fam": cr_fam,
                    "mean_ll": sum(vals) / len(vals) if vals else float("nan")}
    lap = [rows[s]["laplace"][0] for s in cont]
    out["_laplace"] = {"label": "laplace", "n_series": len(cont),
                       "mean_ll": sum(lap) / len(lap),
                       "n_families": len({family(s) for s in cont})}
    return out


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
    try:
        classic = classic_baselines()
    except Exception as exc:                       # noqa: BLE001
        classic = {"_error": f"{type(exc).__name__}: {exc}"}
    if "--json" in sys.argv:
        print(json.dumps({"head_to_head": h2h, "nozzle": noz, "derived": der,
                          "package": pkg, "classic": classic}, indent=2))
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
    if "_error" not in classic:
        lap = classic["_laplace"]
        print("\nLAPLACE VS THE CLASSIC ARMS "
              "({} continuous series, {} families)\n".format(
                  lap["n_series"], lap["n_families"]))
        print("  {:28s}{:>14s}{:>15s}{:>7s}".format("arm", "LL raw/fam",
                                                    "CRPS raw/fam", "N"))
        for k, v in classic.items():
            if k.startswith("_"):
                continue
            ll = "{:.0f}/{:.0f}%".format(v["ll_raw"], v["ll_fam"])
            cr = "{:.0f}/{:.0f}%".format(v["crps_raw"], v["crps_fam"])
            print("  {:28s}{:>14s}{:>15s}{:>7d}".format(
                v["label"], ll, cr, v["n_series"]))

    print(f"\nPACKAGE SIZE\n\n  {pkg['n_files']} .py files, {pkg['bytes']} bytes "
          f"= {pkg['kb_rounded']} KB\n")
    print("DERIVED CLAIMS\n")
    for k, v in der.items():
        print(f"  {k:46s} {v}")


if __name__ == "__main__":
    main()
