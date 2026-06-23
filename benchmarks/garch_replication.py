"""Replication accuracy: how closely do our online GARCH leaves reproduce arch's
*volatility-forecast path*, treating GARCH-t as an oracle (issue #25).

Aggregate LL can tie with very different per-step predictions. Here we compare the
PREDICTIVE VARIANCE path h_t of each online leaf against arch's GARCH-t h_t, on
the same scored steps, via:
  * corr  = Pearson correlation of log h_t (do we track the vol *shape*?)
  * rmse  = RMS of log(h_ours / h_arch) (do we match the *level*?)

Bare leaves on the raw changes (constant/zero mean), so the variance path is
directly comparable to arch's. Requires arch.

    PYTHONPATH=src python benchmarks/garch_replication.py   (MAX_SERIES caps gap set)
"""

from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import csv
import math
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import fred
from study import _cfg, _start_for, _rfrac, MIN_CHANGES, MAX_CHANGES
from opponents import FIT_WIN
from arch import arch_model
from garch_member import betat_garch_leaf
from skaters.leaf import garch_leaf

CFG = _cfg("sota")
REFIT = CFG["refit"]
MAX_WORKERS = min(8, (os.cpu_count() or 4))


def _prep(sid):
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    if len(ch) < MIN_CHANGES:
        return None, None
    if len(ch) > MAX_CHANGES:
        ch = ch[-MAX_CHANGES:]
    return ch, _start_for(len(ch), CFG)


def _arch_var_path(ch, start, refit=REFIT):
    """arch GARCH-t predictive variance per scored step, in ORIGINAL units."""
    y = np.asarray(ch, float); n = len(y)
    s = 1.0 / (np.std(y[:start]) or 1.0); ys = y * s
    mu = om = al = be = None; h_prev = res_prev = None; have = False
    out = []
    for t in range(start, n):
        if (not have) or (t - start) % refit == 0:
            hist = ys[max(0, t - FIT_WIN):t]
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    r = arch_model(hist, mean="Constant", vol="GARCH", p=1, q=1, dist="t",
                                   rescale=False).fit(disp="off", options={"maxiter": 200})
                mu = r.params["mu"]; om = r.params["omega"]
                al = r.params["alpha[1]"]; be = r.params["beta[1]"]
                h_prev = float(r.conditional_volatility[-1]) ** 2
                res_prev = float(hist[-1] - mu); have = True
            except Exception:
                if not have:
                    return None
        h_t = om + al * res_prev ** 2 + be * h_prev
        out.append(h_t / (s * s))                 # back to original units
        res_prev = ys[t] - mu; h_prev = h_t
    return out


def _leaf_var_path(factory, ch, start):
    """Our leaf's predictive variance per scored step (the emitted Dist variance)."""
    f = factory(); state = None; pend = None; out = []
    for i, y in enumerate(ch):
        if pend is not None and i >= start:
            out.append(pend[0].var)
        d, state = f(y, state)
        pend = d
    return out


def _agree(ours, arch):
    o = np.log(np.maximum(ours, 1e-300)); a = np.log(np.maximum(arch, 1e-300))
    m = min(len(o), len(a))
    o, a = o[-m:], a[-m:]
    if m < 10 or np.std(o) < 1e-9 or np.std(a) < 1e-9:
        return None
    corr = float(np.corrcoef(o, a)[0, 1])
    rmse = float(np.sqrt(np.mean((o - a) ** 2)))
    return corr, rmse


def _score(sid):
    ch, start = _prep(sid)
    if ch is None:
        return None
    arch = _arch_var_path(ch, start)
    if arch is None:
        return None
    arch = np.asarray(arch)
    res = {}
    for nm, fac in [("garch_leaf", lambda: garch_leaf(k=1)),
                    ("beta-t", lambda: betat_garch_leaf(k=1))]:
        ours = np.asarray(_leaf_var_path(fac, ch, start))
        ag = _agree(ours, arch)
        if ag is None:
            return None
        res[nm] = ag
    return (sid, res)


def main():
    rows = {}
    with open(CFG["results"]) as fh:
        for r in csv.DictReader(fh):
            rows.setdefault(r["series"], {})[r["method"]] = (float(r["logpdf"]), float(r["crps"]))
    gap = [s for s, d in rows.items() if "laplace" in d and "GARCH-t" in d
           and not math.isnan(d["laplace"][0]) and not math.isnan(d["GARCH-t"][0])
           and d["GARCH-t"][0] > d["laplace"][0] and _rfrac(s) < 0.05]
    cap = int(os.environ.get("MAX_SERIES", "0"))
    if cap:
        gap = gap[:cap]
    print(f"gap series: {len(gap)}")

    out = []
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(_score, s): s for s in gap}
        done = 0
        for fut in as_completed(futs):
            r = fut.result(); done += 1
            if r:
                out.append(r)
            if done % 20 == 0:
                print(f"  {done}/{len(gap)}", flush=True)

    print(f"\n=== volatility-path replication vs arch GARCH-t, n={len(out)} ===")
    print("  (corr of log h_t = tracks the vol shape; rmse of log h_t = level match)")
    for nm in ("garch_leaf", "beta-t"):
        corr = np.array([r[1][nm][0] for r in out])
        rmse = np.array([r[1][nm][1] for r in out])
        print(f"  {nm:12s}  corr(log h): mean {corr.mean():.3f} median {np.median(corr):.3f}   "
              f"rmse(log h): mean {rmse.mean():.3f} median {np.median(rmse):.3f}")


if __name__ == "__main__":
    main()
