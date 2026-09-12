"""Terminal-leaf bake-off on the whitened residual stream.

Same harness as conformal_decomposition.py: fixed laplace mean, EWMA scale,
AR(1) whitening. The contest is what terminal law to attach to the whitened
residuals w_t — the "conform last" design decision:

  gauss    N(0, EWMA var of w)                       (fitted, thin)
  mix      scale_mixture_leaf                        (fitted, shipped default)
  emp      expanding empirical (pure conforming)     (KDE-smoothed for log)
  empsm    smoothed empirical: banded order-stat     (small-n smoothing;
           averaging, band ~3% of n capped at 25)     converges to emp)
  empw     windowed empirical, last 300 w's          (recency: hedges drift
                                                      the transforms missed)
  qsgd     99 quantiles by online pinball SGD        (bounded memory, recency;
                                                      CRPS contract only)
  empgpd   empirical body + moment-fit GPD tails     (conform body, model tail)
  empcp    conformal tail completion (log only):     (the minimal completion:
           KDE body carries n/(n+1); the reserved     conform all observed data,
           1/(n+1) spread by GPD beyond extremes)     model only reserved mass)
  ens      score-weighted ensemble of the above      (the learned schedule:
           (decayed-CRPS softmax, quantile-averaged;   weights migrate from
           log side: decayed-log-lik opinion pool)     parametric to empirical
                                                       as the sample grows)

Scores: CRPS (99-quantile pinball grid, all leaves) and log score (leaves with
a density; empirical variants via a 256-center binned KDE, Silverman
bandwidth; empgpd swaps GPD densities in beyond the 95% thresholds).

Interpretation caveat: the mean pass cannot remove volatility clustering, so
all vol-recency here is carried by the single-speed EWMA scale state. If empw
beats emp, that may be shape drift OR vol dynamics faster than the EWMA
tracks (leaf recency acting as a second, crude vol tracker). Disambiguate by
rerunning with a richer scale state (GARCH / multi-speed) before concluding
the leaf itself should forget.

    PYTHONPATH=src python benchmarks/leaf_bakeoff.py [N_SERIES]
"""

from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import bisect
import csv
import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fred
from conformal_decomposition import (_corpus, crps_from_quantiles, emp_quantiles,
                                     TAUS, _PHI_INV, BURN)
from skaters.api import laplace
from skaters.leaf import scale_mixture_leaf

MAX_WORKERS = min(8, (os.cpu_count() or 4))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leaf_bakeoff.csv")

LEAVES = ["gauss", "mix", "emp", "empsm", "empw", "qsgd", "empgpd", "ens"]
LOGLEAVES = ["gauss", "mix", "emp", "empw", "empgpd", "empcp", "ens"]
WINDOW = 300   # recency window for empw
ENS_BASE = ["gauss", "mix", "empsm", "empw", "empgpd"]  # ens combines these
RHO = 0.995    # decay for the ensemble's running scores
ETA = 8.0      # softmax sharpness on decayed CRPS (scale-normalized)
ETA_L = 0.8    # learning rate on decayed log-lik
COLS = [f"crps_{m}" for m in LEAVES] + [f"ll_{m}" for m in LOGLEAVES]


def _kde_logpdf(centers, h, x):
    if not centers or h <= 0:
        return -20.0
    s = 0.0
    c = 1.0 / (h * math.sqrt(2 * math.pi))
    for m in centers:
        s += math.exp(-0.5 * ((x - m) / h) ** 2)
    v = s * c / len(centers)
    return math.log(v) if v > 0 else -50.0


def _gpd_moment(exc):
    """Moment estimator for GPD (xi, beta) from exceedances."""
    n = len(exc)
    mu = sum(exc) / n
    var = sum((e - mu) ** 2 for e in exc) / max(n - 1, 1)
    if var <= 0 or mu <= 0:
        return 0.0, max(mu, 1e-6)
    xi = 0.5 * (1.0 - mu * mu / var)
    xi = max(-0.4, min(0.9, xi))
    beta = 0.5 * mu * (mu * mu / var + 1.0)
    return xi, max(beta, 1e-6)


def _gpd_quantile(p, xi, beta):
    """Quantile of exceedance beyond threshold at tail prob p in (0,1]."""
    if abs(xi) < 1e-6:
        return -beta * math.log(p)
    return beta / xi * (p ** (-xi) - 1.0)


def _gpd_logpdf(e, xi, beta):
    if e < 0:
        return -50.0
    if abs(xi) < 1e-6:
        return -math.log(beta) - e / beta
    z = 1.0 + xi * e / beta
    if z <= 0:
        return -50.0
    return -math.log(beta) - (1.0 / xi + 1.0) * math.log(z)


def score_series(job):
    sid, series = job
    try:
        return _score(sid, series)
    except Exception as e:
        return [sid, len(series)] + [float("nan")] * len(COLS) + [repr(e)]


def _score(sid, series):
    f = laplace(k=1, objective="likelihood")
    state = None
    pend = None
    means = []
    for y in series:
        means.append(pend[0].mean if pend is not None else 0.0)
        d, state = f(y, state)
        pend = d

    alpha = 0.03
    lam = 0.995
    v = None
    g = None
    nR = 0
    sxx = 1e-8; sxy = 0.0
    s2w = 1.0
    leaf = scale_mixture_leaf(k=1)
    leaf_state = None
    leaf_pend = None
    z_prev = 0.0
    sorted_w = []
    from collections import deque
    win = deque()
    sorted_win = []
    qsgd = None                    # online pinball-tracked quantiles of w
    crps = {m: 0.0 for m in LEAVES}
    ll = {m: 0.0 for m in LOGLEAVES}
    dc = {m: None for m in ENS_BASE}    # decayed CRPS per base leaf
    dl = {m: 0.0 for m in ENS_BASE if m != "empsm"}  # decayed log-lik weights
    nsc = 0

    for t in range(1, len(series)):
        y = series[t]
        m = means[t]
        r = y - m

        lo = 0.0025 * (g if g else 0.0)
        vt = max(v if v is not None else 1.0, lo)
        sig = math.sqrt(vt) if vt > 0 else 1.0
        phi = max(-0.99, min(0.99, sxy / sxx)) if sxx > 1e-9 else 0.0
        arm = phi * z_prev
        sw = math.sqrt(max(s2w, 1e-12))

        nw = len(sorted_w)
        if t > BURN and nw > 100 and leaf_pend is not None:
            scale_out = lambda q: m + sig * (arm + q)
            # --- quantiles of w under each leaf ---
            qg = [sw * q for q in _PHI_INV]
            D = leaf_pend[0]
            qm = [D.quantile(tau) for tau in TAUS]
            qe = emp_quantiles(sorted_w)
            # smoothed empirical: banded mean of order stats via prefix sums
            band = min(25, max(1, round(0.03 * nw)))
            pref = [0.0]
            for x in sorted_w:
                pref.append(pref[-1] + x)
            qsm = []
            for tau in TAUS:
                i = round(tau * (nw - 1))
                a = max(0, i - band); b = min(nw, i + band + 1)
                qsm.append((pref[b] - pref[a]) / (b - a))
            qwin = emp_quantiles(sorted_win) if len(sorted_win) > 100 else qe
            qq = list(qsgd)
            # empgpd: replace tau<.05 / tau>.95 with GPD-splice quantiles
            iu = int(0.95 * (nw - 1)); il = int(0.05 * (nw - 1))
            uhi = sorted_w[iu]; ulo = sorted_w[il]
            exc_hi = [x - uhi for x in sorted_w[iu:] if x > uhi]
            exc_lo = [ulo - x for x in sorted_w[:il + 1] if x < ulo]
            qgpd = list(qe)
            if len(exc_hi) >= 20:
                xh, bh = _gpd_moment(exc_hi)
                for i, tau in enumerate(TAUS):
                    if tau > 0.95:
                        qgpd[i] = uhi + _gpd_quantile((1 - tau) / 0.05, xh, bh)
            if len(exc_lo) >= 20:
                xl, bl = _gpd_moment(exc_lo)
                for i, tau in enumerate(TAUS):
                    if tau < 0.05:
                        qgpd[i] = ulo - _gpd_quantile(tau / 0.05, xl, bl)
            qs = {"gauss": qg, "mix": qm, "emp": qe, "empsm": qsm,
                  "empw": qwin, "qsgd": qq, "empgpd": qgpd}
            # ens: decayed-CRPS softmax over base leaves, quantile-averaged
            vals = [dc[m] for m in ENS_BASE if dc[m] is not None]
            if vals:
                cbar = sum(vals) / len(vals) or 1e-12
                ws = [math.exp(-ETA * (dc[m] if dc[m] is not None else cbar) / cbar)
                      for m in ENS_BASE]
                tot = sum(ws)
                ws = [x / tot for x in ws]
            else:
                ws = [1.0 / len(ENS_BASE)] * len(ENS_BASE)
            qs["ens"] = [sum(w * qs[m][i] for w, m in zip(ws, ENS_BASE))
                         for i in range(len(TAUS))]
            step_crps = {}
            for mth in LEAVES:
                c = crps_from_quantiles([scale_out(q) for q in qs[mth]], y)
                crps[mth] += c
                step_crps[mth] = c
            for mth in ENS_BASE:
                dc[mth] = step_crps[mth] if dc[mth] is None else \
                    RHO * dc[mth] + (1 - RHO) * step_crps[mth]
            # --- log score of w under density leaves (scale back: -log sig) ---
            w_obs = (r / sig) - arm
            lg = -0.5 * math.log(2 * math.pi * sw * sw) - w_obs * w_obs / (2 * sw * sw)
            lm = D.logpdf(w_obs)
            if not math.isfinite(lm):
                lm = -50.0
            h = 1.06 * (sw if sw > 0 else 1.0) * nw ** (-0.2)
            centers = emp_quantiles(sorted_w)[::1] if nw < 256 else \
                [sorted_w[int(i * (nw - 1) / 255)] for i in range(256)]
            le = _kde_logpdf(centers, h, w_obs)
            nwin = len(sorted_win)
            if nwin > 100:
                hw = 1.06 * (sw if sw > 0 else 1.0) * nwin ** (-0.2)
                cw = sorted_win if nwin < 256 else \
                    [sorted_win[int(i * (nwin - 1) / 255)] for i in range(256)]
                lew = _kde_logpdf(cw, hw, w_obs)
            else:
                lew = le
            if w_obs > uhi and len(exc_hi) >= 20:
                lgp = math.log(0.05) + _gpd_logpdf(w_obs - uhi, xh, bh)
            elif w_obs < ulo and len(exc_lo) >= 20:
                lgp = math.log(0.05) + _gpd_logpdf(ulo - w_obs, xl, bl)
            else:
                lgp = le
            lsig = math.log(sig) if sig > 0 else 0.0
            wmax = sorted_w[-1]; wmin = sorted_w[0]
            half = 1.0 / (2.0 * (nw + 1))
            if w_obs > wmax and len(exc_hi) >= 20:
                lcp = math.log(half) + _gpd_logpdf(w_obs - wmax, xh, bh)
            elif w_obs < wmin and len(exc_lo) >= 20:
                lcp = math.log(half) + _gpd_logpdf(wmin - w_obs, xl, bl)
            else:
                lcp = math.log(nw / (nw + 1.0)) + le
            # uniform delta-mixture floor: every leaf's w-density is mixed
            # with the expanding Gaussian reference so no leaf is clamped
            # differently from another (log columns are genuine log scores).
            gvar = sum(x * x for x in (sorted_w[int(i*(nw-1)/255)] for i in range(256))) / 256.0
            gvar = max(gvar, 1e-12)
            lref = -0.5 * math.log(2 * math.pi * gvar) - w_obs * w_obs / (2 * gvar)
            def _floor(lw):
                a = math.log(0.99) + max(lw, -1e12)
                b = math.log(0.01) + lref
                hi2 = max(a, b)
                return hi2 + math.log(math.exp(a - hi2) + math.exp(b - hi2))
            lg = _floor(lg); lm = _floor(lm); le = _floor(le)
            lew = _floor(lew); lgp = _floor(lgp); lcp = _floor(lcp)
            base_ll = {"gauss": lg, "mix": lm, "empw": lew, "empgpd": lgp}
            mx = max(dl.values())
            lws = {m: math.exp(dl[m] - mx) for m in dl}
            ltot = sum(lws.values())
            mmax = max(base_ll.values())
            mix_dens = sum(lws[m] / ltot * math.exp(base_ll[m] - mmax) for m in dl)
            lens = mmax + math.log(mix_dens)
            for mth, lw in (("gauss", lg), ("mix", lm), ("emp", le),
                            ("empw", lew), ("empgpd", lgp), ("empcp", lcp),
                            ("ens", lens)):
                ll[mth] += lw - lsig
            for m in dl:
                dl[m] = RHO * dl[m] + ETA_L * base_ll[m]
            nsc += 1

        # --- updates ---
        nR += 1
        g = r * r if g is None else g + (r * r - g) / nR
        v = r * r if v is None else (1 - alpha) * v + alpha * r * r
        z = r / sig
        w = z - arm
        sxx = lam * sxx + z_prev * z_prev
        sxy = lam * sxy + z_prev * z
        s2w = (1 - alpha) * s2w + alpha * w * w
        ld, leaf_state = leaf(w, leaf_state)
        leaf_pend = ld
        bisect.insort(sorted_w, w)
        win.append(w)
        bisect.insort(sorted_win, w)
        if len(win) > WINDOW:
            old = win.popleft()
            del sorted_win[bisect.bisect_left(sorted_win, old)]
        if qsgd is None:
            qsgd = [q * sw for q in _PHI_INV]
        lr = 0.05 * sw
        qsgd = sorted(q + lr * (tau - (1.0 if w < q else 0.0))
                      for q, tau in zip(qsgd, TAUS))
        z_prev = z

    if not nsc:
        return [sid, len(series)] + [float("nan")] * len(COLS) + ["too short"]
    return ([sid, len(series)] + [crps[m] / nsc for m in LEAVES]
            + [ll[m] / nsc for m in LOGLEAVES])


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    data = _corpus()
    ids = sorted(data)
    if limit:
        step = max(1, len(ids) // limit)
        ids = ids[::step][:limit]
    jobs = [(sid, data[sid]) for sid in ids]
    print(f"{len(jobs)} series, leaves {LEAVES}, {MAX_WORKERS} workers -> {OUT}",
          flush=True)

    rows = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(score_series, j): j[0] for j in jobs}
        for done, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if done % 10 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}", flush=True)

    rows.sort()
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["series", "n"] + COLS)
        w.writerows(rows)

    good = [r for r in rows if len(r) == 2 + len(COLS)
            and all(isinstance(x, float) and math.isfinite(x) for x in r[2:])]
    print(f"\n{len(good)}/{len(rows)} series scored")
    if not good:
        return
    import statistics

    def report(subset, label):
        if not subset:
            return
        print(f"\n[{label}: {len(subset)} series]")
        print("CRPS relative to gauss leaf (mean / median; lower better):")
        base = COLS.index("crps_gauss")
        for m in LEAVES:
            i = COLS.index(f"crps_{m}")
            v = [r[2 + i] / r[2 + base] for r in subset if r[2 + base] > 0]
            print(f"  {m:7s} {statistics.mean(v):.4f} / {statistics.median(v):.4f}")
        print("log score minus gauss leaf (nats/obs, mean / median; higher better):")
        baseL = COLS.index("ll_gauss")
        for m in LOGLEAVES:
            i = COLS.index(f"ll_{m}")
            v = [r[2 + i] - r[2 + baseL] for r in subset]
            wins = sum(1 for x in v if x > 0) / len(v)
            print(f"  {m:7s} {statistics.mean(v):+.4f} / {statistics.median(v):+.4f}"
                  f"  beats gauss on {100*wins:.0f}%")

    report(good, "all")
    report([r for r in good if r[1] <= 1200], "short: n <= 1200")
    report([r for r in good if r[1] > 2500], "long: n > 2500")


if __name__ == "__main__":
    main()
