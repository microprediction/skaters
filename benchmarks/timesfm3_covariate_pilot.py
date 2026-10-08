"""Cheap pilot: does feeding TimesFM3 laplace's own calibration signal as a
past-only covariate beat plain univariate TimesFM3?

The covariate is laplace's z-score stream (state["z"][0]: the PIT of each
point under the predictive laplace issued for it, through the standard-normal
quantile -- roughly N(0,1) when calibrated, large when laplace was surprised),
not its mean prediction. The mean stream is redundant with the raw context
(a smoothed copy of the same series -- TimesFM's attention can already form
that from the context alone); z-score is a genuinely different signal, laplace's
own real-time "how wrong was I" track, not otherwise recoverable from the raw
series. Toggle with PILOT_COVARIATE=z|mean|quantiles|z-horizons.
  "quantiles"   laplace's own predictive value at each of the SAME nine
                deciles (0.1..0.9) TimesFM3 itself is asked to emit, one
                covariate row per decile -- laplace's full predictive shape at
                h=1, not a scalar summary of it.
  "z-horizons"  laplace's z-score at horizons (1,2,3,5,10), one row per
                horizon -- laplace's own multi-horizon calibration state,
                already tracked natively by laplace(k), no new plumbing.
  "zcoord"      a different mechanism, not a covariate at all: TimesFM3
                forecasts laplace's z-COORDINATE itself (context = past
                z-values, target = next z), inverted back to raw units
                through the same laplace Dist that defined the z-transform.
                See run_zcoord_pilot().

Not a claim that this beats laplace -- it's the narrower question of whether
laplace's online signal, fed IN to TimesFM3's attention (a cross-variate
input) rather than combined with its output post-hoc (the existing +lap /
~lap / @lap / &lap sandwiches), gives the foundation model anything to work
with. univariate=True (the production adapter's setting) hard-drops covariates
inside timesfm3.evaluator, so this pilot runs univariate=False instead --
that alone is a different code path from the arm actually in the study.

Bounded on purpose: a few dozen cached series, log-score only, no sandwich,
no strata. A real study (if this shows anything) is a separate piece of work.

    PYTHONPATH=src:benchmarks .venv-timesfm3/bin/python benchmarks/timesfm3_covariate_pilot.py
"""
from __future__ import annotations
import os
import sys
import random
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fred
import bench_core as bc
from skaters.api import laplace
from study import _scope_tag

N_SERIES = int(os.environ.get("PILOT_N", 30))
CTX = int(os.environ.get("PILOT_CTX", 128))
TEST = int(os.environ.get("PILOT_TEST", 40))
MIN_CHANGES = TEST + CTX + 50
DEVICE = os.environ.get("FM_DEVICE", "cpu")
COVARIATE = os.environ.get("PILOT_COVARIATE", "z")

# The same nine deciles TimesFM3's own quantile head emits and is scored on
# (see foundation_study.py's timesfm3_dists) -- "quantiles" mode feeds laplace's
# value at each of these as a separate covariate row, its complete predictive
# answer in the same basis TimesFM3 is being asked to produce, not a scalar
# summary of it.
DECILES = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def laplace_mean_stream(ch):
    """Causal one-step-ahead mean prediction of laplace(1) at every index:
    mu_hat[i] is the mean laplace predicted BEFORE seeing ch[i] (0.0 at i=0,
    no history yet, laplace itself has no prediction). Shape (1, len(ch))."""
    f = laplace(1); state = None; pend = None
    out = []
    for y in ch:
        out.append(pend[0].mean if pend is not None else 0.0)
        pend, state = f(y, state)
    return np.asarray([out], dtype=np.float32)


def laplace_z_stream(ch):
    """Causal one-step-ahead z-score of laplace(1) at every index: z[i] is the
    standardized PIT of ch[i] under the predictive laplace issued BEFORE
    seeing it (state["z"][0], the same calibration diagnostic laplace() always
    carries -- see skaters.api.laplace docstring). None at i=0 (not yet
    matured), filled with 0.0 (a neutral "no surprise" prior). Shape (1, len(ch))."""
    f = laplace(1); state = None
    out = []
    for y in ch:
        _, state = f(y, state)
        z = state["z"][0]
        out.append(z if z is not None and np.isfinite(z) else 0.0)
    return np.asarray([out], dtype=np.float32)


def laplace_z_multihorizon_stream(ch, horizons=(1, 2, 3, 5, 10)):
    """Causal z-score of laplace(k=max(horizons)) at each of `horizons`, one
    covariate row per horizon. state["z"][h-1] is already exactly this: the
    PIT (through the standard-normal quantile) of ch[i] under the h-step-ahead
    predictive issued h steps before it -- laplace's own multi-horizon
    calibration bookkeeping, not new plumbing. Undefined (not yet matured)
    entries fill with 0.0. Shape (len(horizons), len(ch))."""
    k = max(horizons)
    f = laplace(k); state = None
    rows = [[] for _ in horizons]
    for y in ch:
        _, state = f(y, state)
        for j, h in enumerate(horizons):
            z = state["z"][h - 1]
            rows[j].append(z if z is not None and np.isfinite(z) else 0.0)
    return np.asarray(rows, dtype=np.float32)


def laplace_quantile_streams(ch, qs=DECILES):
    """Causal one-step-ahead predictive quantiles of laplace(1) at every index,
    one covariate row per level in `qs` -- laplace's complete predictive
    answer, not a scalar summary of it. Row j, index i is laplace's q=qs[j]
    quantile of the predictive issued BEFORE seeing ch[i] (0.0 at i=0, no
    prediction yet). Shape (len(qs), len(ch))."""
    f = laplace(1); state = None; pend = None
    rows = [[] for _ in qs]
    for y in ch:
        for j, p in enumerate(qs):
            rows[j].append(pend[0].quantile(p) if pend is not None else 0.0)
        pend, state = f(y, state)
    return np.asarray(rows, dtype=np.float32)


def laplace_z_and_dist_stream(ch):
    """Causal z-score AND the exact laplace Dist that produced it, at every
    index: dists[i] is the predictive laplace issued BEFORE seeing ch[i] (None
    at i=0), and z[i] = Phi^-1(dists[i].cdf(ch[i])) -- the same object needed
    later to invert a z-space forecast back to raw units."""
    f = laplace(1); state = None; pend = None
    z = []; dists = []
    for y in ch:
        d = pend[0] if pend is not None else None
        pend, state = f(y, state)
        zv = state["z"][0]
        z.append(zv if zv is not None and np.isfinite(zv) else 0.0)
        dists.append(d)
    return np.asarray(z, dtype=np.float32), dists


def run_zcoord_pilot():
    """Does TimesFM3 forecasting laplace's own z-coordinate (context = past
    z-values, target = next z) beat it forecasting the raw change series?

    This is NOT the covariate pilot's mechanism (side-channel input, same raw
    target): here the TARGET itself changes. If laplace has calibrated a
    series into ~stationary N(0,1) surprises, TimesFM3 works in an already-
    normalized regime instead of the raw, non-stationary change series --
    a fundamentally different task, not just extra context. TimesFM3's
    z-quantile forecast is inverted back to raw units through the SAME
    laplace Dist that defined the z-transform at that step: since
    z = Phi^-1(F_laplace(y)) is monotone in y, y_hat(p) = F_laplace^-1(Phi(
    z_hat(p))) preserves the probability level p exactly.
    """
    from timesfm3 import TimesFM3Evaluator, ModelConfig
    from skaters.dist import Dist
    from bench_core import grid_dist
    Phi = Dist.gaussian(0.0, 1.0)
    model = TimesFM3Evaluator(ModelConfig(
        checkpoint_path="google/timesfm-3.0-pytorch", per_core_batch_size=32, device=DEVICE))

    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    random.Random(0).shuffle(ids)
    picked = []
    for sid in ids:
        lv = fred._load_levels(sid)
        ch = fred._to_changes(lv) if lv else []
        if len(ch) >= MIN_CHANGES and not _scope_tag(ch):
            picked.append((sid, ch[-(MIN_CHANGES + 200):]))
        if len(picked) >= N_SERIES:
            break
    print(f"[pilot] {len(picked)} series, CTX={CTX} TEST={TEST} device={DEVICE} "
          f"mode=zcoord", flush=True)

    levels = DECILES
    lp_base_tot = lp_cov_tot = lp_lap_tot = 0.0
    n_tot = 0
    per_series = []

    for sid, ch in picked:
        z, dists = laplace_z_and_dist_stream(ch)
        n = len(ch); start = n - TEST
        raw_ctx = [np.asarray(ch[t - CTX:t], dtype=np.float32) for t in range(start, n)]
        z_ctx = [z[t - CTX:t] for t in range(start, n)]
        targets = [ch[t] for t in range(start, n)]

        base_outs = list(model.predict_batch(
            raw_ctx, horizon=1, return_quantiles=True, use_symmetric_averaging=False,
            make_positive=False, univariate=True))
        z_outs = list(model.predict_batch(
            z_ctx, horizon=1, return_quantiles=True, use_symmetric_averaging=False,
            make_positive=False, univariate=True))

        f = laplace(1); state = None; pend = None; lap_dists = []
        for i, y in enumerate(ch):
            if pend is not None and i >= start:
                lap_dists.append(pend[0])
            pend, state = f(y, state)

        lp_base = lp_cov = lp_lap = 0.0
        for i, y in enumerate(targets):
            t = start + i
            qb = np.asarray(base_outs[i].quantiles, dtype=float)
            qb = qb[0] if qb.ndim == 3 else qb
            db = grid_dist(levels, qb[0] if qb.ndim == 2 else qb)

            qz = np.asarray(z_outs[i].quantiles, dtype=float)
            qz = qz[0] if qz.ndim == 3 else qz
            qz = qz[0] if qz.ndim == 2 else qz
            ld = dists[t]                       # laplace's Dist at this exact origin
            if ld is not None:
                y_q = [ld.quantile(min(max(Phi.cdf(zv), 1e-6), 1 - 1e-6)) for zv in qz]
                dc = grid_dist(levels, y_q)
            else:
                dc = db

            ab, _ = bc.score_dist(db, y) if db is not None else (-20.0, None)
            ac, _ = bc.score_dist(dc, y) if dc is not None else (-20.0, None)
            al, _ = bc.score_dist(lap_dists[i], y)
            lp_base += ab; lp_cov += ac; lp_lap += al

        m = len(targets)
        per_series.append((sid, lp_base / m, lp_cov / m, lp_lap / m))
        lp_base_tot += lp_base; lp_cov_tot += lp_cov; lp_lap_tot += lp_lap
        n_tot += m
        print(f"  {sid}: base={lp_base/m:+.3f} zcoord={lp_cov/m:+.3f} laplace={lp_lap/m:+.3f}",
              flush=True)

    print(f"\n[pilot] pooled mean logpdf over {n_tot} steps, {len(picked)} series:")
    print(f"  TimesFM3 (raw-value target):  {lp_base_tot/n_tot:+.4f}")
    print(f"  TimesFM3 (z-coordinate target): {lp_cov_tot/n_tot:+.4f}")
    print(f"  laplace:                        {lp_lap_tot/n_tot:+.4f}")
    deltas = [c - b for _, b, c, _ in per_series]
    wins = sum(1 for d in deltas if d > 0)
    print(f"  z-coordinate beats raw-value on {wins}/{len(deltas)} series, "
          f"median per-series delta {np.median(deltas):+.4f}")


def build_windows(ch, mu, start, n):
    """TEST context windows (each CTX long) ending just before each test step,
    for both the target and the laplace covariate rows, aligned identically.
    `mu` is (K, len(ch)) for K covariate rows."""
    ctx_windows = [np.asarray(ch[t - CTX:t], dtype=np.float32) for t in range(start, n)]
    cov_windows = [mu[:, t - CTX:t] for t in range(start, n)]
    targets = [ch[t] for t in range(start, n)]
    return ctx_windows, cov_windows, targets


def run_pilot():
    from timesfm3 import TimesFM3Evaluator, ModelConfig
    model = TimesFM3Evaluator(ModelConfig(
        checkpoint_path="google/timesfm-3.0-pytorch", per_core_batch_size=32, device=DEVICE))

    # A sorted-prefix scan clusters alphabetically (e.g. the "00XALC*" EU
    # indices are all short, near-constant, and all sort first) -- shuffle a
    # deterministic seed over the WHOLE cache first so the sample is a real
    # cross-section, not one corner of it.
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    random.Random(0).shuffle(ids)
    picked = []
    for sid in ids:
        lv = fred._load_levels(sid)
        ch = fred._to_changes(lv) if lv else []
        if len(ch) >= MIN_CHANGES and not _scope_tag(ch):
            picked.append((sid, ch[-(MIN_CHANGES + 200):]))
        if len(picked) >= N_SERIES:
            break
    print(f"[pilot] {len(picked)} series, CTX={CTX} TEST={TEST} device={DEVICE} "
          f"covariate={COVARIATE}", flush=True)

    lp_base_tot = lp_cov_tot = lp_lap_tot = 0.0
    n_tot = 0
    per_series = []
    levels = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    from bench_core import grid_dist  # quantile -> Dist, reused, not reinvented

    stream_fn = {"z": laplace_z_stream, "mean": laplace_mean_stream,
                 "quantiles": laplace_quantile_streams,
                 "z-horizons": laplace_z_multihorizon_stream}[COVARIATE]

    for sid, ch in picked:
        mu = stream_fn(ch)
        n = len(ch); start = n - TEST
        ctx_windows, cov_windows, targets = build_windows(ch, mu, start, n)

        base_outs = list(model.predict_batch(
            ctx_windows, horizon=1, return_quantiles=True, use_symmetric_averaging=False,
            make_positive=False, univariate=True))
        cov_outs = list(model.predict_batch(
            ctx_windows, horizon=1, return_quantiles=True, use_symmetric_averaging=False,
            make_positive=False, univariate=False,
            past_only_covariates=cov_windows))

        # plain laplace on the identical steps, for a sanity anchor
        f = laplace(1); state = None; pend = None; lap_dists = []
        for i, y in enumerate(ch):
            if pend is not None and i >= start:
                lap_dists.append(pend[0])
            pend, state = f(y, state)

        lp_base = lp_cov = lp_lap = 0.0
        for i, y in enumerate(targets):
            qb = np.asarray(base_outs[i].quantiles, dtype=float)
            qb = qb[0] if qb.ndim == 3 else qb
            db = grid_dist(levels, qb[0] if qb.ndim == 2 else qb)
            qc = np.asarray(cov_outs[i].quantiles, dtype=float)
            qc = qc[0] if qc.ndim == 3 else qc
            dc = grid_dist(levels, qc[0] if qc.ndim == 2 else qc)
            ab, _ = bc.score_dist(db, y) if db is not None else (-20.0, None)
            ac, _ = bc.score_dist(dc, y) if dc is not None else (-20.0, None)
            al, _ = bc.score_dist(lap_dists[i], y)
            lp_base += ab; lp_cov += ac; lp_lap += al

        m = len(targets)
        per_series.append((sid, lp_base / m, lp_cov / m, lp_lap / m))
        lp_base_tot += lp_base; lp_cov_tot += lp_cov; lp_lap_tot += lp_lap
        n_tot += m
        print(f"  {sid}: base={lp_base/m:+.3f} cov={lp_cov/m:+.3f} laplace={lp_lap/m:+.3f}",
              flush=True)

    print(f"\n[pilot] pooled mean logpdf over {n_tot} steps, {len(picked)} series:")
    print(f"  TimesFM3 (univariate, no covariate): {lp_base_tot/n_tot:+.4f}")
    print(f"  TimesFM3 (+ laplace-{COVARIATE} covariate): {lp_cov_tot/n_tot:+.4f}")
    print(f"  laplace:                             {lp_lap_tot/n_tot:+.4f}")
    deltas = [c - b for _, b, c, _ in per_series]
    wins = sum(1 for d in deltas if d > 0)
    print(f"  covariate beats base on {wins}/{len(deltas)} series, "
          f"median per-series delta {np.median(deltas):+.4f}")


if __name__ == "__main__":
    if COVARIATE == "zcoord":
        run_zcoord_pilot()
    else:
        run_pilot()
