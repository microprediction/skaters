"""Accuracy vs speed frontier for the landing page.

Accuracy = mean held-out log-likelihood on the GENERAL / non-price economic
universe (all qualifying cached FRED rates/credit/other series; equity/fx/
commodity excluded — that is GARCH-t's turf, reported separately). Read live from
the study CSV so the figure tracks the committed results. Speed = forecasts per
second = 300 / (single-core seconds per series); per-method runtimes are measured
separately (universe-independent) and kept as a lookup. Both axes higher = better.

    STUDY_RESULTS=benchmarks/results_nonprice.csv PYTHONPATH=src python benchmarks/make_frontier.py
"""
import os, sys, csv, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from study import _rfrac

WINDOW = 300  # one-step forecasts per series
RESULTS = os.environ.get("STUDY_RESULTS", "benchmarks/results_nonprice.csv")

# Measured single-core runtime (ms/series at TEST=300) — universe-independent.
SPEED_MS = {
    "laplace": 196, "GARCH-t": 226, "AutoETS": 275, "ETS-sm": 300,
    "SARIMAX": 1178, "AutoARIMA": 863, "AutoARIMA+ACI": 900,
    "AutoARIMA+conformal": 900, "NF-StudentT": 1897,
}
DISPLAY = {"NF-StudentT": "NeuralForecast-t", "ETS-sm": "ETS"}

rows = {}
with open(RESULTS) as fh:
    for r in csv.DictReader(fh):
        lp = r["logpdf"]
        if lp in ("", "nan"):
            continue
        rows.setdefault(r["series"], {})[r["method"]] = float(lp)
cont = [s for s in rows if "laplace" in rows[s] and _rfrac(s) < 0.05]


def mean_ll(method):
    v = [rows[s][method] for s in cont if method in rows[s]]
    return sum(v) / len(v) if v else None


pts = []
for method, ms in SPEED_MS.items():
    acc = mean_ll(method)
    if acc is not None:
        pts.append((DISPLAY.get(method, method), 1000.0 * WINDOW / ms, acc, method == "laplace"))

lap_acc, lap_spd = mean_ll("laplace"), 1000.0 * WINDOW / SPEED_MS["laplace"]
print(f"non-price continuous series: {len(cont)};  laplace mean LL {lap_acc:.3f}")

fig, ax = plt.subplots(figsize=(7.8, 4.8))
fig.patch.set_facecolor("white")
ax.axhline(lap_acc, color="#4a3aff", lw=0.8, ls=":", alpha=0.5)
ax.axvline(lap_spd, color="#4a3aff", lw=0.8, ls=":", alpha=0.5)
for label, spd, acc, ours in pts:
    if ours:
        ax.scatter(spd, acc, s=290, marker="*", color="#4a3aff", zorder=5,
                   edgecolor="white", linewidth=1.2)
        ax.annotate(label, (spd, acc), xytext=(-10, 10), textcoords="offset points",
                    fontsize=12.5, fontweight="bold", color="#4a3aff", ha="right")
    else:
        ax.scatter(spd, acc, s=55, color="#888", zorder=3)
        ax.annotate(label, (spd, acc), xytext=(8, -3), textcoords="offset points",
                    fontsize=10, color="#444", ha="left")

ax.set_xscale("log")
ax.set_xlabel("forecasts per second  (faster →)", fontsize=11)
ax.set_ylabel("accuracy  (mean held-out log-likelihood — better ↑)", fontsize=11)
ax.set_title(f"Accuracy vs. speed on {len(cont)} general (non-price) FRED series",
             fontsize=13, pad=12)
ax.grid(True, which="both", alpha=0.18)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig("docs/assets/frontier.svg", format="svg", bbox_inches="tight")
fig.savefig("docs/assets/frontier.png", format="png", dpi=160, bbox_inches="tight")
print("wrote docs/assets/frontier.svg and frontier.png")
