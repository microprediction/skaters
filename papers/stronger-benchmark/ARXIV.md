# arXiv submission pack

`stronger-benchmark_arxiv.tar.gz` holds everything arXiv's AutoTeX needs and
nothing else: `stronger-benchmark.tex`, the vendored `jss.cls`, the compiled
`stronger-benchmark.bbl` (arXiv does not run BibTeX), and `benchmark.bib` for
readers. No figures: every result is a table typeset from the source.

## Rebuilding the pack

```
cd papers/stronger-benchmark
../../.venv-sota/bin/python verify_paper.py          # must print OK
tectonic --keep-intermediates -o /tmp/ab stronger-benchmark.tex
mkdir -p /tmp/pack && cp stronger-benchmark.tex jss.cls benchmark.bib /tmp/ab/stronger-benchmark.bbl /tmp/pack/
(cd /tmp/pack && tar czf ../stronger-benchmark_arxiv.tar.gz .)
```

Then check the `.bbl` the way arXiv will use it: unpack into a clean directory,
delete `benchmark.bib`, and run `tectonic --pass tex --keep-intermediates
--keep-logs stronger-benchmark.tex` three times (TeX only, no BibTeX; the
`.aux` must survive between runs). The third log must contain no
"Citation ... undefined" and no "Reference ... undefined". A plain `tectonic`
run is not a valid check: it re-runs BibTeX, fails without the `.bib`, and
overwrites the shipped `.bbl` with an empty one.

## Form fields

**Title.** A Stronger Univariate Benchmark for Foundational Time-Series Model Evaluation

**Authors.** Peter Cotton

**Abstract** (plain text; no macros).

Reported progress for foundation time-series models rests on comparisons that
leave out a strong classical reference. Across eleven benchmark papers the
classical arms are per-window refits of ETS, ARIMA and Theta; no online
forecaster appears, and no suite scores a full predictive density by log score. We supply the
missing reference, laplace, an online distributional forecaster with no
pretraining and no tunable parameters, and score it against TimesFM 3.0 one
step ahead on held-out log density over an 19,940-series panel of
FRED and M4-hourly series. The comparison is decided by a step the
suites leave unstated: how the model's nine quantiles become a density. Under
a tight reconstruction the reference leads by half a nat on the median series
of every stratum; under a generous one the two are level at the median, and
the reference keeps the better coverage. The reference is a pip install,
with a Rust core and bit-exact parity.


**Primary category.** stat.ML (Machine Learning, statistics)

**Cross-lists.** cs.LG (Machine Learning), stat.ME (Methodology), econ.EM (Econometrics)

**Comments field.** Code: https://github.com/microprediction/skaters
(papers/stronger-benchmark; every number derives from a version-controlled
store and verify_paper.py exits non-zero on drift). Data vintage: release
asset in microprediction/skaters-benchmarking-data. All results reproduced at
https://skaters.microprediction.org.

**License.** CC BY 4.0.

**MSC / ACM classes.** 62M10 (time series), 62M20 (prediction); ACM I.2.6, G.3.

## Before submitting

- The date is a fixed string in the tex (`\date{...}`); update it for a revision.
- `cotton2026transforms` carries its SSRN id (7220478); the companion paper
  was posted 4 August 2026.
- Re-run `verify_paper.py` on the tex that goes into the pack.
