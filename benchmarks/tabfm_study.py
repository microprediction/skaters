"""TabFM (Google's tabular foundation model, June 2026) vs laplace on the
foundation-model protocol, via the autoregressive tabular reduction.

TabFM is not a forecaster, so the change stream is presented to it as a table:
each training row is a lag-vector of the preceding LAGS changes and its target
is the next change; the test row is the current lag-vector. The context is the
same CTX=256 changes the other foundation models saw, arranged as CTX-LAGS rows.

TabFM's regression head decodes to a single value (no quantiles, no density),
so the distributional bout is run through its *classifier*: training targets
are binned into up-to-10 decile classes (10 is the model's max_classes), the
predicted class probabilities become a bar distribution, and that is smoothed
into the same `Dist` and scored by the same code as everyone else. This
reconstruction is ours, not Google's, and is disclosed wherever results are
reported. The regressor's point output is scored as an MAE undercard against
the median of laplace's predictive.

Concessions TabFM needed (all favour TabFM being runnable at all on CPU):
the in-context table is refreshed every STRIDE=10 steps rather than every step
(test-row features are still current at every step), and the ensemble is
trimmed to NE=4 members from the default 32. Each checkpoint is 1.64B
parameters (~6.5 GB fp32), so the two passes run sequentially.

Run (needs the `skaters-fm` env with `tabfm` installed; weights are converted
once from safetensors to pytorch_model.bin under ~/.cache/tabfm_bin because
the pip loader and the HF repo disagree on the checkpoint format):
  PYTHONPATH=src python benchmarks/tabfm_study.py
"""
from __future__ import annotations
import os, sys, gc, time, csv, math, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import foundation_study as fs
from skaters.dist import Dist
from skaters.api import laplace

_HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(_HERE, "results_foundation_tabfm.csv")
MAE_RESULTS = os.path.join(_HERE, "results_tabfm_mae.csv")
WEIGHTS = os.path.expanduser("~/.cache/tabfm_bin")

LAGS = int(os.environ.get("TB_LAGS", 8))
STRIDE = int(os.environ.get("TB_STRIDE", 10))
NE = int(os.environ.get("TB_NE", 4))
N_SMOKE = int(os.environ.get("TB_SMOKE", 0))     # >0: only this many series
TEST, CTX = fs.TEST, fs.CTX


# ---------------------------------------------------------------- reduction
def lag_rows(ch, lo, hi):
    """Feature matrix and target vector for steps lo..hi-1 of the change list."""
    X = np.array([ch[j - LAGS:j] for j in range(lo, hi)], dtype=np.float32)
    y = np.array(ch[lo:hi], dtype=np.float64)
    return X, y


def bin_labels(train_y):
    """Decile bin edges (deduplicated) and per-row class labels, or None if the
    window is constant."""
    edges = np.unique(np.quantile(train_y, np.linspace(0.0, 1.0, 11)))
    if len(edges) < 2:
        return None, None
    lab = np.clip(np.searchsorted(edges, train_y, side="right") - 1,
                  0, len(edges) - 2)
    return edges, lab


def bar_dist(edges, probs):
    """Smoothed `Dist` from class probabilities over bins. One Gaussian per bin
    at the bin centre; bandwidth ~ width/sqrt(12), the moment match for a
    uniform bin."""
    comps = []
    for i, p in enumerate(probs):
        w = float(max(p, 1e-6))
        lo, hi = float(edges[i]), float(edges[i + 1])
        width = hi - lo
        comps.append((w, (lo + hi) / 2.0, max(0.29 * width, 1e-9)))
    return Dist(comps)


def laplace_dists(ch):
    """Per-step laplace predictive `Dist`s over the TEST window."""
    f = laplace(1); st = None; pend = None; out = []
    start = len(ch) - TEST
    for i, yv in enumerate(ch):
        if pend is not None and i >= start:
            out.append(pend[0])
        d, st = f(yv, st); pend = d
    return out


# ---------------------------------------------------------------- passes
def _blocks(n):
    start = n - TEST
    for t0 in range(start, n, STRIDE):
        yield t0, min(t0 + STRIDE, n)


def classifier_pass(series, done):
    from tabfm import TabFMClassifier, tabfm_v1_0_0_pytorch as V
    model = V.load(model_type="classification", checkpoint_path=WEIGHTS)
    mode = "a" if os.path.exists(RESULTS) else "w"
    with open(RESULTS, mode, newline="") as fh:
        w = csv.writer(fh)
        if mode == "w":
            w.writerow(["series", "method", "logpdf", "crps", "n"])
        for j, (sid, ch) in enumerate(series.items()):
            if sid in done:
                continue
            t0 = time.time()
            n = len(ch); y = ch[n - TEST:]
            dists = []
            for lo, hi in _blocks(n):
                Xtr, ytr = lag_rows(ch, lo - CTX + LAGS, lo)
                edges, lab = bin_labels(ytr)
                Xte, _ = lag_rows(ch, lo, hi)
                if edges is None or len(edges) == 2 and edges[0] == edges[1]:
                    v = float(np.median(ytr))
                    dists += [Dist([(1.0, v, 1e-9)])] * (hi - lo)
                    continue
                if len(edges) == 2:      # a single bin: degenerate classifier
                    dists += [bar_dist(edges, [1.0])] * (hi - lo)
                    continue
                clf = TabFMClassifier(model=model, n_estimators=NE)
                clf.fit(Xtr, lab)
                probs = clf.predict_proba(Xte)
                full = np.zeros((len(Xte), len(edges) - 1))
                for col, c in enumerate(clf.classes_):
                    full[:, int(c)] = probs[:, col]
                dists += [bar_dist(edges, row) for row in full]
            a, b = fs.score_steps(dists, y)
            lp, cr = fs.laplace_scores(ch)
            w.writerow([sid, "laplace", f"{lp:.6f}", f"{cr:.6f}", TEST])
            w.writerow([sid, "TabFM", f"{a:.6f}", f"{b:.6f}", TEST])
            fh.flush()
            print(f"  clf {j+1}/{len(series)} {sid}: TabFM ll {a:.3f} crps {b:.4f} "
                  f"| laplace ll {lp:.3f} crps {cr:.4f} ({time.time()-t0:.0f}s)",
                  flush=True)
    del model; gc.collect()


def regressor_pass(series, done):
    from tabfm import TabFMRegressor, tabfm_v1_0_0_pytorch as V
    model = V.load(model_type="regression", checkpoint_path=WEIGHTS)
    mode = "a" if os.path.exists(MAE_RESULTS) else "w"
    with open(MAE_RESULTS, mode, newline="") as fh:
        w = csv.writer(fh)
        if mode == "w":
            w.writerow(["series", "tabfm_mae", "laplace_mae", "n"])
        for j, (sid, ch) in enumerate(series.items()):
            if sid in done:
                continue
            t0 = time.time()
            n = len(ch); y = np.array(ch[n - TEST:])
            preds = []
            for lo, hi in _blocks(n):
                Xtr, ytr = lag_rows(ch, lo - CTX + LAGS, lo)
                Xte, _ = lag_rows(ch, lo, hi)
                if float(np.ptp(ytr)) == 0.0:
                    preds += [float(ytr[0])] * (hi - lo)
                    continue
                reg = TabFMRegressor(model=model, n_estimators=NE)
                reg.fit(Xtr, ytr)
                preds += [float(v) for v in reg.predict(Xte)]
            med = np.array([d.quantile(0.5) for d in laplace_dists(ch)])
            tm = float(np.mean(np.abs(np.array(preds) - y)))
            lm = float(np.mean(np.abs(med - y)))
            w.writerow([sid, f"{tm:.6f}", f"{lm:.6f}", TEST])
            fh.flush()
            print(f"  reg {j+1}/{len(series)} {sid}: TabFM mae {tm:.4f} "
                  f"| laplace mae {lm:.4f} ({time.time()-t0:.0f}s)", flush=True)
    del model; gc.collect()


# ---------------------------------------------------------------- driver
def _done(path, col=1, want=None):
    if not os.path.exists(path):
        return set()
    rows = list(csv.DictReader(open(path)))
    if want:
        return {r["series"] for r in rows if r[col] == want}
    return {r["series"] for r in rows}


def run():
    series = fs.load_series()
    if N_SMOKE:
        series = dict(list(series.items())[:N_SMOKE])
    print(f"TabFM study: {len(series)} series, LAGS={LAGS}, STRIDE={STRIDE}, "
          f"NE={NE}, CTX={CTX}, TEST={TEST}", flush=True)
    classifier_pass(series, _done(RESULTS, "method", "TabFM"))
    regressor_pass(series, _done(MAE_RESULTS))
    summarize()


def summarize():
    by = {}
    for r in csv.DictReader(open(RESULTS)):
        by.setdefault(r["series"], {})[r["method"]] = (
            float(r["logpdf"]), float(r["crps"]))
    both = {s: d for s, d in by.items() if "TabFM" in d and "laplace" in d}

    def rfrac(sid):
        ch = fs.fred._to_changes(fs.fred._load_levels(sid) or [])[-TEST:]
        return sum(1 for i in range(1, len(ch)) if ch[i] == ch[i - 1]) / max(len(ch) - 1, 1)
    cont = {s for s in both if rfrac(s) < 0.05}
    print(f"\n=== TabFM (classifier bar-distribution) vs laplace: "
          f"{len(both)} series ({len(cont)} continuous) ===")
    for label, sub in (("all", set(both)), ("continuous", cont)):
        d = [both[s] for s in sub]
        if not d:
            continue
        ll = 100 * sum(1 for x in d if x["laplace"][0] > x["TabFM"][0]) / len(d)
        cr = 100 * sum(1 for x in d if x["laplace"][1] < x["TabFM"][1]) / len(d)
        gap = float(np.median([x["laplace"][0] - x["TabFM"][0] for x in d]))
        print(f"  {label:12s} laplace wins LL {ll:.0f}%, CRPS {cr:.0f}%, "
              f"median LL gap {gap:.2f} nats (n={len(d)})")
    if os.path.exists(MAE_RESULTS):
        rows = list(csv.DictReader(open(MAE_RESULTS)))
        if rows:
            wins = 100 * sum(1 for r in rows
                             if float(r["laplace_mae"]) < float(r["tabfm_mae"])) / len(rows)
            print(f"  MAE undercard: laplace median beats TabFM regressor on "
                  f"{wins:.0f}% of {len(rows)} series")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        summarize()
    else:
        run()
