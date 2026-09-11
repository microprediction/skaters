# SSRN submission packet — the skaters paper

Upload this FIRST, before the conformal-information-gap paper: once it has an SSRN
number, the gap paper's `cotton_skaters` bibliography entry cites a stable dated
document instead of a bare repository URL (see
`conformalprediction/paper/frontier/SUBMIT.md` §4).

---

## 0. File to upload

`papers/skaters-jss.pdf` (24 pp, title page carries author, site URL, and date).

Optional before uploading: the title's em-dash ("Transforms All the Way Down — Automatic
...") could become a colon to match house style. Say the word and I'll rebuild.

## 1. Title

```
Transforms All the Way Down: Automatic Online Distributional Forecasting by Conjugation
```

(or keep the em-dash form exactly as in the PDF if uploading unmodified)

## 2. Abstract (plain text for the SSRN box)

```
The Python package skaters is an online, distributional, univariate time-series
forecaster built by conjugation: invertible transforms nest all the way down onto a
single distributional leaf fitted by a proper scoring rule. The collection collapses
into one forecast function with no exposed tuning parameters, laplace, which leads the
per-series held-out log-likelihood race against classical, neural, and foundation-model
baselines on FRED series; on asset prices a GARCH-t model remains better, a split we
report rather than average away. Run in laplace's coordinates and mapped back exactly
(the sandwich), existing models improve dramatically without retraining. The library is
implemented in pure Python (pip install skaters), zero-dependency JavaScript (npm
install skaters), R, and a portable Rust core, held to 1e-6 agreement by a shared parity
suite, so models run unchanged on a server or in a browser.
```

## 3. Keywords

```
time series; probabilistic forecasting; online learning; proper scoring rules;
calibration; extreme value theory; Bayesian model averaging; volatility; GARCH;
open-source software
```

## 4. JEL codes

- **C53** — Forecasting and Prediction Methods
- **C58** — Financial Econometrics (the asset-price split and GARCH-t comparison)
- **C87** — Econometric Software
- (optional) **C14** — Semiparametric and Nonparametric Methods

## 5. eJournals

- CompSciRN: Machine Learning eJournal
- ERN: Econometric Modeling: Statistical Methods eJournal
- ERN: Forecasting eJournal (if offered)
- FEN: Econometric Modeling: Capital Markets (the quant-finance angle that has worked
  for prior submissions)

## 6. Author metadata

Peter Cotton, peter.cotton@microprediction.com (as in the fan-note packet).

## 7. After approval

1. Note the SSRN number.
2. In `conformalprediction/paper/references.bib`, update `cotton_skaters` to cite this
   paper with the SSRN URL (keep the GitHub URL as a secondary link), rebuild
   `paper/frontier/`, refresh `arxiv/`, and then upload the gap paper per its SUBMIT.md.
