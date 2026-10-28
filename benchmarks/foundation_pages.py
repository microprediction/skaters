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
TEST = int(os.environ.get("FM_TEST", 64))   # rolling one-step test window, as foundation_study.TEST

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
    "chronos": dict(name="Chronos", key="Chronos(wide)", tight_key="Chronos", vendor="Amazon",
                    license="Apache-2.0", arms=True,
                    blurb="Chronos tokenizes a series into a fixed vocabulary and "
                          "forecasts it autoregressively, like a language model over "
                          "quantized values.",
                    note="Reused from the earlier foundation study; run zero-shot on the "
                         "one-step change series.",
                    links=[
                        ("GitHub", "https://github.com/amazon-science/chronos-forecasting"),
                        ("Model card", "https://huggingface.co/amazon/chronos-bolt-small"),
                        ("Paper (arXiv 2403.07815)", "https://arxiv.org/abs/2403.07815"),
                    ],
                    arch="Chronos treats forecasting as language modelling. It scales and "
                         "quantises the series into a fixed token vocabulary, trains a "
                         "T5-style transformer on the token sequences with a cross-entropy "
                         "loss, and forecasts by sampling tokens. This study runs the "
                         "Chronos-Bolt variant (chronos-bolt-small), which patches the "
                         "context and emits quantiles directly in a single forward pass "
                         "rather than sampling autoregressively; it is far faster, but its "
                         "log-likelihood is a quantile reconstruction, so read its CRPS as "
                         "the primary signal."),
    "tirex": dict(name="TiRex", key="TiRex(wide)", tight_key="TiRex", vendor="NX-AI",
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
                  arch="TiRex is built on the xLSTM recurrent architecture rather than "
                       "attention, at 35M parameters. It ingests the context and emits nine "
                       "quantiles directly in one pass, and is trained for in-context "
                       "zero-shot forecasting across both short and long horizons. Its small "
                       "size is the notable part: it leads public leaderboards while being "
                       "an order of magnitude smaller than the transformer foundation models.",
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
    "timesfm": dict(name="TimesFM", key="TimesFM(wide)", tight_key="TimesFM", vendor="Google", version="2.5",
                    license="Apache-2.0", arms=True,
                    blurb="TimesFM is a decoder-only, patched time-series transformer; "
                          "we score version 2.5.",
                    note="Run zero-shot with a fixed 128-length context.",
                    links=[
                        ("GitHub", "https://github.com/google-research/timesfm"),
                        ("Paper (arXiv 2310.10688)", "https://arxiv.org/abs/2310.10688"),
                    ],
                    arch="TimesFM is a decoder-only transformer in the style of a language "
                         "model. It splits the context into fixed-length patches, treats "
                         "each patch as a token, and is pretrained on a large corpus of real "
                         "and synthetic series. This study scores version 2.5 (200M "
                         "parameters) with its continuous quantile head, which emits the "
                         "predictive spread directly."),
    "timesfm3": dict(name="TimesFM3", key="TimesFM3(wide)", tight_key="TimesFM3", vendor="Google",
                      license="timesfm-non-commercial-license-v1.0", arms=True,
                      blurb="Google's next TimesFM generation; same decoder-only, "
                            "patched-transformer family as 2.5, scored on the identical "
                            "protocol so the two checkpoints are directly comparable.",
                      note="Run zero-shot with a fixed 128-length context, same as 2.5. "
                           "Research/benchmarking use only under the model's license.",
                      links=[
                          ("GitHub", "https://github.com/google-research/timesfm"),
                          ("Model card", "https://huggingface.co/google/timesfm-3.0-pytorch"),
                      ],
                      arch="Same decoder-only, patched-transformer architecture as TimesFM "
                           "2.5. This study scores the 3.0 checkpoint with its native "
                           "quantile head, under the identical protocol (128-length "
                           "context, one-step change series) used for every other model "
                           "here, so a comparison to the 2.5 numbers on the "
                           "<a href=\"/foundation/timesfm.html\">TimesFM page</a> is "
                           "apples-to-apples."),
    "sundial": dict(name="Sundial", key="Sundial", vendor="Tsinghua (THUML)",
                    license="see model card", arms=False,
                    blurb="Sundial is a generative time-series model; we draw samples "
                          "per step and score the empirical predictive.",
                    note="Run raw only in this study; the collaborative arms were built "
                         "for the three strongest models first.",
                    links=[
                        ("GitHub", "https://github.com/thuml/Sundial"),
                        ("Model card", "https://huggingface.co/thuml/sundial-base-128m"),
                        ("Paper (arXiv 2502.00816)", "https://arxiv.org/abs/2502.00816"),
                    ],
                    arch="Sundial is a decoder-only transformer trained without discrete "
                         "tokenisation. It embeds continuous-valued patches and learns a "
                         "generative TimeFlow head by flow-matching, so instead of a "
                         "parametric density it produces samples of plausible futures. This "
                         "study draws those samples (the base-128m model) and scores their "
                         "empirical predictive; it is pretrained on the trillion-point "
                         "TimeBench corpus."),
    "flowstate": dict(name="FlowState", key="flowstate(wide)", tight_key="flowstate", vendor="IBM",
                      license="research checkpoint (arXiv:2508.05287)", arms=False,
                      blurb="FlowState is a state-space time-series model, loaded via "
                            "IBM's granite-tsfm.",
                      note="Research checkpoint (research use only); run raw. The "
                           "collaborative arms were built for the three strongest "
                           "models first.",
                      links=[
                          ("Model card", "https://huggingface.co/ibm-research/flowstate"),
                          ("Paper (arXiv 2508.05287)", "https://arxiv.org/abs/2508.05287"),
                      ],
                      arch="FlowState pairs a state-space model (SSM) encoder with a "
                           "functional-basis decoder. The decoder is continuous in time, "
                           "which makes the model equivariant to the sampling rate and able "
                           "to forecast at any resolution and horizon without retraining; it "
                           "emits quantiles directly. It is an IBM research checkpoint loaded "
                           "through granite-tsfm."),
    "timestral": dict(name="Timestral", key="Timestral-209M(q21)", tight_key="Timestral-209M",
                      recon="native21", vendor="Mistral AI",
                      version="209M", license="code Apache-2.0; weights Modified MIT",
                      arms=False,
                      blurb="Timestral is Mistral's zero-shot time-series model, released "
                            "15 October 2026 in four sizes; it emits 21 non-crossing "
                            "quantiles per step, from the 1st to the 99th percentile.",
                      note="Run zero-shot on CPU with a fixed 128-length context, "
                           "symmetric averaging and the nonnegativity clip switched off "
                           "(the series are signed changes). The headline row is the 209M "
                           "checkpoint scored on all 21 native levels; the other sizes and "
                           "the nine-decile reconstruction are tabled below.",
                      links=[
                          ("GitHub", "https://github.com/mistralai/timestral"),
                          ("Model card", "https://huggingface.co/mistralai/Timestral-28M"),
                      ],
                      arch="Timestral is a patched transformer with an hourglass encoder, "
                           "trained to emit 21 quantile levels per step with a context of "
                           "up to 32,768 points and support for covariates and multiple "
                           "variates, none of which this univariate study uses. Its 1% and "
                           "99% quantiles are native outputs, so its density needs no "
                           "bandwidth inflation to carry tails. Scored on all 21 levels, the "
                           "123M and 209M are ahead of Laplace at the median on weekly, "
                           "monthly and M4-hourly series, level on price, and a few "
                           "hundredths behind on daily econ, with the same coverage as "
                           "Laplace. On the nine deciles alone it reads like every other "
                           "quantile model, about half a nat behind. Pretraining "
                           "contamination is unchecked.",
                      variants=[
                          ("Timestral-5M(q21)", "5M, 21 levels"),
                          ("Timestral-28M(q21)", "28M, 21 levels"),
                          ("Timestral-123M(q21)", "123M, 21 levels"),
                          ("Timestral-209M(q21)", "209M, 21 levels"),
                          ("Timestral-5M", "5M, nine deciles"),
                          ("Timestral-28M", "28M, nine deciles"),
                          ("Timestral-123M", "123M, nine deciles"),
                          ("Timestral-209M", "209M, nine deciles"),
                      ]),
    "t0gamma": dict(name="t0-gamma", key="t0-gamma(q21)", tight_key="t0-gamma",
                    recon="native21", vendor="The Forecasting Company",
                    version="256M", license="Apache-2.0", arms=False,
                    blurb="t0-gamma is The Forecasting Company's third public t0 checkpoint, "
                          "released 13 October 2026: a 256M-parameter decoder-style patch "
                          "transformer that predicts 21 quantile levels natively and ranks "
                          "first among single zero-shot models on fev-bench and TIME.",
                    note="Run zero-shot on CPU with a fixed 128-length context (four 32-point "
                         "patches) through the direct predict path, with the nonnegativity clip, "
                         "integer snapping and sign-flip averaging switched off and no "
                         "cross-series inference. The headline row is all 21 native levels; the "
                         "nine-decile subset and the vendor's sign-flip averaging are tabled "
                         "below.",
                    links=[
                        ("GitHub", "https://github.com/theforecastingcompany/tfc-t0"),
                        ("Model card", "https://huggingface.co/theforecastingcompany/t0-gamma"),
                        ("Paper (arXiv 2609.24559)", "https://arxiv.org/abs/2609.24559"),
                        ("Release post", "https://www.theforecastingcompany.com/blog/t0-gamma/"),
                    ],
                    arch="t0 is a decoder-style patch transformer built for forecasting with "
                         "covariates and multivariate context, with a 32-step patch and a "
                         "1,024-step native horizon; none of the covariate machinery is used "
                         "here. The paper (arXiv 2609.24559) documents the alpha and beta "
                         "checkpoints; gamma's training recipe is described only in the release "
                         "post. On its native 21 levels it is within 0.1 nats of Laplace on "
                         "daily econ, level on price and weekly, and ahead on monthly and "
                         "M4-hourly, with coverage 0.89 to 0.91. The vendor's sign-flip "
                         "averaging adds about 0.02 nats at twice the runtime. Pretraining "
                         "contamination is unchecked.",
                    variants=[
                        ("t0-gamma(q21)", "21 levels"),
                        ("t0-gamma(q21+sym)", "21 levels, sign-flip averaging"),
                        ("t0-gamma", "nine deciles"),
                    ]),
}

# NAV comes from docs/sweep_nav.py, the single source of truth. This file used
# to hold its own copy and rewrite only the inner <nav>, which is how the site
# ended up serving three different menus simultaneously.
import sys as _sys
_sys.path.insert(0, os.path.join(ROOT, "docs"))
from sweep_nav import NAV                      # noqa: E402


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
    log-likelihood win rate (Laplace = the dashed 1.0 ring, outward beats Laplace
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
             f'six regime axes; the log-likelihood win rate, Laplace on the 1.0 ring.">']
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
    layers = [(model["key"], color, "", "")]
    if model.get("tight_key"):
        layers.append((model["tight_key"], "#8a8a9a", ' stroke-dasharray="6 4"', " (tight nine-decile reconstruction)"))
    for key, col, dash, tag in reversed(layers):
        d = radar.get(key)
        pairs = [(i, v) for i, v in enumerate(d["ll"])] if d else []
        pairs = [(i, v) for i, v in pairs if v is not None]
        if not pairs:
            continue
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, v) for i, v in pairs))
        fill = f'fill="{col}" fill-opacity=".16"' if not dash else 'fill="none"'
        parts.append(f'<polygon points="{pts}" {fill} stroke="{col}" stroke-width="2"{dash}/>')
        for i, v in pairs:
            x, y = pt(i, v)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{col}" '
                         f'stroke="#fff" stroke-width="1.5"><title>{RADAR_AXES[i][0]}: '
                         f'{key} log-likelihood win rate {v:.2f} vs Laplace{tag} '
                         f'(n={d["n"][i]})</title></circle>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------- page builder
def fmt_pct(x):
    return f"{x:.0%}"


def standalone_rows(model, vs, cov, key=None):
    key = key or model["key"]
    rows = []
    for k, _short, long in STRATA:
        r = vs.get((k, key))
        c = cov.get((k, key))
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

_TABLE_HEAD = """    <table>
      <thead><tr><th>stratum</th><th class="num">n</th><th>win / draw / loss vs Laplace</th>
      <th class="num">med &Delta;LL</th><th class="num">CRPS ratio</th>
      <th class="num">cov&#8320;&#8320;</th></tr></thead>
      <tbody>
"""
_TABLE_TAIL = """      </tbody>
    </table>
    <div class="key">
      <span><i style="background:var(--good)"></i>beats Laplace</span>
      <span><i style="background:#c8c8d4"></i>draw</span>
      <span><i style="background:var(--warn)"></i>loses to Laplace</span>
    </div>
"""
_COLS_NOTE = ("Median per-series &Delta; log-likelihood in nats (negative is worse than "
              "Laplace); CRPS ratio to Laplace (above 1 is worse); central-90% coverage "
              "(0.90 target).")


def standalone_tables(model, vs, cov):
    """The headline table on the arm the page is about, then (for quantile
    models) the tight nine-decile reconstruction, each saying what it is."""
    tight = model.get("tight_key")
    if not tight:
        head = (f"<p>{model['name']} issues sample paths rather than quantiles. The arm "
                f"draws 30 samples per step and scores a kernel density on them. That is "
                f"also a reconstruction, with a bandwidth and a sample count behind it, "
                f"and it has not been rescored under a more generous one as the quantile "
                f"models have, so these numbers are a lower bound on the model.</p>")
        return (head + _TABLE_HEAD + standalone_rows(model, vs, cov) + _TABLE_TAIL
                + f'<p style="font-size:.9rem;color:var(--muted)">{_COLS_NOTE}</p>')
    if model.get("recon") == "native21":
        fair = (f"<h3>On the model's native 21 quantile levels</h3>"
                f"<p>Arm <code>{model['key']}</code>: the model's own 1% to 99% quantiles "
                f"through the fixed-bandwidth reconstruction, with no bandwidth inflation. "
                f"The tails are the model's. This is the fairest density the model can be "
                f"given, so it is the headline.</p>")
        fair_note = ("Coverage is that of the reconstruction on the native 21 levels; fed "
                     "a calibrated normal's quantiles it covers about 0.89, so a perfectly "
                     "calibrated model reads 0.89 here.")
    else:
        fair = (f"<h3>Generous reconstruction</h3>"
                f"<p>Arm <code>{model['key']}</code>: the same nine-decile forecasts, "
                f"reconstructed at three times the local bandwidth "
                f"(<code>nozzles.nozzle_wide</code>), the most generous of the "
                f"reconstructions tested in the <a href=\"/papers.html\">benchmark "
                f"paper</a>. The paper found that the tight reconstruction produces most "
                f"of the half-nat gap, so this arm is the headline.</p>")
        fair_note = ("Coverage is that of the wide reconstruction; fed a calibrated "
                     "normal's deciles it covers about 0.88, so a perfectly calibrated "
                     "model reads 0.88 here.")
    tight_block = (f"<h3>Tight nine-decile reconstruction</h3>"
                   f"<p>Arm <code>{tight}</code>: the same forecasts through "
                   f"<code>quantile_dist</code>, the reconstruction the original study used. "
                   f"Fed the exact deciles of a standard normal it covers 0.81, so a "
                   f"perfectly calibrated model reads 0.81 in this coverage column and "
                   f"pays for it in log score. It understates the model and is kept here "
                   f"for comparison with the earlier numbers.</p>")
    return (fair + _TABLE_HEAD + standalone_rows(model, vs, cov, model["key"]) + _TABLE_TAIL
            + f'<p style="font-size:.9rem;color:var(--muted)">{_COLS_NOTE} {fair_note}</p>'
            + tight_block + _TABLE_HEAD + standalone_rows(model, vs, cov, tight) + _TABLE_TAIL
            + f'<p style="font-size:.9rem;color:var(--muted)">{_COLS_NOTE}</p>')


SANDWICH_ARMS = [
    ("+lap", "vincentize with Laplace"),
    ("~lap", "model location, Laplace residual scale"),
    ("@lap", "Laplace on the model's normal scores"),
    ("&amp;lap", "online portfolio with Laplace"),
]


def _wdl_cell(r):
    if not r:
        return '<td class="num">&ndash;</td><td class="num">&ndash;</td>'
    n = int(r["n_series"]) or 1
    return (f'<td class="num">{float(r["med_dLL"]):+.3f}</td>'
            f'<td class="num">{fmt_pct(int(r["loss"]) / n)}</td>')


def combined_section(model, vs, cov):
    base = model["key"]
    have = any(vs.get((k, base + a.replace("&amp;", "&"))) for k, _s, _l in STRATA for a, _ in SANDWICH_ARMS)
    if not have:
        return (f'<h2>Collaborative use</h2>\n<p>The sandwich arms (<code>+lap</code>, '
                f'<code>~lap</code>, <code>@lap</code>, <code>&amp;lap</code>) have not been run on '
                f'{model["name"]}. The sidecar wraps any per-step predictive, so they can be added '
                f'without retraining. See the <a href="/sidecar.html">sidecar pattern</a>.</p>')
    rows, crows = [], []
    for k, _short, long in STRATA:
        raw = vs.get((k, base))
        if not raw:
            continue
        cells = _wdl_cell(raw)
        for a, _ in SANDWICH_ARMS:
            cells += _wdl_cell(vs.get((k, base + a.replace("&amp;", "&"))))
        rows.append(f'<tr><td>{long}</td>{cells}</tr>')
        cr, ca, cp, cl = (cov.get((k, base)), cov.get((k, base + "@lap")),
                          cov.get((k, base + "&lap")), cov.get((k, "laplace")))
        f = lambda c: f'{float(c["cov_central90"]):.3f}' if c else "&ndash;"
        crows.append(f'<tr><td>{long}</td><td class="num">{f(cr)}</td><td class="num">{f(ca)}</td>'
                     f'<td class="num">{f(cp)}</td><td class="num">{f(cl)}</td></tr>')
    heads = "".join(f'<th class="num" colspan="2">{a}</th>' for a, _ in SANDWICH_ARMS)
    sub = "".join('<th class="num">&Delta;LL</th><th class="num">loss</th>' for _ in range(1 + len(SANDWICH_ARMS)))
    legend = "".join(f'<li><code>{a}</code>: {d}.</li>' for a, d in SANDWICH_ARMS)
    return f"""<h2>Collaborative use</h2>
    <p>Four sandwich arms wrap {model['name']}'s own predictive on this same base
      (<code>{base}</code>), each paired with the standalone run on identical series and windows.
      Each cell gives the median per-series &Delta; log-likelihood against Laplace in nats
      (positive means better than Laplace) and the fraction of series where the arm loses to
      Laplace by the <a href="/draws.html">Diebold&ndash;Mariano test</a>.</p>
    <ul>
      {legend}
    </ul>
    <table>
      <thead><tr><th rowspan="2">stratum</th><th class="num" colspan="2">standalone</th>{heads}</tr>
      <tr>{sub}</tr></thead>
      <tbody>
      {chr(10).join(rows)}
      </tbody>
    </table>
    <p>Central-90% coverage (0.90 target) of the standalone model, its <code>@lap</code> and
      <code>&amp;lap</code> wraps, and Laplace on the same windows:</p>
    <table>
      <thead><tr><th>stratum</th><th class="num">standalone</th><th class="num">@lap</th>
      <th class="num">&amp;lap</th><th class="num">laplace</th></tr></thead>
      <tbody>
      {chr(10).join(crows)}
      </tbody>
    </table>
    <p style="font-size:.9rem;color:var(--muted)">The <a href="/sidecar.html#fairbase">sidecar
      page</a> reads these arms across all six fair bases.</p>"""


def variants_section(model, vs, cov):
    """Optional table of sibling arms (other checkpoint sizes, other quantile
    level sets) scored on the same windows: median dLL vs Laplace and the
    reconstruction's central-90% coverage per stratum."""
    variants = model.get("variants")
    if not variants:
        return ""
    head = "".join(f'<th class="num">{short}</th>' for _k, short, _long in STRATA)
    rows = []
    for key, label in variants:
        cells = []
        for k, _short, _long in STRATA:
            r = vs.get((k, key)); c = cov.get((k, key))
            if not r:
                cells.append('<td class="num">&ndash;</td>'); continue
            cv = f' <span class="muted">({float(c["cov_central90"]):.2f})</span>' if c else ""
            cells.append(f'<td class="num">{float(r["med_dLL"]):+.2f}{cv}</td>')
        mark = " <strong>&larr; page</strong>" if key == model["key"] else ""
        rows.append(f'<tr><td>{label}{mark}</td>{"".join(cells)}</tr>')
    return f"""<h2>Checkpoints and level sets</h2>
    <p>The same model family scored several ways on the identical windows. Each cell is the
      median per-series &Delta; log-likelihood in nats against Laplace (negative is worse),
      with the reconstructed central-90% coverage in parentheses (0.90 target). The nine-decile
      rows use the same fixed-bandwidth reconstruction as TiRex-2; the 21-level rows feed the
      model's native 1% to 99% quantiles to that reconstruction. The model is the same in
      both blocks; only the reconstruction differs.</p>
    <table>
      <thead><tr><th>arm</th>{head}</tr></thead>
      <tbody>
      {chr(10).join(rows)}
      </tbody>
    </table>"""


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


def arch_section(model):
    if not model.get("arch"):
        return ""
    return f"""<h2>Architecture and methodology</h2>
    <p>{model['arch']}</p>"""


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
    <p>This page measures one thing: how sharp and how well calibrated {model['name']}'s
      univariate predictive density is, one step ahead on a change series, scored against
      Laplace on identical windows. It leaves out the covariates, the multivariate inputs,
      the long horizons and the native quantile or path outputs the model was built for, and
      its log score passes through a reconstruction of the model's quantiles (the table note
      says which). A model can trail here and be the better tool for its own job.</p>
    <p><span class="snapshot" style="background:#ece9ff;color:var(--accent-dark);
      border-radius:4px;padding:2px 9px;font-size:.8rem;font-weight:600">Live snapshot</span>
      &nbsp;Derived from the week-long round-robin study; counts grow as coverage deepens.
      Everything scores against Laplace on the identical series and windows.</p>

    <h2>Standalone</h2>
    <p>The model's own predictive, run zero-shot, scored per series against Laplace. Win,
      draw and loss are decided one series at a time. Each series has a rolling test window
      of {TEST} one-step-ahead points, and both forecasters are scored on the same points. For
      each point take the difference of log predictive densities,
      <code>d<sub>t</sub> = log p<sub>model</sub>(y<sub>t</sub>) &minus;
      log p<sub>Laplace</sub>(y<sub>t</sub>)</code>, with each log density floored at
      &minus;20 first. The series' mean <code>d&#772;</code> is tested against zero by a
      <a href="/draws.html">Diebold&ndash;Mariano test</a>: the standard error is Newey&ndash;West
      with a Bartlett kernel and lag round(n<sup>1/3</sup>). The model <em>wins</em> the series
      if <code>d&#772; &gt; 1.96&middot;SE</code>, <em>loses</em> it if
      <code>d&#772; &lt; &minus;1.96&middot;SE</code>, and otherwise the series is a
      <em>draw</em>; a series with fewer than eight finite differences is a draw. A draw
      says the {TEST} points cannot separate the two forecasters at the 5% level. It does not
      say they are equal. With a window this short both win and loss counts understate the
      true rates, and the median &Delta;LL is the better measure of size. Counts are over the
      series both arms cover.</p>
    {standalone_tables(model, vs, cov)}

    {variants_section(model, vs, cov)}

    <h2>Star plot</h2>
    <p>{model['name']} standalone against Laplace, on the same six regime axes as the site's
      <a href="/challengers.html">standalone radar</a>. Each radius is the log-likelihood
      win rate, <code>(wins + &frac12;&middot;ties) / n</code>, divided by one half so an even
      split with Laplace sits on the dashed 1.0 ring; outward beats Laplace more often, inward
      less. The quantity is a share of series. The solid polygon is the headline arm and
      the dashed grey one, where present, is the tight nine-decile reconstruction. The
      M4-hourly set splits into soft and hard waveforms by corpus order, matching that
      radar.</p>
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

    {arch_section(model)}
  </main>

  <footer>
    <a href="https://github.com/microprediction/skaters">Source</a> &middot;
    Part of the <a href="https://github.com/microprediction">microprediction</a> family.
  </footer>
</body>
</html>
"""


FAIR_BASES = ["Timestral-209M(q21)", "t0-gamma(q21)", "TimesFM3(wide)", "TimesFM(wide)",
              "TiRex(wide)", "Chronos(wide)", "PyMC"]
FAIR_SHORT = {"Timestral-209M(q21)": "Timestral", "t0-gamma(q21)": "t0-gamma", "TimesFM3(wide)": "TimesFM3",
              "TimesFM(wide)": "TimesFM", "TiRex(wide)": "TiRex", "Chronos(wide)": "Chronos",
              "PyMC": "PyMC-forecast"}
SIDECAR = os.path.join(os.path.dirname(BENCH), "docs", "sidecar.html")


def sidecar_fairbase_section(vs, cov):
    """The cross-model reading of the sandwich arms on the fair bases, rendered
    from the summary CSVs into docs/sidecar.html between the fairbase markers."""
    arms = ["", "+lap", "~lap", "@lap", "&lap"]
    # table 1: median dLL by arm, two economic strata
    t1 = []
    for k, _s, long in STRATA:
        if k not in ("weekly:econ", "monthly:econ"):
            continue
        for b in FAIR_BASES:
            if (k, b) not in vs:
                continue
            cells = []
            for a in arms:
                r = vs.get((k, b + a))
                cells.append(f'<td class="num">{float(r["med_dLL"]):+.3f} <span style="color:var(--muted)">({int(r["n_series"]):,})</span></td>'
                             if r else '<td class="num">&ndash;</td>')
            t1.append(f'<tr><td>{long}</td><td>{FAIR_SHORT[b]}</td>{"".join(cells)}</tr>')
    # table 2: loss rate standalone -> &lap, every stratum x base
    t2 = []
    for k, _s, long in STRATA:
        cells = []
        for b in FAIR_BASES:
            r, q = vs.get((k, b)), vs.get((k, b + "&lap"))
            if r and q:
                cells.append(f'<td class="num">{fmt_pct(int(r["loss"]) / (int(r["n_series"]) or 1))} &rarr; '
                             f'{fmt_pct(int(q["loss"]) / (int(q["n_series"]) or 1))}</td>')
            else:
                cells.append('<td class="num">&ndash;</td>')
        t2.append(f'<tr><td>{long}</td>{"".join(cells)}</tr>')
    # computed ranges for the prose
    def rng(suffix):
        v = [float(c["cov_central90"]) for (k, m), c in cov.items()
             if any(m == b + suffix for b in FAIR_BASES) and k in dict((x[0], 1) for x in STRATA)]
        return (min(v), max(v)) if v else (float("nan"), float("nan"))
    cs, ca, cp = rng(""), rng("@lap"), rng("&lap")
    econ = [k for k, _s, _l in STRATA if k.endswith(":econ") and k != "m4-hourly:econ"]
    longname = {k: short for k, short, _l in STRATA}
    def dmed(suffix, strata=econ):
        d = {(k, b): float(vs[(k, b + suffix)]["med_dLL"]) - float(vs[(k, b)]["med_dLL"])
             for k in strata for b in FAIR_BASES if (k, b + suffix) in vs and (k, b) in vs}
        lo, hi = min(d, key=d.get), max(d, key=d.get)
        return d[lo], d[hi], lo, hi, sum(1 for v in d.values() if v < 0), len(d)
    dr, dp = dmed("~lap"), dmed("@lap")
    da = dmed("&lap", [k for k, _s, _l in STRATA])
    def lossrate(k, m):
        return int(vs[(k, m)]["loss"]) / (int(vs[(k, m)]["n_series"]) or 1)
    worse = [(k, b) for k, _s, _l in STRATA for b in FAIR_BASES
             if (k, b + "&lap") in vs and (k, b) in vs and lossrate(k, b + "&lap") > lossrate(k, b)]
    worse_amp = len(worse)
    worse_txt = "; ".join(f"{FAIR_SHORT[b]} on {longname[k]}" for k, b in worse) or "none"
    cells_total = sum(1 for k, _s, _l in STRATA for b in FAIR_BASES if (k, b + "&lap") in vs and (k, b) in vs)
    heads = "".join(f"<th>{FAIR_SHORT[b]}</th>" for b in FAIR_BASES)
    # the reverse sandwich: laplace as the base, PyMC on laplace's normal scores
    rev = []
    for k, short, _l in STRATA:
        r = vs.get((k, "laplace@PyMC"))
        if r:
            rev.append(f"{short} {float(r['med_dLL']):+.3f} ({r['win']}W/{r['draw']}D/{r['loss']}L of {r['n_series']})")
    rev_txt = "; ".join(rev)
    return f"""<!-- fairbase:begin (generated by benchmarks/foundation_pages.py; do not edit by hand) -->
    <h2>On the fair bases</h2>
    <p>The arms above were built on the tight reconstruction, and part of what they repaired was the
      reconstruction. The same four sandwiches have now been run on the fair bases: Timestral-209M and
      t0-gamma on their native 21 levels, and TimesFM 3.0, TimesFM 2.5, TiRex and Chronos through the
      generous reconstruction, plus the PyMC-forecast challenger (a Student-t regression on lagged
      changes, fit by ADVI) on the monthly stratum. Each arm is paired with its standalone run on
      identical series and windows; <code>~lap</code> and <code>@lap</code> need a longer warm-up
      window, so their series counts are smaller. Median per-series &Delta; log-likelihood against
      Laplace, in nats, positive meaning better than Laplace, with the number of series:</p>
    <table>
      <thead><tr><th>stratum</th><th>base</th><th class="num">standalone</th><th class="num">+lap</th>
      <th class="num">~lap</th><th class="num">@lap</th><th class="num">&amp;lap</th></tr></thead>
      <tbody>
      {chr(10).join(t1)}
      </tbody>
    </table>
    <p>With no reconstruction defect to repair, the wraps mostly cost accuracy. Replacing the model's
      scale with Laplace's residual scale (<code>~lap</code>) lowers the median in {dr[4]} of {dr[5]}
      economic cells, by {dr[0]:+.2f} ({FAIR_SHORT[dr[2][1]]}, {longname[dr[2][0]]}) to
      {dr[1]:+.2f} nats ({FAIR_SHORT[dr[3][1]]}, {longname[dr[3][0]]}). Forecasting the model's normal
      scores (<code>@lap</code>) lowers it in {dp[4]} of {dp[5]}, from {dp[0]:+.2f}
      ({FAIR_SHORT[dp[2][1]]}, {longname[dp[2][0]]}) to {dp[1]:+.2f}
      ({FAIR_SHORT[dp[3][1]]}, {longname[dp[3][0]]}): it still helps the weakest base and costs the
      strongest. The standalone fair bases cover {cs[0]:.2f} to {cs[1]:.2f} at the 90% level;
      <code>@lap</code> pushes that to {ca[0]:.2f} to {ca[1]:.2f}, past the target, and
      <code>&amp;lap</code> sits at {cp[0]:.2f} to {cp[1]:.2f}. Loss rate against Laplace,
      standalone &rarr; <code>&amp;lap</code>:</p>
    <table>
      <thead><tr><th>stratum</th>{heads}</tr></thead>
      <tbody>
      {chr(10).join(t2)}
      </tbody>
    </table>
    <p>The portfolio lowers the loss rate in {cells_total - worse_amp} of {cells_total} base-stratum
      cells; the exceptions are {worse_txt}. Its median moves by {da[0]:+.2f} ({FAIR_SHORT[da[2][1]]}, {longname[da[2][0]]}) to
      {da[1]:+.2f} nats ({FAIR_SHORT[da[3][1]]}, {longname[da[3][0]]}) against the standalone base:
      a strong base gives up part of its lead for the lower loss rate, a weak base is pulled most of
      the way back to Laplace. The reading for the strongest base is on
      <a href="/foundation/timestral.html">Timestral's page</a>: no sandwich improves it at the
      median, and the portfolio is the safe way to run it. Each model's page carries the full
      per-stratum table with loss rates and coverage.</p>
    <p>The reverse sandwich was also run: laplace as the base, with the PyMC regression forecasting
      laplace's own normal scores and its posterior mixture inverted through laplace's predictive.
      An earlier version of the home-page figure showed this construction edging laplace, from a
      July study with a frozen pre-test fit and a typed speed table. Through the canonical protocol,
      paired against laplace on the first 500 series of each economic stratum, the median is below
      zero on every stratum: {rev_txt}. That claim is withdrawn.</p>
    <!-- fairbase:end -->"""


def write_sidecar(vs, cov):
    html = open(SIDECAR).read()
    a, b = "<!-- fairbase:begin", "<!-- fairbase:end -->"
    i, j = html.index(a), html.index(b) + len(b)
    html = html[:i] + sidecar_fairbase_section(vs, cov) + html[j:]
    open(SIDECAR, "w").write(html)
    print("[page] sidecar.html fair-base section")


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
    write_sidecar(vs, cov)
    sweep_nav()


if __name__ == "__main__":
    main()
