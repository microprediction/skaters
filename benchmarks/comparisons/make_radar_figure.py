"""Static star/radar figure for the README (docs/assets/radar.svg + .png).

Mirrors the interactive challengers radar: per-regime win-rate of each challenger
against laplace, ties split, scaled so a 50/50 draw sits on the dashed laplace
ring at 1.0. Reads the same data the site ships (docs/js/challenges-radar-data.js),
so regenerate this after make_challenges_radar.py. Metric is log-likelihood, the
study's headline. Shows the page's default four challengers, including GARCH-t,
which loses the five non-price regimes but wins the price/returns axis ~1.8x.

    python benchmarks/comparisons/make_radar_figure.py
"""
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
DATA = os.path.join(_ROOT, "docs", "js", "challenges-radar-data.js")

METRIC = "ll"                       # study headline; matches the site default
RMAX = 2.0                          # radial cap (GARCH-t's price win reaches ~1.8)
# The interactive radar's default four challengers, in the site's slot colours,
# so the README/homepage figure matches challengers.html exactly: CSP and nnetar
# win the waveform regimes, GARCH-t stars on price, Theta (R) sits inside the
# ring (laplace beats it almost everywhere).
MODELS = ["CSP", "Theta (R)", "nnetar (R)", "GARCH-t"]
COLORS = ["#2a78d6", "#1baf7a", "#eda100", "#008300"]


def load():
    txt = open(DATA).read()
    return json.loads(txt[txt.index("{"):txt.rindex("}") + 1])


def main():
    data = load()
    axes = data["axes"]
    K = len(axes)
    # Zero location N + clockwise direction already put spoke 0 at the top, so
    # angles are measured plainly from there (no extra pi/2 offset).
    angles = [i * 2 * math.pi / K for i in range(K)]

    fig, ax = plt.subplots(figsize=(6.4, 7.0), subplot_kw={"polar": True})
    fig.patch.set_facecolor("white")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, RMAX)
    ax.set_rgrids([0.5, 1.0, 1.5, 2.0], labels=["", "", "", ""])
    ax.set_xticks(angles)
    ax.set_xticklabels(axes, fontsize=11)
    ax.tick_params(axis="x", pad=10)
    ax.spines["polar"].set_visible(False)
    ax.grid(color="#dddddd", lw=0.8)

    # The laplace reference ring at 1.0.
    ring = [angles[i % K] for i in range(K + 1)]
    ax.plot(ring, [1.0] * (K + 1), color="#5a5a5a", lw=1.6, ls=(0, (5, 4)), zorder=4)
    ax.annotate("laplace = 1", xy=(angles[0], 1.0), fontsize=9.5, color="#5a5a5a",
                xytext=(6, -2), textcoords="offset points")

    for name, color in zip(MODELS, COLORS):
        m = data["models"].get(name)
        if not m:
            continue
        vals = m[METRIC]
        pres = [(angles[i], min(vals[i], RMAX)) for i in range(K) if vals[i] is not None]
        if not pres:
            continue
        th = [p[0] for p in pres] + [pres[0][0]]
        r = [p[1] for p in pres] + [pres[0][1]]
        ax.plot(th, r, color=color, lw=2.0, label=name, zorder=5)
        ax.fill(th, r, color=color, alpha=0.08, zorder=2)
        ax.scatter([p[0] for p in pres], [p[1] for p in pres], s=26, color=color,
                   edgecolor="white", linewidth=1.0, zorder=6)

    ax.set_title("Challenger strength vs. laplace, by regime (log-likelihood)",
                 fontsize=12.5, pad=24)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.20), ncol=3,
              frameon=False, fontsize=10, handlelength=1.2, columnspacing=1.6)
    fig.subplots_adjust(bottom=0.16, top=0.90)
    for ext in ("svg", "png"):
        out = os.path.join(_ROOT, "docs", "assets", f"radar.{ext}")
        fig.savefig(out, format=ext, dpi=160, bbox_inches="tight",
                    facecolor="white")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
