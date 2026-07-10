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
48 series per cell, at most 2 per FRED family per cell (diversity), fixed
seed. The selected list with strata and characteristics is
committed at benchmarks/preregistrations/tabfm_wide_universe.txt. The run
order interleaves strata round-robin so partial results stay representative.

Arms (all zero-shot, CTX=256 context arranged as lag tables, STRIDE=10
in-context refresh, NE=4 ensemble members):
  clf8    decile-bin classifier density, 8 lags   (replication of bout 1)
  clf16   decile-bin classifier density, 16 lags  (lag depth)
  clf32   decile-bin classifier density, 32 lags  (lag depth, further)
  clfew   equal-width bins spanning the 1st-99th percentile (binning scheme)
  clf2g   two staggered decile grids averaged: ~20 effective bins under the
          model's 10-class ceiling (bin resolution)
  clfx100 clf8 on 100x the series, scores adjusted back by the exact affine
          change of variables (scale invariance: equals clf8 iff invariant)
  clf8h5  clf8 forecasting the change 5 steps ahead; scored against
  clf8h20 laplace's native 5- and 20-step predictives (laplace_h5/h20 rows)
  blr8    control: conjugate Bayesian linear regression on the same 8-lag
          table, predictive Gaussian (does 1.6B of in-context learning beat
          a closed-form linear posterior on the identical table?)
  blr2    control: the same with a minimal 2-lag table
  regres  regressor point + residual density: fit on all but the last 40
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
FAKE = os.environ.get("TB_FAKE", "") == "1"
_SUFFIX = "_fake" if FAKE else ""      # fake runs must never touch real resume files
RESULTS = os.path.join(_HERE, f"results_tabfm_wide{_SUFFIX}.csv")
MAE_RESULTS = os.path.join(_HERE, f"results_tabfm_wide_mae{_SUFFIX}.csv")
UNIVERSE_TXT = os.path.join(_HERE, "preregistrations", "tabfm_wide_universe.txt")
WEIGHTS = os.path.expanduser("~/.cache/tabfm_bin")

STRIDE = int(os.environ.get("TB_STRIDE", 10))
NE = int(os.environ.get("TB_NE", 4))
DEVICE = os.environ.get("TB_DEVICE", "cpu")
N_SMOKE = int(os.environ.get("TB_SMOKE", 0))
TEST, CTX, HIST = fs.TEST, fs.CTX, 1000
PER_CELL = int(os.environ.get("TB_PER_CELL", 48))
SEED = 20260709
RESID_ROWS = 40

CLF_ARMS = ["clf8", "clf16", "clf32", "clfew", "clf2g", "clfx100",
            "clf8h5", "clf8h20", "blr8", "blr2"]
REG_ARMS = ["regres"]
X100 = 100.0                                   # scale for the invariance arm
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
    """Character of the PRE-TEST history: repeat fraction, lag-1
    autocorrelation of changes (martingality), excess kurtosis, and lag-1
    autocorrelation of absolute changes (volatility clustering)."""
    a = np.asarray(hist_ch, float)
    rf = float(np.mean(a[1:] == a[:-1])) if len(a) > 1 else 1.0
    v = float(np.var(a))
    if v <= 0:
        return rf, None, None, None
    rho1 = float(np.corrcoef(a[:-1], a[1:])[0, 1])
    if not math.isfinite(rho1):
        return rf, None, None, None
    kurt = float(np.mean((a - a.mean()) ** 4) / v ** 2 - 3.0)
    ab = np.abs(a)
    vv = float(np.var(ab))
    vcl = float(np.corrcoef(ab[:-1], ab[1:])[0, 1]) if vv > 0 else 0.0
    return rf, rho1, kurt, vcl


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
        rf, rho1, kurt, vcl = characterize(ch[:-TEST])
        if rho1 is None:            # constant or degenerate pre-test history:
            continue                # measures the fallback, not the model
        key = (_rho_bin(rho1), _rf_bin(rf))
        cells.setdefault(key, []).append(
            (sid, fu.family(sid), rho1, rf, kurt, vcl))
    # Within each cell, round-robin across FRED families (at most
    # FAM_CAP per family per cell) so a curve or panel of near-duplicate
    # series cannot crowd out diversity; families and series within a
    # family are visited in seeded random order.
    FAM_CAP = 2
    rng = np.random.default_rng(SEED)
    picked = []                     # (record, stratum, position-in-cell)
    for key in sorted(cells):
        fams = {}
        for rec in sorted(cells[key]):
            fams.setdefault(rec[1], []).append(rec)
        fam_order = [sorted(fams)[int(i)]
                     for i in rng.permutation(len(fams))]
        for f in fam_order:
            fams[f] = [fams[f][int(i)]
                       for i in rng.permutation(len(fams[f]))][:FAM_CAP]
        chosen, depth = [], 0
        while len(chosen) < PER_CELL:
            row = [fams[f][depth] for f in fam_order if depth < len(fams[f])]
            if not row:
                break
            chosen.extend(row[:PER_CELL - len(chosen)])
            depth += 1
        for pos, rec in enumerate(chosen):
            picked.append((rec, "|".join(key), pos))
    # round-robin over strata so partial runs stay representative
    picked.sort(key=lambda t: (t[2], t[1]))
    return [(rec[0], stratum, rec[1], rec[2], rec[3], rec[4], rec[5])
            for rec, stratum, _ in picked]


def write_universe(sel):
    os.makedirs(os.path.dirname(UNIVERSE_TXT), exist_ok=True)
    with open(UNIVERSE_TXT, "w") as fh:
        fh.write("# series_id\tstratum\tfamily\trho1\trepeat_frac\t"
                 "excess_kurtosis\tvol_clustering  (run order; "
                 "characteristics from pre-test history only)\n")
        for sid, stratum, fam, rho1, rf, kurt, vcl in sel:
            fh.write(f"{sid}\t{stratum}\t{fam}\t{rho1:.4f}\t{rf:.4f}\t"
                     f"{kurt:.2f}\t{vcl:.4f}\n")


def load_universe():
    if os.path.exists(UNIVERSE_TXT):
        out = []
        for line in open(UNIVERSE_TXT):
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            out.append((parts[0], parts[1]))
        return out
    sel = select_universe()
    write_universe(sel)
    return [(t[0], t[1]) for t in sel]


# ---------------------------------------------------------------- densities
def lag_rows(ch, lo, hi, lags, h=1):
    """Rows j in [lo, hi): features are `lags` consecutive changes ending
    h steps before the target ch[j], so the forecast of ch[j] uses only
    information available h steps earlier."""
    X = np.array([ch[j - h - lags + 1:j - h + 1] for j in range(lo, hi)],
                 dtype=np.float32)
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


def stagger_edges(train_y):
    """The second grid of the clf2g arm: 9 inner quantiles offset half a
    decile from the decile grid, bracketed by the training min/max, so the
    averaged pair acts like ~20 bins despite the 10-class ceiling."""
    inner = np.quantile(train_y, np.linspace(0.05, 0.95, 9))
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


def laplace_dists(ch, h=1):
    """Per-step laplace predictive for horizon h over the test window: the
    h-th element of the k-step list emitted h observations earlier."""
    f = laplace(h); st = None; queue = []; out = []
    start = len(ch) - TEST
    for i, yv in enumerate(ch):
        if len(queue) >= h and i >= start:
            out.append(queue[-h][h - 1])
        d, st = f(yv, st)
        queue.append(d)
        if len(queue) > h:
            queue.pop(0)
    return out


# Scoring for this study: per-point logpdf is floored at -20 whether it is
# non-finite OR merely astronomically negative. The stub-model sweep exposed
# administered-rate step series (IOER, IORR) where a policy jump lands far
# outside a 1e-9-bandwidth atom and the finite logpdf reaches -5e14, letting
# one point decide the series. The floor applies to every method identically,
# laplace included; adopted before any real TabFM result existed.
def score_steps(dists, y):
    lp = cr = 0.0
    for d, yt in zip(dists, y):
        yv = float(yt)
        v = d.logpdf(yv)
        lp += max(v, -20.0) if math.isfinite(v) else -20.0
        cr += d.crps(yv)
    n = len(dists)
    return lp / n, cr / n


def laplace_scores(ch):
    dists = laplace_dists(ch)
    return score_steps(dists, ch[len(ch) - TEST:])


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


def _grid_dists(Xtr, ytr, Xte, edges, model, TabFMClassifier):
    """Per-test-row bar Dists for one bin grid, or None if degenerate."""
    if len(edges) < 2:
        return None
    if len(edges) == 2:
        return [bar_dist(edges, [1.0]) for _ in range(len(Xte))]
    lab = labels_for(edges, ytr)
    clf = TabFMClassifier(model=model, n_estimators=NE)
    clf.fit(Xtr, lab)
    probs = clf.predict_proba(Xte)
    full = np.zeros((len(Xte), len(edges) - 1))
    for col, c in enumerate(clf.classes_):
        full[:, int(c)] = probs[:, col]
    return [bar_dist(edges, row) for row in full]


def clf_arm_dists(ch, lags, edgers, model, TabFMClassifier, h=1):
    """Classifier-arm densities; `edgers` is a list of bin-grid builders and
    the per-step Dist averages the grids (one grid for plain arms, two for
    the staggered clf2g arm). h>1 forecasts the change h steps ahead."""
    n = len(ch)
    dists = []
    for lo, hi in _blocks(n):
        Xtr, ytr = lag_rows(ch, lo - CTX + lags + h - 1, lo, lags, h)
        Xte, _ = lag_rows(ch, lo, hi, lags, h)
        per_grid = [_grid_dists(Xtr, ytr, Xte, e(ytr), model, TabFMClassifier)
                    for e in edgers]
        per_grid = [g for g in per_grid if g is not None]
        if not per_grid:
            v = float(np.median(ytr))
            dists += [Dist([(1.0, v, 1e-9)])] * (hi - lo)
            continue
        for i in range(hi - lo):
            row = [g[i] for g in per_grid]
            dists.append(row[0] if len(row) == 1 else Dist.combine(row))
    return dists


def blr_arm_dists(ch, lags):
    """Control arm: conjugate Bayesian linear regression (evidence-maximised
    ridge) on the identical lag table, predictive Gaussian per step."""
    from sklearn.linear_model import BayesianRidge
    n = len(ch)
    dists = []
    for lo, hi in _blocks(n):
        Xtr, ytr = lag_rows(ch, lo - CTX + lags, lo, lags)
        Xte, _ = lag_rows(ch, lo, hi, lags)
        if float(np.ptp(ytr)) == 0.0:
            v = float(ytr[0])
            dists += [Dist([(1.0, v, 1e-9)])] * (hi - lo)
            continue
        m = BayesianRidge()
        m.fit(np.asarray(Xtr, float), ytr)
        mu, sd = m.predict(np.asarray(Xte, float), return_std=True)
        dists += [Dist([(1.0, float(a), max(float(b), 1e-9))])
                  for a, b in zip(mu, sd)]
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
    tab_arms = {"clf8": (8, [decile_edges], 1), "clf16": (16, [decile_edges], 1),
                "clf32": (32, [decile_edges], 1), "clfew": (8, [width_edges], 1),
                "clf2g": (8, [decile_edges, stagger_edges], 1),
                "clf8h5": (8, [decile_edges], 5),
                "clf8h20": (8, [decile_edges], 20)}
    blr_arms = {"blr8": 8, "blr2": 2}
    tab_arms = {k: v for k, v in tab_arms.items() if k in CLF_ARMS}
    blr_arms = {k: v for k, v in blr_arms.items() if k in CLF_ARMS}
    with fh:
        for j, (sid, stratum) in enumerate(universe):
            todo = [a for a in CLF_ARMS if (sid, a) not in done]
            need_lap = (sid, "laplace") not in done
            if not todo and not need_lap:
                continue
            t0 = time.time()
            ch = _load_ch(sid)
            y = ch[len(ch) - TEST:]
            if need_lap:
                lp, cr = laplace_scores(ch)
                w.writerow([sid, "laplace", f"{lp:.6f}", f"{cr:.6f}", TEST, stratum])
            for h in (5, 20):
                if f"clf8h{h}" in CLF_ARMS and (sid, f"laplace_h{h}") not in done:
                    la, lb = score_steps(laplace_dists(ch, h), ch[len(ch) - TEST:])
                    w.writerow([sid, f"laplace_h{h}", f"{la:.6f}", f"{lb:.6f}",
                                TEST, stratum])
            for a in todo:
                if a == "clfx100":
                    # scale-invariance arm: identical design on X100*series,
                    # scored on X100*y, then adjusted back by the exact
                    # affine change of variables. Equal to clf8 iff the
                    # pipeline is scale-invariant.
                    sch = [X100 * v for v in ch]
                    dists = clf_arm_dists(sch, 8, [decile_edges], model, Clf)
                    aa, bb = score_steps(dists, [X100 * v for v in y])
                    aa, bb = aa + math.log(X100), bb / X100
                elif a in tab_arms:
                    lags, edgers, h = tab_arms[a]
                    dists = clf_arm_dists(ch, lags, edgers, model, Clf, h)
                    aa, bb = score_steps(dists, y)
                else:
                    dists = blr_arm_dists(ch, blr_arms[a])
                    aa, bb = score_steps(dists, y)
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
                aa, bb = score_steps(dists, list(y))
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
    arms = sorted({m for d in by.values() for m in d}
                  - {"laplace", "laplace_h5", "laplace_h20"})
    base_for = lambda a: ("laplace_h5" if a.endswith("h5") else
                          "laplace_h20" if a.endswith("h20") else "laplace")
    print(f"\n=== TabFM wide study: {len(by)} series scored ===")
    print(f"{'arm':8s}{'split':22s}{'n':>5s}{'lap LL wins':>13s}{'lap CRPS wins':>15s}"
          f"{'med LL gap':>12s}")
    for a in arms:
        base = base_for(a)
        pairs = {s: d for s, d in by.items() if a in d and base in d}
        groups = {"ALL": set(pairs)}
        for s in pairs:
            groups.setdefault(strat[s], set()).add(s)
        for g in ["ALL"] + sorted(k for k in groups if k != "ALL"):
            sub = [pairs[s] for s in groups[g]]
            if not sub:
                continue
            ll = 100 * sum(1 for d in sub if d[base][0] > d[a][0]) / len(sub)
            cr = 100 * sum(1 for d in sub if d[base][1] < d[a][1]) / len(sub)
            gap = float(np.median([d[base][0] - d[a][0] for d in sub]))
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
        for k, v in sorted(Counter(t[1] for t in sel).items()):
            print(f"  {k:28s}{v:4d}")
    else:
        run()
