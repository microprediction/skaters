# Reproducing this paper

This file is meant to be sufficient on its own. An agent or a person who can
run a shell should be able to follow it top to bottom with no other context and
end up with the paper's numbers.

Work in three tiers. Tier 1 takes seconds and checks that the prose matches the
store. Tier 2 takes minutes and rebuilds the summaries from per-step records.
Tier 3 takes days and a GPU and regenerates those records from raw data. Most
reviewers want Tier 1.

---

## 0. Prerequisites

```bash
git clone https://github.com/microprediction/skaters
cd skaters
python3 --version          # 3.10 or newer
```

The `skaters` package is pure Python with zero dependencies, so the reference
method needs no install beyond `PYTHONPATH=src`. Tier 1 additionally needs
nothing at all. Tier 2 needs `numpy`. Tier 3 needs a separate virtual
environment per foundation model, because their dependency sets conflict.

---

## 1. Tier 1: check every number in the paper (seconds)

```bash
python papers/stronger-benchmark/constants.py
```

Every figure quoted in the paper is printed by that script, computed from
`benchmarks/canonical_summary_vs_laplace.csv` and
`benchmarks/_nozzle_study.log`, both of which are committed. No number in the
prose is typed by hand. If the script's output and the paper disagree, the
script is right and the paper has drifted.

To check that the paper's prose has not drifted from the store, which is the
thing a typed markdown table cannot guarantee on its own:

```bash
python papers/stronger-benchmark/verify_paper.py
```

That parses every results table and the quoted figures out of `paper.md`,
re-derives each from the store, and exits non-zero on any mismatch. Expected
output is one line reporting 10 table rows and 6 prose figures matching.

Machine-readable form, for diffing in CI:

```bash
python papers/stronger-benchmark/constants.py --json > /tmp/claims.json
```

### Expected output

```
stratum                     n               w/d/l   med dLL   loss%
daily, economic          2179         66/923/1190   -0.8539   54.6%
daily, price/returns     7633        15/4593/3025   -0.6162   39.6%
weekly, economic         3013       517/1481/1015   -0.5199   33.7%
monthly, economic        5576       193/3592/1791   -0.6472   32.1%
M4-hourly, seasonal       414           8/241/165   -0.5430   39.9%
```

and for the reconstruction study, mean logpdf of `grid +2.0321`, `local
+1.4159`, `narrow -0.3731`, `wide +2.1043`, with a mean per-point spread of
`3.1276`.

These are exact. Tier 1 reads committed files, so any difference means the
files changed, not that a run was noisy.

---

## 2. Get the data (Tier 2 and 3 only)

The benchmark runs on a frozen vintage of the FRED level cache. FRED revises
series, so a fresh pull from the API returns different vintages and will not
reproduce these numbers. Use the published archive.

```bash
gh release download fred-cache-20260921 \
  -R microprediction/skaters-benchmarking-data -p '*.tar.zst'
mkdir -p data-fred-cache
zstd -dc fred-cache-pubdomain-20260921.tar.zst | tar -x -C data-fred-cache
ln -s ../data-fred-cache benchmarks/data
```

That is 210,574 series, 2.1G expanded. It carries only public-domain series.
Commercial index data (Nasdaq, ICE BofA, Wilshire) is excluded and listed in
`excluded-series.txt` in that repo. The consequence is stated in section 5
below.

---

## 3. Tier 2: rebuild the summaries from the per-step store (minutes)

The per-step store is `benchmarks/preds/`, one row per (series, method, step)
holding the realized change and the predictive it was scored against. Every
derived metric comes from it.

```bash
PYTHONPATH=src:benchmarks python benchmarks/summarize_canonical.py
```

That writes `benchmarks/canonical_summary_vs_laplace.csv` and
`benchmarks/canonical_summary_coverage.csv`. Re-run Tier 1 afterwards; the
numbers should be unchanged.

Aggregation is paired on purpose. A mean of log-likelihood across
heterogeneous series estimates nothing, because a few near-constant series
dominate it. The summary reports per-series Diebold-Mariano win/draw/loss with
HAC standard errors and a draw band, the median per-series ΔLL, and a
scale-free CRPS ratio.

The store is gitignored because it is large and regenerable. If you do not
have it, go to Tier 3.

---

## 4. Tier 3: regenerate the per-step store (days, GPU)

Each arm is scored by the same runner, which appends rows in one schema and
skips any (series, method) pair already present, so it is resumable.

```bash
# the reference method, no GPU, no extra dependencies
PYTHONPATH=src:benchmarks \
  ARM_METHODS=laplace ARM_CORPUS=monthly PRED_OUT=preds/laplace__monthly.csv \
  python benchmarks/run_arm.py
```

```bash
# a foundation model, in its own environment
PYTHONPATH=src:benchmarks \
  ARM_METHODS=TimesFM3 ARM_CORPUS=monthly PRED_OUT=preds/TimesFM3__monthly.csv \
  FM_CTX=128 FM_DEVICE=mps .venv-timesfm3/bin/python benchmarks/run_arm.py
```

Corpus arms are `daily`, `weekly`, `monthly` and `m4-hourly`, defined by fixed
enumeration rules in `benchmarks/corpus.py` and never by hand-picked
identifiers. Frequency is verified per series from cached dates rather than
trusted from the FRED tag. The protocol for every arm is a 128-length context,
a rolling one-step-ahead test window, and no fitting.

Set `STUDY_EXCLUDE_PRICE=1` for the economic strata and `STUDY_ONLY_PRICE=1`
for the price stratum. The sandwich arms (`TimesFM3&lap` and siblings) are
produced by the same runner from the same stored predictives, with no
retraining.

### The reconstruction study

```bash
PYTHONPATH=src:benchmarks .venv-timesfm3/bin/python benchmarks/nozzle_study.py
```

That holds TimesFM3 and the test points fixed and varies only the
quantiles-to-density reconstruction, over the four methods registered in
`benchmarks/nozzles.py`. Output goes to `benchmarks/_nozzle_study.log`, which
Tier 1 reads.

---

## 5. What this file cannot reproduce

**The price stratum.** The published archive excludes the commercial index
series that the price universe is built from. Everything reported for the
economic strata is unaffected, since those runs set `STUDY_EXCLUDE_PRICE=1`.
To rebuild `daily:price`, refetch the identifiers in `excluded-series.txt`
with a free FRED API key, accepting that a fetch today returns a current
vintage rather than the one scored here.

**The contamination stratification.** Its generator,
`benchmarks/contamination_page.py`, lives on branch
`study/one-flow-and-protocol-fixes` and reads a tidy store under
`surrogate/bench/` that is not published. Retrieve the script with
`git show study/one-flow-and-protocol-fixes:benchmarks/contamination_page.py`.
Reproducing its numbers needs that store.

**Exact hardware agreement.** Foundation-model inference is not bit-stable
across devices. Tier 3 re-runs should reproduce the signs, the win/draw/loss
pattern and the median gaps, not the trailing digits. Tier 1 and Tier 2 are
exact, because they read stored records rather than recomputing inference.
