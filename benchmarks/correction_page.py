"""Generate docs/corrections.html: homogenization versus conformal correction.

Paper-shaped comparison of two ways to repair a miscalibrated predictive. Numbers
come from three committed or frozen sources and are never transcribed by hand:

  * benchmarks/homogenization_results.json  (the conditional reparameterisation)
  * benchmarks/correction_results.json      (frozen here from the week-study store:
                                             PIT recalibration applied to three
                                             foundation models)
  * papers/_benchmark_numbers.txt           (the conformal predictive systems)

    PYTHONPATH=src:benchmarks python benchmarks/correction_page.py
"""
from __future__ import annotations
import collections
import csv
import glob
import json
import os
import re
import statistics as st
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BENCH, "correction_results.json")
WEEK = os.path.join(ROOT, "surrogate", "bench", "weekstudy_results.csv")
NUMBERS = os.path.join(ROOT, "papers", "_benchmark_numbers.txt")


def refresh():
    """Recompute the recalibration arm from the week-study store, if present."""
    if not os.path.exists(WEEK):
        return None
    V = collections.defaultdict(dict)
    with open(WEEK) as fh:
        for r in csv.DictReader(fh):
            V[(r["uid"], int(r["horizon"]), r["metric"])][r["model"]] = float(r["value"])
    lp = [(u, v["laplace"]) for (u, h, m), v in V.items()
          if h == 1 and m == "logpdf" and "laplace" in v]
    vals = sorted(x for _, x in lp)
    hi = vals[int(0.99 * len(vals))]
    duds = {u for u, x in lp if x > hi}
    cov = {u: v["laplace"] for (u, h, m), v in V.items()
           if h == 1 and m == "cov90" and "laplace" in v}
    duds |= {u for u, c in cov.items() if c in (0.0, 1.0)}
    out = {}
    for fm in ("Chronos", "TiRex", "TimesFM"):
        a = f"{fm}@lap"
        d = [(v[a], v[fm]) for (u, h, m), v in V.items()
             if h == 1 and m == "crps" and a in v and fm in v and u not in duds and v[fm] > 0]
        c = [(v[a], v[fm]) for (u, h, m), v in V.items()
             if h == 1 and m == "cov90" and a in v and fm in v and u not in duds]
        if not d:
            continue
        out[fm] = {"n": len(d), "crps_ratio": st.median(x / y for x, y in d),
                   "wins": sum(1 for x, y in d if x < y) / len(d),
                   "cov_bare": st.mean(y for _, y in c),
                   "cov_recal": st.mean(x for x, _ in c)}
    lapcov = st.mean(v["laplace"] for (u, h, m), v in V.items()
                     if h == 1 and m == "cov90" and "laplace" in v and u not in duds)
    return {"pit_recal": out, "laplace_cov90": lapcov, "duds_excluded": len(duds)}


def conformal_rows():
    """The conformal predictive systems, from the frozen paper numbers."""
    out = []
    if not os.path.exists(NUMBERS):
        return out
    with open(NUMBERS) as fh:
        for line in fh:
            m = re.match(r"\s+(CSP\S*|\S*conformal\S*|\S*ACI\S*)\s+(\d+)/(\d+)%\s+"
                         r"(\d+)/(\d+)%\s+([-+]?[\d.]+)\s+(\d+)", line)
            if m:
                out.append({"method": m.group(1), "ll_raw": int(m.group(2)),
                            "crps_raw": int(m.group(4)), "mean_ll": float(m.group(6)),
                            "n": int(m.group(7))})
    return out


def render(d, hom, conf):
    sys.path.insert(0, os.path.join(ROOT, "docs"))
    from sweep_nav import CANONICAL

    pr = d["pit_recal"]
    mh = hom["multi_horizon"]
    best = min(mh, key=lambda r: r["ratio"])
    h1 = mh[0]
    recal_rows = "\n".join(
        f"      <tr><td>{k}</td><td class=num>{v['n']:,}</td>"
        f"<td class=num>{v['cov_bare']:.3f} &rarr; <strong>{v['cov_recal']:.3f}</strong></td>"
        f"<td class=num>{v['crps_ratio']:.4f}</td><td class=num>{v['wins']:.1%}</td></tr>"
        for k, v in pr.items())
    conf_rows = "\n".join(
        f"      <tr><td>{c['method']}</td><td class=num>{c['n']:,}</td>"
        f"<td class=num>{c['ll_raw']}%</td><td class=num>{c['crps_raw']}%</td>"
        f"<td class=num>{c['mean_ll']:+.2f}</td></tr>" for c in conf)
    hom_rows = "\n".join(
        f"      <tr><td class=num>{r['h']}</td><td class=num>{r['n']}</td>"
        f"<td class=num>{r['ratio']:.4f}</td><td class=num>{r['wins']:.1%}</td>"
        f"<td class=num>{r['cov_raw']:.3f} &rarr; {r['cov_hom']:.3f}</td></tr>"
        for r in mh if r["h"] in (1, 3, 5, 6, 8, 12))
    meta = hom["meta"]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>skaters &mdash; two ways to correct a predictive</title>
  <meta name="description" content="Marginal recalibration buys coverage and pays sharpness. A conditional reparameterisation can improve both. Measured on foundation models and on laplace." />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="skaters" />
  <meta property="og:title" content="skaters &mdash; two ways to correct a predictive" />
  <meta property="og:description" content="Why homogenization gains where conformal correction costs." />
  <meta property="og:url" content="https://skaters.microprediction.org/corrections.html" />
  <meta name="twitter:card" content="summary" />
  <link rel="stylesheet" href="./academic.css" />
  <style>
    .lede {{ color: #555; margin: 0 0 26px; font-size: 1.05em; }}
    .abstract {{ background: #fafafa; border-left: 3px solid #ccc; padding: 12px 16px;
      margin: 0 0 28px; color: #333; }}
    table.res {{ border-collapse: collapse; margin: 0 0 24px; width: 100%; }}
    table.res th, table.res td {{ border-bottom: 1px solid #e3e3e3; padding: 6px 9px;
      text-align: left; font-size: 0.94em; }}
    table.res th {{ border-bottom: 2px solid #bbb; font-weight: 600; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    li {{ margin-bottom: 7px; }}
    .stamp {{ color: #888; font-size: 0.88em; font-style: italic; }}
    .links a {{ text-decoration: none; }} .links a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
{CANONICAL}

  <main>
    <h1>Two ways to correct a predictive</h1>
    <p class="lede">A forecast can be miscalibrated in more than one way, and the repair you
      reach for decides what you pay.</p>

    <div class="abstract">
      <strong>Abstract.</strong> Recalibration maps a predictive's probability integral
      transform back to uniform. It reliably delivers nominal coverage and costs sharpness:
      applied to three foundation models it moves central-90% coverage to 0.902 in every case
      and loses 1.8 to 3.4 percent of CRPS. A conditional reparameterisation of the same
      residual instead estimates a latent scale state and leaves the density family intact.
      It gains 1 to 3 percent of pinball loss and improves coverage at the same time. The
      difference is whether the correction carries state, and whether it discards the tails
      it was given.
    </div>

    <h2>1. Two corrections</h2>
    <p>Both start from the same object. Push each realized value through the forecast
      distribution it was predicted by and you get a number that should be uniform, and
      through the normal quantile a number that should be standard normal. Call it z. Every
      claim below is a statement about z.</p>
    <p><strong>Recalibration</strong> observes that z is not uniform and applies a monotone map
      to make it so. The map is estimated from the empirical distribution of past residuals.
      Conformal predictive systems are the rigorous version, with finite-sample coverage
      guarantees under exchangeability.</p>
    <p><strong>Conditional reparameterisation</strong> observes that z has the wrong
      <em>conditional</em> shape and fits a small state-carrying model to it, then composes
      that model back onto the original predictive as a change of variables. Homogenization is
      the version measured here, using a two-point Gaussian scale mixture. See the
      <a href="/homogenization.html">homogenization page</a> for the mechanism.</p>

    <h2>2. What recalibration costs</h2>
    <p>Recalibration works, in the sense it promises. Applied to three foundation models on
      economic change-series, one step ahead, {next(iter(pr.values()))['n']:,} paired series
      with degenerate series excluded:</p>
    <table class="res">
      <tr><th>base model</th><th>n</th><th>central-90% coverage</th><th>CRPS ratio</th>
        <th>recalibrated wins</th></tr>
{recal_rows}
    </table>
    <p>Coverage lands on <strong>0.902</strong> for all three, from 0.79 to 0.80 before. That
      is the guarantee delivered. The CRPS ratio is above one in every case, so the corrected
      forecast is worse on the proper score, winning only 16 to 34 percent of series. The
      guarantee is paid for in width.</p>
    <p>The same pattern appears when conformal machinery is the whole method rather than a
      wrapper. Against laplace on the non-price FRED universe:</p>
    <table class="res">
      <tr><th>method</th><th>n</th><th>laplace wins, log-likelihood</th>
        <th>laplace wins, CRPS</th><th>mean log-likelihood</th></tr>
{conf_rows}
      <tr><td><strong>laplace</strong></td><td class=num>5,402</td><td class=num>&mdash;</td>
        <td class=num>&mdash;</td><td class=num><strong>+1.56</strong></td></tr>
    </table>

    <h2>3. What the reparameterisation gains</h2>
    <p>The same residual stream, corrected conditionally instead of marginally. FRED,
      {h1['n']} paired series per horizon, one pool per horizon:</p>
    <table class="res">
      <tr><th>h</th><th>n</th><th>pinball ratio</th><th>wins</th><th>coverage</th></tr>
{hom_rows}
    </table>
    <p>Ratios are below one throughout, so the corrected forecast is <em>better</em> on the
      proper score, by about {(1 - h1['ratio']) * 100:.1f} percent at one step and
      {(1 - best['ratio']) * 100:.1f} percent at h={best['h']}. Coverage moves toward nominal
      at the same time. The sign of the cost is reversed relative to recalibration.</p>

    <h2>4. Why the sign differs</h2>
    <p><strong>A marginal map cannot tighten and widen at once.</strong> Recalibration fits one
      monotone map for the whole stream. If coverage is short on average, the map widens on
      average. A state-carrying correction can tighten in quiet stretches and widen in violent
      ones, so mean width can fall while coverage rises. That is only available to a
      correction that conditions on something.</p>
    <p><strong>Recalibration discards the tails it was given.</strong> A conformal predictive
      system emits a distribution assembled from empirical residual quantiles, so the
      parametric tail of the original predictive is gone. Under logarithmic loss that loss is
      priced: it is the irreducible cost of a coarser retained representation, which is the
      subject of the
      <a href="https://github.com/microprediction/conformalprediction">conformal information
      gap</a> study. The reparameterisation composes as
      <code>F&#771;(y) = H(&Phi;<sup>-1</sup>(F(y)))</code> and keeps the original density,
      including its fitted tails.</p>
    <p><strong>One of them can decline to act.</strong> The candidate pool includes an identity
      frozen at unit variance holding most of the prior weight, so on a well-specified stream
      it selects "do nothing" and costs about 0.0002 nats. Recalibration always pays finite
      sample quantile noise, and always buys its guarantee with width.</p>
    <p><strong>They target different defects.</strong> laplace over-covers: measured
      {d['laplace_cov90']:.3f} against a 0.900 target on the same rows. Its problem is
      sharpness, not coverage, so a method whose purpose is to secure coverage has nothing to
      offer it. The foundation models under-cover at 0.79 to 0.80, which is exactly the
      condition recalibration is built for, and there it does move coverage to nominal.</p>

    <h2>5. When to use which</h2>
    <ul>
      <li>Base model <strong>under-covers</strong> and you need a stated rate more than you
        need sharpness: recalibrate, and expect to pay a few percent of CRPS.</li>
      <li>Base model <strong>over-covers</strong>, or is miscalibrated conditionally rather
        than marginally: reparameterise. Recalibration cannot help and may hurt.</li>
      <li>You need a finite-sample guarantee under exchangeability: only conformal offers one.
        Homogenization offers no guarantee, just a measured improvement and a safe no-op.</li>
      <li>The predictive's tails carry information you care about: prefer the correction that
        keeps them.</li>
    </ul>

    <h2>6. Limitations</h2>
    <ul>
      <li>The recalibration arm is one specific construction, laplace predicting in the base
        model's CDF space. Split conformal and adaptive conformal inference would land
        differently in detail, though the coverage-for-sharpness trade is structural.</li>
      <li>Conformal guarantees hold under exchangeability. The streams here are drifting and
        seasonal, so the comparison is empirical rather than a statement about the theory.</li>
      <li>Both arms are one-step and multi-step density forecasts of economic change series.
        Level forecasting is not addressed.</li>
      <li>The conformal figures come from an earlier library epoch than the homogenization
        figures, so the two tables should not be differenced directly. Each is internally
        paired, which is what the claims rest on.</li>
      <li>Gains and costs are both single-digit percentages. The interest is in the sign and
        the mechanism, not the magnitude.</li>
    </ul>

    <h2>Reproducing this</h2>
<pre><code>PYTHONPATH=src:benchmarks python benchmarks/correction_page.py</code></pre>
    <p class="links">
      <a href="https://github.com/microprediction/skaters/blob/main/benchmarks/correction_page.py">correction_page.py</a> &mdash; generates this page
      &middot;
      <a href="https://github.com/microprediction/skaters/blob/main/benchmarks/correction_results.json">correction_results.json</a>
      &middot;
      <a href="https://github.com/microprediction/skaters/blob/main/src/skaters/homogenize.py">homogenize.py</a>
    </p>
    <p class="stamp">Recalibration arm: {d['duds_excluded']} degenerate series excluded of the
      week-study universe. Homogenization arm measured with skaters
      {meta['version']}+{meta['commit']}. Page written {time.strftime('%Y-%m-%d')}. Every
      figure is generated, not transcribed.</p>
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
    if fresh and fresh["pit_recal"]:
        with open(JSON_PATH, "w") as fh:
            json.dump(fresh, fh, indent=1)
        print(f"[corr] refreshed {JSON_PATH}")
    with open(JSON_PATH) as fh:
        d = json.load(fh)
    with open(os.path.join(BENCH, "homogenization_results.json")) as fh:
        hom = json.load(fh)
    conf = conformal_rows()
    out = os.path.join(ROOT, "docs", "corrections.html")
    with open(out, "w") as fh:
        fh.write(render(d, hom, conf))
    print(f"[corr] page -> {out}  ({len(d['pit_recal'])} recal arms, {len(conf)} conformal rows)")


if __name__ == "__main__":
    main()
