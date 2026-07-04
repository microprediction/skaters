# skaters papers

The formal write-up of `skaters` and the *model first, conform last* recipe.

| File | What it is |
|---|---|
| `skaters-jss.tex` | The paper, in Journal of Statistical Software (JSS) format. |
| `skaters.bib` | Bibliography. |
| `compile_paper.sh` | One-command build (Tectonic). |
| `skaters.md` | An informal markdown draft of the same material, for quick reading on GitHub. |
| `tweedie-note.md` | A short essay: how Tweedie's formula ties the package's recursions to the Kalman filter, empirical Bayes, and diffusion models. |

## Build

Tectonic handles the multiple LaTeX passes and downloads packages on demand:

```bash
# macOS
brew install tectonic

cd papers
./compile_paper.sh        # downloads jss.cls on first run, emits skaters-jss.pdf
```

Or manually:

```bash
cd papers
curl -O https://www.jstatsoft.org/public/journals/1/jss.cls
tectonic skaters-jss.tex
```

## Reproducing the empirical results

Table 1 (the twelve-baseline study) is produced end-to-end by
`benchmarks/study.py` with the `sota` preset. With a `FRED_API_KEY` and the
optional baselines installed (`statsforecast`, `arch`, the R
`forecast`/`smooth`/`rugarch` stack, CSP):

```bash
PYTHONPATH=src python benchmarks/study.py sota             # parallel across cores
PYTHONPATH=src python benchmarks/study.py sota summarize   # reprint the table
```

The multi-step table is produced by `benchmarks/multistep_study.py` under the
same `Dist` protocol.

Every method — ours and theirs — is scored through the identical `Dist`
interface on held-out log-likelihood and CRPS.
