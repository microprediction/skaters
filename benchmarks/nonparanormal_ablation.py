"""Does the nonparanormal marginal transform pay? (issue #80 ablation)

Liu, Lafferty and Wasserman (JMLR 2009) estimate a Gaussian copula by
Gaussianizing each margin through a Winsorized empirical CDF:
z = Phi^{-1}(F_n(y)). The multivariate payoff (graph estimation) has no
univariate analogue, but the marginal transform itself is a candidate
coordinate: model the series where its stationary marginal is exactly N(0,1),
then push the predictive back through the monotone inverse so it inherits the
empirical marginal's skew and kurtosis.

Placement matters. In "model first, conform last" the trunk combines candidate
MEANS and the terminal leaf supplies all variance and tails, so a pool
candidate's inverse-mapped shape never reaches the output (terminal.py). The
real test is the outer conjugation of the whole forecaster:

    npn = conjugate(laplace(k=1, tails="gaussian"), gaussianize(), k=1)

Three departures from the paper, all deliberate and all measured. First, no
hard Winsorization: delta_n-clipping is variance control for covariance
estimation, and it flattens F exactly where the log-score is decided (new
records). The empirical CDF is instead blended with a running Gaussian,
F = (n0*Phi + n*G)/(n0+n), which keeps F strictly increasing with Gaussian
tails. Second, the transform is online and causal: F uses only past
observations, so it is a legal skaters (forward, inverse_k) pair. Third, the
predictive is scored by exact change of variables (PushforwardDist), because
component-wise delta mapping (the yeo_johnson idiom) cannot carry skew: the
inner components all sit near z = 0 and the mapped mixture comes out
location-symmetric about the median. On skewed iid synthetic data the delta
method loses 0.20 nats to plain laplace while the exact pushforward closes to
within 0.10 nats of the true entropy.

Control arm: the same wrapper with n0 -> inf is cumulative standardization.
It separates "the nonparametric shape helped" from "an outer standardize
helped". The shipped GPD-splice default stays in the comparison as its own
arm, since "does this help" now means "beyond what the tail splice already
does".

Arms:
    gpd      laplace(k=1)                     the shipped default
    plain    laplace(k=1, tails="gaussian")   no tail splice
    npn      gaussianize(n0=8) around plain
    npn_gpd  gaussianize(n0=8) around the shipped default
    ctrl     gaussianize(n0=inf) around plain

    PYTHONPATH=src python benchmarks/nonparanormal_ablation.py
    MAX_SERIES=40 PYTHONPATH=src python benchmarks/nonparanormal_ablation.py

Findings (2026-07-21, 140 non-price FRED daily change series, k=1, burn 300).
Log-likelihood says no: on the continuous universe (rfrac < 0.05, n=104) npn
loses to plain on 81% of series (median -0.07 nats) and npn_gpd loses to the
shipped default on 87% (median -0.08). The synthetic best case (+0.37 nats on
skewed iid, verified by this file's transform) does not transfer: a cumulative
marginal fights the conditional dynamics, and the GPD splice already owns the
tails.

CRPS says sometimes: npn wins CRPS on 56-63% of continuous skewed series
(|skew| > 0.72). The recoding helps the body of skewed marginals exactly where
CRPS weighs it, and costs the tails exactly where the log-score is decided.

Lattice series are structural losses (rfrac >= 0.05: median -1.3 nats, win
11%). sticky detects repeated values in y; the evolving recoding maps equal
y to drifting z, the repeats disappear, and the terminal leaf's scale
collapses. Any promoted composition would need the lattice projection outside
the marginal recoding, and sticky consumes mixture components, which the
exact pushforward does not have.

Verdict for issue #80: not a default and not a pool candidate (placement is
forced outer, see above). The one measured edge, body shape on skewed
continuous series, is a CRPS-only effect. The multivariate content of the
paper (rank correlations, Gaussian copula) is a covariance idea and belongs
with the cov side of the house, not the univariate forecaster.
"""

from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import bisect
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fred
import fred_universe
from bench_core import roll_dist_scores
from skaters import laplace
from skaters.conjugate import conjugate
from skaters.dist import Dist
from skaters.tails import _phi, _phi_inv

MIN_CHANGES = 700
MAX_WORKERS = min(8, (os.cpu_count() or 4))
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "comparisons", "_nonparanormal.csv")


# ---------------------------------------------------------------------------
# The transform
# ---------------------------------------------------------------------------

def gaussianize(n0: float = 8.0, max_buffer: int = 4000, knots: int = 128,
                min_obs: int = 16):
    """Nonparanormal marginal transform: z = Phi^{-1}(F(y)), F a blended CDF.

    F(y) = (n0 * Phi((y - mu)/sigma) + n * G(y)) / (n0 + n)

    G is the empirical CDF read at midranks and interpolated linearly between
    quantile-spaced knots. A raw step ECDF concentrates the inverse map on
    data atoms (many quantile levels invert to the same past value), which
    spikes the mapped predictive at old observations and starves the density
    between them. Interpolation is what makes the quantile function usable for
    density forecasting. Beyond the extreme knots the map extends linearly in
    z per y, which is a Gaussian-weight tail in the original coordinate.

    (mu, sigma) are cumulative running moments and n0 is the prior weight of
    the Gaussian anchor: once n >> n0 the empirical shape dominates. n0 = inf
    never builds a table and is the cumulative-standardization control. The
    forward is causal (the table excludes the current point at evaluation
    time). The inverse wraps each z-space predictive in a PushforwardDist,
    the exact change of variables through the same table.

    The whole map is a pair of piecewise-linear tables (ys, zs) rebuilt from
    pure data each tick. Both directions are the same table, so forward and
    inverse are exact inverses of each other.
    """
    pure_gauss = math.isinf(n0)

    def _build_table(buf, n, mu, sigma):
        """(ys, zs): strictly increasing knots of the y <-> z map.

        Spacing guards keep every segment's slope sane in both directions:
        float-adjacent knots (lattice data) would otherwise give a segment a
        slope like 1e18, and a record observation extrapolating through it an
        astronomical z whose finite logpdf poisons a whole study.
        """
        m = min(knots, n)
        y_eps = 1e-9 * max(sigma, 1e-12)
        ys, zs = [], []
        prev_f = 0.0
        for j in range(m):
            r = (j + 0.5) * n / m            # fractional rank in [0, n)
            i = min(int(r), n - 1)
            y_j = buf[i]
            # midrank of y_j in the full buffer (ties collapse to one knot)
            lo = bisect.bisect_left(buf, y_j)
            hi = bisect.bisect_right(buf, y_j)
            g = (lo + 0.5 * (hi - lo) + 0.5) / (n + 1.0)
            f = (n0 * _phi((y_j - mu) / sigma) + n * g) / (n0 + n)
            if f <= prev_f + 1e-12 or (ys and y_j <= ys[-1] + y_eps):
                continue
            ys.append(y_j)
            zs.append(_phi_inv(f))
            prev_f = f
        return ys, zs

    def forward(y: float, state: dict | None) -> tuple[float, dict]:
        if state is None:
            state = {"buf": [], "count": 0, "mean": 0.0, "m2": 0.0,
                     "ys": [], "zs": []}
        if not math.isfinite(y):
            return 0.0, state
        count = state["count"]
        sigma = math.sqrt(state["m2"] / count) if count >= 2 and state["m2"] > 0 else 0.0
        if sigma <= 0:
            z = 0.0
        elif len(state["ys"]) >= 2:
            z = _pw(y, state["ys"], state["zs"])
        else:
            z = (y - state["mean"]) / sigma
        # update running moments (Welford), the sorted buffer, and the table
        count += 1
        delta = y - state["mean"]
        mean = state["mean"] + delta / count
        m2 = state["m2"] + delta * (y - mean)
        buf = state["buf"]
        ys, zs = state["ys"], state["zs"]
        if not pure_gauss:
            bisect.insort(buf, y)
            if len(buf) > max_buffer:
                # drop an interior point rather than an extreme (keep the tails)
                del buf[len(buf) // 2]
            n = len(buf)
            if n >= min_obs and m2 > 0:
                ys, zs = _build_table(buf, n, mean, math.sqrt(m2 / count))
        return z, {"buf": buf, "count": count, "mean": mean, "m2": m2,
                   "ys": ys, "zs": zs}

    def inverse_k(dists: list, state: dict) -> list:
        count = state["count"]
        if count < 2 or state["m2"] <= 0:
            return dists
        ys, zs = state["ys"], state["zs"]
        if len(ys) < 2:
            # warm-up: the map is the standardization affine, as a 2-knot table
            sigma = math.sqrt(state["m2"] / count)
            mu = state["mean"]
            ys, zs = [mu - sigma, mu + sigma], [-1.0, 1.0]
        return [PushforwardDist(d, ys, zs) for d in dists]

    return forward, inverse_k


class PushforwardDist:
    """The exact pushforward of a z-space predictive through y <-> z tables.

    Delta-method component mapping loses the skew: the inner components all
    sit near z = 0, so a component-wise map yields a location-symmetric
    mixture around the median whatever the marginal looks like. The change of
    variables is exact instead:

        log p_Y(y) = log p_Z(z(y)) + log dz/dy
        F_Y(y)     = F_Z(z(y))

    z(y) is piecewise linear, so dz/dy is the segment slope. CRPS integrates
    in z-coordinates, where dy = y'(z) dz with y'(z) constant per segment:

        crps(x) = integral (F_Z(z) - 1{z >= z(x)})^2 y'(z) dz

    evaluated by trapezoid on the table knots plus tail extensions.
    """

    __slots__ = ("inner", "ys", "zs")

    def __init__(self, inner: Dist, ys: list, zs: list):
        self.inner = inner
        self.ys = ys
        self.zs = zs

    def _z(self, y: float) -> float:
        # clamp the linear extrapolation: beyond ~8 z-units past the table the
        # density is already negligible, and an extreme slope must not launch
        # z to a magnitude whose finite logpdf distorts study means
        z = _pw(y, self.ys, self.zs)
        return min(max(z, self.zs[0] - 8.0), self.zs[-1] + 8.0)

    def _y(self, z: float) -> float:
        return _pw(z, self.zs, self.ys)

    def _slope(self, y: float) -> float:
        """dz/dy at y (end segments extend beyond the table)."""
        ys, zs = self.ys, self.zs
        i = bisect.bisect_left(ys, y)
        i = min(max(i, 1), len(ys) - 1)
        return (zs[i] - zs[i - 1]) / (ys[i] - ys[i - 1])

    def logpdf(self, x: float) -> float:
        return self.inner.logpdf(self._z(x)) + math.log(self._slope(x))

    def pdf(self, x: float) -> float:
        return self.inner.pdf(self._z(x)) * self._slope(x)

    def cdf(self, x: float) -> float:
        return self.inner.cdf(self._z(x))

    def quantile(self, p: float) -> float:
        return self._y(self.inner.quantile(p))

    def crps(self, x: float) -> float:
        zstar = self._z(x)
        zs, ys = self.zs, self.ys
        s_lo = (ys[1] - ys[0]) / (zs[1] - zs[0])
        s_hi = (ys[-1] - ys[-2]) / (zs[-1] - zs[-2])
        base = [zs[0] - 8.0, zs[0] - 6.0, zs[0] - 4.0, zs[0] - 2.0, zs[0] - 1.0]
        base += zs
        base += [zs[-1] + 1.0, zs[-1] + 2.0, zs[-1] + 4.0, zs[-1] + 6.0, zs[-1] + 8.0]
        # the indicator kink must be a node wherever the realization fell
        base += [zstar - 1.0, zstar, zstar + 1.0]
        base = sorted(set(base))
        # refine: trapezoid needs steps ~0.1 where the integrand curves
        nodes = [base[0]]
        for z in base[1:]:
            lo = nodes[-1]
            gap = z - lo
            if gap > 0.1:
                pieces = min(int(gap / 0.1) + 1, 40)
                step = gap / pieces
                nodes.extend(lo + step * (j + 1) for j in range(pieces - 1))
            nodes.append(z)
        cdf = self.inner.cdf
        total = 0.0
        prev_z = nodes[0]
        c_prev = cdf(prev_z)
        for z in nodes[1:]:
            c = cdf(z)
            # zstar is a node, so each segment lies wholly on one side of the
            # kink; the indicator belongs to the segment, not the node
            ind = 1.0 if prev_z >= zstar else 0.0
            g0 = (c_prev - ind) ** 2
            g1 = (c - ind) ** 2
            # y'(z) for this z-segment: table slope inside, end slopes outside
            if z <= zs[0]:
                yp = s_lo
            elif prev_z >= zs[-1]:
                yp = s_hi
            else:
                yp = (self._y(z) - self._y(prev_z)) / (z - prev_z)
            total += 0.5 * (g0 + g1) * (z - prev_z) * yp
            prev_z, c_prev = z, c
        return total

    @property
    def mean(self) -> float:
        # quantile-average through the map; used for reporting only
        qs = [self._y(self.inner.quantile((j + 0.5) / 32)) for j in range(32)]
        return sum(qs) / len(qs)

    @property
    def std(self) -> float:
        qs = [self._y(self.inner.quantile((j + 0.5) / 32)) for j in range(32)]
        mu = sum(qs) / len(qs)
        return math.sqrt(sum((q - mu) ** 2 for q in qs) / len(qs))

    def __repr__(self) -> str:
        return f"PushforwardDist(knots={len(self.ys)}, inner={self.inner!r})"


def _pw(x, xs, fs):
    """Piecewise-linear with linear extrapolation from the end segments."""
    i = bisect.bisect_left(xs, x)
    if i <= 0:
        i = 1
    elif i >= len(xs):
        i = len(xs) - 1
    x0, x1 = xs[i - 1], xs[i]
    f0, f1 = fs[i - 1], fs[i]
    return f0 + (f1 - f0) * (x - x0) / (x1 - x0)


# ---------------------------------------------------------------------------
# Study harness
# ---------------------------------------------------------------------------

ARMS = {
    "gpd":     lambda: laplace(k=1),
    "plain":   lambda: laplace(k=1, tails="gaussian"),
    "npn":     lambda: conjugate(laplace(k=1, tails="gaussian"), gaussianize(n0=8.0), k=1),
    "npn_gpd": lambda: conjugate(laplace(k=1), gaussianize(n0=8.0), k=1),
    "ctrl":    lambda: conjugate(laplace(k=1, tails="gaussian"), gaussianize(n0=float("inf")), k=1),
}


def score(sid):
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    if len(ch) < MIN_CHANGES:
        return None
    row = {"sid": sid}
    for name, make in ARMS.items():
        lp, cr, n = roll_dist_scores(make, ch)
        if not (math.isfinite(lp) and math.isfinite(cr)):
            return None
        row[name + "_lp"], row[name + "_cr"] = lp, cr
    # marginal shape of the changes, for the split
    m = len(ch)
    mu = sum(ch) / m
    c2 = sum((x - mu) ** 2 for x in ch) / m
    c3 = sum((x - mu) ** 3 for x in ch) / m
    c4 = sum((x - mu) ** 4 for x in ch) / m
    row["skew"] = c3 / c2 ** 1.5 if c2 > 0 else 0.0
    row["kurt"] = c4 / c2 ** 2 - 3.0 if c2 > 0 else 0.0
    # repeat fraction of recent changes (study.py convention): lattice series
    # are sticky territory, and sticky lives in y-space where the wrapper
    # cannot reach it, so they are reported as their own split
    tail = ch[-300:]
    row["rfrac"] = (sum(1 for i in range(1, len(tail)) if tail[i] == tail[i - 1])
                    / max(len(tail) - 1, 1))
    return row


def main():
    uj = os.path.join(fred._CACHE, "universe_daily.json")
    tmap = ({s["id"]: s.get("title", "") for s in json.load(open(uj))}
            if os.path.exists(uj) else {})
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    if os.environ.get("STUDY_EXCLUDE_PRICE") == "1":
        _PRICE = {"equity", "fx", "commodity"}
        ids = [s for s in ids if fred_universe.asset_class(tmap.get(s, "")) not in _PRICE]
    cap = int(os.environ.get("MAX_SERIES", "0"))
    if cap:
        ids = ids[::max(1, len(ids) // cap)][:cap]

    rows = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score, s): s for s in ids}
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r:
                rows.append(r)
            if done % 20 == 0:
                print(f"  {done}/{len(ids)} scored ({len(rows)} kept)", flush=True)

    if not rows:
        print("no qualifying series (need cached FRED data)")
        return

    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    cols = list(rows[0].keys())
    with open(RESULTS, "w") as fh:
        fh.write(",".join(cols) + "\n")
        for r in rows:
            fh.write(",".join(str(r[c]) for c in cols) + "\n")
    print(f"wrote {len(rows)} rows -> {RESULTS}\n")

    import numpy as np
    cont = [r for r in rows if r["rfrac"] < 0.05]
    med = float(np.median([abs(r["skew"]) for r in cont])) if cont else 0.0
    splits = [
        ("ALL", rows),
        ("continuous (rfrac < 0.05), the study universe", cont),
        (f"continuous, |skew| > {med:.2f}: shape should matter",
         [r for r in cont if abs(r["skew"]) > med]),
        (f"continuous, |skew| <= {med:.2f}: shape should be ~neutral",
         [r for r in cont if abs(r["skew"]) <= med]),
        ("lattice-ish (rfrac >= 0.05): sticky territory, wrapper handicapped",
         [r for r in rows if r["rfrac"] >= 0.05]),
    ]
    for label, sub in splits:
        if not sub:
            continue
        print(f"{label}: n={len(sub)}")
        for arm, ref in (("npn", "plain"), ("ctrl", "plain"),
                         ("npn_gpd", "gpd"), ("npn", "gpd")):
            dlp = np.array([r[arm + "_lp"] - r[ref + "_lp"] for r in sub])
            dcr = np.array([r[ref + "_cr"] - r[arm + "_cr"] for r in sub])  # + = arm better
            print(f"  {arm} vs {ref}:  LL mean {float(np.mean(dlp)):+.4f} "
                  f"median {float(np.median(dlp)):+.4f} nats "
                  f"(win {float(np.mean(dlp > 0)) * 100:.0f}%)   "
                  f"CRPS win {float(np.mean(dcr > 0)) * 100:.0f}%")
        print()


if __name__ == "__main__":
    main()
