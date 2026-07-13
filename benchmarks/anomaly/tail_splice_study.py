"""The conditional tail fit: does a trailing tail-skater, fit by censored
ML on the region the standard skater defines, fit the tail better?

Construction (proper by the predictable-region argument): skater (i) =
laplace(1) runs as usual; its predictive defines the tail region each tick
(parade z beyond the running 98% thresholds — set before y arrives).
Skater (ii) trails, modelling only the exceedances of z. The censored
likelihood factorizes as (binomial exceedance-rate term) + (conditional
GPD density on the exceedances), so "fit by censored ML" = empirical zeta
+ ML-fitted GPD shape. Three tails are scored, strictly prequentially,
each as a full spliced density in z-space carried back to y-space by
log f(y) = log f_body(y) + log g(z) - log phi(z):

    base:  plain laplace (Gaussian z tail — the panel's 8x offender)
    mom:   GPD splice, method-of-moments fit (gpdtail's estimator)
    cml:   GPD splice, censored-ML fit (Grimshaw profile likelihood over
           the same exceedance window) — the user's conditional tail fit

Scores: overall log-lik, log-lik on tail ticks, and CSL (censored
likelihood score, region = the predictable tail region) — the proper
tail-weighted comparison from the scoring-rules discussion.

Usage:
    python benchmarks/anomaly/tail_splice_study.py --limit 500 --workers 10
"""

from __future__ import annotations
import argparse
import json
import math
import os
import sys
import time
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "src"))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, _HERE)

from benchmarks.fred import _load_levels, _to_changes  # noqa: E402
from benchmarks import fred_universe  # noqa: E402

UNIVERSE = os.path.join(_HERE, "..", "data", "universe_daily.json")
MIN_LEN = 1000
LEVEL = 0.98
WARMUP = 500
NEXC = 1000
REFIT_EVERY = 25
_PRICE = {"equity", "fx", "commodity"}
CLAMP = -20.0
VARIANTS = ("mom", "cml")


def _phi_log(z):
    return -0.5 * z * z - 0.5 * math.log(2.0 * math.pi)


def _phi_cdf(z):
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def _gpd_logpdf(e, gamma, sigma):
    if abs(gamma) < 1e-9:
        return -math.log(sigma) - e / sigma
    arg = 1.0 + gamma * e / sigma
    if arg <= 0:
        return -745.0
    return -math.log(sigma) - (1.0 / gamma + 1.0) * math.log(arg)


class _Tail:
    """One side's running POT state on z, with MoM and censored-ML fits."""

    def __init__(self):
        self.t = None
        self.exc, self.s1, self.s2 = [], 0.0, 0.0
        self.nx = 0
        self._ml = (0.0, 1.0)
        self._since = 0

    def mom(self):
        cnt = len(self.exc)
        m = self.s1 / cnt
        v = self.s2 / cnt - m * m
        if v <= 0 or cnt < 10:
            return 0.0, max(m, 1e-12)
        gamma = 0.5 * (1.0 - m * m / v)
        sigma = max(0.5 * m * (m * m / v + 1.0), 1e-12)
        return gamma, sigma

    def _fit_ml(self):
        """Grimshaw profile: given tau=gamma/sigma, gamma_hat(tau) is the
        mean log(1+tau*e); profile log-lik maximized by grid over tau."""
        exc = self.exc
        n = len(exc)
        if n < 20:
            self._ml = self.mom()
            return
        emax = max(exc)
        emean = self.s1 / n
        best, best_ll = None, -1e18
        # tau grid: log-spaced around 1/mean, plus mild negatives
        taus = [x / emean for x in
                (0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0, 3.0,
                 5.0, 8.0)]
        taus += [-0.5 / emax, -0.25 / emax, -0.1 / emax]
        for tau in taus:
            if tau <= -1.0 / emax or abs(tau) < 1e-12:
                continue
            g = sum(math.log1p(tau * e) for e in exc) / n
            if g <= 1e-9:
                continue
            sigma = g / tau
            if sigma <= 0:
                continue
            ll = -n * math.log(sigma) - (1.0 + 1.0 / g) * n * g
            if ll > best_ll:
                best_ll, best = ll, (g, sigma)
        self._ml = best if best is not None else self.mom()

    def ml(self):
        return self._ml

    def add(self, e):
        self.exc.append(e)
        self.s1 += e
        self.s2 += e * e
        self.nx += 1
        if len(self.exc) > NEXC:
            old = self.exc.pop(0)
            self.s1 -= old
            self.s2 -= old * old
        self._since += 1
        if self._since >= REFIT_EVERY or len(self.exc) == 20:
            self._fit_ml()
            self._since = 0


def run_one(args):
    sid, = args
    levels = _load_levels(sid)
    xs = _to_changes(levels) if levels else []
    if len(xs) < MIN_LEN:
        return None
    t0 = time.time()

    from skaters import laplace

    f = laplace(1)
    state = None
    pend = None
    up, lo = _Tail(), _Tail()
    warm, n_scored = [], 0
    ll = {"base": 0.0, "mom": 0.0, "cml": 0.0}
    llt = {"base": 0.0, "mom": 0.0, "cml": 0.0}
    csl = {"base": 0.0, "mom": 0.0, "cml": 0.0}
    ticks = tail_ticks = 0

    for y in xs:
        base_lp = pend.logpdf(y) if pend is not None else None
        dists, state = f(y, state)
        pend = dists[0]
        z = state["z"][0]
        if base_lp is None or z is None:
            continue

        if up.t is None:                        # threshold warm-up
            warm.append(z)
            if len(warm) >= WARMUP:
                w = sorted(warm)
                iu = min(int(LEVEL * len(w)), len(w) - 1)
                up.t = w[iu]
                lo.t = w[max(len(w) - 1 - iu, 0)]
                for x in w:
                    if x > up.t:
                        up.add(x - up.t)
                    elif x < lo.t:
                        lo.add(lo.t - x)
                n_scored = len(w)
            continue

        # ---- score under current estimates (before update) ----
        zeta_up = up.nx / n_scored
        zeta_lo = lo.nx / n_scored
        interior = max(_phi_cdf(up.t) - _phi_cdf(lo.t), 1e-12)
        c = max(1.0 - zeta_up - zeta_lo, 1e-12) / interior
        in_tail = (z > up.t and len(up.exc) >= 10) or \
                  (z < lo.t and len(lo.exc) >= 10)
        b = max(base_lp, CLAMP)
        ticks += 1
        ll["base"] += b
        if in_tail:
            tail_ticks += 1
            llt["base"] += b
            csl["base"] += b
            side, e = (up, z - up.t) if z > up.t else (lo, lo.t - z)
            zeta = zeta_up if z > up.t else zeta_lo
            for name, (gamma, sigma) in (("mom", side.mom()),
                                         ("cml", side.ml())):
                corr = (math.log(max(zeta, 1e-300))
                        + _gpd_logpdf(e, gamma, sigma) - _phi_log(z))
                s = max(base_lp + corr, CLAMP)
                ll[name] += s
                llt[name] += s
                csl[name] += s
        else:
            corr = math.log(c)
            for name in VARIANTS:
                ll[name] += max(base_lp + corr, CLAMP)
            csl["base"] += math.log(interior)
            for name in VARIANTS:
                csl[name] += math.log(max(1.0 - zeta_up - zeta_lo, 1e-12))

        # ---- update ----
        n_scored += 1
        if z > up.t:
            up.add(z - up.t)
        elif z < lo.t:
            lo.add(lo.t - z)

    if ticks < 200 or tail_ticks < 10:
        return None
    res = {"sid": sid, "ticks": ticks, "tail_ticks": tail_ticks,
           "seconds": round(time.time() - t0, 1)}
    for name in VARIANTS:
        res[f"dll_{name}"] = (ll[name] - ll["base"]) / ticks
        res[f"dllt_{name}"] = (llt[name] - llt["base"]) / tail_ticks
        res[f"dcsl_{name}"] = (csl[name] - csl["base"]) / ticks
    res["dcsl_cml_vs_mom"] = (csl["cml"] - csl["mom"]) / ticks
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    metas = json.load(open(UNIVERSE))
    picked = []
    for m in metas:
        if fred_universe.asset_class(m.get("title", "")) in _PRICE:
            continue
        path = os.path.join(_HERE, "..", "data", f"{m['id']}.csv")
        if os.path.exists(path) and os.path.getsize(path) > MIN_LEN * 12:
            picked.append(m["id"])
        if len(picked) >= args.limit:
            break

    out = os.path.join(_HERE, f"tail_splice_n{len(picked)}.jsonl")
    results = []
    if os.path.exists(out):
        with open(out) as fh:
            results = [json.loads(line) for line in fh if line.strip()]
        done = {r["sid"] for r in results}
        picked = [s for s in picked if s not in done]
        print(f"resuming {out}: {len(results)} done, {len(picked)} to go",
              flush=True)
    total = len(results) + len(picked)

    ofh = open(out, "a")
    with Pool(args.workers) as pool:
        for res in pool.imap_unordered(run_one, [(s,) for s in picked]):
            if res is None:
                total -= 1
                continue
            results.append(res)
            ofh.write(json.dumps(res) + "\n")
            ofh.flush()
            os.fsync(ofh.fileno())
            wins = sum(1 for r in results if r["dcsl_cml"] > 0)
            print(f"[{len(results)}/{total}] {res['sid'][:18]:18s} "
                  f"dllt mom={res['dllt_mom']:+.3f} cml={res['dllt_cml']:+.3f}"
                  f"  dcsl cml={res['dcsl_cml']:+.4f}"
                  f"  cml-csl-wins {wins}/{len(results)}", flush=True)
    ofh.close()

    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        for r in sorted(results, key=lambda r: r["sid"]):
            fh.write(json.dumps(r) + "\n")
    os.replace(tmp, out)

    nres = len(results)
    med = lambda k: sorted(r[k] for r in results)[nres // 2]  # noqa: E731
    win = lambda k: sum(1 for r in results if r[k] > 0)       # noqa: E731
    print(f"\n=== conditional tail fit vs plain laplace, {nres} series ===")
    for name, label in (("mom", "GPD splice (MoM)"),
                        ("cml", "GPD splice (censored ML)")):
        print(f"{label}:")
        print(f"  overall LL   median {med('dll_' + name):+.4f} nats/tick, "
              f"wins {win('dll_' + name)}/{nres}")
        print(f"  tail-tick LL median {med('dllt_' + name):+.3f}, "
              f"wins {win('dllt_' + name)}/{nres}")
        print(f"  CSL          median {med('dcsl_' + name):+.4f}, "
              f"wins {win('dcsl_' + name)}/{nres}")
    print(f"censored-ML vs MoM: CSL median {med('dcsl_cml_vs_mom'):+.5f}, "
          f"wins {win('dcsl_cml_vs_mom')}/{nres}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
