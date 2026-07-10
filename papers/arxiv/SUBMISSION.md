# arXiv submission notes

Upload `skaters-arxiv.tar.gz` at https://arxiv.org/submit. The tarball
contains the .tex, the vendored jss.cls, the compiled .bbl, and the .bib;
arXiv compiles the tex and reads the .bbl directly, so it does not need
to run BibTeX.

## Form fields

**Primary category:** stat.CO (Computation).
**Cross-lists:** stat.ME (Methodology), q-fin.ST (Statistical Finance).

**Title:**
Transforms All the Way Down --- Automatic Online Distributional
Forecasting by Conjugation

**Abstract (plain text for the form):**
The Python package skaters is an online, distributional, univariate
time-series forecaster built by conjugation: invertible transforms nest
all the way down onto a single distributional leaf fitted by a proper
scoring rule. The collection collapses into one forecast function with no
exposed tuning parameters, laplace, which leads the per-series held-out
log-likelihood race against classical, neural, and foundation-model
baselines on FRED series; on asset prices a GARCH-t model remains better,
a split we report rather than average away. The library is written twice,
in pure Python (pip install skaters) and in zero-dependency JavaScript
(npm install skaters) agreeing to 1e-6, so models run unchanged in a
browser.

**Comments field:**
Software: https://github.com/microprediction/skaters (pip install
skaters, npm install skaters). Site: https://skaters.microprediction.org

**License:** the default arXiv non-exclusive license keeps all journal
options open. CC-BY cannot be revoked later; pick it only deliberately.

The submitting account must be yours; arXiv has no delegated submission.
A first-time stat.CO submission may need endorsement, though your
publication history likely auto-endorses.

Once posted, tell me the arXiv id: the JOSS paper, the README, and the
site should then cite it, and the DOI (10.48550/arXiv.<id>) becomes the
citable reference while JSS review runs.
