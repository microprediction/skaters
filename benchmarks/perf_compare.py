"""Cost comparison: laplace against the foundation models, and the site page.

Accuracy studies live in the results store; this is the RUNTIME axis they do not
record. A distributional forecaster is only interesting at a stated cost, so the
numbers here are meant to be published alongside the accuracy tables rather than
quoted from memory.

Two regimes are reported, because they disagree and a single number hides the
argument:

  COLD  one forecast for a series never seen before, given L history points.
        This is the benchmark protocol. Foundation models BATCH here and that is
        decisive: chronos falls ~10x per series from batch 1 to batch 64, so
        quoting unbatched inference flatters laplace. laplace has to consume the
        L history points to warm up, so it is at its WORST in this regime.

  WARM  one new observation arrives on a series already being tracked; emit an
        updated forecast. laplace is ONLINE: one state update, independent of
        history length. A foundation model carries no state, so it must re-run
        the whole forward pass over a shifted window. This is where the gap is
        large, and it is the regime a live deployment actually runs in.

Both the Rust core (skaters_fast) and the pure-Python reference are timed, since
they differ by ~18x and a published ratio has to say which one it means.

    PYTHONPATH=src:benchmarks .venv-gifteval/bin/python benchmarks/perf_compare.py
    ... writes benchmarks/perf_results.json and docs/performance.html
"""
from __future__ import annotations
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import json
import logging
import platform
import statistics as st
import subprocess
import time
import warnings

import numpy as np

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)
import torch                                                    # noqa: E402

THREADS = int(os.environ.get("TORCH_THREADS", "1"))
torch.set_num_threads(THREADS)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = int(os.environ.get("PERF_L", "256"))
H = int(os.environ.get("PERF_H", "12"))
NSER = int(os.environ.get("PERF_N", "64"))
LEV = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
BATCHES = (1, 16, 64)

_rng = np.random.default_rng(0)
CTX = [np.cumsum(_rng.standard_normal(L)).astype(np.float32) for _ in range(NSER)]


def med(fn, reps=3):
    return st.median([(lambda t0: (fn(), time.perf_counter() - t0)[1])(time.perf_counter())
                      for _ in range(reps)])


def stamp():
    ver = "unknown"
    with open(os.path.join(ROOT, "pyproject.toml")) as fh:
        for line in fh:
            if line.startswith("version = "):
                ver = line.split('"')[1]
                break
    try:
        sha = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:                                            # noqa: BLE001
        sha = "nogit"
    return {"version": ver, "commit": sha, "python": platform.python_version(),
            "machine": f"{platform.system()} {platform.machine()}",
            "torch_threads": THREADS, "context": L, "horizon": H, "series": NSER,
            "date": time.strftime("%Y-%m-%d")}


def measure():
    rows = []

    def add(model, regime, ms, note):
        rows.append({"model": model, "regime": regime, "ms": ms, "note": note})

    import skaters_fast
    from skaters.api import laplace as py_laplace

    for k in (1, H):
        def cold(k=k):
            for c in CTX:
                g = skaters_fast.laplace(k)
                for y in c:
                    g.step(float(y))
        add(f"laplace (Rust) k={k}", "cold", med(cold) / NSER * 1000, f"replays {L} points")
        f = skaters_fast.laplace(k)
        for y in CTX[0]:
            f.step(float(y))

        def warm(f=f):
            for _ in range(500):
                f.step(1.0)
        add(f"laplace (Rust) k={k}", "warm", med(warm) / 500 * 1000, "one online update")

    def cold_py():
        for c in CTX[:8]:
            s = None
            g = py_laplace(1)
            for y in c:
                _, s = g(float(y), s)
    add("laplace (Python) k=1", "cold", med(cold_py) / 8 * 1000, f"replays {L} points")

    s = None
    g = py_laplace(1)
    for y in CTX[0]:
        _, s = g(float(y), s)

    def warm_py(g=g, s=s):
        st_ = s
        for _ in range(300):
            _, st_ = g(1.0, st_)
    add("laplace (Python) k=1", "warm", med(warm_py) / 300 * 1000, "one online update")

    def fm(name, call, params):
        try:
            call(CTX[:2])
        except Exception as e:                                   # noqa: BLE001
            add(name, "cold", float("nan"),
                f"unavailable: {type(e).__name__}: {str(e)[:70]}")
            return
        for bs in BATCHES:
            def run(bs=bs):
                for i in range(0, NSER, bs):
                    call(CTX[i:i + bs])
            add(name, f"cold b={bs}", med(run) / NSER * 1000, f"{params}, batched")
        add(name, "warm", med(lambda: call(CTX[:1]), reps=5) * 1000,
            "stateless: full re-forward")

    try:
        from chronos import BaseChronosPipeline
        pipe = BaseChronosPipeline.from_pretrained("amazon/chronos-bolt-small",
                                                   device_map="cpu",
                                                   torch_dtype=torch.float32)

        def c_chronos(cs):
            with torch.no_grad():
                pipe.predict_quantiles(inputs=[torch.tensor(c) for c in cs],
                                       prediction_length=H, quantile_levels=LEV)
        fm("Chronos-Bolt-small", c_chronos, "48M params")
    except Exception as e:                                       # noqa: BLE001
        add("Chronos-Bolt-small", "cold", float("nan"), f"load failed: {type(e).__name__}")

    try:
        from tirex import load_model
        tx = load_model("NX-AI/TiRex", device="cpu", backend="torch")

        def c_tirex(cs):
            tx.forecast(context=torch.tensor(np.stack(cs)), prediction_length=H,
                        output_type="numpy")
        fm("TiRex", c_tirex, "35M params, xLSTM")
    except Exception as e:                                       # noqa: BLE001
        add("TiRex", "cold", float("nan"), f"load failed: {type(e).__name__}")

    try:
        from transformers import AutoModelForCausalLM
        sd = AutoModelForCausalLM.from_pretrained("thuml/sundial-base-128m",
                                                  trust_remote_code=True).eval()

        def c_sundial(cs):
            with torch.no_grad():
                sd.generate(torch.tensor(np.stack(cs), dtype=torch.float32),
                            num_samples=30, max_new_tokens=H)
        fm("Sundial-base-128m", c_sundial, "128M params, 30 sample paths")
    except Exception as e:                                       # noqa: BLE001
        add("Sundial-base-128m", "cold", float("nan"), f"load failed: {type(e).__name__}")

    try:
        # Convention copied from foundation_study.timesfm_dists: the 2.5 torch
        # class plus an explicit compile(), not the older TimesFm(hparams=...)
        # constructor, which does not exist in this version.
        import timesfm as _tfm
        M = _tfm.TimesFM_2p5_200M_torch
        tfm = M.from_pretrained(M.DEFAULT_REPO_ID)
        tfm.compile(_tfm.ForecastConfig(max_context=L, max_horizon=H,
                                        normalize_inputs=True,
                                        use_continuous_quantile_head=True,
                                        per_core_batch_size=64))

        def c_timesfm(cs):
            tfm.forecast(horizon=H, inputs=[c.astype(np.float32) for c in cs])
        fm("TimesFM-2.5-200M", c_timesfm, "200M params")
    except Exception as e:                                       # noqa: BLE001
        add("TimesFM-2.5-200M", "cold", float("nan"), f"load failed: {type(e).__name__}")

    # ---- classical models that REFIT. This is the honest upper end of the cost
    # range and the sharpest contrast to an online update: a refitting model pays
    # its whole fit again for every new observation, so its warm cost IS its cold
    # cost. Batching does not exist for them, hence one column.
    try:
        from statsforecast.models import AutoARIMA
        def one_arima(c):
            m = AutoARIMA(season_length=1)
            m.fit(np.asarray(c, dtype=np.float64))
            m.predict(h=H)
        one_arima(CTX[0][:128])                                  # warm up numba/JIT
        t = med(lambda: one_arima(CTX[0]), reps=3) * 1000
        add("AutoARIMA (refit)", "cold", t, f"fit on {L} points")
        add("AutoARIMA (refit)", "warm", t, "refits from scratch every step")
    except Exception as e:                                       # noqa: BLE001
        add("AutoARIMA (refit)", "cold", float("nan"), f"unavailable: {type(e).__name__}")

    try:
        from statsforecast.models import AutoETS
        def one_ets(c):
            m = AutoETS(season_length=1)
            m.fit(np.asarray(c, dtype=np.float64))
            m.predict(h=H)
        one_ets(CTX[0][:128])
        t = med(lambda: one_ets(CTX[0]), reps=3) * 1000
        add("AutoETS (refit)", "cold", t, f"fit on {L} points")
        add("AutoETS (refit)", "warm", t, "refits from scratch every step")
    except Exception as e:                                       # noqa: BLE001
        add("AutoETS (refit)", "cold", float("nan"), f"unavailable: {type(e).__name__}")

    try:
        import pandas as pd
        from prophet import Prophet
        logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
        def one_prophet(c):
            df = pd.DataFrame({"ds": pd.date_range("2000-01-01", periods=len(c), freq="D"),
                               "y": np.asarray(c, dtype=float)})
            m = Prophet(uncertainty_samples=0)
            m.fit(df)
            m.predict(m.make_future_dataframe(periods=H, freq="D").iloc[-H:])
        one_prophet(CTX[0][:64])
        t = med(lambda: one_prophet(CTX[0]), reps=2) * 1000
        add("Prophet (refit)", "cold", t, f"fit on {L} points")
        add("Prophet (refit)", "warm", t, "refits from scratch every step")
    except Exception as e:                                       # noqa: BLE001
        add("Prophet (refit)", "cold", float("nan"), f"unavailable: {type(e).__name__}")

    return rows


def render(rows, meta):
    import sys
    sys.path.insert(0, os.path.join(ROOT, "docs"))
    from sweep_nav import CANONICAL                              # one nav source of truth

    warm = {r["model"]: r["ms"] for r in rows if r["regime"] == "warm"}
    base = warm.get("laplace (Rust) k=1")
    best_cold = {}
    for r in rows:
        if r["regime"].startswith("cold"):
            m = r["model"]
            if r["ms"] == r["ms"] and (m not in best_cold or r["ms"] < best_cold[m][0]):
                best_cold[m] = (r["ms"], r["regime"])

    def tr(r):
        ms = "n/a" if r["ms"] != r["ms"] else f"{r['ms']:.4f}"
        return (f"      <tr><td>{r['model']}</td><td>{r['regime']}</td>"
                f"<td class=num>{ms}</td><td class=note>{r['note']}</td></tr>")

    ratio_rows = "\n".join(
        f"      <tr><td>{m}</td><td class=num>{v:.4f}</td>"
        f"<td class=num>{v / base:,.0f}&times;</td></tr>"
        for m, v in sorted(warm.items(), key=lambda kv: kv[1]) if v == v and m != "laplace (Rust) k=1")
    cold_rows = "\n".join(
        f"      <tr><td>{m}</td><td class=num>{v[0]:.4f}</td><td class=note>{v[1]}</td></tr>"
        for m, v in sorted(best_cold.items(), key=lambda kv: kv[1][0]))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>skaters &mdash; performance</title>
  <meta name="description" content="Measured cost of laplace against foundation models, in both the batch-benchmark regime and the streaming regime a deployment actually runs in." />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="skaters" />
  <meta property="og:title" content="skaters &mdash; performance" />
  <meta property="og:description" content="Measured cost of laplace against foundation models, batch and streaming." />
  <meta property="og:url" content="https://skaters.microprediction.org/performance.html" />
  <meta name="twitter:card" content="summary" />
  <link rel="stylesheet" href="./academic.css" />
  <style>
    .lede {{ color: #555; margin: 0 0 28px; font-size: 1.05em; }}
    table.perf {{ border-collapse: collapse; margin: 0 0 26px; width: 100%; }}
    table.perf th, table.perf td {{ border-bottom: 1px solid #e3e3e3; padding: 6px 10px;
      text-align: left; font-size: 0.95em; }}
    table.perf th {{ border-bottom: 2px solid #bbb; font-weight: 600; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    td.note {{ color: #777; font-size: 0.88em; }}
    .caveats li {{ margin-bottom: 7px; }}
    .stamp {{ color: #888; font-size: 0.88em; font-style: italic; }}
  </style>
</head>
<body>
{CANONICAL}

  <main>
    <h1>Performance</h1>
    <p class="lede">What a forecast costs. Accuracy comparisons live on the
      <a href="/benchmarks.html">benchmarks page</a>; this is the runtime axis, measured
      on one machine with every model given the same core budget. There are two regimes
      and they disagree, so both are reported.</p>

    <h2>Streaming: one new observation arrives</h2>
    <p><code>laplace</code> is online. A new observation costs a single state update
      whose cost does not depend on how much history preceded it. A foundation model
      carries no state, so it re-runs its whole forward pass over a shifted window
      every time. This is the regime a live deployment runs in.</p>
    <table class="perf">
      <tr><th>model</th><th>ms per observation</th><th>vs laplace (Rust) k=1</th></tr>
{ratio_rows}
    </table>

    <h2>Batch: one forecast for a series never seen before</h2>
    <p>This is the benchmark protocol, and it is <em>laplace at its worst</em>: it must
      consume the whole history to warm up, while a foundation model amortises a batched
      forward pass across many series. Best batch size shown per model.</p>
    <table class="perf">
      <tr><th>model</th><th>ms per series</th><th>regime</th></tr>
{cold_rows}
    </table>

    <h2>Every measurement</h2>
    <table class="perf">
      <tr><th>model</th><th>regime</th><th>ms</th><th>note</th></tr>
{chr(10).join(tr(r) for r in rows)}
    </table>

    <h2>Caveats</h2>
    <ul class="caveats">
      <li><strong>CPU only, {meta['torch_threads']} torch thread.</strong> A GPU changes the
        foundation-model numbers substantially and does not change laplace's.</li>
      <li><strong>The two regimes disagree, and neither is wrong.</strong> Batched, a
        foundation model can be cheaper per series than laplace replaying a history.
        Streaming, laplace is orders of magnitude cheaper. Which number applies depends
        entirely on whether you are scoring a benchmark or running a service.</li>
      <li><strong>Rust and Python differ by roughly 18&times;.</strong> Ratios here are
        against the Rust core (<code>skaters_fast</code>), which is what ships; the
        pure-Python reference is correspondingly slower.</li>
      <li><strong>Horizon costs laplace.</strong> Going from k=1 to k={H} costs it roughly
        an order of magnitude, because the multi-scale ensemble runs a full candidate pool
        per decimation stride per horizon.</li>
      <li><strong>Not size-ordered.</strong> The models differ in parameter count and in
        output mechanism (quantile heads versus sampled paths), so this ranks
        implementations as configured, not architectures in the abstract.</li>
      <li><strong>Dependencies are not in the table.</strong> laplace is pure Python (and
        JavaScript, and Rust) with no weights to download and runs in a browser; the
        foundation models need torch and hundreds of megabytes of weights.</li>
    </ul>

    <p class="stamp">Measured {meta['date']} on {meta['machine']}, Python
      {meta['python']}, skaters {meta['version']}+{meta['commit']}, context {meta['context']}
      points, horizon {meta['horizon']}, {meta['series']} series, median of repeats.
      Regenerate with <code>benchmarks/perf_compare.py</code>.</p>
  </main>

  <footer>
    <a href="https://github.com/microprediction/skaters">Source</a> &middot;
    Part of the <a href="https://repos.microprediction.org/">microprediction</a> family
    (see also <a href="http://thurstone.microprediction.org">thurstone</a>,
    <a href="http://schur.microprediction.org">schur</a>).
  </footer>
</body>
</html>
"""


def main():
    meta = stamp()
    rows = measure()
    out = {"meta": meta, "rows": rows}
    jp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perf_results.json")
    with open(jp, "w") as fh:
        json.dump(out, fh, indent=1)
    hp = os.path.join(ROOT, "docs", "performance.html")
    with open(hp, "w") as fh:
        fh.write(render(rows, meta))
    print(f"[perf] {len(rows)} measurements -> {jp}")
    print(f"[perf] page -> {hp}")
    for r in rows:
        ms = "n/a" if r["ms"] != r["ms"] else f"{r['ms']:.4f}"
        print(f"   {r['model']:24s}{r['regime']:12s}{ms:>10}  {r['note']}")


if __name__ == "__main__":
    main()
