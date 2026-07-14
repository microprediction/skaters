"""PYMC-Forecast sandwich study: a Bayesian challenger in and out of
laplace coordinates, plus the first cross-series pooling arm.

Statement: benchmarks/preregistrations/2026-07-14-pymc-forecast-sandwich.md
(committed before this ran). Five log-likelihoods per series, identical
per-point flooring at -20, strictly causal throughout:

    laplace  plain laplace(1), the standing opponent
    raw      pymc-forecast Student-t regression on 8 lagged raw changes,
             ADVI, refit each 10-step block on the trailing 248 lag-rows,
             block-standardized with the exact affine adjustment -log s
    sand     the identical design on the parade z stream, mapped back
             through the exact Jacobian
             log f_y(y) = log f_z(z) + log f_lap(y) - log phi(z)
    solo     the same z-space model fit once per series on all pre-test z
             (no refits), test-window predictions from live lag rows
    hier     the same z-space model fit once JOINTLY across every series
             in the universe with hierarchical (partially pooled) priors;
             per-series posteriors scored exactly like solo

hier vs solo isolates pooling: same window, same freeze, same model form,
only the priors differ. Every predictive density is computed exactly as
the posterior-draw mixture of Student-t densities, the object the
package's forecast sampler draws from (verified against fc.forecast()
in the smoke log).

Usage (env at ~/.venvs/skaters-pymc: pymc-forecast 0.0.1, arviz<1.0):
    PYTHONPATH=src ~/.venvs/skaters-pymc/bin/python \
        benchmarks/pymc_forecast_sandwich_study.py
Env knobs: PF_SMOKE=<n> series, PF_STEPS=<n> ADVI steps (plumbing tests),
PF_ARMS=comma list to restrict arms.
"""
from __future__ import annotations
import csv
import math
import os
import sys
import time
import warnings
import zlib

warnings.filterwarnings("ignore")

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, _HERE)

from tabfm_wide_study import load_universe, _load_ch, lag_rows, TEST  # noqa: E402
from skaters import laplace  # noqa: E402
from skaters.tails import _phi_inv  # noqa: E402

OUT = os.path.join(_HERE, "results_pymc_forecast_sandwich.csv")
FLOOR = -20.0
LAGS = 8
CTX = 256                  # block training context, mirrors the TabFM studies
STRIDE = 10
M = 500                    # posterior draws per fit
NUM_STEPS = int(os.environ.get("PF_STEPS", 5000))
HIER_STEPS = 4 * NUM_STEPS
SEED = 20260714
N_SMOKE = int(os.environ.get("PF_SMOKE", 0))
_EPS = 1e-12
_LOG_SQRT2PI = 0.5 * math.log(2.0 * math.pi)

ARMS = ["raw", "sand", "solo", "hier"]
_sel = os.environ.get("PF_ARMS", "")
if _sel:
    ARMS = [a for a in ARMS if a in set(_sel.split(","))]


def _seed(*parts):
    return zlib.crc32("|".join(str(p) for p in parts).encode()) % (2**31 - 1)


# --------------------------------------------------------------- laplace pass
def _lap_pass(series):
    """Per-step 1-step-ahead laplace predictive for each y_t (None at t=0)."""
    f = laplace(1)
    st = None
    pend = None
    dists = []
    for y in series:
        dists.append(pend)
        d, st = f(y, st)
        pend = d[0]
    return dists


def series_pass(ch):
    """One laplace pass: floored test-window LL, raw test-window logpdf
    (Jacobian piece), and the full z stream (z[0] is a 0.0 placeholder)."""
    n = len(ch)
    lp = _lap_pass(ch)
    ll_lap, lap_logf, zs = [], [], [0.0]
    for t in range(1, n):
        d = lp[t]
        u = min(max(d.cdf(ch[t]), _EPS), 1.0 - _EPS)
        zs.append(_phi_inv(u))
        if t >= n - TEST:
            raw = d.logpdf(ch[t])
            ll_lap.append(max(raw, FLOOR) if math.isfinite(raw) else FLOOR)
            lap_logf.append(raw)
    return float(np.mean(ll_lap)), np.array(lap_logf), np.array(zs)


# --------------------------------------------------------------- pymc pieces
def _model_zreg(h, covariates):
    """Student-t regression on lag covariates; priors centred at 'no
    structure, unit scale' (exactly right in z coordinates by construction)."""
    import pymc as pm
    import pytensor.tensor as pt
    from pymc_forecast import predict
    Xf = covariates.transpose("time", "lag").values
    alpha = pm.Normal("alpha", 0.0, 0.2)
    beta = pm.Normal("beta", 0.0, 0.2, dims=("lag",))
    sigma = pm.LogNormal("sigma", 0.0, 0.5)
    nu = pm.Gamma("nu", 2.0, 0.1)
    predict(h, lambda name, m, dims, obs: pm.StudentT(
        name, nu=nu, mu=m, sigma=sigma, dims=dims, observed=obs),
        alpha + pt.dot(Xf, beta))


def _model_hier(h, covariates):
    """The same regression with non-centred hierarchical priors across
    series: per-series alpha, beta, sigma partially pooled, shared nu."""
    import pymc as pm
    import pytensor.tensor as pt
    from pymc_forecast import predict
    Xf = covariates.transpose("time", "series", "lag").values
    mu_a = pm.Normal("mu_a", 0.0, 0.1)
    tau_a = pm.HalfNormal("tau_a", 0.1)
    ea = pm.Normal("ea", 0.0, 1.0, dims=("series",))
    alpha = pm.Deterministic("alpha", mu_a + tau_a * ea, dims=("series",))
    mu_b = pm.Normal("mu_b", 0.0, 0.1, dims=("lag",))
    tau_b = pm.HalfNormal("tau_b", 0.1, dims=("lag",))
    eb = pm.Normal("eb", 0.0, 1.0, dims=("series", "lag"))
    beta = pm.Deterministic(
        "beta", mu_b[None, :] + tau_b[None, :] * eb, dims=("series", "lag"))
    m_s = pm.Normal("m_s", 0.0, 0.2)
    t_s = pm.HalfNormal("t_s", 0.3)
    es = pm.Normal("es", 0.0, 1.0, dims=("series",))
    sigma = pm.Deterministic("sigma", pt.exp(m_s + t_s * es), dims=("series",))
    nu = pm.Gamma("nu", 2.0, 0.1)
    mu = alpha[None, :] + pt.sum(Xf * beta[None, :, :], axis=-1)
    predict(h, lambda name, m, dims, obs: pm.StudentT(
        name, nu=nu, mu=m, sigma=sigma[None, :], dims=dims, observed=obs), mu)


def _fit_zreg(ytr, Xtr, seed):
    """One pymc-forecast ADVI fit; returns M posterior draws of
    (alpha, beta, sigma, nu). One retry with a shifted seed."""
    import pandas as pd
    import xarray as xr
    from pymc_forecast import Forecaster
    t = pd.date_range("2000-01-01", periods=len(ytr), freq="D")
    train = xr.DataArray(np.asarray(ytr, float), dims=("time",),
                         coords={"time": t})
    cov = xr.DataArray(np.asarray(Xtr, float), dims=("time", "lag"),
                       coords={"time": t, "lag": np.arange(LAGS)})
    for attempt in (0, 7):
        try:
            fc = Forecaster(_model_zreg, train, covariates=cov,
                            num_steps=NUM_STEPS, random_seed=seed + attempt)
            post = fc.draw_posterior(M, random_seed=seed + attempt + 1)
            a = post["alpha"].values.ravel()
            b = post["beta"].values.reshape(-1, LAGS)
            s = post["sigma"].values.ravel()
            v = post["nu"].values.ravel()
            if np.all(np.isfinite(a)) and np.all(np.isfinite(b)) \
                    and np.all(np.isfinite(s)) and np.all(np.isfinite(v)):
                return a, b, s, v
        except Exception:
            if attempt:
                raise
    raise RuntimeError("non-finite posterior after retry")


def _mix_logpdf(params, Xte, yte):
    """Exact predictive log-density: log mean over posterior draws of the
    Student-t observation density."""
    from scipy import stats
    from scipy.special import logsumexp
    a, b, s, v = params
    mu = a[None, :] + np.asarray(Xte, float) @ b.T          # (steps, draws)
    lp = stats.t.logpdf(np.asarray(yte, float)[:, None],
                        df=v[None, :], loc=mu, scale=s[None, :])
    return logsumexp(lp, axis=1) - math.log(lp.shape[1])


def _floored_mean(lp):
    lp = np.where(np.isfinite(lp), lp, FLOOR)
    return float(np.mean(np.maximum(lp, FLOOR)))


def _blocks(n):
    for t0 in range(n - TEST, n, STRIDE):
        yield t0, min(t0 + STRIDE, n)


def _atom_logpdf(y, v):
    """Fallback for a constant training window: the standing 1e-9 atom."""
    sd = 1e-9
    return -0.5 * ((np.asarray(y) - v) / sd) ** 2 - math.log(sd) - _LOG_SQRT2PI


def raw_arm(sid, ch):
    """Blockwise refit on raw changes, block-standardized; exact affine
    adjustment -log s takes each block's density back to y units."""
    n = len(ch)
    out = []
    for bi, (lo, hi) in enumerate(_blocks(n)):
        Xtr, ytr = lag_rows(ch, lo - CTX + LAGS, lo, LAGS)
        Xte, yte = lag_rows(ch, lo, hi, LAGS)
        m0, s0 = float(np.mean(ytr)), float(np.std(ytr))
        if s0 <= 0.0:
            out.extend(_atom_logpdf(yte, m0))
            continue
        params = _fit_zreg((ytr - m0) / s0, (Xtr - m0) / s0,
                           _seed(SEED, sid, "raw", bi))
        lp = _mix_logpdf(params, (Xte - m0) / s0, (yte - m0) / s0)
        out.extend(lp - math.log(s0))
    return _floored_mean(np.array(out))


def sand_arm(sid, zs, lap_logf):
    """The identical blockwise design on the parade z stream, mapped back
    through the exact Jacobian."""
    n = len(zs)
    lz = []
    for bi, (lo, hi) in enumerate(_blocks(n)):
        Xtr, ytr = lag_rows(list(zs), lo - CTX + LAGS, lo, LAGS)
        Xte, zte = lag_rows(list(zs), lo, hi, LAGS)
        params = _fit_zreg(ytr, Xtr, _seed(SEED, sid, "sand", bi))
        lz.extend(_mix_logpdf(params, Xte, zte))
    return _jacobian_back(np.array(lz), zs[n - TEST:], lap_logf)


def solo_arm(sid, zs, lap_logf):
    """One pre-test fit per series, frozen through the test window; the
    no-pooling control for hier."""
    n = len(zs)
    Xtr, ytr = lag_rows(list(zs), LAGS + 1, n - TEST, LAGS)
    params = _fit_zreg(ytr, Xtr, _seed(SEED, sid, "solo"))
    Xte, zte = lag_rows(list(zs), n - TEST, n, LAGS)
    lz = _mix_logpdf(params, Xte, zte)
    return _jacobian_back(lz, zs[n - TEST:], lap_logf)


def _jacobian_back(lz, z_test, lap_logf):
    lphi = -0.5 * z_test**2 - _LOG_SQRT2PI
    return _floored_mean(lz + lap_logf - lphi)


def hier_arm(streams):
    """One joint hierarchical fit on every series' pre-test z; returns
    {sid: test-window LL}. streams: {sid: (zs, lap_logf)}."""
    import pandas as pd
    import xarray as xr
    from pymc_forecast import Forecaster
    sids = sorted(streams)
    n = len(next(iter(streams.values()))[0])
    lo, hi = LAGS + 1, n - TEST
    Z = np.stack([streams[s][0] for s in sids], axis=1)      # (n, S)
    ytr = Z[lo:hi]                                           # (T, S)
    # lag columns in ascending time order, matching lag_rows at scoring time
    Xtr = np.stack([Z[lo - LAGS + c:hi - LAGS + c] for c in range(LAGS)],
                   axis=2)
    t = pd.date_range("2000-01-01", periods=hi - lo, freq="D")
    train = xr.DataArray(ytr, dims=("time", "series"),
                         coords={"time": t, "series": sids})
    cov = xr.DataArray(Xtr, dims=("time", "series", "lag"),
                       coords={"time": t, "series": sids,
                               "lag": np.arange(LAGS)})
    fc = Forecaster(_model_hier, train, covariates=cov,
                    num_steps=HIER_STEPS, random_seed=_seed(SEED, "hier"))
    post = fc.draw_posterior(M, random_seed=_seed(SEED, "hier", "draw"))
    S = len(sids)
    a = post["alpha"].values.reshape(-1, S)
    b = post["beta"].values.reshape(-1, S, LAGS)
    s = post["sigma"].values.reshape(-1, S)
    v = post["nu"].values.ravel()
    out = {}
    for i, sid in enumerate(sids):
        zs, lap_logf = streams[sid]
        Xte, zte = lag_rows(list(zs), n - TEST, n, LAGS)
        lz = _mix_logpdf((a[:, i], b[:, i, :], s[:, i], v), Xte, zte)
        out[sid] = _jacobian_back(lz, zs[n - TEST:], lap_logf)
    return out


# --------------------------------------------------------------- driver
def _done_pairs():
    if not os.path.exists(OUT):
        return set()
    return {(r["series"], r["method"]) for r in csv.DictReader(open(OUT))}


def _open_results():
    mode = "a" if os.path.exists(OUT) else "w"
    fh = open(OUT, mode, newline="")
    w = csv.writer(fh)
    if mode == "w":
        w.writerow(["series", "method", "logpdf", "n", "stratum"])
    return fh, w


def run():
    universe = load_universe()
    if N_SMOKE:
        universe = universe[:N_SMOKE]
    print(f"pymc-forecast sandwich study: {len(universe)} series, arms "
          f"{ARMS}, LAGS={LAGS}, CTX={CTX}, STRIDE={STRIDE}, M={M}, "
          f"NUM_STEPS={NUM_STEPS}, TEST={TEST}", flush=True)
    done = _done_pairs()
    fh, w = _open_results()
    streams = {}
    per_series = [a for a in ARMS if a != "hier"]
    with fh:
        for j, (sid, stratum) in enumerate(universe):
            need = [a for a in per_series if (sid, a) not in done]
            need_lap = (sid, "laplace") not in done
            need_hier = "hier" in ARMS and (sid, "hier") not in done
            if not need and not need_lap and not need_hier:
                continue
            t0 = time.time()
            try:
                ch = _load_ch(sid)
                ll_lap, lap_logf, zs = series_pass(ch)
                if need_hier:
                    streams[sid] = (zs, lap_logf)
                if need_lap:
                    w.writerow([sid, "laplace", f"{ll_lap:.6f}", TEST, stratum])
                vals = {}
                for a in need:
                    if a == "raw":
                        vals[a] = raw_arm(sid, ch)
                    elif a == "sand":
                        vals[a] = sand_arm(sid, zs, lap_logf)
                    elif a == "solo":
                        vals[a] = solo_arm(sid, zs, lap_logf)
                    w.writerow([sid, a, f"{vals[a]:.6f}", TEST, stratum])
            except Exception as e:
                print(f"  FAIL {sid}: {e!r}", flush=True)
                continue
            fh.flush()
            os.fsync(fh.fileno())
            msg = " ".join(f"{a}={vals[a]:+.3f}" for a in vals)
            print(f"  pf {j + 1}/{len(universe)} {sid} [{stratum}] "
                  f"lap={ll_lap:+.3f} {msg} ({time.time() - t0:.0f}s)",
                  flush=True)
        if "hier" in ARMS:
            todo = [sid for sid, _ in universe if (sid, "hier") not in done]
            if todo:
                strat = dict(universe)
                # the joint fit always spans the FULL universe (restarts
                # included), so the pooled posterior never depends on how
                # the run was interrupted; only todo rows are written
                for sid, _ in universe:
                    if sid not in streams:
                        ll_lap, lap_logf, zs = series_pass(_load_ch(sid))
                        streams[sid] = (zs, lap_logf)
                t0 = time.time()
                print(f"  hier: joint fit over {len(streams)} series, "
                      f"{HIER_STEPS} steps", flush=True)
                lls = hier_arm(streams)
                for sid in todo:
                    w.writerow([sid, "hier", f"{lls[sid]:.6f}", TEST,
                                strat[sid]])
                fh.flush()
                print(f"  hier done ({time.time() - t0:.0f}s)", flush=True)
    summarize()


def summarize():
    if not os.path.exists(OUT):
        print("no results yet")
        return
    by, strat = {}, {}
    for r in csv.DictReader(open(OUT)):
        by.setdefault(r["series"], {})[r["method"]] = float(r["logpdf"])
        strat[r["series"]] = r["stratum"]
    contrasts = [("laplace", "raw"), ("laplace", "sand"), ("laplace", "solo"),
                 ("laplace", "hier"), ("sand", "raw"), ("hier", "solo")]
    print(f"\n=== pymc-forecast sandwich study: {len(by)} series scored ===")
    print(f"{'contrast':16s}{'split':22s}{'n':>5s}{'first wins':>12s}"
          f"{'med gap':>10s}")
    for hi_arm, lo_arm in contrasts:
        pairs = {s: d for s, d in by.items() if hi_arm in d and lo_arm in d}
        groups = {"ALL": set(pairs)}
        for s in pairs:
            groups.setdefault(strat[s], set()).add(s)
        for g in ["ALL"] + sorted(k for k in groups if k != "ALL"):
            sub = [pairs[s] for s in groups[g]]
            if not sub:
                continue
            wins = 100 * sum(1 for d in sub if d[hi_arm] > d[lo_arm]) / len(sub)
            gap = float(np.median([d[hi_arm] - d[lo_arm] for d in sub]))
            print(f"{hi_arm + '>' + lo_arm:16s}{g:22s}{len(sub):5d}"
                  f"{wins:11.0f}%{gap:+10.3f}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        summarize()
    else:
        run()
