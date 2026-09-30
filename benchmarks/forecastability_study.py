"""Forecastability profile with the conformal share inside it.

Companion study to "Marginally Useful: Conformal Prediction Adds No
Forecastability". Forecastability at horizon h (DelSole 2004; Catt 2026) is
F(h) = I(Y_{t+h}; past): the most any forecaster can gain in expected log score
over the unconditional law. The paper's theorem: a pooled forecaster (one
shape for every past, i.e. a conformal predictive system in score coordinates
T = phi_x(y)) captures at most F - I(T; X), and the conformal step itself only
fixes the marginal shape of T; it adds nothing that depends on X. This script
makes that visible on real data as a profile over horizons.

For each series and horizon h, four predictive densities for y_{t+h} are
scored prequentially on the SAME held-out targets, all on the y scale:

  unc   pooled law of y: Gaussian KDE over past values of y
  cps   base h-step mean m + KDE of past raw h-step residuals r = y - m
        (smoothed signed conformal predictive system, split-free/online)
  cpsz  m + s_t * KDE of past standardized residuals z = r / s, with the
        log-Jacobian -log s_t (normalized CPS)
  lap   laplace(h)'s own h-step predictive density (a feasible conditional
        model)

Each is wrapped in the same delta-mixture with the expanding Gaussian
reference fitted to past y (delta = 0.01), so all four are genuine densities
and a single wild point cannot dominate a mean.

Timing (no look-ahead). Every predictive for target s is formed at the forecast
origin t = s - h. The y value y_u, the residual r_u and the standardized
residual z_u all enter their pooled stores (and the scale EWMA) only once the
origin has reached u, i.e. at target s they hold u <= s - h. The base mean m_s
and laplace's density are the h-step forecast laplace(h) issued at s - h.

Base mean and scale (judgment call, fixed here). m = mean of laplace(h)'s
h-step predictive, i.e. the same model whose density is `lap`, so cps/cpsz and
lap share one point forecast and differ only in shape. s_t = EWMA of squared
h-step residuals, alpha = 0.03, floored at 0.0025 x the expanding mean square,
exactly as conformal_infogap._streams. We deliberately do NOT use laplace's own
predictive sd: normalized conformal is defined by a separate, simple scale
model, and borrowing laplace's sd would import its conditional-shape machinery
into the "pooled" arm.

The target y is the arm's change series (fred._to_changes: log-difference for
strictly positive levels, else first difference), the same convention as every
corpus arm in corpus.py. The h-step target is the single change at t+h, as in
the canonical multi-horizon study (arm_adapters.laplace_dists, run_arm ARM_H).

Derived per (series, h), in nats per scored target:

  F_hat  = L_lap  - L_unc   feasible forecastability
  X_cps  = L_cps  - L_unc   what the pooled raw-residual system captures
  X_cpsz = L_cpsz - L_unc   what the pooled normalized system captures
  left   = L_lap  - L_cps   what the pooled system leaves on the table

Read these plainly. F_hat is a feasible LOWER estimate: the gain of one
particular conditional model (laplace), not I(Y; past); a better model can only
raise it. `left` is, by Gibbs' inequality and in expectation, a LOWER bound on
the pooled system's regret to the oracle P(Y_{t+h} | past), because the oracle
scores at least as well as laplace. The paper predicts X_cps(h), X_cpsz(h) sit
inside F_hat(h) and that `left` stays positive where F_hat is.

Usage (see benchmarks/FORECASTABILITY_STUDY.md for the runbook):

    PYTHONPATH=src python benchmarks/forecastability_study.py --arm fred \\
        --horizons 1,2,3,5,8,13 --workers 32
    PYTHONPATH=src python benchmarks/forecastability_study.py --arm metr-la --list
    PYTHONPATH=src python benchmarks/forecastability_study.py --summarize \\
        --out benchmarks/forecastability_fred.csv benchmarks/forecastability_metr-la.csv

Resumable: (series, h) cells already in --out without an error are skipped;
rows are appended and flushed as they finish.
"""

from __future__ import annotations
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import bisect
import csv
import io
import json
import math
import sys
import time
import urllib.request
import zipfile
from collections import deque
from concurrent.futures import ProcessPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import fred
from conformal_infogap import _mix_logpdf, _kde_logpdf_sorted

BURN = 300              # first scored target index (as conformal_decomposition)
MIN_POOL = 50           # minimum pooled-store size before a target is scored
MIN_LEN = 600           # minimum change-series length (as conformal_decomposition)
MAX_REPEAT = 0.05       # drop series whose consecutive changes repeat >= 5%
ALPHA = 0.03            # scale EWMA rate (conformal_infogap._streams)
HORIZONS = [1, 2, 3, 5, 8, 13]
DENS = ["unc", "cps", "cpsz", "lap"]
DERIVED = ["F_hat", "X_cps", "X_cpsz", "left"]
FIELDS = (["arm", "series", "h", "n", "n_scored", "backend"]
          + [f"L_{d}" for d in DENS] + DERIVED + ["secs", "error"])

# New arm caches live in their own subdirectory so they never leak into the
# `fred` arm, which lists every *.csv directly under benchmarks/data.
CACHE = os.environ.get("FORECASTABILITY_CACHE",
                       os.path.join(fred._CACHE, "forecastability"))


# ---------------------------------------------------------------- corpus arms
def _qualifies(ch):
    if len(ch) < MIN_LEN:
        return False
    rep = sum(1 for i in range(1, len(ch)) if ch[i] == ch[i - 1]) / (len(ch) - 1)
    return rep < MAX_REPEAT


def _download(url, path, timeout=600):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"  fetching {url} -> {path}", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.7.1"})  # FRED tarpits other UAs
    with urllib.request.urlopen(req, timeout=timeout) as r, open(path + ".part", "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    os.replace(path + ".part", path)


def arm_fred():
    """The 702-csv FRED cache in benchmarks/data (conformal_decomposition._corpus:
    >= 600 changes, < 5% repeated changes). Offline; the cache is gitignored, so
    copy it from an existing machine (see runbook)."""
    from conformal_decomposition import _corpus
    return [(sid, ch, None) for sid, ch in sorted(_corpus().items())]


def _arm_corpus(name):
    """A corpus.py arm, from the offline jsonl cache written by
    build_corpus_cache.py if present, else live. Only m4-hourly is exposed: the
    FRED daily/weekly/monthly corpus arms enumerate through the FRED API and
    write new csvs into benchmarks/data, which would silently change the
    `fred` arm (it lists that directory). See the runbook TODO."""
    def load():
        cache = os.path.join(_HERE, "preds", f"_corpus_{name}.jsonl")
        if os.path.exists(cache):
            rows = [json.loads(line) for line in open(cache)]
            it = ((r["sid"], r["title"], r["ch"]) for r in rows)
        else:
            import corpus
            it = corpus.iter_arm(name)
        return [(sid, ch, None) for sid, _t, ch in it if _qualifies(ch)]
    load.__doc__ = f"corpus.py arm {name!r} (see corpus.py for enumeration rules)."
    return load


_M4_DAILY_URL = ("https://raw.githubusercontent.com/Mcompetitions/M4-methods/"
                 "master/Dataset/Train/Daily-train.csv")


def arm_m4_daily():
    """M4 competition daily training set (4,227 series, public CSV)."""
    path = os.path.join(CACHE, "m4_daily.csv")
    if not os.path.exists(path):
        _download(_M4_DAILY_URL, path)
    out = []
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if not row or row[0] == "V1":
                continue
            vals = [float(v) for v in row[1:] if v not in ("", "NA")]
            ch = fred._to_changes([(str(i), v) for i, v in enumerate(vals)])
            if _qualifies(ch):
                out.append((row[0].strip('"'), ch, None))
    return out


_ELEC_URL = ("https://archive.ics.uci.edu/static/public/321/"
             "electricityloaddiagrams20112014.zip")


def arm_electricity():
    """UCI ElectricityLoadDiagrams20112014: 370 Portuguese clients, 15-min kW,
    2011-2014. Aggregated to hourly means (the usual 'electricity' benchmark
    resolution), leading all-zero stretch (client not yet connected) dropped."""
    hourly = os.path.join(CACHE, "electricity_hourly.csv")
    if not os.path.exists(hourly):
        z = os.path.join(CACHE, "electricity.zip")
        if not os.path.exists(z):
            _download(_ELEC_URL, z)
        with zipfile.ZipFile(z) as zf:
            name = [n for n in zf.namelist() if n.endswith(".txt")][0]
            with zf.open(name) as fh:
                txt = io.TextIOWrapper(fh, encoding="utf-8")
                header = next(txt).rstrip("\n").split(";")[1:]
                ids = [h.strip('"') for h in header]
                acc = [0.0] * len(ids)
                rows, k = [], 0
                for line in txt:
                    parts = line.rstrip("\n").split(";")[1:]
                    for i, p in enumerate(parts):
                        acc[i] += float(p.replace(",", ".")) if p else 0.0
                    k += 1
                    if k == 4:
                        rows.append([a / 4 for a in acc])
                        acc = [0.0] * len(ids)
                        k = 0
        with open(hourly, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(ids)
            w.writerows(rows)
    with open(hourly, newline="") as f:
        r = csv.reader(f)
        ids = next(r)
        cols = list(zip(*[[float(x) for x in row] for row in r]))
    out = []
    for sid, col in zip(ids, cols):
        i0 = next((i for i, v in enumerate(col) if v != 0.0), len(col))
        ch = fred._to_changes([(str(i), v) for i, v in enumerate(col[i0:])])
        if _qualifies(ch):
            out.append((sid, ch, None))
    return out


_METR_URL = "https://drive.switch.ch/index.php/s/Z8cKHAVyiDqkzaG/download"


def arm_metr_la():
    """METR-LA loop-detector speeds: 207 sensors, 5-min, Mar-Jun 2012, via the
    same public zip torch-spatiotemporal (tsl.datasets.MetrLA) downloads. Zero
    speed means missing (tsl's mask convention). Sensors with > 15% missing are
    dropped; gaps are linearly interpolated in levels so the models see a
    continuous stream, but a target is SCORED only if both levels behind the
    change were observed. Needs h5py + numpy for the fetch step only."""
    npz = os.path.join(CACHE, "metr_la.npz")
    if not os.path.exists(npz):
        z = os.path.join(CACHE, "metr_la.zip")
        if not os.path.exists(z):
            _download(_METR_URL, z)
        import h5py
        import numpy as np
        with zipfile.ZipFile(z) as zf:
            zf.extract("metr_la.h5", CACHE)
        with h5py.File(os.path.join(CACHE, "metr_la.h5")) as f:
            X = f["data"]["block0_values"][:].astype(float)
            ids = [s.decode() for s in f["data"]["axis0"][:]]
        np.savez_compressed(npz, X=X, ids=np.array(ids))
    import numpy as np
    d = np.load(npz)
    X, ids = d["X"], [str(s) for s in d["ids"]]
    out = []
    for j, sid in enumerate(ids):
        x = X[:, j]
        obs = x != 0
        if obs.mean() < 0.85 or obs.sum() < 2:
            continue
        t = np.arange(len(x))
        lv = np.interp(t, t[obs], x[obs])
        ch = fred._to_changes([(str(i), float(v)) for i, v in enumerate(lv)])
        mask = [bool(obs[i] and obs[i + 1]) for i in range(len(x) - 1)]
        if _qualifies(ch):
            out.append((sid, ch, mask))
    return out


# Daily asset prices from FRED's keyless public CSV endpoint
# (fred.stlouisfed.org/graph/fredgraph.csv?id=...; no API key). The list is
# every H.10 daily FX rate still published, FRED's daily equity indices, its
# daily energy spot prices and Coinbase crypto. Stooq and Yahoo now block
# scripted downloads. Some ids also sit in the 702 `fred` cache (overlap).
RETURNS_IDS = [
    # equity indices
    "SP500", "NASDAQCOM", "NASDAQ100", "DJIA", "DJTA", "DJUA", "DJCA",
    # H.10 FX
    "DEXUSEU", "DEXJPUS", "DEXUSUK", "DEXCAUS", "DEXCHUS", "DEXSZUS", "DEXMXUS",
    "DEXKOUS", "DEXINUS", "DEXBZUS", "DEXUSAL", "DEXSDUS", "DEXNOUS", "DEXDNUS",
    "DEXHKUS", "DEXSIUS", "DEXTAUS", "DEXTHUS", "DEXSFUS", "DEXMAUS", "DEXSLUS",
    "DEXUSNZ",
    # energy spot
    "DCOILWTICO", "DCOILBRENTEU", "DHHNGSP", "DGASNYH", "DGASUSGULF", "DHOILNYH",
    "DJFUELUSGULF", "DPROPANEMBTX",
    # crypto
    "CBBTCUSD", "CBETHUSD", "CBLTCUSD", "CBBCHUSD",
]


def arm_returns():
    """Daily log returns of FRED asset prices (RETURNS_IDS), keyless fetch."""
    out = []
    for sid in RETURNS_IDS:
        path = os.path.join(CACHE, "returns", f"{sid}.csv")
        if not os.path.exists(path):
            try:
                _download(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}",
                          path, timeout=60)
            except Exception as e:                            # noqa: BLE001
                print(f"  {sid}: fetch failed ({e})", flush=True)
                continue
        levels = []
        with open(path, newline="") as f:
            for row in csv.reader(f):
                try:
                    levels.append((row[0], float(row[1])))
                except (ValueError, IndexError):
                    continue            # header and FRED "." gap markers
        ch = fred._to_changes(levels)
        if _qualifies(ch):
            out.append((sid, ch, None))
    return out


ARMS = {
    "fred": arm_fred,
    "m4-hourly": _arm_corpus("m4-hourly"),
    "m4-daily": arm_m4_daily,
    "electricity": arm_electricity,
    "metr-la": arm_metr_la,
    "returns": arm_returns,
}


# ---------------------------------------------------------------- scoring
def _backend(pref):
    if pref in ("auto", "fast"):
        try:
            import skaters_fast  # noqa: F401
            return "fast"
        except ImportError:
            if pref == "fast":
                raise
    return "python"


def _laplace_stepper(h, backend):
    """y -> list of k=h predictives (index h-1 is the h-step one). Default
    laplace(h), as arm_adapters.laplace_dists. The Rust backend agrees with the
    Python reference to ~1e-15 and is 10-17x faster."""
    if backend == "fast":
        import skaters_fast
        g = skaters_fast.laplace(h)
        return g.step
    from skaters.api import laplace
    f = laplace(h)
    st = [None]

    def step(y):
        d, st[0] = f(y, st[0])
        return d
    return step


class _Pool:
    """Sorted values + Welford moments."""
    __slots__ = ("v", "n", "mu", "m2")

    def __init__(self):
        self.v, self.n, self.mu, self.m2 = [], 0, 0.0, 0.0

    def add(self, x):
        bisect.insort(self.v, x)
        self.n += 1
        d = x - self.mu
        self.mu += d / self.n
        self.m2 += d * (x - self.mu)

    @property
    def var(self):
        return self.m2 / (self.n - 1) if self.n > 1 else 0.0


def score_series(y, h, backend, mask=None):
    """Mean log scores of unc, cps, cpsz, lap on the common scored targets."""
    step = _laplace_stepper(h, backend)
    issued = deque()                 # laplace h-step predictives, oldest first
    delay = deque()                  # (u, y_u, r_u, z_u) awaiting origin >= u
    py, pr, pz = _Pool(), _Pool(), _Pool()
    v = None; g = 0.0; nR = 0        # scale EWMA state
    tot = dict.fromkeys(DENS, 0.0); n = 0
    for s, ys in enumerate(y):
        while delay and delay[0][0] <= s - h:        # origin has reached u
            _u, yu, ru, zu = delay.popleft()
            py.add(yu)
            if ru is not None:
                pr.add(ru)
                nR += 1
                g += (ru * ru - g) / nR
                v = ru * ru if v is None else (1 - ALPHA) * v + ALPHA * ru * ru
                if zu is not None:
                    pz.add(zu)
        ru = zu = None
        if len(issued) == h:                         # forecast issued at s - h
            d = issued.popleft()
            m = d.mean
            ru = ys - m
            sc = math.sqrt(max(v, 0.0025 * g)) if v is not None else 0.0
            if sc > 0 and math.isfinite(sc):
                zu = ru / sc
            if (s >= BURN and (mask is None or mask[s]) and zu is not None
                    and min(py.n, pr.n, pz.n) > MIN_POOL
                    and py.var > 0 and pr.var > 0 and pz.var > 0):
                mu, var = py.mu, py.var
                lu = _kde_logpdf_sorted(py.v, math.sqrt(var), ys)
                lc = _kde_logpdf_sorted(pr.v, math.sqrt(pr.var), ru)
                lz = _kde_logpdf_sorted(pz.v, math.sqrt(pz.var), zu) - math.log(sc)
                ll = d.logpdf(ys)
                tot["unc"] += _mix_logpdf(lu, ys, mu, var)
                tot["cps"] += _mix_logpdf(lc, ys, mu, var)
                tot["cpsz"] += _mix_logpdf(lz, ys, mu, var)
                tot["lap"] += _mix_logpdf(ll, ys, mu, var)
                n += 1
        delay.append((s, ys, ru, zu))
        issued.append(step(float(ys))[h - 1])
    if not n:
        return {k: float("nan") for k in DENS}, 0
    return {k: tot[k] / n for k in DENS}, n


def score(job):
    arm, sid, h, y, mask, backend = job
    t0 = time.time()
    row = dict(arm=arm, series=sid, h=h, n=len(y), backend=backend, error="")
    try:
        L, n = score_series(y, h, backend, mask)
        row["n_scored"] = n
        for k in DENS:
            row[f"L_{k}"] = L[k]
        row["F_hat"] = L["lap"] - L["unc"]
        row["X_cps"] = L["cps"] - L["unc"]
        row["X_cpsz"] = L["cpsz"] - L["unc"]
        row["left"] = L["lap"] - L["cps"]
        if not n:
            row["error"] = "no scored targets"
    except Exception as e:                                    # noqa: BLE001
        row["error"] = repr(e)[:200]
    row["secs"] = round(time.time() - t0, 2)
    return row


def _read_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def run(args):
    horizons = [int(x) for x in args.horizons.split(",")]
    t0 = time.time()
    data = ARMS[args.arm]()
    print(f"[{args.arm}] {len(data)} qualifying series loaded in "
          f"{time.time() - t0:.0f}s", flush=True)
    if args.list:
        for sid, y, mask in data[:20]:
            print(f"  {sid:24s} n={len(y)}" + ("" if mask is None else
                  f" observed={sum(mask) / len(mask):.2f}"))
        return
    if args.limit:
        stride = max(1, len(data) // args.limit)
        data = data[::stride][:args.limit]
    if args.max_len:
        data = [(sid, y[-args.max_len:], None if m is None else m[-args.max_len:])
                for sid, y, m in data]
    out = args.out[0] if args.out else os.path.join(
        _HERE, f"forecastability_{args.arm}.csv")
    done = {(r["series"], int(r["h"])) for r in _read_rows(out) if not r["error"]}
    backend = _backend(args.backend)
    jobs = [(args.arm, sid, h, y, m, backend) for sid, y, m in data for h in horizons
            if (sid, h) not in done]
    jobs.sort(key=lambda j: -len(j[3]) * (1 + 0.1 * j[2]))   # longest first
    print(f"[{args.arm}] {len(jobs)} (series, h) cells to run, {len(done)} done; "
          f"backend={backend} workers={args.workers} -> {out}", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    new = not os.path.exists(out)
    with open(out, "a", newline="") as fh, \
            ProcessPoolExecutor(max_workers=args.workers) as pool:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        futs = [pool.submit(score, j) for j in jobs]
        for k, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            w.writerow(r)
            fh.flush()
            if k % 10 == 0 or k == len(jobs) or r["error"]:
                print(f"  {k}/{len(jobs)} {r['series']} h={r['h']} n={r['n']} "
                      f"{r['secs']}s F_hat={r.get('F_hat', float('nan')):+.4f} "
                      f"{r['error']}", flush=True)
    print(f"[{args.arm}] finished in {time.time() - t0:.0f}s wall", flush=True)


# ---------------------------------------------------------------- summary
def _cluster(arm, sid):
    """Bootstrap unit: FRED series cluster by family (curves and FX panels
    are far from independent); every other arm resamples series. Sensors and
    electricity clients are cross-sectionally dependent too, so their
    intervals are optimistic."""
    if arm.startswith("fred") or arm == "returns":
        import fred_universe
        return fred_universe.family(sid)
    return sid


def _boot(units, stat, B=1000, seed=0):
    import random
    rng = random.Random(seed)
    keys = list(units)
    vals = []
    for _ in range(B):
        rows = [r for _ in keys for r in units[keys[rng.randrange(len(keys))]]]
        vals.append(stat(rows))
    vals.sort()
    return vals[int(0.05 * B)], vals[int(0.95 * B) - 1]


def summarize(paths, fig_path, csv_path):
    import statistics
    rows = {}
    for p in paths:
        for r in _read_rows(p):
            if r["error"]:
                continue
            try:
                vals = {k: float(r[k]) for k in DERIVED}
            except ValueError:
                continue
            if all(math.isfinite(x) for x in vals.values()):
                rows[(r["arm"], r["series"], int(r["h"]))] = vals  # last wins
    arms = sorted({a for a, _, _ in rows})
    table = []
    for arm in arms:
        for h in sorted({h for a, _, h in rows if a == arm}):
            cell = {s: v for (a, s, hh), v in rows.items() if a == arm and hh == h}
            units = {}
            for s, v in cell.items():
                units.setdefault(_cluster(arm, s), []).append(v)
            rec = dict(arm=arm, h=h, n_series=len(cell), n_clusters=len(units))
            for k in DERIVED:
                xs = [v[k] for v in cell.values()]
                lo, hi = _boot(units, lambda rr, k=k: sum(r[k] for r in rr) / len(rr))
                rec.update({f"{k}_mean": statistics.mean(xs), f"{k}_lo": lo,
                            f"{k}_hi": hi, f"{k}_median": statistics.median(xs),
                            f"{k}_pos": sum(x > 0 for x in xs) / len(xs)})
            for k in ("X_cps", "X_cpsz"):
                ratio = (lambda rr, k=k: sum(r[k] for r in rr)
                         / sum(r["F_hat"] for r in rr)
                         if sum(r["F_hat"] for r in rr) else float("nan"))
                lo, hi = _boot(units, ratio)
                rec.update({f"{k}/F_hat": ratio(list(cell.values())),
                            f"{k}/F_hat_lo": lo, f"{k}/F_hat_hi": hi})
            table.append(rec)
    if not table:
        print("no scored rows")
        return
    for arm in arms:
        print(f"\n== {arm}  (nats per scored target; [90% bootstrap CI]; "
              f"median; share > 0) ==")
        for rec in (r for r in table if r["arm"] == arm):
            print(f"h={rec['h']:<3d} series={rec['n_series']} "
                  f"clusters={rec['n_clusters']}")
            for k in DERIVED:
                print(f"   {k:7s} {rec[k + '_mean']:+.4f} [{rec[k + '_lo']:+.4f},"
                      f"{rec[k + '_hi']:+.4f}]  med {rec[k + '_median']:+.4f}  "
                      f"pos {100 * rec[k + '_pos']:.0f}%")
            for k in ("X_cps", "X_cpsz"):
                print(f"   {k}/F_hat  {rec[k + '/F_hat']:+.3f} "
                      f"[{rec[k + '/F_hat_lo']:+.3f},{rec[k + '/F_hat_hi']:+.3f}]")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    print(f"\nsummary -> {csv_path}")
    _figure(table, arms, fig_path)


def _figure(table, arms, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    series = [("F_hat", "F̂ = L_lap − L_unc (feasible forecastability)", "#2a78d6"),
              ("X_cps", "X_cps = L_cps − L_unc (pooled raw residuals)", "#eb6834"),
              ("X_cpsz", "X_cpsz = L_cpsz − L_unc (pooled standardized)", "#1baf7a")]
    ncol = min(3, len(arms))
    nrow = math.ceil(len(arms) / ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 3.4 * nrow),
                             squeeze=False)
    for ax, arm in zip(axes.flat, arms):
        recs = sorted((r for r in table if r["arm"] == arm), key=lambda r: r["h"])
        hs = [r["h"] for r in recs]
        for k, _lab, col in series:
            ax.fill_between(hs, [r[k + "_lo"] for r in recs],
                            [r[k + "_hi"] for r in recs], color=col, alpha=0.15, lw=0)
            ax.plot(hs, [r[k + "_mean"] for r in recs], color=col, lw=2,
                    marker="o", ms=5)
        ax.axhline(0, color="#52514e", lw=0.8)
        ax.set_xscale("log")
        ax.set_xticks(hs)
        ax.set_xticklabels([str(h) for h in hs])
        ax.minorticks_off()
        ax.set_title(f"{arm} ({recs[0]['n_series']} series)", fontsize=10)
        ax.set_xlabel("horizon h")
        ax.grid(alpha=0.25, lw=0.5)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    for ax in list(axes.flat)[len(arms):]:
        ax.axis("off")
    axes[0][0].set_ylabel("nats per target over unconditional")
    fig.legend([plt.Line2D([], [], color=c, lw=2) for _, _, c in series],
               [lab for _, lab, _ in series], loc="lower center", ncol=1,
               fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.14 if nrow == 1 else 0.08, 1, 1))
    fig.savefig(path, dpi=150)
    print(f"figure  -> {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--arm", choices=sorted(ARMS))
    ap.add_argument("--horizons", default=",".join(map(str, HORIZONS)))
    ap.add_argument("--limit", type=int, default=0,
                    help="evenly spaced subset of N series (0 = all)")
    ap.add_argument("--max-len", type=int, default=0,
                    help="keep only the last N changes of each series (0 = all)")
    ap.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 4))
    ap.add_argument("--backend", choices=["auto", "fast", "python"], default="auto",
                    help="laplace backend: skaters_fast (Rust) if importable")
    ap.add_argument("--out", nargs="*",
                    help="results CSV (run) / CSVs to pool (--summarize)")
    ap.add_argument("--list", action="store_true",
                    help="load (and fetch/cache) the arm, print series, exit")
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--fig", default=os.path.join(_HERE, "forecastability_profile.png"))
    ap.add_argument("--summary-csv",
                    default=os.path.join(_HERE, "forecastability_summary.csv"))
    args = ap.parse_args()
    if args.summarize:
        import glob
        paths = args.out or sorted(glob.glob(os.path.join(_HERE, "forecastability_*.csv")))
        paths = [p for p in paths if not p.endswith("_summary.csv")]
        summarize(paths, args.fig, args.summary_csv)
    elif args.arm:
        run(args)
    else:
        ap.error("--arm or --summarize required")


if __name__ == "__main__":
    main()
