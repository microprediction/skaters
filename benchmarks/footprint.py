"""Footprint: what it costs to carry skaters, measured, and the site page.

Accuracy lives in the results store and runtime on the performance page;
this is the third axis, size and dependencies: source bytes and lines per
port, the published wheel, declared dependencies, import time, the bytes a
live laplace state occupies (what a checkpoint costs), and resident memory
of one running instance. Every number is measured by this script; nothing
on the page is typed.

    PYTHONPATH=src python benchmarks/footprint.py
    ... writes benchmarks/footprint_results.json and docs/footprint.html

    python benchmarks/footprint.py --models
    ... refreshes only the "models" list in footprint_results.json: the bytes
    every other arm carries (MODEL_SIZES below), which needs no accuracy or
    timing run, so an arm has a size as soon as its weights are cached
"""
from __future__ import annotations

import glob
import json
import os
import pickle
import platform
import subprocess
import sys
import time
import tracemalloc
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


HUB = os.path.expanduser("~/.cache/huggingface/hub")
WEIGHT_EXT = (".safetensors", ".bin", ".pt", ".pth", ".ckpt")

# (display name, model-page slug, source). Sources:
#   hub:<org>--<repo>[:<file>]  weight files of the one cached snapshot the arm
#                               loads; <file> when the repo ships several
#                               checkpoints and the adapter reads one
#   pkg:<venv>:<module>         the installed package directory, dependencies
#                               not counted (arms that refit and carry no weights)
MODEL_SIZES = [
    ("Chronos-Bolt-small", "chronos", "hub:amazon--chronos-bolt-small"),
    ("Chronos-2", "chronos2", "hub:amazon--chronos-2"),
    ("ci-proto", "ciproto", "hub:ContinuousIntelligence--ci-proto:model.ckpt"),
    ("CITRAS-FM", "citras", "hub:hitachi-nlp--citras-fm"),
    ("Hirondel-7M", "hirondel", "hub:Tncrd--Hirondel-7M"),
    ("iAmTime-base", "iamtime", "hub:anishsaha--iAmTime-base-forecast"),
    ("Kairos-50m", "kairos", "hub:mldi-lab--Kairos_50m"),
    ("Moirai 2.0 small", "moirai2", "hub:Salesforce--moirai-2.0-R-small"),
    ("PatchTST-FM-r2", "patchtstfm", "hub:ibm-granite--granite-timeseries-patchtst-fm-r2"),
    ("Simons-297M", "simons", "hub:abel-lab--Simons-297M"),
    ("Simons-178M", "simons", "hub:abel-lab--Simons-178M"),
    ("Simons-60M", "simons", "hub:abel-lab--Simons-60M"),
    ("Simons-25M", "simons", "hub:abel-lab--Simons-25M"),
    ("t0-gamma", "t0gamma", "hub:theforecastingcompany--t0-gamma"),
    ("Tabby-Pretrain", "tabby", "hub:paris-noah--Tabby-Pretrain"),
    ("Tafsut-base", "tafsut", "hub:Tafsut-FM--tafsut-univariate-base"),
    ("TimeH2O-v1", "timeh2o", "hub:h2oai--timeh2o-v1"),
    ("TimeH2O-v1-tiny", "timeh2o", "hub:h2oai--timeh2o-v1-tiny"),
    ("Timer-S1", "timers1", "hub:bytedance-research--Timer-S1"),
    ("TimesFM 2.5", "timesfm", "hub:google--timesfm-2.5-200m-pytorch"),
    ("TimesFM 3.0", "timesfm3", "hub:google--timesfm-3.0-pytorch"),
    ("TimeSSM-2.5M", "timessm", "hub:IUseAMouse--timessm-2.5m"),
    ("Timestral-209M", "timestral", "hub:mistralai--Timestral-209M"),
    ("Timestral-123M", "timestral", "hub:mistralai--Timestral-123M"),
    ("Timestral-28M", "timestral", "hub:mistralai--Timestral-28M"),
    ("Timestral-5M", "timestral", "hub:mistralai--Timestral-5M"),
    ("TinyCast", "tinycast", "hub:raws-labs--tinycast"),
    ("TiRex", "tirex", "hub:NX-AI--TiRex"),
    ("TiRex-2", "tirex2", "hub:NX-AI--TiRex-2"),
    ("Toto 2.0 2.5B", "toto2", "hub:Datadog--Toto-2.0-2.5B"),
    ("Toto 2.0 1B", "toto2", "hub:Datadog--Toto-2.0-1B"),
    ("Toto 2.0 313M", "toto2", "hub:Datadog--Toto-2.0-313m"),
    ("Toto 2.0 22M", "toto2", "hub:Datadog--Toto-2.0-22m"),
    ("Toto 2.0 4M", "toto2", "hub:Datadog--Toto-2.0-4m"),
    ("TS-ICL", "tsicl", "hub:taharnbl--TS-ICL"),
    ("TTM-R3", "ttm3", "hub:ibm-granite--granite-timeseries-ttm-r3"),
    ("Yug", "yug", "hub:birlaailabs--yug"),
    ("CSP", "csp", "pkg:.venv-csp:csp_forecaster"),
    ("AutoARIMA", "autoarima", "pkg:.venv-sota:statsforecast"),
    ("AutoETS", "autoets", "pkg:.venv-sota:statsforecast"),
    ("AutoTheta", "autotheta", "pkg:.venv-sota:statsforecast"),
    ("GARCH-t", "garcht", "pkg:.venv-sota:arch"),
]


def weight_bytes(repo, only=None):
    """Bytes of the weight files in ONE cached snapshot of a Hub repo, or None.

    A cache can hold several snapshots of a repo (revisions fetched over time)
    and a snapshot several formats of the same weights; summing them counts
    the model more than once. The snapshot is refs/main when that snapshot
    holds weights, else one holding safetensors, else the newest; within it
    safetensors are counted when present, else the other weight formats."""
    base = os.path.join(HUB, f"models--{repo}")
    cands = []
    for snap in sorted(glob.glob(os.path.join(base, "snapshots", "*"))):
        files = [p for p in glob.glob(os.path.join(snap, "**", "*"), recursive=True) if os.path.isfile(p)]
        if only:
            w = [p for p in files if os.path.relpath(p, snap) == only]
        else:
            st = [p for p in files if p.endswith(".safetensors")]
            w = st or [p for p in files if p.endswith(WEIGHT_EXT)]
        if w:
            cands.append((snap, w))
    if not cands:
        return None
    ref = os.path.join(base, "refs", "main")
    main = open(ref).read().strip() if os.path.exists(ref) else None
    cands.sort(key=lambda c: (os.path.basename(c[0]) == main,
                              any(p.endswith(".safetensors") for p in c[1]),
                              os.path.getmtime(c[0])))
    return sum(os.stat(p).st_size for p in cands[-1][1])     # stat follows the blob symlink


def package_bytes(venv, module):
    """Installed size of one package directory in a study venv, or None."""
    py = os.path.join(ROOT, venv, "bin", "python")
    cp = subprocess.run([py, "-c", f"import {module}, os; print(os.path.dirname({module}.__file__))"],
                        capture_output=True, text=True, timeout=300)
    d = cp.stdout.strip().splitlines()[-1] if cp.returncode == 0 and cp.stdout.strip() else None
    if not d or not os.path.isdir(d):
        return None
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in fs)


def measure_models():
    """One record per MODEL_SIZES entry that can be measured on this machine."""
    out = []
    for name, slug, src in MODEL_SIZES:
        kind, _, rest = src.partition(":")
        if kind == "hub":
            repo, _, only = rest.partition(":")
            b = weight_bytes(repo, only or None)
            how = (f"{only} as cached from the Hub" if only else "weight files as cached from the Hub")
        else:
            venv, _, module = rest.partition(":")
            b = package_bytes(venv, module)
            how = f"the installed {module} package, dependencies not counted"
        if b is None:
            print(f"[footprint] no size for {name}: {src} not found")
            continue
        out.append({"name": name, "slug": slug, "bytes": b, "footprint_how": how, "source": src})
    return out


def _bytes_lines(paths):
    b = l = 0
    for p in paths:
        with open(p, "rb") as fh:
            data = fh.read()
        b += len(data); l += data.count(b"\n")
    return b, l


def _pypi_json():
    """PyPI's metadata, via urllib, or curl when the interpreter lacks CA certificates."""
    url = "https://pypi.org/pypi/skaters/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.load(r)
    except Exception:  # noqa: BLE001
        cp = subprocess.run(["curl", "-sSf", "--max-time", "15", url], capture_output=True, text=True, check=True)
        return json.loads(cp.stdout)


def fast_so_bytes():
    """Size of the compiled skaters_fast extension in a study venv, or None. A
    worktree has no venvs of its own, so the checkout holding the per-step
    store (reached through the benchmarks/preds symlink) is searched as well."""
    roots = [ROOT, os.path.dirname(os.path.dirname(os.path.realpath(os.path.join(HERE, "preds"))))]
    for root in dict.fromkeys(roots):
        so = sorted(glob.glob(os.path.join(root, ".venv*", "lib", "python*", "site-packages", "skaters_fast", "*.so")))
        if so:
            return os.path.getsize(so[0])
    return None


def measure():
    out = {}
    py = [p for p in glob.glob(os.path.join(ROOT, "src", "skaters", "**", "*.py"), recursive=True)
          if "/torch/" not in p]
    out["python_bytes"], out["python_lines"] = _bytes_lines(py)
    out["python_files"] = len(py)
    js = glob.glob(os.path.join(ROOT, "docs", "js", "skaters", "*.mjs"))
    out["js_bytes"], out["js_lines"] = _bytes_lines(js)
    rs = glob.glob(os.path.join(ROOT, "rust", "src", "**", "*.rs"), recursive=True)
    out["rust_bytes"], out["rust_lines"] = _bytes_lines(rs)
    out["fast_so_bytes"] = fast_so_bytes()

    # declared dependencies: pyproject's [project] dependencies list
    deps = None
    with open(os.path.join(ROOT, "pyproject.toml")) as fh:
        for line in fh:
            if line.startswith("dependencies"):
                deps = line.split("=", 1)[1].strip()
    out["dependencies"] = deps

    # the published wheel, if PyPI is reachable (recorded with its version)
    try:
        d = _pypi_json()
        v = d["info"]["version"]
        wheel = [u for u in d["releases"][v] if u["packagetype"] == "bdist_wheel"]
        out["pypi_version"] = v
        out["wheel_bytes"] = wheel[0]["size"] if wheel else None
    except Exception as e:  # noqa: BLE001
        out["pypi_version"] = None; out["wheel_bytes"] = None; out["pypi_note"] = type(e).__name__

    # import time, fresh interpreter, median of 5
    cmd = [sys.executable, "-c", "import time; t=time.perf_counter(); import skaters; print(time.perf_counter()-t)"]
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
    ts = sorted(float(subprocess.run(cmd, capture_output=True, text=True, env=env, check=True).stdout) for _ in range(5))
    out["import_ms"] = ts[2] * 1000

    # a live laplace: state bytes (the checkpoint cost) and resident memory
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import random
    from skaters import laplace
    random.seed(0)
    series = [random.gauss(0, 1) for _ in range(500)]
    for k in (1, 3):
        f = laplace(k)
        tracemalloc.start()
        st = None
        for y in series:
            _, st = f(y, st)
        cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        out[f"laplace_k{k}_state_pickle_bytes"] = len(pickle.dumps(st))
        out[f"laplace_k{k}_resident_bytes"] = cur
        out[f"laplace_k{k}_peak_bytes"] = peak
    out["meta"] = {"date": time.strftime("%Y-%m-%d"), "python": platform.python_version(),
                   "machine": platform.machine(),
                   "commit": subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                                            capture_output=True, text=True).stdout.strip()}
    return out


def _kb(b):
    return "n/a" if b is None else f"{b / 1024:.0f} KB"


def render(r):
    sys.path.insert(0, os.path.join(ROOT, "docs"))
    from sweep_nav import CANONICAL
    m = r["meta"]
    wheel = _kb(r["wheel_bytes"]) + (f" (skaters {r['pypi_version']} on PyPI)" if r.get("pypi_version") else "")
    rows = [
        ("Python reference, source", f"{_kb(r['python_bytes'])}, {r['python_lines']:,} lines in {r['python_files']} files",
         "the whole library, standard library only; skaters.torch excluded"),
        ("Declared dependencies", "none" if r["dependencies"] in ("[]", None) else r["dependencies"],
         "pyproject.toml; numpy is not required"),
        ("Published wheel", wheel, "what pip downloads"),
        ("Import time", f"{r['import_ms']:.0f} ms", "fresh interpreter, median of 5"),
        ("laplace(1) checkpoint", _kb(r["laplace_k1_state_pickle_bytes"]), "pickled state after 500 observations"),
        ("laplace(3) checkpoint", _kb(r["laplace_k3_state_pickle_bytes"]), "pickled state after 500 observations"),
        ("laplace(1) resident memory", _kb(r["laplace_k1_resident_bytes"]),
         f"tracemalloc, one instance, 500 steps; peak {_kb(r['laplace_k1_peak_bytes'])}"),
        ("laplace(3) resident memory", _kb(r["laplace_k3_resident_bytes"]),
         f"tracemalloc, one instance, 500 steps; peak {_kb(r['laplace_k3_peak_bytes'])}"),
        ("JavaScript port, source", f"{_kb(r['js_bytes'])}, {r['js_lines']:,} lines", "ES modules, no dependencies; runs in the browser"),
        ("Rust core, source", f"{_kb(r['rust_bytes'])}, {r['rust_lines']:,} lines", "the fast backend and the wasm build"),
        ("skaters_fast binary", _kb(r["fast_so_bytes"]), "the compiled PyO3 extension, this machine"),
    ]
    trs = "\n".join(f"      <tr><td>{a}</td><td>{b}</td><td class=\"muted\">{c}</td></tr>" for a, b, c in rows)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>skaters &mdash; footprint</title>
  <meta name="description" content="What it costs to carry skaters: source size per port, dependencies, import time, checkpoint bytes and resident memory of a live laplace, all measured." />
  <link rel="stylesheet" href="./academic.css?v=20261117" />
  <style>
    table.fp {{ border-collapse: collapse; margin: 0 0 26px; width: 100%; }}
    table.fp th, table.fp td {{ border-bottom: 1px solid #e3e3e3; padding: 6px 10px; text-align: left; font-size: 0.94em; }}
    table.fp th {{ border-bottom: 2px solid #bbb; font-weight: 600; }}
    .muted {{ color: #777; }}
    .stamp {{ color: #888; font-size: 0.88em; font-style: italic; }}
  </style>
</head>
<body>
{CANONICAL}

  <main>
    <h1>Footprint</h1>
    <p class="lede">Accuracy is on the <a href="/benchmarks.html">accuracy page</a> and runtime
      on the <a href="/performance.html">performance page</a>. This page is the third axis:
      what the library costs to carry. Every number is measured by
      <a href="https://github.com/microprediction/skaters/blob/main/benchmarks/footprint.py"><code>benchmarks/footprint.py</code></a>.</p>

    <table class="fp">
      <thead><tr><th>item</th><th>measured</th><th>how</th></tr></thead>
      <tbody>
{trs}
      </tbody>
    </table>

    <h2>Reading it</h2>
    <p>The reference is a few hundred kilobytes of standard-library Python with no
      dependencies, so it installs anywhere Python runs, including Pyodide in the
      browser. A running <code>laplace</code> is a dictionary of floats: its checkpoint is
      the state above, which round-trips through pickle or JSON bit for bit (the parity
      suite checks the restore), so a forecaster can be paused, stored and resumed per
      series. The compiled core is larger than the source it mirrors, as compiled code
      is, and is optional.</p>

    <h2>Reproducing this</h2>
<pre><code>PYTHONPATH=src python benchmarks/footprint.py</code></pre>
    <p class="stamp">Measured {m['date']} on {m['machine']}, Python {m['python']},
      commit {m['commit']}.</p>
  </main>

  <footer>
    <a href="https://github.com/microprediction/skaters">Source</a> &middot;
    Part of the <a href="https://repos.microprediction.org/">microprediction</a> family &middot;
    Authored by <a href="https://home.microprediction.org">Peter Cotton</a>.
  </footer>
</body>
</html>
"""


def main():
    path = os.path.join(HERE, "footprint_results.json")
    if "--models" in sys.argv:
        r = json.load(open(path))
        r["models"] = measure_models()
        r["models_date"] = time.strftime("%Y-%m-%d")
        if r.get("fast_so_bytes") is None:           # a record written where no venv held the extension
            r["fast_so_bytes"] = fast_so_bytes()
        with open(path, "w") as fh:
            json.dump(r, fh, indent=1)
        for m in sorted(r["models"], key=lambda m: m["bytes"]):
            print(f"  {m['name']:22s} {m['bytes'] / 1e6:10.1f} MB")
        return
    r = measure()
    r["models"] = measure_models()
    r["models_date"] = r["meta"]["date"]
    with open(os.path.join(HERE, "footprint_results.json"), "w") as fh:
        json.dump(r, fh, indent=1)
    with open(os.path.join(ROOT, "docs", "footprint.html"), "w") as fh:
        fh.write(render(r))
    for k, v in r.items():
        if k != "meta":
            print(f"  {k:36s} {v}")
    print("[footprint] page -> docs/footprint.html")


if __name__ == "__main__":
    main()
