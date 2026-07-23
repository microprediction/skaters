"""Zero-shot foundation-model study: laplace vs Chronos / TimesFM / Moirai /
Lag-Llama.

A *different protocol* from the rolling-refit study (study.py). Foundation models are pretrained and
used **zero-shot**: at each test step we feed a fixed-length context window of the
preceding one-step *changes* and ask for the next change --- no fitting, no
refit. All test windows for a series are batched into a single inference call,
which is what makes CPU evaluation tractable. Every model's predictive is turned
into the same `Dist` (samples -> Gaussian KDE; quantiles -> a smoothed mixture)
and scored on held-out log-likelihood and CRPS, exactly as in the main study.
`laplace` is re-scored on the identical series and window so the per-series
comparison is apples-to-apples.

Caveats reported honestly: (1) this is zero-shot with a fixed context window, not
the rolling-refit protocol of the eight-baseline study; (2) the models forecast
the *change* stream (the shared target), which is not the level series they were
chiefly trained on; (3) Chronos/TimesFM densities are reconstructed from
samples/quantiles. Run (needs the `skaters-fm` env + a FRED key):
  PYTHONPATH=src python benchmarks/foundation_study.py
"""
from __future__ import annotations
import os, sys, math, time, warnings
warnings.filterwarnings("ignore")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import csv
import numpy as np

import fred
from skaters.dist import Dist
from skaters.api import laplace

_HERE = os.path.dirname(os.path.abspath(__file__))
# One results file per run-tag, so models that need different envs (conflicting
# deps) write separate files that summarize() then merges.
FM_TAG = os.environ.get("FM_TAG", "main")
RESULTS = os.path.join(_HERE, f"results_foundation_{FM_TAG}.csv")

N_SERIES = int(os.environ.get("FM_N", 120))     # subset size (zero-shot CPU cost)
HIST = 1000
TEST = int(os.environ.get("FM_TEST", 150))      # rolling one-step test window
CTX = int(os.environ.get("FM_CTX", 256))        # context window length
NUM_SAMPLES = int(os.environ.get("FM_SAMPLES", 30))
DEVICE = os.environ.get("FM_DEVICE", "cpu")     # cpu | mps (Mac Studio) | cuda


# ---------------------------------------------------------------- data + scoring
def load_series():
    ids = sorted(f[:-4] for f in os.listdir(fred._CACHE) if f.endswith(".csv"))
    out = {}
    for sid in ids:
        lv = fred._load_levels(sid)
        if not lv:
            continue
        ch = fred._to_changes(lv)
        if len(ch) < HIST:
            continue
        out[sid] = ch[-HIST:]
        if len(out) >= N_SERIES:
            break
    return out


def score_dist(d, y):
    lp = d.logpdf(y)
    return (lp if math.isfinite(lp) else -20.0), d.crps(y)


def sample_dist(samples):
    """Gaussian-KDE Dist from predictive samples (Silverman bandwidth)."""
    s = np.asarray(samples, float)
    mu, sd = float(s.mean()), float(s.std())
    iqr = float(np.subtract(*np.percentile(s, [75, 25])))
    spread = min(sd, iqr / 1.349) if iqr > 0 else sd
    if spread <= 0:
        spread = abs(mu) * 1e-3 + 1e-9
    h = max(0.9 * spread * len(s) ** (-0.2), 1e-9)
    w = 1.0 / len(s)
    return Dist([(w, float(x), h) for x in s])


def quantile_dist(levels, qs):
    """Smoothed-mixture Dist from a set of predictive quantiles (levels ascending,
    qs the corresponding values). Each quantile point carries the probability mass
    of its surrounding interval; bandwidth is the local spacing."""
    levels = np.asarray(levels, float); qs = np.asarray(qs, float)
    order = np.argsort(levels); levels, qs = levels[order], qs[order]
    comps = []
    for i in range(len(qs)):
        lo = levels[i - 1] if i > 0 else 0.0
        hi = levels[i + 1] if i < len(qs) - 1 else 1.0
        w = max((hi - lo) / 2.0, 1e-6)
        if i == 0:
            sp = abs(qs[1] - qs[0])
        elif i == len(qs) - 1:
            sp = abs(qs[-1] - qs[-2])
        else:
            sp = abs(qs[i + 1] - qs[i - 1]) / 2.0
        comps.append((w, float(qs[i]), max(0.5 * sp, 1e-9)))
    return Dist(comps)


def score_steps(dists, y):
    """Mean logpdf/CRPS of a per-step list of Dists against the realized y."""
    lp = cr = 0.0
    for d, yt in zip(dists, y):
        a, b = score_dist(d, float(yt)); lp += a; cr += b
    n = len(dists)
    return lp / n, cr / n


def laplace_scores(ch):
    f = laplace(1); st = None; pend = None
    n = len(ch); start = n - TEST
    lp = cr = 0.0; m = 0
    for i, yv in enumerate(ch):
        if pend is not None and i >= start:
            a, b = score_dist(pend[0], yv); lp += a; cr += b; m += 1
        d, st = f(yv, st); pend = d
    return lp / m, cr / m


# ---------------------------------------------------------------- model adapters
# Each adapter loads its model once (module-level cache) and returns a list of
# TEST per-step Dists for the change-series `ch`, or None if unavailable.

def _ctx_batch(ch):
    """Tensor of the TEST context windows (each CTX long) ending just before each
    test step."""
    import torch
    n = len(ch); start = n - TEST
    return torch.stack([torch.tensor(ch[t - CTX:t], dtype=torch.float32)
                        for t in range(start, n)])


_chronos = None
def chronos_dists(ch, h=1):
    """Chronos-Bolt (quantile head) zero-shot. We use Bolt rather than the
    autoregressive T5 sampler: it is ~36x faster (a single forward pass) and does
    not stall, at the cost of being quantile-only -> its log-likelihood is a
    reconstruction (like TimesFM), so read its CRPS as the primary signal."""
    global _chronos
    try:
        import torch
        if _chronos is None:
            from chronos import BaseChronosPipeline
            _chronos = BaseChronosPipeline.from_pretrained(
                "amazon/chronos-bolt-small", device_map=DEVICE, torch_dtype=torch.float32)
        ctx = _ctx_batch(ch if h == 1 else ch[:len(ch) - (h - 1)])
        levels = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        q, _ = _chronos.predict_quantiles(inputs=ctx, prediction_length=h,
                                          quantile_levels=levels)
        q = q[:, h - 1, :].cpu().numpy()    # [B, n_levels] at horizon h
        return [quantile_dist(levels, q[i]) for i in range(len(q))]
    except Exception as e:                  # noqa: BLE001
        print(f"  chronos failed: {e}", flush=True); return None


_moirai = None
def moirai_dists(ch):
    global _moirai
    try:
        import torch
        from uni2ts.model.moirai import MoiraiForecast, MoiraiModule
        if _moirai is None:
            _moirai = MoiraiModule.from_pretrained("Salesforce/moirai-1.1-R-small")
        ctx = _ctx_batch(ch)                # [TEST, CTX]
        model = MoiraiForecast(
            module=_moirai, prediction_length=1, context_length=CTX,
            patch_size=8, num_samples=NUM_SAMPLES, target_dim=1,
            feat_dynamic_real_dim=0, past_feat_dynamic_real_dim=0).to(DEVICE)
        ctx = ctx.to(DEVICE)
        past_target = ctx.unsqueeze(-1)                       # [B, CTX, 1]
        past_observed = torch.ones_like(past_target, dtype=torch.bool)
        past_is_pad = torch.zeros(ctx.shape[0], CTX, dtype=torch.bool, device=DEVICE)
        fc = model(past_target=past_target, past_observed_target=past_observed,
                   past_is_pad=past_is_pad)                    # [B, num_samples, 1]
        s = fc[:, :, 0].cpu().numpy()
        return [sample_dist(s[i]) for i in range(len(s))]
    except Exception as e:                  # noqa: BLE001
        print(f"  moirai failed: {e}", flush=True); return None


_lagllama = None
def lagllama_dists(ch):
    """Lag-Llama via its gluonts predictor; returns sample paths per window."""
    global _lagllama
    try:
        import torch
        from gluonts.dataset.pandas import PandasDataset
        import pandas as pd
        if _lagllama is None:
            # The Lag-Llama checkpoint predates torch 2.6's weights_only=True
            # default; force full unpickling for this trusted file.
            _orig_load = torch.load
            torch.load = lambda *a, **k: _orig_load(*a, **{**k, "weights_only": False})
            from huggingface_hub import hf_hub_download
            from lag_llama.gluon.estimator import LagLlamaEstimator
            ckpt_path = hf_hub_download(repo_id="time-series-foundation-models/Lag-Llama",
                                        filename="lag-llama.ckpt")
            ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
            args = ckpt["hyper_parameters"]["model_kwargs"]
            est = LagLlamaEstimator(
                ckpt_path=ckpt_path, prediction_length=1, context_length=CTX,
                input_size=args["input_size"], n_layer=args["n_layer"],
                n_embd_per_head=args["n_embd_per_head"], n_head=args["n_head"],
                scaling=args["scaling"], time_feat=args["time_feat"],
                num_parallel_samples=NUM_SAMPLES, device=torch.device(DEVICE))
            _lagllama = est.create_predictor(est.create_transformation(),
                                             est.create_lightning_module())
        n = len(ch); start = n - TEST
        # one PandasDataset row per test window
        frames = {}
        for k, t in enumerate(range(start, n)):
            frames[str(k)] = pd.DataFrame(
                {"target": np.asarray(ch[t - CTX:t], dtype=np.float32)},
                index=pd.date_range("2000-01-01", periods=CTX, freq="D"))
        ds = PandasDataset(frames, target="target")
        fc = list(_lagllama.predict(ds, num_samples=NUM_SAMPLES))
        out = [None] * TEST
        for f in fc:
            k = int(f.item_id)
            out[k] = sample_dist(f.samples[:, 0])    # [num_samples, 1] -> step 0
        return out
    except Exception as e:                  # noqa: BLE001
        print(f"  lag-llama failed: {e}", flush=True); return None


_timesfm = None
def timesfm_dists(ch, h=1):
    """TimesFM 2.5 zero-shot; decile quantile head -> quantile_dist. For h>1 the
    context ends h steps before each target and the horizon-h forecast is scored."""
    global _timesfm
    try:
        import timesfm
        if _timesfm is None:
            M = timesfm.TimesFM_2p5_200M_torch
            m = M.from_pretrained(M.DEFAULT_REPO_ID)
            m.compile(timesfm.ForecastConfig(
                max_context=CTX, max_horizon=h, normalize_inputs=True,
                use_continuous_quantile_head=True, per_core_batch_size=64))
            _timesfm = m
        n = len(ch); start = n - TEST; sh = h - 1
        inputs = [np.asarray(ch[t - sh - CTX:t - sh], dtype=np.float32)
                  for t in range(start, n)]
        _, quant = _timesfm.forecast(horizon=h, inputs=inputs)   # [B, h, Q]
        Q = quant.shape[-1]
        # TimesFM emits deciles; a leading column is the mean when Q==10.
        if Q >= 10:
            qcols, levels = quant[:, h - 1, 1:10], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        else:
            qcols = quant[:, h - 1, :Q]
            levels = list(np.linspace(0.1, 0.9, Q))
        # NB forecast() pads `inputs` in place to per_core_batch_size but returns
        # exactly one row per real window; iterate over the returned rows.
        return [quantile_dist(levels, qcols[i]) for i in range(qcols.shape[0])]
    except Exception as e:                  # noqa: BLE001
        print(f"  timesfm failed: {e}", flush=True); return None


# ---------------------------------------------------------------- runner
_ALL_MODELS = [("Chronos", chronos_dists), ("Moirai", moirai_dists),
               ("Lag-Llama", lagllama_dists), ("TimesFM", timesfm_dists)]
_SEL = os.environ.get("FM_MODELS", "")      # comma list; empty = all
MODELS = [(n, f) for n, f in _ALL_MODELS if not _SEL or n in _SEL.split(",")]


def run():
    series = load_series()
    sids = list(series)
    print(f"loaded {len(sids)} series; TEST={TEST} CTX={CTX} samples={NUM_SAMPLES}",
          flush=True)
    with open(RESULTS, "w") as fh:
        w = csv.writer(fh); w.writerow(["series", "method", "logpdf", "crps", "n"])
        for j, sid in enumerate(sids):
            ch = series[sid]
            y = ch[len(ch) - TEST:]
            lp, cr = laplace_scores(ch)
            w.writerow([sid, "laplace", f"{lp:.6f}", f"{cr:.6f}", TEST])
            for name, fn in MODELS:
                t0 = time.time()
                dists = fn(ch)
                if dists is not None:
                    a, b = score_steps(dists, y)
                    w.writerow([sid, name, f"{a:.6f}", f"{b:.6f}", TEST])
            fh.flush()
            if (j + 1) % 5 == 0:
                print(f"  done {j+1}/{len(sids)} ({time.time()-t0:.1f}s last model)",
                      flush=True)
    summarize()


def summarize():
    import collections, glob
    by = collections.defaultdict(dict)
    for path in sorted(glob.glob(os.path.join(_HERE, "results_foundation_*.csv"))):
        for r in csv.DictReader(open(path)):
            by[r["series"]][r["method"]] = (float(r["logpdf"]), float(r["crps"]))

    def rfrac(sid):
        ch = fred._to_changes(fred._load_levels(sid) or [])[-TEST:]
        return sum(1 for i in range(1, len(ch)) if ch[i] == ch[i - 1]) / max(len(ch) - 1, 1)
    cont = {s for s in by if rfrac(s) < 0.05}
    methods = ["Chronos", "TimesFM", "Moirai", "Lag-Llama"]
    methods = [m for m in methods if any(m in d for d in by.values())]
    print(f"\n=== Foundation study: {len(by)} series ({len(cont)} continuous), "
          f"zero-shot 1-step ===")
    print("per-series win-rate, laplace vs each (LL higher; CRPS lower):")
    print(f"  {'model':16s}{'LL all/cont':>14s}{'CRPS all/cont':>16s}{'n':>6s}")

    def wr(method, subset, idx, lower=False):
        sub = [by[s] for s in subset if method in by[s] and "laplace" in by[s]]
        if not sub:
            return float("nan")
        if lower:
            w = sum(1 for d in sub if d["laplace"][idx] < d[method][idx])
        else:
            w = sum(1 for d in sub if d["laplace"][idx] > d[method][idx])
        return 100.0 * w / len(sub)

    alls = set(by)
    for m in methods:
        n = sum(1 for s in by if m in by[s])
        ll = f"{wr(m, alls, 0):.0f}/{wr(m, cont, 0):.0f}%"
        cp = f"{wr(m, alls, 1, lower=True):.0f}/{wr(m, cont, 1, lower=True):.0f}%"
        print(f"  {m:16s}{ll:>14s}{cp:>16s}{n:>6d}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        summarize()
    else:
        run()
