"""CRPS is nearly tail-blind: a demonstration for the likelihood-vs-CRPS essay.

Truth is Student-t(df=3) (heavy tails; Var = df/(df-2) = 3). We fit a Gaussian
N(0, sigma^2) to it under each proper score. Log-likelihood insists on covering
the tail (its optimum is variance-matching, sigma = sqrt(3)); CRPS, whose penalty
for a far outcome grows only linearly, prefers a sharper central fit with the
tail squished in. So the CRPS-optimal Gaussian is markedly narrower than the
likelihood-optimal one: it wins CRPS and loses log-likelihood.

Propriety still holds -- the TRUE t3 beats every Gaussian on BOTH scores. The
trade-off lives only among imperfect forecasts. Conformal is the limit: a
bounded-support predictive law assigns zero density (‑inf log-score) to any tail
outcome while keeping a finite, competitive CRPS.

    python benchmarks/crps_tail_blindness.py    # prints the table, writes docs/assets/crps-tail-blindness.{svg,png}
"""
import os
import numpy as np
from scipy import stats
from scipy.optimize import minimize_scalar
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(REPO, "docs", "assets")
DF, N, SEED = 3, 4_000_000, 0
SQRT_PI = np.sqrt(np.pi)

rng = np.random.default_rng(SEED)
y = stats.t.rvs(DF, size=N, random_state=rng)          # realized outcomes ~ truth


def gauss_crps(y, mu, sig):                            # closed-form Gaussian CRPS
    w = (y - mu) / sig
    return sig * (w * (2 * stats.norm.cdf(w) - 1) + 2 * stats.norm.pdf(w) - 1 / SQRT_PI)


def gauss_nll(y, mu, sig):                             # negative log-likelihood
    return 0.5 * np.log(2 * np.pi * sig ** 2) + (y - mu) ** 2 / (2 * sig ** 2)


mean_crps = lambda s: gauss_crps(y, 0.0, s).mean()
mean_nll = lambda s: gauss_nll(y, 0.0, s).mean()
sC = minimize_scalar(mean_crps, bounds=(0.3, 6), method="bounded").x
sL = minimize_scalar(mean_nll, bounds=(0.3, 6), method="bounded").x

# true-t3 baseline (wins both, by propriety) via the energy form for CRPS
xs = stats.t.rvs(DF, size=1_000_000, random_state=rng)
xs2 = stats.t.rvs(DF, size=1_000_000, random_state=rng)
t3_crps = np.abs(xs - y[:len(xs)]).mean() - 0.5 * np.abs(xs - xs2).mean()
t3_nll = (-stats.t.logpdf(y[:1_000_000], DF)).mean()

# conformal-style bounded support: t3 truncated to an observed calibration range
cal = stats.t.rvs(DF, size=2000, random_state=rng)
lo, hi = float(cal.min()), float(cal.max())
outside = float(np.mean((y < lo) | (y > hi)))

print("=== Gaussian fit to Student-t(3) truth (lower is better) ===")
print(f"  likelihood-optimal  sigma = {sL:.3f}  (var {sL**2:.2f} = Var t3)   CRPS {mean_crps(sL):.4f}   NLL {mean_nll(sL):.4f}")
print(f"  CRPS-optimal        sigma = {sC:.3f}  (var {sC**2:.2f})            CRPS {mean_crps(sC):.4f}   NLL {mean_nll(sC):.4f}")
print(f"  CRPS-best Gaussian is {100*(1-sC/sL):.0f}% narrower: tail squished in -> wins CRPS, loses NLL.")
print(f"  TRUE t3 (propriety: best at both)                          CRPS {t3_crps:.4f}   NLL {t3_nll:.4f}")
print(f"  conformal support [{lo:.1f}, {hi:.1f}]: {100*outside:.2f}% of outcomes get -inf log-score, CRPS finite.")

# ---- figure: the two scores want different widths ----
sig = np.linspace(0.6, 3.2, 140)
crps = np.array([mean_crps(s) for s in sig])
nll = np.array([mean_nll(s) for s in sig])
c_crps, c_nll = "#1a9850", "#762a83"

fig, ax1 = plt.subplots(figsize=(8.2, 4.9))
fig.patch.set_facecolor("white")
ax1.plot(sig, crps, color=c_crps, lw=2.4)
ax1.set_xlabel(r"Gaussian forecast width  $\sigma$   (smaller = tail squished in $\rightarrow$)", fontsize=11)
ax1.set_ylabel("mean CRPS", color=c_crps, fontsize=11)
ax1.tick_params(axis="y", labelcolor=c_crps)
ax1.axvline(sC, color=c_crps, ls=":", lw=1.4)
ax2 = ax1.twinx()
ax2.plot(sig, nll, color=c_nll, lw=2.4)
ax2.set_ylabel("mean negative log-likelihood", color=c_nll, fontsize=11)
ax2.tick_params(axis="y", labelcolor=c_nll)
ax2.axvline(sL, color=c_nll, ls=":", lw=1.4)
ax1.scatter([sC], [crps.min()], color=c_crps, s=95, zorder=5, edgecolor="white", linewidth=1.3)
ax2.scatter([sL], [nll.min()], color=c_nll, s=95, zorder=5, edgecolor="white", linewidth=1.3)
ax1.annotate(f"CRPS wants $\\sigma$={sC:.2f}\n(narrow tail)", (sC, crps.min()),
             xytext=(sC + 0.02, crps.min() + 0.055), color=c_crps, fontsize=10.5,
             fontweight="bold", ha="center", va="bottom")
ax2.annotate(f"likelihood wants $\\sigma$={sL:.2f}\n(covers the tail)", (sL, nll.min()),
             xytext=(sL + 0.68, nll.min() + 0.14), color=c_nll, fontsize=10.5,
             fontweight="bold", ha="center", va="bottom")
ax1.axvspan(sC, sL, color="#bbbbbb", alpha=0.25)
ax1.annotate("tail mass CRPS\nlets you shave off", ((sC + sL) / 2, crps.max() * 0.985),
             fontsize=9.5, color="#555", ha="center", va="top", style="italic")
ax1.set_title("Two proper scores, two different forecasts:\nfit a Gaussian to heavy-tailed "
              r"($t_3$) data and CRPS picks the thinner tail", fontsize=12.5, pad=10)
ax1.spines["top"].set_visible(False)
ax2.spines["top"].set_visible(False)
ax1.set_xlim(sig.min(), sig.max())
fig.tight_layout()
for ext in ("svg", "png"):
    fig.savefig(os.path.join(ASSETS, f"crps-tail-blindness.{ext}"), dpi=155, bbox_inches="tight")
print(f"wrote {ASSETS}/crps-tail-blindness.svg and .png")
