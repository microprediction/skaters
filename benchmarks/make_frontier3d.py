"""The three-axis frontier: accuracy, speed and footprint, one point per model.

Replaces the two-axis frontier figure. Every coordinate is measured:

  accuracy   median per-series delta log-likelihood against laplace on the
             FRED non-price economic strata (daily, weekly, monthly), paired
             on identical series and windows, from the canonical per-step
             store (the same quantity as canonical_summary_vs_laplace.csv,
             pooled over the three strata); laplace sits at zero
  speed      milliseconds per new observation, streaming regime, from
             benchmarks/perf_results.json (one machine, CPU, 1 torch thread)
  footprint  megabytes a deployment carries: the model's weight files as
             cached from the Hub, or for laplace the published wheel (and
             the compiled core when that is the point being plotted)

Writes docs/assets/frontier3d.js, a self-contained Plotly scatter3d (data
and render code) that fills <div id="frontier3d"> and the caption paragraph
<p id="frontier3d-caption">, plus benchmarks/frontier3d.json for the record.

    PYTHONPATH=src:benchmarks .venv-gifteval/bin/python benchmarks/make_frontier3d.py
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

STRATA = ("daily:econ", "weekly:econ", "monthly:econ")
HUB = os.path.expanduser("~/.cache/huggingface/hub")

# display name -> (store method, perf model, hub repo or None, group)
MODELS = {
    "laplace (Rust core)":    ("laplace", "laplace (Rust) k=1", None, "laplace"),
    "laplace (pure Python)":  ("laplace", "laplace (Python) k=1", None, "laplace"),
    "Timestral-209M":         ("Timestral-209M(q21)", "Timestral-209M", "mistralai--Timestral-209M", "fm"),
    "Timestral-28M":          ("Timestral-28M(q21)", "Timestral-28M", "mistralai--Timestral-28M", "fm"),
    "t0-gamma":               ("t0-gamma(q21)", "t0-gamma", "theforecastingcompany--t0-gamma", "fm"),
    "TimesFM 3.0":            ("TimesFM3(wide)", "TimesFM-3.0", "google--timesfm-3.0-pytorch", "fm"),
    "TimesFM 2.5":            ("TimesFM(wide)", "TimesFM-2.5-200M", "google--timesfm-2.5-200m-pytorch", "fm"),
    "TiRex":                  ("TiRex(wide)", "TiRex", "NX-AI--TiRex", "fm"),
    "Chronos-Bolt-small":     ("Chronos(wide)", "Chronos-Bolt-small", "amazon--chronos-bolt-small", "fm"),
}
# Sundial and FlowState are left out: only their tight-reconstruction runs exist
# in the store, and the reconstruction study showed that nozzle, not the model,
# sets most of such a gap (Sundial reads -2.8 nats through 30 sampled paths).
OMITTED = "Sundial and FlowState are omitted: no fair-reconstruction run exists for them."
WEIGHT_EXT = (".safetensors", ".bin", ".pt", ".pth", ".ckpt")


def weight_bytes(repo):
    snap = os.path.join(HUB, f"models--{repo}", "snapshots")
    total = 0
    for p in glob.glob(os.path.join(snap, "*", "**", "*"), recursive=True):
        if p.endswith(WEIGHT_EXT):
            total += os.stat(p).st_size      # follows the blob symlink
    return total or None


def accuracy(store):
    """Paired median dLL vs laplace per store method, pooled over STRATA,
    mirroring summarize_canonical (per-series mean logpdf floored at -20)."""
    import summarize_canonical as sc
    by_method = {}
    for (study, s, m), d in store.items():
        if study not in STRATA or m == "laplace":
            continue
        bl = store.get((study, s, "laplace"))
        if bl is None or len(bl["logpdf"]) != len(d["logpdf"]):
            continue
        by_method.setdefault(m, []).append(sc._series_mean(d["logpdf"], -20.0)
                                           - sc._series_mean(bl["logpdf"], -20.0))
    out = {}
    for m, v in by_method.items():
        v = np.asarray(v, float)
        v = v[np.isfinite(v)]
        if len(v):
            out[m] = {"med_dll": float(np.median(v)), "q25": float(np.percentile(v, 25)),
                      "q75": float(np.percentile(v, 75)), "n_series": int(len(v)),
                      "win_frac": float(np.mean(v > 0))}
    return out


def main():
    import summarize_canonical as sc
    perf = json.load(open(os.path.join(HERE, "perf_results.json")))
    warm = {r["model"]: r["ms"] for r in perf["rows"] if r["regime"] == "warm"}
    fp = json.load(open(os.path.join(HERE, "footprint_results.json")))
    jp = os.path.join(HERE, "frontier3d.json")
    if os.environ.get("FRONTIER3D_REUSE") and os.path.exists(jp):
        # layout-only rebuild: keep the measured points, re-render the script
        prev = json.load(open(jp))
        points = prev["points"]
        print(f"[frontier3d] reusing {len(points)} points from frontier3d.json", flush=True)
    else:
        print("[frontier3d] loading per-step store ...", flush=True)
        acc = accuracy(sc.load_all())
        points = []
    for name, (method, pmodel, repo, group) in ([] if points else MODELS.items()):
        a = acc.get(method) if method != "laplace" else {"med_dll": 0.0, "q25": 0.0, "q75": 0.0,
                                                          "n_series": None, "win_frac": None}
        if a is None or pmodel not in warm:
            print(f"[frontier3d] skip {name}: acc={a is not None} perf={pmodel in warm}")
            continue
        if repo:
            mb = weight_bytes(repo) / 1e6
            foot = "weight files as cached from the Hub"
        elif "Rust" in name:
            mb = (fp["wheel_bytes"] + fp["fast_so_bytes"]) / 1e6
            foot = "published wheel plus the compiled core"
        else:
            mb = fp["wheel_bytes"] / 1e6
            foot = "published wheel, no dependencies"
        points.append({"name": name, "group": group, "method": method, "ms": warm[pmodel],
                       "mb": mb, "footprint_how": foot, **a})
    meta = {"date": time.strftime("%Y-%m-%d"), "strata": list(STRATA),
            "perf_meta": perf.get("meta", {}), "footprint_date": fp["meta"]["date"]}
    json.dump({"meta": meta, "points": points}, open(os.path.join(HERE, "frontier3d.json"), "w"), indent=1)
    fms = [p for p in points if p["group"] == "fm"]
    lo, hi = min(p["med_dll"] for p in fms), max(p["med_dll"] for p in fms)
    lap = next(p for p in points if "Rust" in p["name"])
    lightest_fm = min(fms, key=lambda p: p["mb"])
    fastest_fm = min(fms, key=lambda p: p["ms"])
    n_pairs = min(p["n_series"] for p in fms)
    n_max = max(p["n_series"] for p in fms)
    caption = (f"Accuracy is the median per-series Δ log-likelihood against laplace on the FRED "
               f"non-price economic strata (daily, weekly, monthly; {n_pairs:,} to {n_max:,} paired series "
               f"per model). The {len(fms)} foundation models span {lo:+.2f} to {hi:+.2f} nats around "
               f"laplace's zero. The lightest of them carries {lightest_fm['mb'] / lap['mb']:,.0f}× "
               f"laplace's bytes and the fastest takes {fastest_fm['ms'] / lap['ms']:,.0f}× as long "
               f"per new observation. Speed is one machine, CPU, streaming regime "
               f"(benchmarks/perf_results.json); footprint is the weight files as cached "
               f"({meta['date']}). " + OMITTED)
    js = f"""// generated by benchmarks/make_frontier3d.py on {meta['date']}; do not edit by hand
(function () {{
  var P = {json.dumps(points)};
  var CAPTION = {json.dumps(caption)};
  function fmtMB(mb) {{ return mb < 1 ? (mb * 1000).toFixed(0) + ' KB' : mb < 1000 ? mb.toFixed(0) + ' MB' : (mb / 1000).toFixed(1) + ' GB'; }}
  function fmtMS(ms) {{ return ms < 1 ? (ms * 1000).toFixed(0) + ' \\u00b5s' : ms.toFixed(1) + ' ms'; }}
  function trace(group, color, symbol) {{
    var pts = P.filter(function (p) {{ return p.group === group; }});
    return {{
      type: 'scatter3d', mode: 'markers+text', name: group === 'laplace' ? 'laplace' : 'foundation models',
      x: pts.map(function (p) {{ return p.mb; }}), y: pts.map(function (p) {{ return p.ms; }}),
      z: pts.map(function (p) {{ return p.med_dll; }}),
      text: pts.map(function (p) {{ return p.name; }}), textposition: 'top center',
      textfont: {{ size: 11, color: '#333' }},
      marker: {{ size: group === 'laplace' ? 9 : 7, color: color, symbol: symbol, opacity: 0.95, line: {{ width: 1, color: '#fff' }} }},
      hovertext: pts.map(function (p) {{
        return '<b>' + p.name + '</b><br>' + fmtMB(p.mb) + ' (' + p.footprint_how + ')<br>' + fmtMS(p.ms) +
          ' per new observation<br>' + (p.n_series ? ('median \\u0394LL ' + (p.med_dll >= 0 ? '+' : '') + p.med_dll.toFixed(3) +
          ' nats, IQR ' + p.q25.toFixed(2) + ' to ' + p.q75.toFixed(2) + ', ' + p.n_series.toLocaleString() + ' paired series') : 'the baseline, 0 by definition');
      }}), hoverinfo: 'text'
    }};
  }}
  var mbs = P.map(function (p) {{ return Math.log10(p.mb); }}), mss = P.map(function (p) {{ return Math.log10(p.ms); }});
  var zs = P.map(function (p) {{ return p.med_dll; }});
  var z0 = Math.min.apply(null, zs) - 0.03, z1 = Math.max.apply(null, zs) + 0.03;
  // a stem from the floor to each point, so the (footprint, speed) position reads at a glance
  var sx = [], sy = [], sz = [];
  P.forEach(function (p) {{ sx.push(p.mb, p.mb, null); sy.push(p.ms, p.ms, null); sz.push(z0, p.med_dll, null); }});
  var stems = {{ type: 'scatter3d', mode: 'lines', x: sx, y: sy, z: sz, line: {{ color: '#b9b9c6', width: 2 }},
    hoverinfo: 'skip', showlegend: false }};
  var x0 = Math.min.apply(null, mbs) - 0.4, x1 = Math.max.apply(null, mbs) + 0.4;
  var y0 = Math.min.apply(null, mss) - 0.4, y1 = Math.max.apply(null, mss) + 0.4;
  // the laplace plane: z = 0 across the whole footprint x speed floor
  var plane = {{ type: 'surface', x: [Math.pow(10, x0), Math.pow(10, x1)], y: [Math.pow(10, y0), Math.pow(10, y1)],
    z: [[0, 0], [0, 0]], showscale: false, opacity: 0.12, colorscale: [[0, '#1a8c4a'], [1, '#1a8c4a']],
    hoverinfo: 'skip', name: 'laplace level' }};
  var layout = {{
    margin: {{ l: 0, r: 0, t: 10, b: 0 }}, height: 520, showlegend: true,
    legend: {{ x: 0, y: 1, orientation: 'h', font: {{ size: 12 }} }},
    paper_bgcolor: 'rgba(0,0,0,0)',
    scene: {{
      xaxis: {{ title: 'footprint (MB, log)', type: 'log', range: [x0, x1], gridcolor: '#e4e4e4' }},
      yaxis: {{ title: 'ms per new observation (log)', type: 'log', range: [y0, y1], gridcolor: '#e4e4e4' }},
      zaxis: {{ title: '\\u0394 log-likelihood vs laplace (nats)', range: [z0, z1], gridcolor: '#e4e4e4', zeroline: true, zerolinecolor: '#1a8c4a' }},
      camera: {{ eye: {{ x: 1.8, y: -1.45, z: 0.42 }} }},
      aspectmode: 'manual', aspectratio: {{ x: 1.5, y: 1.0, z: 0.8 }}
    }}
  }};
  function render() {{
    var el = document.getElementById('frontier3d');
    if (!el || typeof Plotly === 'undefined') return;
    Plotly.newPlot(el, [plane, stems, trace('fm', '#8f84ff', 'circle'), trace('laplace', '#1a8c4a', 'diamond')], layout,
      {{ displayModeBar: false, responsive: true }});
    var cap = document.getElementById('frontier3d-caption');
    if (cap) cap.textContent = CAPTION;
  }}
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', render); else render();
}})();
"""
    open(os.path.join(ROOT, "docs", "assets", "frontier3d.js"), "w").write(js)
    for p in points:
        print(f"  {p['name']:24s} {p['mb']:10.2f} MB {p['ms']:9.4f} ms  dLL {p['med_dll']:+.3f}  n={p['n_series']}")
    print("[frontier3d] wrote docs/assets/frontier3d.js and benchmarks/frontier3d.json")


if __name__ == "__main__":
    main()
