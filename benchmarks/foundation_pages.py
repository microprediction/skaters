"""Generate the per-model 'Foundational' pages and sweep the site nav.

One page per foundation model (docs/foundation/<slug>.html), each a full workup
from the canonical week-study summaries: a standalone head-to-head vs Laplace
per stratum, a star plot (not-worse rate across the five strata, one polygon per
variant), and the collaborative sandwich/sidecar results where those arms exist.
The pages are DATA-DRIVEN and regenerate from the live summaries, so re-running
this refreshes them as the study deepens. It also rewrites the <nav> block in
every docs page so the site menu stays consistent.

    PYTHONPATH=src:benchmarks .venv-sota/bin/python benchmarks/foundation_pages.py
"""
from __future__ import annotations
import collections
import csv
import json
import math
import os
import re

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
FDIR = os.path.join(DOCS, "foundation")
BENCH = os.path.dirname(os.path.abspath(__file__))
PREDS = os.path.join(BENCH, "preds")

# Radar regime axes, matching the site's challenges radar exactly
# (make_challenges_radar.py): six axes, the M4-hourly stratum split into soft
# waveforms (first 180 series in corpus order) and hard waveforms (the rest).
# Tuple: (axis label, study key, m4 block or None).
RADAR_AXES = [
    ("economic (daily)", "daily:econ",     None),
    ("weekly cycles",    "weekly:econ",    None),
    ("yearly cycles",    "monthly:econ",   None),
    ("soft waveforms",   "m4-hourly:econ", "soft"),
    ("hard waveforms",   "m4-hourly:econ", "hard"),
    ("price / returns",  "daily:price",    None),
]

# (csv study key, short radar axis label, long stratum label)
STRATA = [
    ("daily:econ",     "daily econ", "economic change-series, business-daily"),
    ("weekly:econ",    "weekly",     "economic change-series, weekly"),
    ("monthly:econ",   "monthly",    "economic change-series, monthly (annual cycle)"),
    ("m4-hourly:econ", "seasonal",   "M4 hourly, strongly seasonal"),
    ("daily:price",    "price",      "asset prices and returns, daily"),
]

MODELS = {
    "chronos": dict(name="Chronos", key="Chronos", vendor="Amazon",
                    license="Apache-2.0", arms=True,
                    blurb="Chronos tokenizes a series into a fixed vocabulary and "
                          "forecasts it autoregressively, like a language model over "
                          "quantized values.",
                    note="Reused from the earlier foundation study; run zero-shot on the "
                         "one-step change series."),
    "tirex": dict(name="TiRex", key="TiRex", vendor="NX-AI",
                  license="NXAI Community License", arms=True,
                  blurb="TiRex is a 35M-parameter, xLSTM-based zero-shot forecaster that "
                        "emits quantile predictions directly.",
                  note="Loaded from NX-AI/TiRex on CPU. Commercial use is gated above "
                       "&euro;100M revenue; included here under research use with the "
                       "required attribution.",
                  links=[
                      ("GitHub", "https://github.com/NX-AI/tirex"),
                      ("Model card", "https://huggingface.co/NX-AI/TiRex"),
                      ("Paper (arXiv 2505.23719)", "https://arxiv.org/abs/2505.23719"),
                      ("License", "https://huggingface.co/NX-AI/TiRex/blob/main/LICENSE"),
                  ],
                  external=[
                      ("GIFT-Eval", "https://huggingface.co/spaces/Salesforce/GIFT-Eval",
                       "Salesforce's general forecasting benchmark: 7 domains, about 98 "
                       "dataset configs, multi-horizon point and quantile accuracy on the "
                       "series levels. TiRex reports at the top of it, a 35M model ahead "
                       "of far larger ones."),
                      ("Chronos-ZS / fev-leaderboard",
                       "https://huggingface.co/spaces/autogluon/fev-leaderboard",
                       "AutoGluon's zero-shot leaderboard over the Chronos evaluation "
                       "datasets, where TiRex also reports strongly."),
                      ("Paper benchmarks (NeurIPS 2025)",
                       "https://arxiv.org/abs/2505.23719",
                       "The authors' own long- and short-horizon evaluation against "
                       "TabPFN-TS, Chronos-Bolt, TimesFM, and Moirai."),
                      ("Third-party analysis",
                       "https://aihorizonforecast.substack.com/p/tirex-lstms-take-the-lead-again-in",
                       "An independent write-up of TiRex's leaderboard results."),
                  ]),
    "timesfm": dict(name="TimesFM", key="TimesFM", vendor="Google", version="2.5",
                    license="Apache-2.0", arms=True,
                    blurb="TimesFM is a decoder-only, patched time-series transformer; "
                          "we score version 2.5.",
                    note="Run zero-shot with a fixed 128-length context."),
    "sundial": dict(name="Sundial", key="Sundial", vendor="",
                    license="see model card", arms=False,
                    blurb="Sundial is a generative time-series model; we draw samples "
                          "per step and score the empirical predictive.",
                    note="Run raw only in this study; the collaborative arms were built "
                         "for the three strongest models first."),
    "flowstate": dict(name="FlowState", key="flowstate", vendor="IBM",
                      license="research checkpoint (arXiv:2508.05287)", arms=False,
                      blurb="FlowState is a state-space time-series model, loaded via "
                            "IBM's granite-tsfm.",
                      note="Research checkpoint (research use only); run raw. The "
                           "collaborative arms were built for the three strongest "
                           "models first."),
}

NAV = """      <nav>
        <a href="/">Home</a>
        <a href="/guide.html">Methodology</a>
        <span class="menu" tabindex="0"><span class="menu-label">Usage &#9662;</span>
          <span class="drop">
            <a href="/challengers.html">Standalone</a>
            <a href="/sandwich.html">Sandwich pattern</a>
            <a href="/sidecar.html">Sidecar pattern</a>
          </span>
        </span>
        <span class="menu" tabindex="0"><span class="menu-label">Foundational &#9662;</span>
          <span class="drop">
            <a href="/foundation/chronos.html">Chronos</a>
            <a href="/foundation/tirex.html">TiRex</a>
            <a href="/foundation/timesfm.html">TimesFM</a>
            <a href="/foundation/sundial.html">Sundial</a>
            <a href="/foundation/flowstate.html">FlowState</a>
          </span>
        </span>
        <a href="/demos/">Demos</a>
        <a href="/papers.html">Papers</a>
        <span class="menu" tabindex="0"><span class="menu-label">Docs &#9662;</span>
          <span class="drop">
            <a href="/guide.html">Methodology</a>
            <a href="/draws.html">Draws</a>
            <a href="/scope.html">Scope</a>
            <a href="/languages.html">Languages</a>
            <a href="/heritage.html">Heritage</a>
            <a href="/faq.html">FAQ</a>
            <a href="/skills.html">Skills</a>
          </span>
        </span>
        <a href="https://github.com/microprediction/skaters">GitHub</a>
      </nav>"""


def load_vs():
    out = {}
    with open(os.path.join(BENCH, "canonical_summary_vs_laplace.csv")) as fh:
        for r in csv.DictReader(fh):
            out[(r["study"], r["model"])] = r
    return out


def load_cov():
    out = {}
    with open(os.path.join(BENCH, "canonical_summary_coverage.csv")) as fh:
        for r in csv.DictReader(fh):
            out[(r["study"], r["method"])] = r
    return out


def sweep_nav():
    pages = []
    for root, _dirs, files in os.walk(DOCS):
        for f in files:
            if f.endswith(".html"):
                pages.append(os.path.join(root, f))
    n = 0
    for p in pages:
        src = open(p).read()
        new, k = re.subn(r"      <nav>.*?</nav>", NAV, src, count=1, flags=re.S)
        if k and new != src:
            open(p, "w").write(new)
            n += 1
    print(f"[nav] rewrote {n} of {len(pages)} pages")


# --------------------------------------------------------------- radar / star plot
def _m4_blocks():
    """(soft, hard) series-id sets: first 180 of the M4-hourly corpus vs the rest,
    the same soft/hard split the challenges radar uses."""
    order = []
    p = os.path.join(PREDS, "_corpus_m4-hourly.jsonl")
    if os.path.exists(p):
        with open(p) as fh:
            for line in fh:
                order.append(json.loads(line)["sid"])
    return set(order[:180]), set(order[180:])


def _smean(a, col):
    a = np.asarray(a, float)
    if col == "logpdf":
        a = np.maximum(a, -20.0)
    return float(np.nanmean(a)) if np.isfinite(a).any() else float("nan")


def _ratio(store, study, subset, method, col, higher_wins):
    """(wins + 0.5*ties)/n / 0.5 vs laplace on the given metric, the same ratio the
    challenges radar plots: 1.0 = an even split with Laplace, 2.0 = always better,
    0 = always worse. None below 30 shared series."""
    wins = ties = n = 0
    for s in subset:
        km, kb = (study, s, method), (study, s, "laplace")
        if km not in store or kb not in store:
            continue
        a, b = _smean(store[km][col], col), _smean(store[kb][col], col)
        if not (np.isfinite(a) and np.isfinite(b)):
            continue
        n += 1
        if a == b:
            ties += 1
        elif (a > b) == higher_wins:
            wins += 1
    return (round((wins + 0.5 * ties) / n / 0.5, 3), n) if n >= 30 else (None, n)


def compute_radar(store):
    """Per method -> {'ll':[6], 'crps':[6], 'n':[6]} over the six regime axes."""
    soft, hard = _m4_blocks()
    per_study = collections.defaultdict(set)
    for (st, s, m) in store:
        if m == "laplace":
            per_study[st].add(s)
    methods = {m for (_, _, m) in store} - {"laplace"}
    out = {}
    for method in methods:
        ll, crps, ns = [], [], []
        for _label, study, block in RADAR_AXES:
            subset = per_study.get(study, set())
            if block == "soft":
                subset = subset & soft
            elif block == "hard":
                subset = subset & hard
            l, n = _ratio(store, study, subset, method, "logpdf", True)
            c, _ = _ratio(store, study, subset, method, "crps", False)
            ll.append(l); crps.append(c); ns.append(n)
        if any(v is not None for v in ll + crps):
            out[method] = {"ll": ll, "crps": crps, "n": ns}
    return out


def radar_svg(model, radar):
    """One six-axis regime star plot: the raw model standalone vs Laplace, on the
    log-likelihood ratio (Laplace = the dashed 1.0 ring, outward beats Laplace
    more often). Standalone only; no sandwich arms."""
    W, H, cx, cy, R = 560, 470, 280, 240, 180
    K = len(RADAR_AXES)
    MAXV = 1.5
    color = "#4a3aff"

    def ang(i):
        return -math.pi / 2 + i * 2 * math.pi / K

    def pt(i, v):
        r = R * min(max(v, 0.0), MAXV) / MAXV
        return cx + r * math.cos(ang(i)), cy + r * math.sin(ang(i))

    parts = [f'<svg viewBox="0 0 {W} {H}" style="width:100%;max-width:560px;height:auto;'
             f'display:block;margin:0 auto" role="img" '
             f'aria-label="Star plot of {model["name"]} standalone versus Laplace across '
             f'six regime axes; the log-likelihood ratio, Laplace on the 1.0 ring.">']
    for rv in (0.5, 1.0, 1.5):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, rv) for i in range(K)))
        if abs(rv - 1.0) < 1e-9:
            parts.append(f'<polygon points="{pts}" fill="none" stroke="#1a8c4a" '
                         f'stroke-dasharray="5 4" stroke-width="1.5" opacity=".75"/>')
        else:
            parts.append(f'<polygon points="{pts}" fill="none" stroke="#e2e2e2" '
                         f'stroke-width="1"/>')
    for i, (label, _study, _blk) in enumerate(RADAR_AXES):
        ex, ey = pt(i, MAXV)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" '
                     f'stroke="#e2e2e2" stroke-width="1"/>')
        lx, ly = pt(i, 1.15)
        anchor = "middle" if abs(lx - cx) < 14 else ("start" if lx > cx else "end")
        dy = 4 if ly >= cy else 0
        parts.append(f'<text x="{lx:.1f}" y="{ly + dy:.1f}" text-anchor="{anchor}" '
                     f'font-size="13" fill="#5a5a5a">{label}</text>')
    lref_x, lref_y = pt(0, 1.0)
    parts.append(f'<text x="{lref_x + 6:.1f}" y="{lref_y - 5:.1f}" font-size="11" '
                 f'fill="#1a8c4a">Laplace = 1.0</text>')
    d = radar.get(model["key"])
    pairs = [(i, v) for i, v in enumerate(d["ll"])] if d else []
    pairs = [(i, v) for i, v in pairs if v is not None]
    if pairs:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, v) for i, v in pairs))
        parts.append(f'<polygon points="{pts}" fill="{color}" fill-opacity=".16" '
                     f'stroke="{color}" stroke-width="2"/>')
        for i, v in pairs:
            x, y = pt(i, v)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" '
                         f'stroke="#fff" stroke-width="1.5"><title>{RADAR_AXES[i][0]}: '
                         f'log-likelihood ratio {v:.2f} vs Laplace '
                         f'(n={d["n"][i]})</title></circle>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------- page builder
def fmt_pct(x):
    return f"{x:.0%}"


def standalone_rows(model, vs, cov):
    rows = []
    for k, _short, long in STRATA:
        r = vs.get((k, model["key"]))
        c = cov.get((k, model["key"]))
        if not r:
            rows.append(f'<tr><td>{long}</td><td colspan="6" class="muted">not yet '
                        f'scored</td></tr>')
            continue
        n = int(r["n_series"])
        w, d, l = int(r["win"]), int(r["draw"]), int(r["loss"])
        dll = float(r["med_dLL"])
        crps = float(r["med_crps_ratio"])
        rawcov = f'{float(c["cov_central90"]):.2f}' if c else "&ndash;"
        tot = w + d + l or 1
        bar = (f'<span class="wdl"><i class="w" style="width:{w/tot*100:.1f}%"></i>'
               f'<i class="d" style="width:{d/tot*100:.1f}%"></i>'
               f'<i class="l" style="width:{l/tot*100:.1f}%"></i></span>')
        rows.append(
            f'<tr><td>{long}</td><td class="num">{n}</td><td>{bar}</td>'
            f'<td class="num">{dll:+.2f}</td><td class="num">{crps:.3f}</td>'
            f'<td class="num">{rawcov}</td></tr>')
    return "\n".join(rows)


def combined_section(model, vs, cov):
    if not model["arms"]:
        return (f'<h2>Collaborative use</h2>\n<p>The recalibration (<code>@lap</code>) '
                f'and portfolio (<code>&amp;lap</code>) arms were built for the three '
                f'strongest models first, so {model["name"]} is scored standalone here. '
                f'The sidecar wraps any per-step predictive, so these arms can be added '
                f'without retraining. See the <a href="/sidecar.html">sidecar pattern</a>.</p>')
    rows = []
    for k, _short, long in STRATA:
        raw = vs.get((k, model["key"]))
        amp = vs.get((k, model["key"] + "&lap"))
        cr = cov.get((k, model["key"]))
        ca = cov.get((k, model["key"] + "@lap"))
        if not (raw and amp):
            continue
        rl = int(raw["loss"]) / (int(raw["n_series"]) or 1)
        al = int(amp["loss"]) / (int(amp["n_series"]) or 1)
        rc = f'{float(cr["cov_central90"]):.2f}' if cr else "&ndash;"
        ac = f'{float(ca["cov_central90"]):.2f}' if ca else "&ndash;"
        rows.append(f'<tr><td>{long}</td><td class="num">{rc}</td>'
                    f'<td class="num">{ac}</td><td class="num">{fmt_pct(rl)}</td>'
                    f'<td class="num">{fmt_pct(al)}</td></tr>')
    return f"""<h2>Collaborative use</h2>
    <p>Two collaborative arms wrap {model['name']}'s own predictive. <code>@lap</code>
      lets Laplace forecast the model's normal scores, which fixes coverage; <code>&amp;lap</code>
      holds Laplace and that wrap in a long-only online portfolio, so the blend is never
      much worse than Laplace alone. The recalibration pulls raw coverage back toward the
      0.90 target, and the portfolio collapses the loss rate against Laplace.</p>
    <table>
      <thead><tr><th>stratum</th><th class="num">raw cov</th><th class="num">@lap cov</th>
      <th class="num">raw loss</th><th class="num">&amp;lap loss</th></tr></thead>
      <tbody>
      {chr(10).join(rows)}
      </tbody>
    </table>
    <p style="font-size:.9rem;color:var(--muted)">Central-90% coverage (0.90 target) and
      the fraction of series where the arm loses to Laplace by a
      <a href="/draws.html">Diebold&ndash;Mariano test</a>.</p>"""


def links_row(model):
    if not model.get("links"):
        return ""
    items = " &middot; ".join(f'<a href="{u}">{l}</a>' for l, u in model["links"])
    return (f'<p class="muted" style="font-size:.92rem;margin-top:-4px">Resources: '
            f'{items}</p>')


def external_section(model):
    ext = model.get("external")
    if not ext:
        return ""
    items = "\n".join(
        f'<li><a href="{u}">{l}</a> &mdash; {note}</li>' for l, u, note in ext)
    return f"""<h2>Existing benchmarks</h2>
    <p>{model['name']} reports strongly on public forecasting leaderboards, which measure a
      different task than this study. Those rank multi-horizon accuracy on curated dataset
      collections; this study scores one-step-ahead density forecasts on economic
      change-series against Laplace. A model can lead one and trail the other, so the
      results here sit alongside, not against, the leaderboards below.</p>
    <ul>
      {items}
    </ul>"""


def build_page(slug, model, vs, cov, radar):
    svg = radar_svg(model, radar)
    ver = f" {model['version']}" if model.get("version") else ""
    vendor = f'{model["vendor"]} &middot; ' if model["vendor"] else ""
    intro = f'{model["blurb"]} {model["note"]}'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>skaters &mdash; {model['name']} vs Laplace</title>
  <meta name="description" content="A per-stratum workup of {model['name']} against the
    Laplace online ensemble: standalone head-to-head, a star plot of not-worse rates, and
    the collaborative sidecar arms." />
  <link rel="stylesheet" href="../academic.css" />
  <style>
    .wdl {{ display:flex; height:15px; width:180px; border-radius:3px; overflow:hidden;
           border:1px solid var(--border); }}
    .wdl i {{ display:block; height:100%; }}
    .wdl .w {{ background:var(--good); }} .wdl .d {{ background:#c8c8d4; }}
    .wdl .l {{ background:var(--warn); }}
    .key {{ display:flex; flex-wrap:wrap; gap:6px 16px; font-size:.85rem;
           color:var(--muted); margin:8px 0 0; justify-content:center; }}
    .key i {{ display:inline-block; width:12px; height:12px; border-radius:2px;
             vertical-align:middle; margin-right:5px; }}
    .muted {{ color:var(--muted); }}
    .meta-row {{ display:flex; flex-wrap:wrap; gap:6px 10px; margin:2px 0 14px; }}
    .meta-row .tag {{ background:#ece9ff; color:var(--accent-dark); border-radius:3px;
                     padding:2px 9px; font-size:.8rem; }}
  </style>
</head>
<body>
  <header class="site-header">
    <div class="nav-inner">
      <a class="brand" href="/">skaters</a>
{NAV}
    </div>
  </header>

  <main>
    <h1>{model['name']} vs Laplace</h1>
    <div class="meta-row">
      <span class="tag">{vendor}{model['name']}{ver}</span>
      <span class="tag">{model['license']}</span>
      <span class="tag">zero-shot</span>
      <span class="tag">one-step change series</span>
    </div>
    <p>{intro}</p>
    {links_row(model)}
    <p><span class="snapshot" style="background:#ece9ff;color:var(--accent-dark);
      border-radius:4px;padding:2px 9px;font-size:.8rem;font-weight:600">Live snapshot</span>
      &nbsp;Derived from the week-long round-robin study; counts grow as coverage deepens.
      Everything scores against Laplace on the identical series and windows.</p>

    <h2>Standalone</h2>
    <p>The model's own predictive, run zero-shot, scored per series against Laplace by a
      one-step-ahead (k=1) <a href="/draws.html">Diebold&ndash;Mariano test</a> on the
      log-score differential.</p>
    <table>
      <thead><tr><th>stratum</th><th class="num">n</th><th>win / draw / loss vs Laplace</th>
      <th class="num">med &Delta;LL</th><th class="num">CRPS ratio</th>
      <th class="num">cov&#8320;&#8320;</th></tr></thead>
      <tbody>
      {standalone_rows(model, vs, cov)}
      </tbody>
    </table>
    <div class="key">
      <span><i style="background:var(--good)"></i>beats Laplace</span>
      <span><i style="background:#c8c8d4"></i>draw</span>
      <span><i style="background:var(--warn)"></i>loses to Laplace</span>
    </div>
    <p style="font-size:.9rem;color:var(--muted)">Median per-series &Delta; log-likelihood
      in nats (negative is worse than Laplace); CRPS ratio to Laplace (above 1 is worse);
      raw central-90% coverage (0.90 target).</p>

    <h2>Star plot</h2>
    <p>{model['name']} standalone against Laplace, on the same six regime axes as the site's
      <a href="/challengers.html">standalone radar</a>. Each radius is the log-likelihood
      ratio, <code>(wins + &frac12;&middot;ties) / n</code> scaled so an even split with
      Laplace sits on the dashed 1.0 ring; outward beats Laplace more often, inward less. The
      M4-hourly set splits into soft and hard waveforms by corpus order, matching that radar.</p>
    <figure style="margin:16px 0 6px">
      {svg}
    </figure>

    {combined_section(model, vs, cov)}

    <h2>Protocol</h2>
    <p>Fixed 128-length context, rolling one-step test window, no fitting, each model in its
      own environment. Strata split the cached FRED universe and the M4-hourly set by
      frequency and regime. Full method on the <a href="/sidecar.html">sidecar pattern</a>
      page and in the <a href="/guide.html">methodology</a>.</p>

    {external_section(model)}
  </main>

  <footer>
    <a href="https://github.com/microprediction/skaters">Source</a> &middot;
    Part of the <a href="https://github.com/microprediction">microprediction</a> family.
  </footer>
</body>
</html>
"""


def main():
    os.makedirs(FDIR, exist_ok=True)
    vs, cov = load_vs(), load_cov()
    import summarize_canonical as sc
    print("[radar] loading per-step store ...", flush=True)
    radar = compute_radar(sc.load_all())
    print(f"[radar] {len(radar)} methods over {len(RADAR_AXES)} regime axes", flush=True)
    for slug, model in MODELS.items():
        html = build_page(slug, model, vs, cov, radar)
        open(os.path.join(FDIR, f"{slug}.html"), "w").write(html)
        print(f"[page] foundation/{slug}.html")
    sweep_nav()


if __name__ == "__main__":
    main()
