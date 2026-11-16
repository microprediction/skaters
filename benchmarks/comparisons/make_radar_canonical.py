"""README radar on the canonical study: foundation models and GARCH-t against
laplace by stratum (docs/assets/radar-canonical.svg + .png).

Same chart and metric as make_radar_figure.py: per-stratum strength against
laplace with ties split, scaled so a draw sits on the dashed laplace ring,

    ratio = (wins + 0.5 * draws) / n / 0.5        (0 .. 2, laplace ring = 1)

but read from the canonical summary (benchmarks/canonical_summary_vs_laplace.csv,
written by summarize_canonical.py), where a win, draw or loss is the per-series
Diebold-Mariano verdict on log score. Each foundation model is shown with its
stronger density reconstruction (native 21 levels, or the generous nozzle for
nine-decile models). Regenerate after summarize_canonical.py.

    python benchmarks/comparisons/make_radar_canonical.py
"""
import csv
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
SUMMARY = os.path.join(_ROOT, "benchmarks", "canonical_summary_vs_laplace.csv")

AXES = [("daily:econ", "economic (daily)"), ("weekly:econ", "economic (weekly)"),
        ("monthly:econ", "economic (monthly)"), ("m4-hourly:econ", "hourly (M4)"),
        ("daily:price", "price / returns")]
MODELS = [("Timestral-209M(q21)", "Timestral-209M"), ("TimeH2O-v1(wide)", "TimeH2O"),
          ("TimesFM3(wide)", "TimesFM 3.0"), ("t0-gamma(q21)", "t0-gamma"),
          ("GARCH-t", "GARCH-t")]
COLORS = ["#2a78d6", "#1baf7a", "#eda100", "#8a5cd6", "#008300"]
RMAX = 1.6


def load():
    cells = {}
    with open(SUMMARY) as fh:
        for r in csv.DictReader(fh):
            n = int(r["n_series"])
            if n:
                cells[(r["model"], r["study"])] = (int(r["win"]) + 0.5 * int(r["draw"])) / n / 0.5
    return cells


def main():
    cells = load()
    K = len(AXES)
    angles = [i * 2 * math.pi / K for i in range(K)]

    fig, ax = plt.subplots(figsize=(6.4, 7.0), subplot_kw={"polar": True})
    fig.patch.set_facecolor("white")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, RMAX)
    ax.set_rgrids([0.5, 1.0, 1.5], labels=["", "", ""])
    ax.set_xticks(angles)
    ax.set_xticklabels([a[1] for a in AXES], fontsize=11)
    ax.tick_params(axis="x", pad=10)
    ax.spines["polar"].set_visible(False)
    ax.grid(color="#dddddd", lw=0.8)

    ring = [angles[i % K] for i in range(K + 1)]
    ax.plot(ring, [1.0] * (K + 1), color="#5a5a5a", lw=1.6, ls=(0, (5, 4)), zorder=4)
    ax.annotate("laplace = 1", xy=(angles[0], 1.0), fontsize=9.5, color="#5a5a5a",
                xytext=(6, -2), textcoords="offset points")

    for (key, label), color in zip(MODELS, COLORS):
        pres = [(angles[i], min(cells[(key, s)], RMAX)) for i, (s, _) in enumerate(AXES)
                if (key, s) in cells]
        if not pres:
            continue
        th = [p[0] for p in pres] + [pres[0][0]]
        r = [p[1] for p in pres] + [pres[0][1]]
        ax.plot(th, r, color=color, lw=2.0, label=label, zorder=5)
        ax.fill(th, r, color=color, alpha=0.06, zorder=2)
        ax.scatter([p[0] for p in pres], [p[1] for p in pres], s=26, color=color,
                   edgecolor="white", linewidth=1.0, zorder=6)

    ax.set_title("Challenger strength vs. laplace, by stratum (log score)",
                 fontsize=12.5, pad=24)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.20), ncol=3,
              frameon=False, fontsize=10, handlelength=1.2, columnspacing=1.6)
    fig.subplots_adjust(bottom=0.16, top=0.90)
    for ext in ("svg", "png"):
        out = os.path.join(_ROOT, "docs", "assets", f"radar-canonical.{ext}")
        fig.savefig(out, format=ext, dpi=160, bbox_inches="tight", facecolor="white")
        print(f"wrote {out}")
    for (key, label) in MODELS:
        print(f"{label:16s}", "  ".join(f"{s}={cells.get((key, s), float('nan')):.2f}"
                                       for s, _ in AXES))


if __name__ == "__main__":
    main()
