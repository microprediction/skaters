"""Wide pre-registered TabFM study: four designs, stratified non-price universe.

Extends the first TabFM bout (benchmarks/tabfm_study.py, pre-registered
2026-07-09) to a much wider universe and several ways of using TabFM. The
statement of intended research is benchmarks/preregistrations/
2026-07-09-tabfm-wide.md; parameters here are the frozen ones.

Universe. All cached non-price FRED series (the same title-based classifier
the main study uses: equity/fx/commodity excluded) with at least 1000
changes, whose pre-test history is not constant. Series are characterized on
the pre-test history ONLY (the last TEST changes never inform selection):
repeat fraction and lag-1 autocorrelation of changes (martingality). The
universe is a stratified sample: 5 martingality bins x 3 repeat bins, up to
24 series per cell, deterministic seed. The selected list with strata is
committed at benchmarks/preregistrations/tabfm_wide_universe.txt. The run
order interleaves strata round-robin so partial results stay representative.

Arms (all zero-shot, CTX=256 context arranged as lag tables, STRIDE=10
in-context refresh, NE=4 ensemble members):
  clf8   decile-bin classifier density, 8 lags   (replication of bout 1)
  clf16  decile-bin classifier density, 16 lags  (does lag depth help?)
  clfew  equal-width-bin classifier density, 8 lags, bins spanning the
         1st-99th percentile of training targets (does the binning matter?)
  regres regressor point + residual density: fit on all but the last 40
         training rows, take residuals on those 40 held-out rows, centre a
         Gaussian-KDE of the residuals on each test prediction
The regres arm also yields the MAE undercard (its raw point vs the median
of laplace's predictive).

Resume. Every (series, arm) result is appended and flushed as it completes;
on restart, finished pairs are skipped. Kill it any time.

Run (skaters-fm env; weights at ~/.cache/tabfm_bin, see tabfm_study.py):
  PYTHONPATH=src python benchmarks/tabfm_wide_study.py
Env knobs: TB_DEVICE=cpu|mps (Mac Studio: try mps, fall back to cpu),
TB_SMOKE=<n> series, TB_FAKE=1 (plumbing test with stub models, no weights),
TB_ARMS=comma list to restrict arms.
"""
from __future__ import annotations
import os, sys, gc, time, csv, math, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import foundation_study as fs
import fred
import fred_universe as fu
from skaters.dist import Dist
from skaters.api import laplace

_HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(_HERE, "results_tabfm_wide.csv")
MAE_RESULTS = os.path.join(_HERE, "results_tabfm_wide_mae.csv")
UNIVERSE_TXT = os.path.join(_HERE, "preregistrations", "tabfm_wide_universe.txt")
WEIGHTS = os.path.expanduser("~/.cache/tabfm_bin")

STRIDE = int(os.environ.get("TB_STRIDE", 10))
NE = int(os.environ.get("TB_NE", 4))
DEVICE = os.environ.get("TB_DEVICE", "cpu")
N_SMOKE = int(os.environ.get("TB_SMOKE", 0))
FAKE = os.environ.get("TB_FAKE", "") == "1"
TEST, CTX, HIST = fs.TEST, fs.CTX, 1000
PER_CELL = int(os.environ.get("TB_PER_CELL", 24))
SEED = 20260709
RESID_ROWS = 40

CLF_ARMS = ["clf8", "clf16", "clfew"]
REG_ARMS = ["regres"]
_sel = os.environ.get("TB_ARMS", "")
if _sel:
    keep = set(_sel.split(","))
    CLF_ARMS = [a for a in CLF_ARMS if a in keep]
    REG_ARMS = [a for a in REG_ARMS if a in keep]

PRICE = {"equity", "fx", "commodity"}


# ---------------------------------------------------------------- selection
def _titles():
    import json
    path = os.path.join(fred._CACHE, "universe_daily.json")
    if os.path.exists(path):
        return {d["id"]: d.get("title", "") for d in json.load(open(path))}
    return {}


def characterize(hist_ch):
    """Repeat fraction and lag-1 autocorrelation on the PRE-TEST history."""
    a = np.asarray(hist_ch, float)
    rf = float(np.mean(a[1:] == a[:-1])) if len(a) > 1 else 1.0
    v = float(np.var(a))
    if v <= 0:
        return rf, None
    rho1 = float(np.corrcoef(a[:-1], a[1:])[0, 1])
    return rf, rho1


def _rho_bin(rho):
    if rho <= -0.2: return "rho<-0.2"
    if rho <= -0.05: return "rho-0.2..-0.05"
    if rho < 0.05: return "rho~0"
    if rho < 0.2: return "rho0.05..0.2"
    return "rho>0.2"


def _rf_bin(rf):
    if rf < 0.05: return "cts"
    if rf < 0.35: return "mixed"
    return "repeat"


def select_universe():
    """Deterministic stratified sample. Selection sees only pre-test history."""
    import re
    tmap = _titles()
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    extra_price = re.compile(
        r"nasdaq|coinbase|bitcoin|ethereum|litecoin|s&p|dow jones|wilshire|"
        r"gold|silver|crude|price index for", re.I)
    cells = {}
    for sid in ids:
        title = tmap.get(sid)
        if title is None:                    # unknown title: cannot classify,
            continue                         # so it cannot enter the universe
        if fu.asset_class(title) in PRICE or extra_price.search(title) \
                or extra_price.search(sid):
            continue
        lv = fred._load_levels(sid)
        if not lv:
            continue
        ch = fred._to_changes(lv)
        if len(ch) < HIST:
            continue
        ch = ch[-HIST:]
        rf, rho1 = characterize(ch[:-TEST])
        if rho1 is None:            # constant pre-test history: measures the
            continue                # fallback convention, not the model
        cells.setdefault((_rho_bin(rho1), _rf_bin(rf)), []).append(sid)
    rng = np.random.default_rng(SEED)
    picked = []                     # (sid, stratum, position-in-cell)
    for key in sorted(cells):
        pool = sorted(cells[key])
        take = list(rng.permutation(len(pool))[:PER_CELL])
        for pos, i in enumerate(take):
            picked.append((pool[int(i)], "|".join(key), pos))
    # round-robin over strata so partial runs stay representative
    picked.sort(key=lambda t: (t[2], t[1]))
    return [(sid, stratum) for sid, stratum, _ in picked]


def write_universe(sel):
    os.makedirs(os.path.dirname(UNIVERSE_TXT), exist_ok=True)
    with open(UNIVERSE_TXT, "w") as fh:
        fh.write("# series_id\tstratum (rho1 bin | repeat bin), run order\n")
        for sid, stratum in sel:
            fh.write(f"{sid}\t{stratum}\n")


def load_universe():
    if os.path.exists(UNIVERSE_TXT):
        out = []
        for line in open(UNIVERSE_TXT):
            if line.startswith("#"):
                continue
            sid, stratum = line.rstrip("\n").split("\t")
            out.append((sid, stratum))
        return out
    sel = select_universe()
    write_universe(sel)
    return sel


# ---------------------------------------------------------------- densities
def lag_rows(ch, lo, hi, lags):
    X = np.array([ch[j - lags:j] for j in range(lo, hi)], dtype=np.float32)
    y = np.array(ch[lo:hi], dtype=np.float64)
    return X, y


def decile_edges(train_y):
    return np.unique(np.quantile(train_y, np.linspace(0.0, 1.0, 11)))


def width_edges(train_y):
    lo, hi = np.quantile(train_y, [0.01, 0.99])
    if hi <= lo:
        return decile_edges(train_y)
    inner = np.linspace(lo, hi, 9)
    return np.unique(np.concatenate([[train_y.min()], inner, [train_y.max()]]))


def labels_for(edges, y):
    return np.clip(np.searchsorted(edges, y, side="right") - 1, 0, len(edges) - 2)


def bar_dist(edges, probs):
    comps = []
    for i, p in enumerate(probs):
        w = float(max(p, 1e-6))
        lo, hi = float(edges[i]), float(edges[i + 1])
        comps.append((w, (lo + hi) / 2.0, max(0.29 * (hi - lo), 1e-9)))
    return Dist(comps)


def resid_dist(residuals, pred):
    return fs.sample_dist(residuals).shift(float(pred))


def laplace_dists(ch):
    f = laplace(1); st = None; pend = None; out = []
    start = len(ch) - TEST
    for i, yv in enumerate(ch):
        if pend is not None and i >= start:
            out.append(pend[0])
        d, st = f(yv, st); pend = d
    return out


# ---------------------------------------------------------------- fake models
class _FakeClf:
    def __init__(self, **kw): pass
    def fit(self, X, y):
        import collections
        c = collections.Counter(int(v) for v in y)
        self.classes_ = np.array(sorted(c))
        n = sum(c.values())
        self._p = np.array([c[k] / n for k in self.classes_])
        return self
    def predict_proba(self, X):
        return np.tile(self._p, (len(X), 1))


class _FakeReg:
    def __init__(self, **kw): pass
    def fit(self, X, y):
        self._m = float(np.mean(y)); return self
    def predict(self, X):
        return np.full(len(X), self._m)


# ---------------------------------------------------------------- passes
def _blocks(n):
    start = n - TEST
    for t0 in range(start, n, STRIDE):
        yield t0, min(t0 + STRIDE, n)


def _load_ch(sid):
    ch = fred._to_changes(fred._load_levels(sid))
    return ch[-HIST:]


def _done_pairs(path):
    if not os.path.exists(path):
        return set()
    return {(r["series"], r["method"]) for r in csv.DictReader(open(path))}


def _open_results(path, header):
    mode = "a" if os.path.exists(path) else "w"
    fh = open(path, mode, newline="")
    w = csv.writer(fh)
    if mode == "w":
        w.writerow(header)
    return fh, w


def clf_arm_dists(ch, lags, edger, model, TabFMClassifier):
    n = len(ch)
    dists = []
    for lo, hi in _blocks(n):
        Xtr, ytr = lag_rows(ch, lo - CTX + lags, lo, lags)
        Xte, _ = lag_rows(ch, lo, hi, lags)
        edges = edger(ytr)
        if len(edges) < 2:
            v = float(np.median(ytr))
            dists += [Dist([(1.0, v, 1e-9)])] * (hi - lo)
            continue
        if len(edges) == 2:
            dists += [bar_dist(edges, [1.0])] * (hi - lo)
            continue
        lab = labels_for(edges, ytr)
        clf = TabFMClassifier(model=model, n_estimators=NE)
        clf.fit(Xtr, lab)
        probs = clf.predict_proba(Xte)
        full = np.zeros((len(Xte), len(edges) - 1))
        for col, c in enumerate(clf.classes_):
            full[:, int(c)] = probs[:, col]
        dists += [bar_dist(edges, row) for row in full]
    return dists


def reg_arm(ch, lags, model, TabFMRegressor):
    """regres arm: per-step (Dist, point). One fit + one predict per block:
    train on all but the last RESID_ROWS rows, predict those rows and the
    block's test rows in a single call."""
    n = len(ch)
    dists, points = [], []
    for lo, hi in _blocks(n):
        Xall, yall = lag_rows(ch, lo - CTX + lags, lo, lags)
        Xte, _ = lag_rows(ch, lo, hi, lags)
        Xtr, ytr = Xall[:-RESID_ROWS], yall[:-RESID_ROWS]
        Xres, yres = Xall[-RESID_ROWS:], yall[-RESID_ROWS:]
        if float(np.ptp(ytr)) == 0.0:
            v = float(ytr[0])
            dists += [Dist([(1.0, v, 1e-9)])] * (hi - lo)
            points += [v] * (hi - lo)
            continue
        reg = TabFMRegressor(model=model, n_estimators=NE)
        reg.fit(Xtr, ytr)
        pred = reg.predict(np.concatenate([Xres, Xte]))
        residuals = yres - np.asarray(pred[:RESID_ROWS], float)
        for p in pred[RESID_ROWS:]:
            dists.append(resid_dist(residuals, p))
            points.append(float(p))
    return dists, points


def classification_pass(universe):
    if FAKE:
        model, Clf = None, _FakeClf
    else:
        from tabfm import TabFMClassifier as Clf, tabfm_v1_0_0_pytorch as V
        model = V.load(model_type="classification", checkpoint_path=WEIGHTS,
                       device=None if DEVICE == "cpu" else DEVICE)
    done = _done_pairs(RESULTS)
    fh, w = _open_results(RESULTS, ["series", "method", "logpdf", "crps", "n", "stratum"])
    arms = {"clf8": (8, decile_edges), "clf16": (16, decile_edges),
            "clfew": (8, width_edges)}
    arms = {k: v for k, v in arms.items() if k in CLF_ARMS}
    with fh:
        for j, (sid, stratum) in enumerate(universe):
            todo = [a for a in arms if (sid, a) not in done]
            need_lap = (sid, "laplace") not in done
            if not todo and not need_lap:
                continue
            t0 = time.time()
            ch = _load_ch(sid)
            y = ch[len(ch) - TEST:]
            if need_lap:
                lp, cr = fs.laplace_scores(ch)
                w.writerow([sid, "laplace", f"{lp:.6f}", f"{cr:.6f}", TEST, stratum])
            for a in todo:
                lags, edger = arms[a]
                dists = clf_arm_dists(ch, lags, edger, model, Clf)
                aa, bb = fs.score_steps(dists, y)
                w.writerow([sid, a, f"{aa:.6f}", f"{bb:.6f}", TEST, stratum])
            fh.flush()
            print(f"  clf {j+1}/{len(universe)} {sid} [{stratum}] "
                  f"({time.time()-t0:.0f}s)", flush=True)
    del model; gc.collect()


def regression_pass(universe):
    if not REG_ARMS:
        return
    if FAKE:
        model, Reg = None, _FakeReg
    else:
        from tabfm import TabFMRegressor as Reg, tabfm_v1_0_0_pytorch as V
        model = V.load(model_type="regression", checkpoint_path=WEIGHTS,
                       device=None if DEVICE == "cpu" else DEVICE)
    done = _done_pairs(RESULTS)
    done_mae = _done_pairs(MAE_RESULTS)
    fh, w = _open_results(RESULTS, ["series", "method", "logpdf", "crps", "n", "stratum"])
    fh2, w2 = _open_results(MAE_RESULTS,
                            ["series", "method", "tabfm_mae", "laplace_mae", "n", "stratum"])
    with fh, fh2:
        for j, (sid, stratum) in enumerate(universe):
            if (sid, "regres") in done and (sid, "regres") in done_mae:
                continue
            t0 = time.time()
            ch = _load_ch(sid)
            y = np.array(ch[len(ch) - TEST:])
            dists, points = reg_arm(ch, 8, model, Reg)
            if (sid, "regres") not in done:
                aa, bb = fs.score_steps(dists, list(y))
                w.writerow([sid, "regres", f"{aa:.6f}", f"{bb:.6f}", TEST, stratum])
                fh.flush()
            if (sid, "regres") not in done_mae:
                med = np.array([d.quantile(0.5) for d in laplace_dists(ch)])
                tm = float(np.mean(np.abs(np.array(points) - y)))
                lm = float(np.mean(np.abs(med - y)))
                w2.writerow([sid, "regres", f"{tm:.6f}", f"{lm:.6f}", TEST, stratum])
                fh2.flush()
            print(f"  reg {j+1}/{len(universe)} {sid} [{stratum}] "
                  f"({time.time()-t0:.0f}s)", flush=True)
    del model; gc.collect()


# ---------------------------------------------------------------- driver
def run():
    universe = load_universe()
    if N_SMOKE:
        universe = universe[:N_SMOKE]
    print(f"TabFM wide study: {len(universe)} series, arms "
          f"{CLF_ARMS + REG_ARMS}, STRIDE={STRIDE}, NE={NE}, CTX={CTX}, "
          f"TEST={TEST}, device={DEVICE}, fake={FAKE}", flush=True)
    if CLF_ARMS:
        classification_pass(universe)
    regression_pass(universe)
    summarize()


def summarize():
    if not os.path.exists(RESULTS):
        print("no results yet"); return
    by, strat = {}, {}
    for r in csv.DictReader(open(RESULTS)):
        by.setdefault(r["series"], {})[r["method"]] = (
            float(r["logpdf"]), float(r["crps"]))
        strat[r["series"]] = r["stratum"]
    arms = sorted({m for d in by.values() for m in d} - {"laplace"})
    print(f"\n=== TabFM wide study: {len(by)} series scored ===")
    print(f"{'arm':8s}{'split':22s}{'n':>5s}{'lap LL wins':>13s}{'lap CRPS wins':>15s}"
          f"{'med LL gap':>12s}")
    for a in arms:
        pairs = {s: d for s, d in by.items() if a in d and "laplace" in d}
        groups = {"ALL": set(pairs)}
        for s in pairs:
            groups.setdefault(strat[s], set()).add(s)
        for g in ["ALL"] + sorted(k for k in groups if k != "ALL"):
            sub = [pairs[s] for s in groups[g]]
            if not sub:
                continue
            ll = 100 * sum(1 for d in sub if d["laplace"][0] > d[a][0]) / len(sub)
            cr = 100 * sum(1 for d in sub if d["laplace"][1] < d[a][1]) / len(sub)
            gap = float(np.median([d["laplace"][0] - d[a][0] for d in sub]))
            print(f"{a:8s}{g:22s}{len(sub):5d}{ll:12.0f}%{cr:14.0f}%{gap:12.2f}")
    if os.path.exists(MAE_RESULTS):
        rows = list(csv.DictReader(open(MAE_RESULTS)))
        if rows:
            wins = 100 * sum(1 for r in rows
                             if float(r["laplace_mae"]) < float(r["tabfm_mae"])) / len(rows)
            print(f"\nMAE undercard (regres): laplace wins {wins:.0f}% of {len(rows)}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        summarize()
    elif len(sys.argv) > 1 and sys.argv[1] == "universe":
        sel = select_universe(); write_universe(sel)
        from collections import Counter
        print(f"{len(sel)} series -> {UNIVERSE_TXT}")
        for k, v in sorted(Counter(s for _, s in sel).items()):
            print(f"  {k:28s}{v:4d}")
    else:
        run()
