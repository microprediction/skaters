"""Accuracy vs speed frontier for the landing page. Accuracy = mean continuous
log-likelihood (500-series study; Prophet from a 25-series spread sample). Speed =
forecasts per second = 300 / (measured single-core seconds per series), the test
window being 300 one-step forecasts. Both axes higher = better."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WINDOW = 300  # one-step forecasts per series
# (label, runtime ms/series at TEST=300, mean continuous logpdf, is_ours)
rows = [
    ("laplace",          196, 2.855, True),
    ("GARCH-t",          226, 2.72, False),
    ("AutoETS",          275, 2.20, False),
    ("SARIMAX",         1178, 2.13, False),
    ("AutoARIMA",        863, 2.09, False),
    ("AutoARIMA+ACI",    900, 1.89, False),
    ("AutoARIMA+conformal", 900, 1.47, False),
    ("NeuralForecast-t", 1897, 0.82, False),
    ("Prophet",         1266, -0.22, False),
]
pts = [(lbl, 1000.0 * WINDOW / rt, acc, ours) for lbl, rt, acc, ours in rows]  # fc/sec

fig, ax = plt.subplots(figsize=(7.8, 4.8))
fig.patch.set_facecolor("white")
ax.axhline(2.855, color="#4a3aff", lw=0.8, ls=":", alpha=0.5)
ax.axvline(1000.0 * WINDOW / 196, color="#4a3aff", lw=0.8, ls=":", alpha=0.5)
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
ax.set_title("Accuracy vs. speed on 500 FRED series", fontsize=13, pad=12)
ax.grid(True, which="both", alpha=0.18)
ax.set_xlim(120, 2600)
ax.set_ylim(-0.6, 3.1)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig("docs/assets/frontier.svg", format="svg", bbox_inches="tight")
fig.savefig("docs/assets/frontier.png", format="png", dpi=160, bbox_inches="tight")
print("wrote docs/assets/frontier.svg and frontier.png")
