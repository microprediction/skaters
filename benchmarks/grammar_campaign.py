"""Empirical campaign for the grammar paper.

Subcommands (each writes grammar_campaign_<name>.csv and prints a summary):

  ladder   The decomposition ladder on the corpus: 39-knot + fixed N(0,1)
           leaf (D0), full-grid + fixed leaf, D (fitted leaf), E (AR refit).
           Prices knot compression, terminal fitting, and serial fitting
           separately.
  alts     Alternative interior transforms in the E position: fixed-lambda
           Yeo-Johnson, sinh-arcsinh, Cauchy link, vs gaussianize (E) and
           none (F).
  nulls    IID null suite: Gaussian, Student-t(3), lognormal skew, mixture.
           Measures the E-minus-D gain when there is nothing to find, i.e.
           how much apparent serial signal the adaptive interpolation itself
           induces.
  guards   Sensitivity of config E to slope_cap x z_max on a subsample.
  res      Resolution sensitivity of config E on a subsample: knot counts,
           particle counts, reference-mixture weights.
  crpspool CRPS-updated pool over the seven chains vs the likelihood pool.

Run:  PYTHONPATH=../src python3 grammar_campaign.py <subcommand> [limit]
"""
from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import csv
import math
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ladder_ablation as LA
import gaussianize_chain as GC
from skaters.conjugate import conjugate
from skaters.dist import Dist
from skaters.leaf import leaf
from skaters.transform import ar, ema_transform, gaussianize, standardize

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- pieces
def fixed_unit_leaf(k: int = 1):
    """N(0,1) every step: the literal terminal stop after gaussianize."""
    def _leaf(y, state):
        return [Dist.gaussian(0.0, 1.0)] * k, state or {}
    return _leaf


def fixed_monotone(fwd, inv, n_particles: int = 9):
    """A fixed, parameter-free monotone transform as a (forward, inverse_k)
    pair, with the same equal-probability particle pushback gaussianize
    uses."""
    from statistics import NormalDist
    nd = NormalDist()
    qs = [nd.inv_cdf((j + 0.5) / n_particles) for j in range(n_particles)]

    def forward(y, state):
        return fwd(y), state or {}

    def inverse_k(dists, state):
        out = []
        for d in dists:
            comps = []
            for (w, mu, sd) in d.components:
                xs = [inv(mu + sd * q) for q in qs]
                for j, x in enumerate(xs):
                    lo = xs[j - 1] if j > 0 else x - (xs[j + 1] - x)
                    hi = xs[j + 1] if j < len(xs) - 1 else x + (x - xs[j - 1])
                    width = max(1e-9, (hi - lo) / 2)
                    comps.append((w / n_particles, x, width))
            out.append(Dist(comps))
        return out

    return forward, inverse_k


def yeo_johnson(lam: float):
    def fwd(y):
        if y >= 0:
            return (((y + 1) ** lam) - 1) / lam if lam != 0 else math.log(y + 1)
        m = 2 - lam
        return -(((-y + 1) ** m) - 1) / m if m != 0 else -math.log(-y + 1)

    def inv(z):
        if z >= 0:
            return ((z * lam + 1) ** (1 / lam)) - 1 if lam != 0 else math.exp(z) - 1
        m = 2 - lam
        return 1 - ((-z * m + 1) ** (1 / m)) if m != 0 else 1 - math.exp(-z)

    return fixed_monotone(fwd, inv)


def sinh_arcsinh(delta: float):
    return fixed_monotone(lambda y: math.sinh(delta * math.asinh(y)),
                          lambda z: math.sinh(math.asinh(z) / delta))


def cauchy_link():
    from statistics import NormalDist
    nd = NormalDist()

    def fwd(y):
        p = 0.5 + math.atan(y) / math.pi
        p = min(max(p, 1e-12), 1 - 1e-12)
        return nd.inv_cdf(p)

    def inv(z):
        p = min(max(nd.cdf(z), 1e-12), 1 - 1e-12)
        return math.tan(math.pi * (p - 0.5))

    return fixed_monotone(fwd, inv)


def crps_pool(cands, eta: float = 1.0, prior_log_weights=None):
    """CRPS-driven exponential-weights mixture over candidate skaters."""
    def _pool(y, state):
        if state is None:
            state = {"s": [None] * len(cands), "pend": [None] * len(cands),
                     "lw": list(prior_log_weights or [0.0] * len(cands))}
        # update weights using each candidate's pending predictive
        if state["pend"][0] is not None:
            for i, pend in enumerate(state["pend"]):
                state["lw"][i] -= eta * pend[0].crps(y)
            mx = max(state["lw"])
            state["lw"] = [w - mx for w in state["lw"]]
        dists_all = []
        for i, c in enumerate(cands):
            d, state["s"][i] = c(y, state["s"][i])
            state["pend"][i] = d
            dists_all.append(d)
        ws = [math.exp(w) for w in state["lw"]]
        tot = sum(ws)
        comps = []
        for w, d in zip(ws, dists_all):
            for (cw, mu, sd) in d[0].components:
                comps.append((w / tot * cw, mu, sd))
        return [Dist(comps)], state
    return _pool


def _chain(*ts, terminal=None):
    sk = terminal if terminal is not None else leaf(k=1)
    for t in reversed(ts):
        sk = conjugate(sk, t, k=1)
    return sk


# ---------------------------------------------------------------- configs
def make_config(name):
    loc, sc = ema_transform(0.1), standardize(0.05)
    if name == "D0_fixed":
        return _chain(ema_transform(0.1), standardize(0.05), gaussianize(),
                      terminal=fixed_unit_leaf())
    if name == "D0_fullgrid":
        return _chain(ema_transform(0.1), standardize(0.05),
                      gaussianize(max_knots=10**9), terminal=fixed_unit_leaf())
    if name == "D_fitted":
        return _chain(ema_transform(0.1), standardize(0.05), gaussianize())
    if name == "E_ar":
        return _chain(ema_transform(0.1), standardize(0.05), gaussianize(), ar(1))
    if name == "E_emin":
        return _chain(ema_transform(0.1), standardize(0.05),
                      gaussianize(guard="emin"), ar(1))
    if name == "E_delete":
        return _chain(ema_transform(0.1), standardize(0.05),
                      gaussianize(guard="delete"), ar(1))
    if name == "D0_delete":
        return _chain(ema_transform(0.1), standardize(0.05),
                      gaussianize(guard="delete"), terminal=fixed_unit_leaf())
    if name == "F_noG":
        return _chain(ema_transform(0.1), standardize(0.05), ar(1))
    if name.startswith("ALT_"):
        key = name[4:]
        tmap = {"yj05": yeo_johnson(0.5), "yj15": yeo_johnson(1.5),
                "sas05": sinh_arcsinh(0.5), "sas20": sinh_arcsinh(2.0),
                "cauchy": cauchy_link()}
        return _chain(ema_transform(0.1), standardize(0.05), tmap[key], ar(1))
    if name.startswith("GUARD_"):
        _, scap, zmax = name.split("_")
        return _chain(ema_transform(0.1), standardize(0.05),
                      gaussianize(slope_cap=float(scap), z_max=float(zmax)), ar(1))
    if name.startswith("KNOTS_"):
        return _chain(ema_transform(0.1), standardize(0.05),
                      gaussianize(max_knots=int(name.split("_")[1])), ar(1))
    if name.startswith("PART_"):
        return _chain(ema_transform(0.1), standardize(0.05),
                      gaussianize(n_particles=int(name.split("_")[1])), ar(1))
    if name == "POOL_crps":
        cands = GC._candidates(with_gauss=True)
        prior = [-0.005 * d for _, d in cands]
        return crps_pool([c for c, _ in cands], eta=1.0, prior_log_weights=prior)
    raise ValueError(name)


# ---------------------------------------------------------------- driving
def _score_job(job):
    sid, series, configs = job
    try:
        row = [sid, len(series)]
        for name in configs:
            ll, cr = GC._score(lambda nm=name: make_config(nm), series)
            row += [ll, cr]
        return row
    except Exception:
        return [sid, len(series)] + [float("nan")] * (2 * len(configs))


def run_corpus(configs, out_name, limit=None, ids_subset=None):
    data = LA._corpus()
    ids = sorted(data)
    if ids_subset:
        ids = [i for i in ids if i in ids_subset]
    if limit:
        step = max(1, len(ids) // limit)
        ids = ids[::step][:limit]
    jobs = [(sid, data[sid], configs) for sid in ids]
    print(f"{len(jobs)} series x {len(configs)} configs -> {out_name}", flush=True)

    rows = []
    with ProcessPoolExecutor(max_workers=GC.MAX_WORKERS) as ex:
        futs = {ex.submit(_score_job, j): j[0] for j in jobs}
        for k, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if k % 50 == 0:
                print(f"{k}/{len(jobs)}", flush=True)
    rows.sort(key=lambda r: r[0])
    out = os.path.join(HERE, out_name)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "n"] + [f"{s}_{c}" for c in configs
                                      for s in ("ll", "crps")])
        w.writerows(rows)
    summarize(rows, configs)
    return rows


def summarize(rows, configs):
    import statistics as st
    for i, c in enumerate(configs):
        ll = [r[2 + 2 * i] for r in rows if r[2 + 2 * i] == r[2 + 2 * i]]
        cr = [r[3 + 2 * i] for r in rows if r[3 + 2 * i] == r[3 + 2 * i]]
        if ll:
            print(f"  {c:16s} ll {st.mean(ll):+.4f}  crps {st.mean(cr):.4f}"
                  f"  (n={len(ll)})", flush=True)


def make_null_series(kind, seed, T=1200):
    rng = random.Random(seed)
    if kind == "gauss":
        return [rng.gauss(0, 1) for _ in range(T)]
    if kind == "t3":
        out = []
        for _ in range(T):
            z = rng.gauss(0, 1)
            chi = sum(rng.gauss(0, 1) ** 2 for _ in range(3))
            out.append(z / math.sqrt(chi / 3))
        return out
    if kind == "skew":
        m = math.exp(0.5)
        return [(math.exp(rng.gauss(0, 1)) - m) for _ in range(T)]
    if kind == "mix":
        return [rng.gauss(0, 4 if rng.random() < 0.1 else 1) for _ in range(T)]
    raise ValueError(kind)


def run_nulls(limit=None):
    kinds = ["gauss", "t3", "skew", "mix"]
    reps = limit or 40
    configs = ["D_fitted", "E_ar", "D0_fixed"]
    rows = []
    for kind in kinds:
        for s in range(reps):
            series = make_null_series(kind, seed=1000 * kinds.index(kind) + s)
            row = [f"{kind}_{s}", len(series)]
            for name in configs:
                ll, cr = GC._score(lambda nm=name: make_config(nm), series)
                row += [ll, cr]
            rows.append(row)
        d = [r[4] - r[2] for r in rows if r[0].startswith(kind)]
        import statistics as st
        print(f"nulls {kind}: E-D ll delta mean {st.mean(d):+.5f} "
              f"frac>0 {sum(x > 0 for x in d)/len(d):.2f}", flush=True)
    out = os.path.join(HERE, "grammar_campaign_nulls.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "n"] + [f"{s}_{c}" for c in configs
                                      for s in ("ll", "crps")])
        w.writerows(rows)


def main():
    cmd = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    if cmd == "ladder":
        run_corpus(["D0_fixed", "D0_fullgrid", "D_fitted", "E_ar"],
                   "grammar_campaign_ladder.csv", limit)
    elif cmd == "alts":
        run_corpus(["E_ar", "F_noG", "ALT_yj05", "ALT_yj15", "ALT_sas05",
                    "ALT_sas20", "ALT_cauchy"],
                   "grammar_campaign_alts.csv", limit)
    elif cmd == "nulls":
        run_nulls(limit)
    elif cmd == "delguard":
        run_corpus(["E_delete", "D0_delete"], "grammar_campaign_delguard.csv", limit=limit)
    elif cmd == "emin":
        run_corpus(["E_emin"], "grammar_campaign_emin.csv", limit=limit)
    elif cmd == "guards":
        cfgs = [f"GUARD_{s}_{z}" for s in (10, 20, 40) for z in (6, 8, 10)]
        run_corpus(cfgs, "grammar_campaign_guards.csv", limit or 100)
    elif cmd == "res":
        cfgs = ["KNOTS_39", "KNOTS_79", "KNOTS_159", "KNOTS_1000000000",
                "PART_9", "PART_19", "PART_49"]
        run_corpus(cfgs, "grammar_campaign_res.csv", limit or 100)
    elif cmd == "crpspool":
        run_corpus(["POOL_crps"], "grammar_campaign_crpspool.csv", limit)
    else:
        raise SystemExit(f"unknown subcommand {cmd}")


if __name__ == "__main__":
    main()
