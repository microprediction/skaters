# comparisons — laplace vs. one opponent at a time

Head-to-head slices of the *same* `sota` study (one FRED loader, one `Dist`
scorer, one rolling one-step protocol — see `../README.md`), each isolated to
**laplace vs. a single opponent** so the story is legible: what is X, why does
it matter, and how the two compare on held-out **log-likelihood** and
**CRPS**. The point of the exercise is to find the corners — the types of
series and regimes where another method outperforms `laplace` — and to state
them plainly when found (seasonal hourly data, soft daily cycles, the
price/return universe so far), rather than to average them away.

Each subfolder is one matchup:

| folder | opponent(s) | what it tests |
|---|---|---|
| `laplace-vs-autoarima/` | `auto.arima-R@*`, `AutoARIMA@*` (statsforecast) | the real Hyndman R auto.arima *and* its Python port, across refit cadences |
| `laplace-vs-adam/` | `ADAM-R@*` | Svetunkov's ADAM — the strongest classical *distributional* forecaster |
| `laplace-vs-theta/` | `Theta-R@*` | the M3 winner; cheap, hard to beat |
| `laplace-vs-nnetar/` | `nnetar-R@*` | a nonlinear (neural AR) opponent with no clean Python twin |
| `laplace-vs-garch/` | `GARCH-t`, `GARCH-t-R@*` | heavy-tail volatility SOTA (its home turf is price/returns) |
| `laplace-vs-bsts/` | `bsts-R@*` | Bayesian structural time series — full posterior predictive |
| `laplace-vs-csp/` | `CSPr-*` (official `csp-forecaster`, 12 configs) | training-free Conformal Seasonal Pools (arXiv:2605.03789), across four corpus arms incl. its seasonal home turf |
| `laplace-vs-nns/` | `NNS-R`, `NNS-R-auto` | Viole's NNS.ARMA — same-phase component forecasting, the seasonal-pool family's prior art |
| `nns-vs-csp/` | `NNS-R` vs `CSPr-*` | third-party bout: the prior art vs the seasonal-pool paper, laplace not in the ring |
| `laplace-vs-tbats/` | `TBATS-R`, `TBATS-R-ms` | the classical multi-seasonal state space; owns the soft-cycle corner of M4-Hourly |

## Reproduce a matchup

```bash
# laplace vs the real R auto.arima at three refit cadences
PYTHONPATH=src python benchmarks/comparisons/run_comparison.py \
    laplace-vs-autoarima R@5 R@25 R@100
```

`run_comparison.py` restricts the `sota` opponent set to laplace + the names you
pass (`STUDY_ONLY`) and writes to `comparisons/<slug>/results.csv`
(`STUDY_RESULTS`). It scores nothing new — it's the one harness, one slice. Paste
the printed summary into that folder's `README.md` under **Result**.

R opponents need R installed (`install.packages(c("forecast","smooth","rugarch","bsts"))`);
if `Rscript` is absent they simply drop out. Budgets (`BENCH_R_MAX`, `BENCH_SF_MAX`,
…) and cadences (`BENCH_R_REFITS`, `BENCH_SF_REFITS`) are the same env vars as the
main study.

## The long sweep (`overnight_sweep.sh`)

`overnight_sweep.sh` is the auto-resuming volume runner behind the results here. It
appends to a resumable CSV (`STUDY_RESULTS`, per series+method — a kill never loses
or re-scores work) and relaunches the study on any non-zero exit. Every knob is an
env override; defaults are the lean max-N config (`laplace,R@25,statsforecast@25,CSP,GARCH-t`,
`bsts-R` skipped).

```bash
# macOS (prevent sleep):  caffeinate keeps it awake; the loop resumes on any kill
caffeinate -is bash benchmarks/comparisons/overnight_sweep.sh &
# Linux:
nohup bash benchmarks/comparisons/overnight_sweep.sh &
```

## Running on another machine (transfer)

The code travels with the branch; two things don't and must be moved by hand:

1. **The FRED cache** — `benchmarks/data/` (~146 MB, ~2600 CSVs, gitignored). Either
   rsync it, or set a `FRED_API_KEY` and run with `STUDY_CACHED_ONLY=0` to re-fetch.
   ```bash
   rsync -av this-machine:~/github/skaters/benchmarks/data/ ./benchmarks/data/
   ```
2. **The in-progress results** — `benchmarks/comparisons/_shared_R25.csv` (gitignored).
   Copy it over to *continue* the accumulation; omit it to start fresh.
   ```bash
   rsync -av this-machine:~/github/skaters/benchmarks/comparisons/_shared_R25.csv \
             ./benchmarks/comparisons/
   ```

Then install deps and launch:
```bash
Rscript -e 'install.packages(c("forecast","smooth","rugarch","bsts"), repos="https://cloud.r-project.org")'
pip install statsforecast arch statsmodels    # Python opponents (absent ones drop out)
caffeinate -is bash benchmarks/comparisons/overnight_sweep.sh &   # or nohup on Linux
```

**Run on one machine at a time.** Two machines appending to the same-named CSV will
duplicate rows and skew `summarize`. To split work, give each a distinct
`STUDY_RESULTS`, then concatenate and de-dup on `(series,method)` before summarizing.

## The rule (unchanged)

Every method — ours and theirs — is turned into the same predictive `Dist` and
scored by the same code on the same held-out points. Gaussian predictives
(auto.arima, Theta) are scored exactly; genuinely non-Gaussian ones (ADAM,
nnetar, GARCH-t, BSTS, CSP) are scored on their **real quantiles**, not a
Gaussian-from-band flattening. CDF-only methods report CRPS and say so.
