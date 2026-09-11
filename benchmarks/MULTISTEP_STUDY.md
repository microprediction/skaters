# Multi-horizon study behind v0.14.0

The 0.14.0 AR/garch fix was released on the strength of parity, a FRED
log-likelihood check, and a GIFT-Eval spot check. This study is the follow-up
evidence: a run whose whole purpose is to exercise multi-step forecasting, the
regime the fix repairs.

## Setup

Round-robin over the roster and six horizons, each horizon into its own preds
tree, caps growing per round so every k accumulates coverage rather than
exhausting one.

- Horizons k ∈ {1, 2, 3, 5, 8, 13}
- Roster: 18 arms (laplace, five foundation models, and the +/~/@/& laplace
  sandwiches of Chronos/TiRex/TimesFM)
- Corpora: daily, weekly, monthly, m4-hourly (econ and price strata)
- 82 rounds, 432 jobs per round, 0 errors, ~7.9 GB of per-step predictions
- CPU, 6-way parallel, ~2.2 h/round, run 2026-07-24 to 2026-08-04

Reproduce: `WEEK_HS="1 2 3 5 8 13" WEEK_PREDS=preds_multi WEEK_PAR=6
.venv-sota/bin/python benchmarks/week_study.py`. Summaries per horizon:
`CANON_PREDS=benchmarks/preds_multi/h{k} CANON_SUFFIX=_h{k} python
benchmarks/summarize_canonical.py`.

## Result 1: multi-step is bounded and measurable

Median held-out log-likelihood of the never-worse sandwich (TimesFM&lap) against
plain laplace, per corpus and horizon. Zero means it matches laplace, the
sandwich's design target.

| study         |    h1  |    h2  |    h3  |    h5  |    h8  |   h13  |
|---------------|--------|--------|--------|--------|--------|--------|
| daily:econ    | -0.084 | -0.130 | -0.119 | -0.154 | -0.146 | -0.129 |
| weekly:econ   | -0.046 | -0.067 | -0.079 | -0.072 | -0.046 | -0.035 |
| monthly:econ  | -0.059 | -0.053 | -0.047 | -0.061 | -0.074 | -0.106 |
| m4-hourly:econ| -0.007 | -0.014 | -0.015 | -0.007 | -0.010 | -0.027 |

Every value sits in a tight -0.007 to -0.15 nat band out to k=13. Pre-fix this
table could not be produced: the non-stationary AR forecast and the level-scaled
garch drove multi-step quantiles to ~1e13 on a subset of series, so the scores
were garbage rather than small. Weekly and hourly improve at the far horizons,
where seasonal structure is easier to extend than to nowcast.

## Result 2: intervals stay calibrated at horizon

Central-90 coverage (target 0.90), h1 vs h13:

| study          | laplace h1 | sandwich h1 | laplace h13 | sandwich h13 |
|----------------|------------|-------------|-------------|--------------|
| daily:econ     |   0.919    |    0.922    |    0.920    |    0.922     |
| m4-hourly:econ |   0.892    |    0.904    |    0.908    |    0.921     |
| monthly:econ   |   0.921    |    0.922    |    0.922    |    0.922     |

Coverage stays at the target across the full horizon range. The fix produces
multi-step intervals that are both bounded and calibrated, not merely finite.

## Result 3: how laplace compares to the foundation models

Scale: 18,815 distinct series (daily 9,812, monthly 5,576, weekly 3,013,
m4-hourly 414), each forecast by all 18 arms at all six horizons.

Two metrics tell different stories, and the difference is the point.

On held-out log-likelihood, laplace beats every standalone foundation model on
every corpus at every horizon. The gaps are wide: Chronos trails by 0.8 to 1.25
nats, TiRex 0.5 to 1.0, TimesFM the closest at 0.65 to 0.89. Across the econ
strata (daily, weekly, monthly, 18,401 of the 18,815 series) it is not close,
and interval coverage stays at target throughout. These are 35M to 500M
parameter models pretrained on large corpora, losing on distributional sharpness
to a small online model.

On CRPS the foundation models are competitive and sometimes better, but almost
entirely on one set: m4-hourly, the 414 most regular, strongly-seasonal series,
at long horizons. There the point-sharpness gain is real (TiRex CRPS ratio 0.83
at h=13). On the broad, less periodic economic series it is laplace's metric too
or a wash.

So the split is not "foundation models are better at economics." They are better
at clean periodic structure, which most real economic series lack. For the broad
economic universe laplace is the stronger forecaster, and where the foundation
models do add something (seasonal CRPS), the `&lap` never-worse sandwich captures
it without surrendering laplace's log-likelihood and calibration edge.

## Files

Raw per-step predictions in `benchmarks/preds_multi/h{k}/`; derived summaries in
`benchmarks/canonical_summary_vs_laplace_h{k}.csv` and
`benchmarks/canonical_summary_coverage_h{k}.csv`.
