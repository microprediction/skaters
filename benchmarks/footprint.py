"""Footprint: what it costs to carry skaters, measured, and the site page.

Accuracy lives in the results store and runtime on the performance page;
this is the third axis, size and dependencies: source bytes and lines per
port, the published wheel, declared dependencies, import time, the bytes a
live laplace state occupies (what a checkpoint costs), and resident memory
of one running instance. Every number is measured by this script; nothing
on the page is typed.

    PYTHONPATH=src python benchmarks/footprint.py
    ... writes benchmarks/footprint_results.json and docs/footprint.html
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
    so = glob.glob(os.path.join(ROOT, ".venv*", "lib", "python*", "site-packages", "skaters_fast", "*.so"))
    out["fast_so_bytes"] = os.path.getsize(so[0]) if so else None

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
  <link rel="stylesheet" href="./academic.css" />
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
    Part of the <a href="https://repos.microprediction.org/">microprediction</a> family
    (see also <a href="http://thurstone.microprediction.org">thurstone</a>,
    <a href="http://schur.microprediction.org">schur</a>).
  </footer>
</body>
</html>
"""


def main():
    r = measure()
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
