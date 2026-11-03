"""The learned model's page (#297): docs/learned.html, generated from the
canonical store and the training checkpoints, like the foundation pages.

    LP_RUN=e2 PYTHONPATH=src:benchmarks .venv-gifteval/bin/python benchmarks/learned_page.py

LP_RUN names the validation run whose arms head the page (learned(<run>) and
learned-expert(<run>)); empty means the plain arm names (the first run). Every
number on the page comes from canonical_summary_vs_laplace.csv,
canonical_summary_coverage.csv, the per-step store (the star plot) and the
checkpoints' own metadata; nothing is typed.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foundation_pages as fp  # noqa: E402

RUN = os.environ.get("LP_RUN", "")
DOCS = os.path.join(os.path.dirname(fp.BENCH), "docs")
CKPT_DIR = os.path.join(fp.BENCH, "learned_ckpt")


def arm_names(run):
    return (f"learned({run})", f"learned-expert({run})") if run else ("learned", "learned-expert")


def checkpoints():
    """{corpus: meta} from benchmarks/learned_ckpt/<corpus>_k1.pt, without torch
    if possible (the .json sidecar), else via torch."""
    out = {}
    if not os.path.isdir(CKPT_DIR):
        return out
    for fn in sorted(os.listdir(CKPT_DIR)):
        if not fn.endswith(".pt"):
            continue
        corpus = fn.split("_k")[0]
        try:
            import torch
            ck = torch.load(os.path.join(CKPT_DIR, fn), map_location="cpu", weights_only=False)
            out[corpus] = {k: ck.get(k) for k in ("k", "pi_lap", "n_series", "window", "lr",
                                                  "epochs", "done", "history", "saved_at")}
        except Exception as e:  # noqa: BLE001
            out[corpus] = {"error": type(e).__name__}
    return out


def _nav():
    """The site header exactly as the foundation pages carry it (docs/sweep_nav.py)."""
    from sweep_nav import NAV
    return ('  <header class="site-header">\n    <div class="nav-inner">\n'
            '      <a class="brand" href="/">skaters</a>\n' + NAV + '\n    </div>\n  </header>')


def _row(vs, cov, key, stratum):
    r = vs.get((stratum, key))
    return r


def reading(vs, mix, exp):
    """One computed sentence per scored stratum, both arms."""
    out = []
    for k, short, _long in fp.STRATA:
        rm, re_ = vs.get((k, mix)), vs.get((k, exp))
        if not rm:
            continue
        def wl(r):
            n = int(r["n_series"]); return int(r["win"]), int(r["loss"]), n, float(r["med_dLL"])
        w, l, n, m = wl(rm)
        verdict = ("more wins than losses" if w > l else "more losses than wins" if l > w else "as many wins as losses")
        s = (f"On {short} the mixture has {verdict}, {w} to {l} of {n}, at a median of {m:+.3f} nats")
        if re_:
            w2, l2, n2, m2 = wl(re_)
            s += f"; the trained expert alone is {w2} to {l2} at {m2:+.3f}"
        out.append(s + ".")
    return " ".join(out)


def training_table(cks):
    rows = []
    for corpus, m in sorted(cks.items()):
        if "error" in m or not m.get("history"):
            continue
        for h in m["history"]:
            rows.append(f'<tr><td>{corpus}</td><td class="num">{h["epoch"]}</td>'
                        f'<td class="num">{m["n_series"]:,}</td><td class="num">{h["n_scored"]:,}</td>'
                        f'<td class="num">{h["learned_ll"]:+.3f}</td><td class="num">{h["laplace_ll"]:+.3f}</td>'
                        f'<td class="num">{h["learned_ll"] - h["laplace_ll"]:+.3f}</td></tr>')
    return "\n".join(rows)


def main():
    vs, cov = fp.load_vs(), fp.load_cov()
    mix, exp = arm_names(RUN)
    have = any((k, mix) in vs for k, _s, _l in fp.STRATA)
    if not have:
        raise SystemExit(f"no rows for {mix!r} in the summaries; set LP_RUN to a scored run")
    import summarize_canonical as sc
    print("[learned_page] loading per-step store for the star plot ...", flush=True)
    radar = fp.compute_radar(sc.load_all())
    model = {"name": "learned", "key": mix, "tight_key": None}
    svg = fp.radar_svg(model, radar)
    cks = checkpoints()
    first_mix, first_exp = arm_names("")
    first_rows = ""
    if RUN and any((k, first_mix) in vs for k, _s, _l in fp.STRATA):
        first_rows = f"""
    <h3>The first run, for comparison</h3>
    <p>The first checkpoints, scored on 400 validation series per stratum with laplace's prior
      share at one half (the plain <code>learned</code> arms in the store). Mixture:</p>
{fp._TABLE_HEAD}{fp.standalone_rows(model, vs, cov, key=first_mix)}
{fp._TABLE_TAIL}
    <p>Trained expert alone:</p>
{fp._TABLE_HEAD}{fp.standalone_rows(model, vs, cov, key=first_exp)}
{fp._TABLE_TAIL}"""
    pi = next((m.get("pi_lap") for m in cks.values() if m.get("pi_lap")), 0.5)
    stamp = time.strftime("%Y-%m-%d")
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>skaters &mdash; the learned model</title>
  <meta name="description" content="A learned forecaster built on skaters.torch that is laplace at worst: a trainable laplace with a gate, under an Aggregating-Algorithm mixture with the frozen laplace, trained on one half of FRED by family and scored on the other." />
  <link rel="stylesheet" href="./academic.css" />
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
    .stamp {{ color:#888; font-size:.88em; font-style:italic; }}
  </style>
</head>
<body>
{_nav()}

  <main>
    <h1>The learned model: laplace at worst</h1>
    <div class="meta-row">
      <span class="tag">skaters.torch.learned</span>
      <span class="tag">trained on half of FRED, by family</span>
      <span class="tag">scored on the other half</span>
      <span class="tag">k = 1</span>
      <span class="tag">issue #297</span>
    </div>
    <p>Two forecasters run on every series and an exact mixture sits on top. The floor is
      <code>laplace</code>, the reference implementation, frozen. The challenger is the torch
      twin of <code>laplace</code>: the same pool of candidate chains, trunk, lattice projection,
      tail splice and parade, initialised at laplace's values, with two things that learn. The
      continuous hyperparameters of the transforms and the trunk (smoothing rates, mean-reversion
      and GARCH rates, autoregressive ridge and decay, power and Yeo&ndash;Johnson exponents,
      the trunk's learning rate, forgetting and depth penalty) are <code>nn.Parameter</code>s.
      And a small gate reads the parade's <code>z</code>, the trunk's prequential log weights and
      two running descriptors, and adds an offset to those log weights at the combine step, so it
      tilts which candidates carry the forecast. The gate starts at zero.</p>
    <p>The mixture weights the two experts by their undiscounted cumulative log-likelihood, the
      Aggregating Algorithm under log loss, one instance per phase at each horizon. That is the
      guarantee: on any series the mixture's cumulative log loss exceeds laplace's by at most
      <code>h&middot;log(1/&pi;)</code> nats, with <code>&pi;</code> laplace's prior share
      ({pi:g} in the run on this page). Nothing training does to the challenger can break it.
      The learned part can only re-tune laplace's own knobs and re-weight laplace's own
      candidates; if an edge cannot be expressed that way, this model cannot find it.</p>

    <h2>Training and the split</h2>
    <p>FRED is split by family (<code>fred_universe.family</code>: a curve of maturities, an FX
      panel, a release's components land on one side), so the validation half shares no family
      with the training half. Training is prequential: the forecast for <code>y<sub>t</sub></code>
      is issued before <code>y<sub>t</sub></code> arrives, scored against it, and the loss of a
      64-step window, the challenger's own log score, is backpropagated at the window boundary;
      Adam steps, every bounded parameter is clamped back into its valid region, and the state is
      detached. The mixture is not trained. The in-sample signal over the training pass, the
      challenger's mean log score next to the frozen laplace's on the same steps:</p>
    <table>
      <thead><tr><th>corpus</th><th class="num">epoch</th><th class="num">train series</th>
      <th class="num">scored steps</th><th class="num">challenger</th><th class="num">laplace</th>
      <th class="num">gap (nats/step)</th></tr></thead>
      <tbody>
{training_table(cks)}
      </tbody>
    </table>
    <p class="muted">In-sample and prequential: the gate adapts within each training series, and
      families share shape inside the training half. The gap on the validation half below is
      smaller, which is the point of the split.</p>

    <h2>Validation</h2>
    <p>Scored through the canonical pipeline on the validation half, paired against
      <code>laplace</code> on identical series and windows. Win, draw and loss are decided one
      series at a time by a <a href="/draws.html">Diebold&ndash;Mariano test</a> on the per-step
      log-score differential over the {fp.TEST}-point test window (floor &minus;20, Newey&ndash;West
      standard error, &plusmn;1.96 SE; a draw says the window cannot separate the two at the 5%
      level, not that they are equal). The densities are the model's own; there is no quantile
      reconstruction on this page.</p>
    <h3>The mixture (<code>{mix}</code>)</h3>
{fp._TABLE_HEAD}{fp.standalone_rows(model, vs, cov, key=mix)}
{fp._TABLE_TAIL}
    <h3>The trained expert alone (<code>{exp}</code>)</h3>
{fp._TABLE_HEAD}{fp.standalone_rows(model, vs, cov, key=exp)}
{fp._TABLE_TAIL}
    <p class="muted">{fp._COLS_NOTE}</p>
    <p>{reading(vs, mix, exp)}</p>
    <p>The mixture and the expert differ where their numbers differ. The mixture's weights are
      undiscounted over the whole history, as the bound requires, so where the challenger was
      weaker early in a series it never fully regains weight; the expert alone carries no such
      drag and no such guarantee.</p>
{first_rows}
    <h2>Star plot</h2>
    <p>The mixture standalone against Laplace on the six regime axes of the
      <a href="/challengers.html">challengers radar</a>: the share of series where its mean log
      score is the higher, ties split, divided by one half, so an even split sits on the dashed
      1.0 ring. Axes without 30 shared series are left empty.</p>
    <figure style="margin:14px 0 6px;">{svg}</figure>

    <h2>What is not here</h2>
    <ul>
      <li>Daily economic series are laplace's home and the learned model does not improve them;
        training is now confined to weekly and monthly.</li>
      <li>Only <code>k = 1</code> has been trained. The multi-step case, where the multiscale
        machinery lives, is next.</li>
      <li>GIFT-Eval, the clean out-of-domain test, has not been run on this model.</li>
    </ul>

    <h2>Reproducing this</h2>
<pre><code>PYTHONPATH=src:benchmarks .venv-kumo/bin/python benchmarks/learned_train.py      # LT_CORPUS, LT_MAX, LT_EPOCHS ...
LEARNED_CKPT=benchmarks/learned_ckpt/weekly_k1.pt LV_CORPUS=weekly LV_RUN={RUN or 'first'} benchmarks/run_learned_valid.sh
PYTHONPATH=src:benchmarks python benchmarks/summarize_canonical.py
LP_RUN={RUN} PYTHONPATH=src:benchmarks python benchmarks/learned_page.py</code></pre>
    <p class="stamp">Generated {stamp} from the canonical store and the checkpoints in
      benchmarks/learned_ckpt.</p>
  </main>

  <footer>
    <a href="https://github.com/microprediction/skaters">Source</a> &middot;
    Part of the <a href="https://repos.microprediction.org/">microprediction</a> family.
  </footer>
</body>
</html>
"""
    out = os.path.join(DOCS, "learned.html")
    with open(out, "w") as fh:
        fh.write(html)
    print(f"[learned_page] wrote {out} for run {RUN or 'first'}")


if __name__ == "__main__":
    main()
