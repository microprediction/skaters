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
forecaster appears, and no suite scores a predictive density. We supply the
missing reference: laplace, an online distributional forecaster with no
pretraining and no tunable parameters. Scored one step ahead on held-out log
density over an 18,815-series FRED panel, it beats TimesFM 3.0 on the median
series of every stratum by about half a nat, and a post-hoc portfolio that sees
only the model's own issued density recovers most of the gap. It is a pip
install, with a Rust core and bit-exact parity.

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

- The date line is the compile date; arXiv's own build sets it.
- `cotton2026transforms` is cited as a techreport with no SSRN id. Put the id
  in `benchmark.bib`, rebuild the `.bbl`, and rebuild the pack.
- Re-run `verify_paper.py` on the tex that goes into the pack.
