"""Generate the challenges radar data (docs/js/challenges-radar-data.js).

Five regime axes plus a price/returns axis, one ratio per model per metric: how
often the model beats laplace with ties split, normalised so a 50/50 draw is 1.0 —

    ratio = (wins + 0.5 * ties) / n / 0.5        (0 .. 2, laplace ring = 1)

Axes: economic daily FRED, weekly cycles, yearly cycles (monthly), and the two
M4-Hourly regimes (soft cycles: the first 180 corpus-order series, phase R^2
~0.76; hard cycles: the rest, R^2 ~0.97; see laplace-vs-tbats). Missing cells
(a model not yet run on an arm) are emitted as null and skipped by the chart.

    PYTHONPATH=src python benchmarks/comparisons/make_challenges_radar.py
"""
import csv
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BENCH = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_BENCH)
sys.path.insert(0, _BENCH)

import corpus

BASE = os.path.join(_HERE, "laplace-vs-csp")
OUT = os.path.join(_ROOT, "docs", "js", "challenges-radar-data.js")

# Daily-axis-only sources from earlier studies (each scored against the laplace
# rows in its own file, so ratios are internally consistent; the seasonal arms
# for these opponents are filled by fill_radar_matrix.sh on a bigger machine).
LEGACY = [
    ("AutoARIMA", "results_sota.csv", "AutoARIMA"),
    ("AutoETS", "results_sota.csv", "AutoETS"),
    ("NF-StudentT", "results_sota.csv", "NF-StudentT"),
    ("auto.arima (R)", "comparisons/_shared_R25.csv", "auto.arima-R@25"),
    ("Theta (R)", "comparisons/_shared_R25.csv", "Theta-R@25"),
    ("ADAM (R)", "comparisons/_shared_R25.csv", "ADAM-R@25"),
    ("nnetar (R)", "comparisons/_shared_R25.csv", "nnetar-R@25"),
    ("GARCH-t", "results_sota.csv", "GARCH-t"),
    ("BSTS (R)", "comparisons/_shared_R25.csv", "bsts-R@25"),
    ("TimesFM", "results_foundation_tf.csv", "TimesFM"),
    ("Chronos-Bolt", "results_foundation_cm.csv", "Chronos"),
    ("Moirai", "results_foundation_cm.csv", "Moirai"),
    ("Lag-Llama", "results_foundation_ll.csv", "Lag-Llama"),
    ("TabFM (clf8)", "results_tabfm_wide.csv", "clf8"),
]

MODELS = {                       # display name -> method name per arm-m
    "CSP": lambda m: f"CSPr-m{m}",
    "NNS.ARMA": lambda m: "NNS-R",
    "TBATS": lambda m: "TBATS-R",
    "TBATS (24+168)": lambda m: "TBATS-R-ms",
    "dantzig": lambda m: "dantzig",
    # These fill from the arm CSVs when fill_radar_matrix.sh has run the
    # opponents there; until then LEGACY supplies the daily cell only.
    "AutoARIMA": lambda m: "AutoARIMA@25",
    "AutoETS": lambda m: "AutoETS@25",
    "auto.arima (R)": lambda m: "auto.arima-R@25",
    "Theta (R)": lambda m: "Theta-R@25",
    "ADAM (R)": lambda m: "ADAM-R@25",
    "nnetar (R)": lambda m: "nnetar-R@25",
    "GARCH-t": lambda m: "GARCH-t",
    "BSTS (R)": lambda m: "bsts-R@25",
}
ARMS = [("economic (daily)", ["results_daily.csv", "results.csv"], 5, None),
        ("weekly cycles", ["results_weekly.csv"], 52, None),
        ("yearly cycles", ["results_monthly.csv"], 12, None),
        ("soft waveforms", ["results_m4_hourly.csv"], 24, "A"),
        ("hard waveforms", ["results_m4_hourly.csv"], 24, "B")]


def load(paths):
    by = {}
    for path in paths:
        with open(path) as f:
            for row in csv.DictReader(f):
                lp = float(row["logpdf"]) if row.get("logpdf") else None
                cr = float(row["crps"]) if row.get("crps") else None
                by.setdefault(row["series"], {}).setdefault(
                    row["method"], (lp, cr))
    return by


def ratio(by, subset, method, idx, higher_wins):
    wins = ties = n = 0
    for s in subset:
        d = by.get(s, {})
        if method not in d or "laplace" not in d:
            continue
        a, b = d[method][idx], d["laplace"][idx]
        if a is None or b is None:
            continue
        n += 1
        if a == b:
            ties += 1
        elif (a > b) == higher_wins:
            wins += 1
    return (round((wins + 0.5 * ties) / n / 0.5, 3), n) if n >= 30 else (None, 0)


def main():
    m4_order = [sid for sid, _, _ in corpus.iter_arm("m4-hourly")]
    blocks = {"A": set(m4_order[:180]), "B": set(m4_order[180:])}
    data = {"axes": [a[0] for a in ARMS], "models": {}}
    for name, meth in MODELS.items():
        crps, ll, ns = [], [], []
        for _, paths, m, block in ARMS:
            by = load([os.path.join(BASE, p) for p in paths])
            subset = blocks[block] if block else set(by)
            method = meth(m)
            c, n = ratio(by, subset, method, 1, higher_wins=False)
            l, _ = ratio(by, subset, method, 0, higher_wins=True)
            crps.append(c); ll.append(l); ns.append(n)
        if any(v is not None for v in crps + ll):
            data["models"][name] = {"crps": crps, "ll": ll, "n": ns}
    K = len(ARMS)
    for name, fname, method in LEGACY:
        path = os.path.join(_BENCH, fname)
        if not os.path.exists(path):
            continue
        by = load([path])
        c, n = ratio(by, set(by), method, 1, higher_wins=False)
        l, _ = ratio(by, set(by), method, 0, higher_wins=True)
        if not n:
            continue
        entry = data["models"].setdefault(
            name, {"crps": [None] * K, "ll": [None] * K, "n": [0] * K})
        if entry["crps"][0] is None and entry["ll"][0] is None:
            entry["crps"][0], entry["ll"][0], entry["n"][0] = c, l, n
    # Prophet: LL-only wide format (ll_laplace / ll_prophet_raw columns)
    pw = os.path.join(_BENCH, "results_prophet_wide.csv")
    if os.path.exists(pw):
        wins = ties = n = 0
        with open(pw) as f:
            for row in csv.DictReader(f):
                try:
                    a, b = float(row["ll_prophet_raw"]), float(row["ll_laplace"])
                except (KeyError, ValueError):
                    continue
                n += 1
                if a == b:
                    ties += 1
                elif a > b:
                    wins += 1
        if n >= 30:
            data["models"]["Prophet"] = {
                "crps": [None] * K,
                "ll": [round((wins + 0.5 * ties) / n / 0.5, 3)] + [None] * (K - 1),
                "n": [n] + [0] * (K - 1)}
    # Price / returns axis (6th spoke): GARCH-t's home turf. Scored against the
    # laplace rows in _price_study.csv (2500 return series). Only the opponents
    # that were run on price get a cell; everyone else stays null there. Appended
    # last so every model built above (incl. Prophet) gets the extra column.
    PRICE_METHOD = {"GARCH-t": "GARCH-t", "AutoARIMA": "AutoARIMA", "AutoETS": "AutoETS"}
    data["axes"].append("price / returns")
    for entry in data["models"].values():
        entry["crps"].append(None); entry["ll"].append(None); entry["n"].append(0)
    price_path = os.path.join(_HERE, "_price_study.csv")
    if os.path.exists(price_path):
        by = load([price_path])
        for name, method in PRICE_METHOD.items():
            c, n = ratio(by, set(by), method, 1, higher_wins=False)
            l, _ = ratio(by, set(by), method, 0, higher_wins=True)
            if not n:
                continue
            entry = data["models"].setdefault(
                name, {"crps": [None] * (K + 1), "ll": [None] * (K + 1), "n": [0] * (K + 1)})
            entry["crps"][-1], entry["ll"][-1], entry["n"][-1] = c, l, n
    with open(OUT, "w") as f:
        f.write("// generated by benchmarks/comparisons/make_challenges_radar.py\n")
        f.write("const CHALLENGES_RADAR = " + json.dumps(data, indent=2) + ";\n")
    print(f"wrote {OUT}")
    for name, d in data["models"].items():
        print(f"  {name:10s} crps {d['crps']}  ll {d['ll']}")


if __name__ == "__main__":
    main()
