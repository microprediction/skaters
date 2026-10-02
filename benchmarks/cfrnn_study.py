"""CF-RNN-style intervals versus laplace's own intervals, multi-horizon, on the
daily FRED change universe.

Stankeviciute, Alaa and van der Schaar (NeurIPS 2021) build an H-step interval
by adding, to a point forecast, one calibration quantile per horizon: the
k-th smallest absolute residual with k = ceil((m+1)(1-alpha/H)) (Bonferroni
over the H horizons, so the H intervals cover jointly with probability at least
1-alpha). The half-width eps_h does not depend on the input. They judge methods
by joint coverage and mean width only.

Here the same construction is applied to laplace's own point forecast (its
predictive mean at each horizon) with a rolling calibration window of the last
WIN resolved absolute residuals per horizon, and compared with the interval
laplace itself reports at the same nominal levels:

  CF   : [mean_h - eps_h, mean_h + eps_h],  eps_h = k-th smallest of the window
  LAP  : [q_h(a/2), q_h(1-a/2)] from the predictive Dist at horizon h

with a = alpha/H (Bonferroni, joint target 1-alpha) and a = alpha (per-horizon).
Same series, same origins, same location model; the only difference is whether
the width may depend on the state. Both are scored by the interval score at
their own level a,

  IS_a(l,u;y) = (u-l) + (2/a)(l-y)1{y<l} + (2/a)(y-u)1{y>u},

which is the proper score for the (a/2, 1-a/2) quantile pair (Gneiting and
Raftery 2007, Winkler 1972), together with coverage and width.

    PYTHONPATH=src python benchmarks/cfrnn_study.py [N_SERIES] [summarize]

Env: CF_H (default 10), CF_ALPHA (0.1), CF_WIN (500), CF_STRIDE (4), CF_LAST
(2000 most recent changes scored), STUDY_WORKERS.
"""
from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")
import csv
import math
import sys
import time
from collections import deque
from concurrent.futures import ProcessPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import fred
import bench_core as bc
from study import _scope_tag, MIN_CHANGES
from skaters.api import laplace

H = int(os.environ.get("CF_H", 10))
ALPHA = float(os.environ.get("CF_ALPHA", 0.1))
WIN = int(os.environ.get("CF_WIN", 500))
STRIDE = int(os.environ.get("CF_STRIDE", 4))
LAST = int(os.environ.get("CF_LAST", 2000))
MIN_CAL = 200                      # residuals per horizon before CF is scored
OUT = os.environ.get("CF_RESULTS", os.path.join(_HERE, f"cfrnn_study_h{H}.csv"))
WORKERS = int(os.environ.get("STUDY_WORKERS", min(10, (os.cpu_count() or 4))))
LEVELS = {"bonf": ALPHA / H, "marg": ALPHA}


def interval_score(lo, hi, y, a):
    s = hi - lo
    if y < lo:
        s += (2.0 / a) * (lo - y)
    elif y > hi:
        s += (2.0 / a) * (y - hi)
    return s


def cf_halfwidth(buf, a):
    """k-th smallest absolute residual, k = ceil((m+1)(1-a)); +inf if k > m."""
    m = len(buf)
    k = math.ceil((m + 1) * (1 - a))
    if k > m:
        return math.inf
    return sorted(buf)[k - 1]


def run_series(sid):
    levels = fred._load_levels(sid)
    ch = fred._to_changes(levels) if levels else []
    if len(ch) < MIN_CHANGES or _scope_tag(ch):
        return sid, None
    ch = ch[-(LAST + bc.BURN + WIN):]
    n = len(ch)
    f = laplace(k=H)
    state = None
    bufs = [deque(maxlen=WIN) for _ in range(H)]      # |y_{o+h} - mean_h(o)| per horizon
    means = {}                                        # origin -> [mean_h]
    pend = {}                                         # scored origin -> dict
    first_scored = max(bc.BURN, n - LAST)
    # accumulators: method -> level -> [sum IS, sum width, sum covered, count]
    acc = {m: {lv: [0.0, 0.0, 0.0, 0] for lv in LEVELS} for m in ("CF", "LAP")}
    joint = {m: [0, 0] for m in ("CF", "LAP")}        # [all-H covered, origins]
    perh = {m: {h: [0.0, 0.0, 0] for h in range(1, H + 1)} for m in ("CF", "LAP")}  # IS bonf, cov, n
    lap_lp = lap_cr = 0.0; lap_n = 0
    for i, y in enumerate(ch):
        # resolve residuals and score anything aimed at this step
        for h in range(1, H + 1):
            o = i - h
            if o in means:
                bufs[h - 1].append(abs(y - means[o][h - 1]))
            if o in pend:
                p = pend[o]
                for m in ("CF", "LAP"):
                    for lv, a in LEVELS.items():
                        lo, hi = p[m][lv][h - 1]
                        s = acc[m][lv]
                        s[0] += interval_score(lo, hi, y, a); s[1] += hi - lo
                        cov = lo <= y <= hi
                        s[2] += cov; s[3] += 1
                        if lv == "bonf":
                            p["jc"][m] = p["jc"][m] and cov
                            q = perh[m][h]; q[0] += interval_score(lo, hi, y, a); q[1] += cov; q[2] += 1
                d = p["dists"][h - 1]
                lp, cr = bc.score_dist(d, y); lap_lp += lp; lap_cr += cr; lap_n += 1
                if h == H:
                    for m in ("CF", "LAP"):
                        joint[m][0] += p["jc"][m]; joint[m][1] += 1
                    del pend[o]
        for o in [o for o in means if o < i - H]:
            del means[o]
        dists, state = f(y, state)
        means[i] = [d.mean for d in dists]
        if i >= first_scored and (i - first_scored) % STRIDE == 0 and i + H < n \
                and all(len(b) >= MIN_CAL for b in bufs):
            p = {"dists": dists, "jc": {"CF": True, "LAP": True}, "CF": {}, "LAP": {}}
            for lv, a in LEVELS.items():
                p["CF"][lv] = []
                p["LAP"][lv] = []
                for h in range(1, H + 1):
                    e = cf_halfwidth(bufs[h - 1], a)
                    mu = means[i][h - 1]
                    p["CF"][lv].append((mu - e, mu + e))
                    d = dists[h - 1]
                    p["LAP"][lv].append((d.quantile(a / 2), d.quantile(1 - a / 2)))
            pend[i] = p
    if joint["CF"][1] == 0:
        return sid, None
    row = {"series": sid, "n_origins": joint["CF"][1], "n_changes": n,
           "lap_logpdf": lap_lp / lap_n, "lap_crps": lap_cr / lap_n}
    for m in ("CF", "LAP"):
        for lv in LEVELS:
            s = acc[m][lv]
            row[f"{m}_{lv}_is"] = s[0] / s[3]; row[f"{m}_{lv}_width"] = s[1] / s[3]
            row[f"{m}_{lv}_cov"] = s[2] / s[3]
        row[f"{m}_joint_cov"] = joint[m][0] / joint[m][1]
        for h in (1, max(1, H // 2), H):
            q = perh[m][h]
            row[f"{m}_bonf_is_h{h}"] = q[0] / q[2]; row[f"{m}_bonf_cov_h{h}"] = q[1] / q[2]
    return sid, row


def _median(v):
    s = sorted(v); k = len(s)
    return s[k // 2] if k % 2 else 0.5 * (s[k // 2 - 1] + s[k // 2])


def summarize(path=OUT):
    rows = list(csv.DictReader(open(path)))
    rows = [{k: (float(v) if k != "series" else v) for k, v in r.items()} for r in rows]
    N = len(rows)
    print(f"{N} series, H={H}, alpha={ALPHA}, window={WIN}, origins/series median "
          f"{_median([r['n_origins'] for r in rows]):.0f}")
    for lv, a in LEVELS.items():
        print(f"\n== level a={a:.4g} per horizon ({'joint target 1-alpha, Bonferroni' if lv=='bonf' else 'per-horizon 1-alpha'})")
        for m in ("CF", "LAP"):
            print(f"  {m:4s} interval score mean {sum(r[f'{m}_{lv}_is'] for r in rows)/N:.4g}"
                  f"  width mean {sum(r[f'{m}_{lv}_width'] for r in rows)/N:.4g}"
                  f"  coverage mean {sum(r[f'{m}_{lv}_cov'] for r in rows)/N:.4f}")
        ratio = [r[f"CF_{lv}_is"] / r[f"LAP_{lv}_is"] for r in rows]
        wins = sum(r[f"LAP_{lv}_is"] < r[f"CF_{lv}_is"] for r in rows)
        print(f"  IS ratio CF/LAP: median {_median(ratio):.4f}  mean {sum(ratio)/N:.4f}; "
              f"laplace better on {100*wins/N:.1f}% of series")
        wr = [r[f"CF_{lv}_width"] / r[f"LAP_{lv}_width"] for r in rows]
        print(f"  width ratio CF/LAP: median {_median(wr):.4f}")
    print("\n== joint coverage (all H horizons covered, Bonferroni intervals)")
    for m in ("CF", "LAP"):
        v = [r[f"{m}_joint_cov"] for r in rows]
        print(f"  {m:4s} mean {sum(v)/N:.4f}  median {_median(v):.4f}  share of series >= {1-ALPHA}: "
              f"{100*sum(x >= 1-ALPHA for x in v)/N:.1f}%")
    print("\n== per horizon (Bonferroni level): IS ratio CF/LAP median, coverage CF / LAP")
    for h in (1, max(1, H // 2), H):
        ratio = [r[f"CF_bonf_is_h{h}"] / r[f"LAP_bonf_is_h{h}"] for r in rows]
        print(f"  h={h:2d}: IS ratio median {_median(ratio):.4f}, laplace better on "
              f"{100*sum(x > 1 for x in ratio)/N:.1f}%;  cov {sum(r[f'CF_bonf_cov_h{h}'] for r in rows)/N:.4f} / "
              f"{sum(r[f'LAP_bonf_cov_h{h}'] for r in rows)/N:.4f}")
    print(f"\n  laplace held-out logpdf mean {sum(r['lap_logpdf'] for r in rows)/N:.4f}, "
          f"crps mean {sum(r['lap_crps'] for r in rows)/N:.4f} (no density exists for CF)")


def main():
    args = [a for a in sys.argv[1:]]
    if "summarize" in args:
        return summarize()
    cap = int(args[0]) if args and args[0].isdigit() else 10**9
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv") and not f.startswith("m4_"))[:cap]
    done = set()
    if os.path.exists(OUT):
        done = {r["series"] for r in csv.DictReader(open(OUT))}
    todo = [s for s in ids if s not in done]
    print(f"{len(ids)} cached series, {len(done)} done, {len(todo)} to run, {WORKERS} workers", flush=True)
    t0 = time.time(); n = 0; header = bool(done)
    with ProcessPoolExecutor(WORKERS) as ex, open(OUT, "a", newline="") as fh:
        w = None
        for fut in as_completed([ex.submit(run_series, s) for s in todo]):
            sid, row = fut.result()
            n += 1
            if row is None:
                continue
            if w is None:
                w = csv.DictWriter(fh, fieldnames=list(row))
                if not header:
                    w.writeheader()
            w.writerow(row); fh.flush()
            if n % 20 == 0:
                print(f"  {n}/{len(todo)}  {time.time()-t0:.0f}s", flush=True)
    summarize()


if __name__ == "__main__":
    main()
