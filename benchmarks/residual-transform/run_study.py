"""Phase-1 ablation: does an online residual transform beat the base skater?

Runs M1 (dynamic scale) and M2 (dynamic scale + leverage) from
``skaters.residual_transform`` against base skaters over a sample of series,
and reports:

  * paired, HAC-robust log-score deltas for M1-vs-M0, M2-vs-M1, M2-vs-M0
    (M0 is the base skater's own forecast -- the residual-transform's
    identity case, see test_m0_reduces_to_base)
  * the same for CRPS, computed on a thinned subset of ticks (CRPS needs a
    32-point quantile-grid quadrature per call; log-score is exact and cheap)
  * the leverage diagnostic L_k = E[z_t (z_{t+k}^2-1)] and the raw z-moments,
    from the (shared) z-stream
  * the learned (a, b, c) at the end of each series

Datasets: fred (local FRED change-series, unfiltered sample), waveform
(M4-hourly, fetched/cached on first use), price (equity/fx/commodity series
classified by a live FRED title lookup). Base skaters: laplace, leaf,
garch_leaf (``laplace(k=1, leaf=garch_leaf)``).

Usage:
    PYTHONPATH=src python benchmarks/residual-transform/run_study.py
    PYTHONPATH=src python benchmarks/residual-transform/run_study.py \\
        --datasets price --bases garch_leaf,laplace --out results_price.csv
"""
from __future__ import annotations
import csv
import json
import math
import os
import random
import re
import subprocess
import sys
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_BENCH = os.path.dirname(_HERE)
sys.path.insert(0, _BENCH)
import fred  # noqa: E402 -- reuse fred._to_changes (log-diff / diff convention)

from skaters import laplace, leaf, garch_leaf, __version__  # noqa: E402
from skaters.residual_transform import residual_transform, ResidualDiagnostics  # noqa: E402

DATA_DIR = os.path.join(_BENCH, "data")
RESULTS_CSV = os.path.join(_HERE, "results.csv")

N_SERIES = 50
MIN_LEN = 400
SEED = 20260807
LR = 0.02
CRPS_EVERY = 5      # thin CRPS scoring (32-node quadrature per call)
WARMUP = 100         # ticks skipped before scoring (base + learner warm-up)
K_LAGS = 5           # leverage-diagnostic lags L_1..L_K

BASE_SKATERS = {
    "laplace": lambda: laplace(k=1, tails="gaussian"),
    "leaf": lambda: leaf(k=1),
    "garch_leaf": lambda: laplace(k=1, leaf=garch_leaf, tails="gaussian"),
}


def load_local_series(n=N_SERIES, min_len=MIN_LEN, seed=SEED):
    """A fixed, deterministic random sample of local benchmarks/data/*.csv
    series long enough to warm up a base skater and still leave a
    substantial held-out tail. No price/non-price filtering (that needs FRED
    title metadata this bare 2-column cache doesn't carry) -- a known
    simplification of this phase, noted in the README."""
    files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".csv"))
    series = {}
    for fn in files:
        sid = fn[:-4]
        levels = []
        with open(os.path.join(DATA_DIR, fn)) as fh:
            for line in fh:
                parts = line.rstrip("\n").split(",")
                if len(parts) != 2:
                    continue
                try:
                    levels.append((parts[0], float(parts[1])))
                except ValueError:
                    continue
        ch = fred._to_changes(levels)
        if len(ch) >= min_len:
            series[sid] = ch
    ids = sorted(series)
    random.Random(seed).shuffle(ids)
    chosen = ids[:n]
    return [(sid, series[sid]) for sid in chosen]


def load_waveform_series(n=N_SERIES, seed=SEED):
    """The M4-hourly competition set (business_line the README's "hard
    waveforms" arm -- near-deterministic, strongly 24-periodic cycles, the
    one regime where laplace cedes ground to CSP). Not cached locally; one
    public-file fetch via benchmarks/corpus.py (cached after the first run)."""
    import corpus
    all_series = [(sid, ch) for sid, _title, ch in corpus.iter_arm("m4-hourly", limit=1000)]
    ids = list(range(len(all_series)))
    random.Random(seed).shuffle(ids)
    return [all_series[i] for i in ids[:n]]


_PRICE_CANDIDATE_RE = re.compile(
    r"(^DEX|^VX|VIX|GOLD|OIL|WTI|BRENT|^D?GAS|NASDAQ|SP500|DJIA|WILL5000|DOWJ|RUSSELL|COMMOD)",
    re.IGNORECASE,
)
_PRICE_CLASSES = {"equity", "fx", "commodity"}  # the same set benchmarks/study.py uses


def _fetch_fred_title(series_id, key):
    if not key:
        return ""
    url = f"https://api.stlouisfed.org/fred/series?series_id={series_id}&api_key={key}&file_type=json"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            seriess = json.loads(resp.read()).get("seriess", [])
        return seriess[0]["title"] if seriess else ""
    except Exception:
        return ""


def load_price_series(n=N_SERIES, min_len=MIN_LEN, seed=SEED):
    """Actual price/return series (equity, fx, commodity) among the local
    cache -- the classical home turf of a leverage effect, unlike the
    generic-macro `fred` arm above (which was an unfiltered sample). No
    local title metadata exists for the bare 2-column CSVs, so this narrows
    to ticker-name candidates first (cheap, no network) and then confirms
    each via a live FRED title lookup classified by the same
    fred_universe.asset_class() rule benchmarks/study.py uses for its own
    price/non-price split -- not a from-scratch heuristic."""
    import fred_universe
    key = fred._api_key()
    files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".csv"))
    candidates = [f[:-4] for f in files if _PRICE_CANDIDATE_RE.search(f[:-4])]
    qualifying = []
    for sid in candidates:
        title = _fetch_fred_title(sid, key)
        if not title or fred_universe.asset_class(title) not in _PRICE_CLASSES:
            continue
        levels = []
        with open(os.path.join(DATA_DIR, f"{sid}.csv")) as fh:
            for line in fh:
                parts = line.rstrip("\n").split(",")
                if len(parts) != 2:
                    continue
                try:
                    levels.append((parts[0], float(parts[1])))
                except ValueError:
                    continue
        ch = fred._to_changes(levels)
        if len(ch) >= min_len:
            qualifying.append((sid, ch, title))
    ids = list(range(len(qualifying)))
    random.Random(seed).shuffle(ids)
    chosen = ids[:n]
    print(f"[residual-transform] price: {len(qualifying)}/{len(candidates)} candidates "
          f"classified equity/fx/commodity, sampling {len(chosen)}", flush=True)
    return [(qualifying[i][0], qualifying[i][1]) for i in chosen]


DATASETS = {
    "fred": load_local_series,
    "waveform": load_waveform_series,
    "price": load_price_series,
}


def _hac_mean_se(d, max_lag=None):
    """Newey-West HAC mean/SE (Bartlett kernel) of a paired difference
    series -- score differences are serially correlated (spec section 12),
    so an iid SE would understate uncertainty."""
    n = len(d)
    if n < 2:
        return float("nan"), float("nan")
    if max_lag is None:
        max_lag = max(1, int(4.0 * (n / 100.0) ** (2.0 / 9.0)))
    max_lag = min(max_lag, n - 1)
    dbar = sum(d) / n
    dc = [x - dbar for x in d]
    gamma0 = sum(x * x for x in dc) / n
    s = gamma0
    for lag in range(1, max_lag + 1):
        g = sum(dc[i] * dc[i + lag] for i in range(n - lag)) / n
        w = 1.0 - lag / (max_lag + 1.0)
        s += 2.0 * w * g
    return dbar, math.sqrt(max(s, 0.0) / n)


def run_series(ys, base_factory, lr=LR, warmup=WARMUP, crps_every=CRPS_EVERY, k_lags=K_LAGS):
    """M1 and M2 each wrap their own fresh base-skater instance over the same
    y-stream, so both see a numerically identical base trajectory (the base
    is a pure function of the observations, independent of which
    residual-transform model sits on top of it) -- the paired-comparison
    requirement of spec section 12 without needing one shared state object.
    """
    fs = {m: residual_transform(base_factory(), model=m, lr=lr) for m in ("m1", "m2")}
    states = {m: None for m in fs}
    diag = ResidualDiagnostics(K=k_lags)

    lp0, lp1, lp2 = [], [], []
    cr0, cr1, cr2 = [], [], []

    for t, y in enumerate(ys):
        correcteds = {}
        raw_ref = None
        for m, f in fs.items():
            dists, states[m] = f(y, states[m])
            correcteds[m] = dists[0]
            raw_ref = states[m]["raw"]
        z = states["m1"]["z"]
        if z is not None:
            diag.update(z)

        if warmup <= t < len(ys) - 1:
            y_next = ys[t + 1]
            a0, a1, a2 = raw_ref.logpdf(y_next), correcteds["m1"].logpdf(y_next), correcteds["m2"].logpdf(y_next)
            if all(math.isfinite(v) for v in (a0, a1, a2)):
                lp0.append(a0); lp1.append(a1); lp2.append(a2)
            if t % crps_every == 0:
                b0, b1, b2 = raw_ref.crps(y_next), correcteds["m1"].crps(y_next), correcteds["m2"].crps(y_next)
                if all(math.isfinite(v) for v in (b0, b1, b2)):
                    cr0.append(b0); cr1.append(b1); cr2.append(b2)

    return {
        "lp0": lp0, "lp1": lp1, "lp2": lp2,
        "cr0": cr0, "cr1": cr1, "cr2": cr2,
        "diag": diag.summary(),
        "learner_m1": dict(states["m1"]["learner"]),
        "learner_m2": dict(states["m2"]["learner"]),
    }


def _parse_args(argv):
    """--datasets a,b  --bases x,y  --out name.csv (all optional; default is
    every registered dataset x the original two bases, written to
    results.csv -- garch_leaf is opt-in via --bases so the phase-1 gate run
    stays reproducible as originally reported)."""
    datasets = list(DATASETS)
    bases = ["laplace", "leaf"]
    out = RESULTS_CSV
    i = 0
    while i < len(argv):
        if argv[i] == "--datasets":
            datasets = argv[i + 1].split(","); i += 2
        elif argv[i] == "--bases":
            bases = argv[i + 1].split(","); i += 2
        elif argv[i] == "--out":
            out = os.path.join(_HERE, argv[i + 1]); i += 2
        else:
            i += 1
    return datasets, bases, out


def main():
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, cwd=_BENCH).stdout.strip()
    except Exception:
        sha = "?"
    print(f"[residual-transform] skaters {__version__} @ {sha}", flush=True)

    dataset_names, base_names, out_csv = _parse_args(sys.argv[1:])
    rows = []
    t0 = time.time()
    for dataset_name in dataset_names:
        series = DATASETS[dataset_name]()
        print(f"[residual-transform] dataset={dataset_name} {len(series)} series, "
              f"bases={base_names}", flush=True)
        for base_name in base_names:
            base_factory = BASE_SKATERS[base_name]
            for i, (sid, ys) in enumerate(series):
                r = run_series(ys, base_factory)
                log_m1v0 = _hac_mean_se([a - b for a, b in zip(r["lp1"], r["lp0"])])
                log_m2v1 = _hac_mean_se([a - b for a, b in zip(r["lp2"], r["lp1"])])
                log_m2v0 = _hac_mean_se([a - b for a, b in zip(r["lp2"], r["lp0"])])
                crps_m1v0 = _hac_mean_se([a - b for a, b in zip(r["cr0"], r["cr1"])])
                crps_m2v1 = _hac_mean_se([a - b for a, b in zip(r["cr1"], r["cr2"])])
                crps_m2v0 = _hac_mean_se([a - b for a, b in zip(r["cr0"], r["cr2"])])
                d = r["diag"]
                rows.append({
                    "dataset": dataset_name, "base": base_name, "series": sid, "n": len(r["lp0"]),
                    "log_m1v0_mean": log_m1v0[0], "log_m1v0_se": log_m1v0[1],
                    "log_m2v1_mean": log_m2v1[0], "log_m2v1_se": log_m2v1[1],
                    "log_m2v0_mean": log_m2v0[0], "log_m2v0_se": log_m2v0[1],
                    "crps_m1v0_mean": crps_m1v0[0], "crps_m1v0_se": crps_m1v0[1],
                    "crps_m2v1_mean": crps_m2v1[0], "crps_m2v1_se": crps_m2v1[1],
                    "crps_m2v0_mean": crps_m2v0[0], "crps_m2v0_se": crps_m2v0[1],
                    "Ez": d["E[z]"], "Ez2": d["E[z2]"], "Ez3": d["E[z3]"], "Ez4": d["E[z4]"],
                    "L1": d["L"][0], "L2": d["L"][1] if len(d["L"]) > 1 else float("nan"),
                    "m1_a": r["learner_m1"]["a"], "m1_c": r["learner_m1"]["c"],
                    "m2_a": r["learner_m2"]["a"], "m2_b": r["learner_m2"]["b"], "m2_c": r["learner_m2"]["c"],
                })
                print(f"  [{dataset_name}/{base_name}] {i+1}/{len(series)} {sid}: "
                      f"M1-M0={log_m1v0[0]:+.4f}(se {log_m1v0[1]:.4f}) "
                      f"M2-M1={log_m2v1[0]:+.4f}(se {log_m2v1[1]:.4f}) "
                      f"n={len(r['lp0'])} b={r['learner_m2']['b']:+.3f}", flush=True)

    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[residual-transform] wrote {out_csv} ({time.time()-t0:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
