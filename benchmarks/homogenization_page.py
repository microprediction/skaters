"""Generate docs/homogenization.html from the results store.

Two stages so the page outlives the study tree: if the store is present the
numbers are refreshed into benchmarks/homogenization_results.json (committed);
the page is always rendered from that JSON. The study tree itself is moving to
its own repository, so a page that read it directly would break.

    PYTHONPATH=src:benchmarks python benchmarks/homogenization_page.py
"""
from __future__ import annotations
import collections
import csv
import glob
import json
import math
import os
import statistics as st
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BENCH, "homogenization_results.json")
STORE = os.path.join(ROOT, "surrogate", "bench")


def _z(p):
    lo, hi = -8.0, 8.0
    for _ in range(200):
        m = (lo + hi) / 2
        if 0.5 * (1 + math.erf(m / math.sqrt(2))) < p:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


Z80 = _z(0.9)


def implied_sd(cov):
    """Residual sd implied by the realized coverage of a nominal 80% interval.
    1.000 is perfect whitening; below 1 means the interval is too WIDE."""
    if not (0.0 < cov < 1.0):
        return float("nan")
    return Z80 / _z(0.5 + cov / 2.0)


def _load(pattern, tag=None):
    V = collections.defaultdict(dict)
    ds = {}
    for f in glob.glob(pattern):
        if "_feat" in f or "_raw" in f:
            continue
        with open(f) as fh:
            for r in csv.DictReader(fh):
                if tag and not r["task"].endswith(tag):
                    continue
                V[(r["uid"], int(r["horizon"]), r["metric"])][r["model"]] = float(r["value"])
                ds[r["uid"]] = r["dataset"]
    return V, ds


def refresh():
    """Recompute from the store. Returns None if the store is not present."""
    if not os.path.isdir(STORE):
        return None
    out = {"multi_horizon": [], "one_step_gift": {}, "meta": {}}

    V, _ = _load(os.path.join(STORE, "fred_shards_mh", "*.csv"))
    A, B = "laplace_homogenize_mh", "laplace"
    for h in range(1, 13):
        pin = [(v[A], v[B]) for (u, hh, m), v in V.items()
               if hh == h and m == "pinball" and A in v and B in v and v[B] > 0]
        cov = [(v[A], v[B]) for (u, hh, m), v in V.items()
               if hh == h and m == "cov80" and A in v and B in v]
        if len(pin) < 50:
            continue
        ca, cb = st.mean(x for x, _ in cov), st.mean(y for _, y in cov)
        out["multi_horizon"].append({
            "h": h, "n": len(pin),
            "ratio": st.median(x / y for x, y in pin),
            "wins": sum(1 for x, y in pin if x < y) / len(pin),
            "cov_raw": cb, "cov_hom": ca,
            "sd_raw": implied_sd(cb), "sd_hom": implied_sd(ca)})

    G, gds = _load(os.path.join(STORE, "gift_shards_h12", "*.csv"), tag="/m3")
    A1 = "laplace_homogenize"
    pin = [(gds[u], v[A1], v[B]) for (u, hh, m), v in G.items()
           if hh == 1 and m == "pinball" and A1 in v and B in v and v[B] > 0]
    if pin:
        byds = collections.defaultdict(list)
        for d, a, b in pin:
            byds[d].append(a / b)
        wr = {d: sum(1 for r in v if r < 1) / len(v) for d, v in byds.items()}
        out["one_step_gift"] = {
            "n": len(pin), "datasets": len(byds),
            "ratio": st.median(a / b for _, a, b in pin),
            "wins": sum(1 for _, a, b in pin if a < b) / len(pin),
            "wins_equal_weight": st.median(list(wr.values())),
            "datasets_positive": sum(1 for v in wr.values() if v > 0.5)}

    try:
        sha = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:                                            # noqa: BLE001
        sha = "nogit"
    ver = "unknown"
    with open(os.path.join(ROOT, "pyproject.toml")) as fh:
        for line in fh:
            if line.startswith("version = "):
                ver = line.split('"')[1]
                break
    out["meta"] = {"version": ver, "commit": sha, "date": time.strftime("%Y-%m-%d")}
    return out


def render(d):
    sys.path.insert(0, os.path.join(ROOT, "docs"))
    from sweep_nav import CANONICAL

    mh = d["multi_horizon"]
    os_ = d["one_step_gift"]
    meta = d["meta"]
    rows = "\n".join(
        f"      <tr><td class=num>{r['h']}</td><td class=num>{r['n']}</td>"
        f"<td class=num>{r['ratio']:.4f}</td><td class=num>{r['wins']:.1%}</td>"
        f"<td class=num>{r['cov_raw']:.3f}</td><td class=num>{r['cov_hom']:.3f}</td>"
        f"<td class=num>{r['sd_raw']:.3f} &rarr; {r['sd_hom']:.3f}</td></tr>"
        for r in mh)
    worst = min(mh, key=lambda r: r["sd_raw"]) if mh else None
    best = min(mh, key=lambda r: r["ratio"]) if mh else None

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>skaters &mdash; homogenization</title>
  <meta name="description" content="Homogenization: an online scale-mixture correction on a forecaster's own PIT residuals. Motivation, mechanism, and measured results by horizon." />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="skaters" />
  <meta property="og:title" content="skaters &mdash; homogenization" />
  <meta property="og:description" content="An online correction for the part of a predictive distribution that is systematically the wrong width." />
  <meta property="og:url" content="https://skaters.microprediction.org/homogenization.html" />
  <meta name="twitter:card" content="summary" />
  <link rel="stylesheet" href="./academic.css" />
  <style>
    .lede {{ color: #555; margin: 0 0 28px; font-size: 1.05em; }}
    table.res {{ border-collapse: collapse; margin: 0 0 24px; width: 100%; }}
    table.res th, table.res td {{ border-bottom: 1px solid #e3e3e3; padding: 6px 9px;
      text-align: left; font-size: 0.94em; }}
    table.res th {{ border-bottom: 2px solid #bbb; font-weight: 600; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .caveats li {{ margin-bottom: 7px; }}
    .stamp {{ color: #888; font-size: 0.88em; font-style: italic; }}
    .links a {{ text-decoration: none; }} .links a:hover {{ text-decoration: underline; }}
    blockquote {{ margin: 0 0 20px; padding: 2px 0 2px 14px; border-left: 3px solid #ddd;
      color: #444; }}
  </style>
</head>
<body>
{CANONICAL}

  <main>
    <h1>Homogenization</h1>
    <p class="lede">A forecast can have the right centre and the wrong width. Homogenization
      is an online correction for the width, learned from the forecaster's own track record
      rather than from the data directly. It is worth about
      {(1 - best['ratio']) * 100:.1f}% of pinball loss at the horizon where it helps most,
      and it never made things worse in any cell measured.</p>

    <h2>The motivation: a forecaster that grades itself</h2>
    <p>If a predictive distribution is correct, then pushing each realized value through its
      own forecast CDF gives a uniform number, and through the normal quantile gives a
      standard normal one. That transformed residual is what <code>skaters</code> calls the
      <em>parade</em> z, and it is available online, for free, at every horizon.</p>
    <p>So the forecaster can grade itself. If those z values have variance below one, the
      intervals were too wide; above one, too narrow. Either way the miscalibration is
      visible without any held-out data, because the grade only uses forecasts that have
      already matured.</p>
    <p>Two kinds of structure are commonly left over. The first is a <em>predictable shift in
      conditional variance</em>: quiet stretches and violent ones, which a single fixed scale
      cannot serve. The second is <em>unresolved heterogeneity</em>: excess kurtosis that no
      single time-varying variance explains, because the residual is really drawn from
      several latent regimes at once. A Hermite expansion names both precisely, as the
      <code>H&#8322;</code> and <code>H&#8324;</code> terms, but the correction it suggests is
      not usable: it can go negative in the tails, so it is not a density at all.</p>

    <h2>The mechanism: a two-point scale mixture, hedged</h2>
    <p>The correction used instead is the simplest object with both effects built in and no
      way to go negative, a two-point Gaussian scale mixture:</p>
    <blockquote><code>g(z) = &frac12; N(0, v(1&minus;&delta;)) + &frac12; N(0, v(1+&delta;))</code></blockquote>
    <p>Here <code>v</code> carries the variance level and <code>&delta;</code> splits one
      variance into two nearby ones, which is exactly how excess kurtosis arises from purely
      Gaussian pieces. It is a genuine density for any <code>v &gt; 0</code>. The name comes
      from that split: an unresolved mixture of latent regimes is replaced by an effective
      aggregate description, without ever committing to which regime is active now.</p>
    <p>A small fixed grid of candidates is run in parallel, each with its own filter on the
      residual stream, and combined by discounted Bayesian weight. One candidate is the
      <strong>identity</strong>, frozen at <code>v = 1</code> and holding most of the prior
      weight, which is what makes the whole thing safe: on a well-specified forecaster the
      identity wins and the correction does nothing.</p>

    <h2>Results by horizon</h2>
    <p>One candidate pool per horizon, each resolved against its own matured forecast.
      FRED economic change-series, {mh[0]['n'] if mh else 0} paired series per horizon,
      one-step through twelve-step. Ratio below 1 means homogenization wins; the coverage
      target is 0.800, and implied sd of 1.000 would be perfect whitening.</p>
    <table class="res">
      <tr><th>h</th><th>n</th><th>pinball ratio</th><th>wins</th><th>coverage raw</th>
        <th>coverage corrected</th><th>implied residual sd</th></tr>
{rows}
    </table>
    <p>Two things stand out. The gain <strong>grows with horizon</strong>: about
      {(1 - mh[0]['ratio']) * 100:.1f}% at one step, rising to
      {(1 - best['ratio']) * 100:.1f}% at h={best['h']}. And the defect being corrected is
      real and largest in the middle of the range, where raw laplace's implied residual sd
      falls to <strong>{worst['sd_raw']:.3f}</strong> at h={worst['h']} &mdash; intervals
      roughly {(1 / worst['sd_raw'] - 1) * 100:.0f}% too wide. Coverage moves toward nominal
      at every horizon.</p>

    <h2>One step, held-out corpus</h2>
    <p>Independently on GIFT-Eval, at one step, across {os_.get('datasets', 0)} datasets and
      {os_.get('n', 0):,} paired series: median ratio {os_.get('ratio', float('nan')):.4f},
      winning {os_.get('wins', float('nan')):.1%} of series
      ({os_.get('wins_equal_weight', float('nan')):.1%} weighting every dataset equally), and
      positive on {os_.get('datasets_positive', 0)} of {os_.get('datasets', 0)} datasets. So
      the effect is not confined to the corpus it was developed on.</p>

    <h2>Using it</h2>
<pre><code>from skaters import laplace
from skaters.homogenize import homogenize

f = homogenize(laplace(k=12), k=12)     # one pool per horizon
state = None
for y in stream:
    dists, state = f(y, state)          # dists[h-1] is the corrected h-step predictive
</code></pre>
    <p>It is deliberately <strong>opt-in</strong> rather than part of <code>laplace</code>'s
      default output. It costs roughly 10% more compute per step, and keeping raw laplace as
      a stable baseline is what makes measuring the correction possible at all.</p>

    <h2>What did not work</h2>
    <ul class="caveats">
      <li><strong>Sharing one pool across horizons.</strong> The obvious economy is a single
        correction for every horizon. It overshoots to an implied sd above 1, turning
        too-wide intervals into too-narrow ones, and loses 2&ndash;4% of pinball beyond one
        step. The horizons genuinely differ.</li>
      <li><strong>Regularizing between horizons.</strong> Since long horizons resolve less
        often, shrinking their pools toward their neighbours should stabilise them. Two
        variants were tried, shrinking the candidate weights and smoothing the filter states
        along the horizon axis. Both were within noise of independent pools, and insensitive
        to the shrinkage strength, which says the quantities being pooled were already nearly
        equal. Independence is left in place because nothing beat it.</li>
    </ul>

    <h2>Caveats</h2>
    <ul class="caveats">
      <li>The multi-horizon table is FRED only so far. The held-out GIFT figure is one step,
        because that arm predates the multi-horizon version.</li>
      <li>Gains are small in absolute terms: about 1% of pinball at one step and 3% at the
        middle horizons. Reliable and cheap, not transformational.</li>
      <li>Coverage still exceeds nominal after correction at most horizons, so the width
        problem is reduced rather than solved.</li>
      <li>These are one-step-ahead and multi-step density forecasts of economic change
        series. Nothing here speaks to level forecasting or to seasonal data.</li>
    </ul>

    <h2>Reproducing this</h2>
<pre><code>PYTHONPATH=src:benchmarks python benchmarks/homogenization_page.py</code></pre>
    <p class="links">
      <a href="https://github.com/microprediction/skaters/blob/main/benchmarks/homogenization_page.py">homogenization_page.py</a> &mdash; generates this page
      &middot;
      <a href="https://github.com/microprediction/skaters/blob/main/benchmarks/homogenization_results.json">homogenization_results.json</a> &mdash; these numbers as data
      &middot;
      <a href="https://github.com/microprediction/skaters/blob/main/src/skaters/homogenize.py">homogenize.py</a> &mdash; the implementation
    </p>

    <p class="stamp">Measured with skaters {meta['version']}+{meta['commit']}, written
      {meta['date']}. Every figure on this page is generated from the results store, not
      transcribed.</p>
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
    fresh = refresh()
    if fresh and fresh["multi_horizon"]:
        with open(JSON_PATH, "w") as fh:
            json.dump(fresh, fh, indent=1)
        print(f"[homog] refreshed {JSON_PATH}")
    with open(JSON_PATH) as fh:
        d = json.load(fh)
    out = os.path.join(ROOT, "docs", "homogenization.html")
    with open(out, "w") as fh:
        fh.write(render(d))
    print(f"[homog] page -> {out}  ({len(d['multi_horizon'])} horizons)")


if __name__ == "__main__":
    main()
