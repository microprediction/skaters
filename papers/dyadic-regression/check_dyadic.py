"""Numbers for the dyadic-regression note.

1. Power-law lag profiles phi_k = k^-alpha: worst relative error of the best one-coefficient-
   per-block approximation, for dyadic blocks (ratio 2) and geometric blocks of ratio r.
2. The fractional-differencing AR(inf) profile pi_k of (1-B)^d: the same, measured directly.
3. Dyadic block-average weights against 1/k: the ratio k * w_k stays in [1, 2).
4. Harmonic dyadic regression: lag k weighted by 1/(2k-1) inside its block, one coefficient per
   block. All coefficients equal reproduces the harmonic kernel of Fishelson & Mohri exactly.

    python check_dyadic.py
"""
import numpy as np

L = 4096


def blocks(r, L):
    """Geometric blocks of ratio r: [1], then lengths growing by r, covering lags 1..L."""
    edges, b = [1], 1.0
    while edges[-1] <= L:
        b *= r
        edges.append(max(edges[-1] + 1, int(round(b))))
    return [(edges[i], min(edges[i + 1], L + 1)) for i in range(len(edges) - 1)]


def worst_rel(phi, r):
    """Max over lags of |psi_k/phi_k - 1| when each block takes the coefficient minimizing the
    worst relative error inside it (the geometric mean of the block's extreme values)."""
    err = 0.0
    nb = 0
    for a, b in blocks(r, len(phi)):
        seg = np.abs(phi[a - 1:b - 1])
        if len(seg) == 0:
            continue
        nb += 1
        hi, lo = seg.max(), seg.min()
        theta = np.sqrt(hi * lo)
        err = max(err, hi / theta - 1, 1 - lo / theta)
    return err, nb


def frac_pi(d, L):
    """AR(inf) coefficients of (1-B)^d y = e, written y_t = sum_k pi_k y_{t-k} + e_t."""
    c = np.empty(L + 1)
    c[0] = 1.0
    for k in range(1, L + 1):
        c[k] = c[k - 1] * (k - 1 - d) / k
    return -c[1:]


k = np.arange(1, L + 1)
print("power law phi_k = k^-alpha, L = 4096: worst relative error / number of blocks")
for alpha in (0.6, 1.0, 1.4, 2.0):
    row = [f"alpha={alpha}"]
    for r in (2.0, 1.5, 1.25):
        e, nb = worst_rel(k ** -alpha, r)
        row.append(f"r={r}: {e:.3f} ({nb})")
    print("  " + "  ".join(row))
print("analytic dyadic bound 2^(alpha/2)-1:",
      {a: round(2 ** (a / 2) - 1, 3) for a in (0.6, 1.0, 1.4, 2.0)})

print("fractional differencing (1-B)^d, L = 4096: worst relative error, dyadic blocks")
for d in (0.1, 0.2, 0.3, 0.4):
    e, nb = worst_rel(frac_pi(d, L), 2.0)
    print(f"  d={d}: {e:.3f} with {nb} blocks (alpha = 1+d, bound {2 ** ((1 + d) / 2) - 1:.3f})")

w = np.zeros(L)
j = 0
while 2 ** j <= L:
    a, b = 2 ** j, min(2 ** (j + 1), L + 1)
    w[a - 1:b - 1] = 2.0 ** -j
    j += 1
ratio = k * w
print(f"dyadic block-average weights: k * w_k in [{ratio.min():.3f}, {ratio.max():.3f}]")
print(f"sum of weights over L={L}: {w.sum():.2f} (log2(L+1) = {np.log2(L + 1):.2f});"
      f" harmonic 1/(2k-1) sum: {np.sum(1 / (2 * k - 1)):.2f} (0.5 ln L = {0.5 * np.log(L):.2f})")

h = 1 / (2 * k - 1)


def worst_rel_harm(phi):
    """As worst_rel, but block j approximates phi_k by theta_j / (2k-1)."""
    err = 0.0
    for a, b in blocks(2.0, len(phi)):
        r = np.abs(phi[a - 1:b - 1]) / h[a - 1:b - 1]
        t = np.sqrt(r.max() * r.min())
        err = max(err, r.max() / t - 1, 1 - r.min() / t)
    return err


print("harmonic dyadic regression, L = 4096: worst relative error (plain dyadic in brackets)")
for alpha in (0.6, 1.0, 1.4, 2.0):
    print(f"  k^-{alpha}: {worst_rel_harm(k ** -alpha):.3f}  [{worst_rel(k ** -alpha, 2.0)[0]:.3f}]"
          f"  bound 2^(|alpha-1|/2)-1 = {2 ** (abs(alpha - 1) / 2) - 1:.3f}")
for d in (0.1, 0.2, 0.3, 0.4):
    pi = frac_pi(d, L)
    print(f"  (1-B)^{d}: {worst_rel_harm(pi):.3f}  [{worst_rel(pi, 2.0)[0]:.3f}]"
          f"  bound 2^(d/2)-1 = {2 ** (d / 2) - 1:.3f}")
